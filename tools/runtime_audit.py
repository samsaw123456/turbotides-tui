#!/usr/bin/env python3
"""Measure the real terminal program without changing simulation or saved records.

Linux /proc supplies Java CPU and RSS. Timed samples drain ANSI immediately and
decode it afterward, avoiding pyte backpressure in the measured interval.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import platform
import shlex
import shutil
import signal
import subprocess
import termios
import time
from pathlib import Path

import pexpect
import pyte
from ansi_audit import BINDINGS, OUTPUT, ROOT, Terminal, racing, require

REPORT = OUTPUT / "runtime"
JAR = ROOT / "build/libs/turbotides-tui.jar"


class ObservedTerminal(Terminal):
    def __init__(self, name, columns=100, rows=34, command=None, artifact=None):
        self.fast = False
        self.pending = []
        self.frame_times = []
        self.output_bytes = 0
        self.carry = ""
        if command is None:

            def command(directory, telemetry, data_dir):
                java_home = os.environ.get("TURBOTIDES_JAVA_HOME") or os.environ.get(
                    "JAVA_HOME"
                )
                java = str(Path(java_home) / "bin/java") if java_home else "java"
                return java, [
                    "--enable-native-access=ALL-UNNAMED",
                    "-jar",
                    str(JAR),
                    "--telemetry",
                    str(telemetry),
                    "--data-dir",
                    str(data_dir),
                ]

        self.directory = REPORT / name
        self.directory.mkdir(parents=True, exist_ok=True)
        self.telemetry = self.directory / "state.json"
        self.telemetry.unlink(missing_ok=True)
        data_dir = self.directory / "data"
        shutil.rmtree(data_dir, ignore_errors=True)
        self.screen = pyte.Screen(columns, rows)
        self.stream = pyte.Stream(self.screen)
        self.raw = ""
        self.raw_log = (self.directory / "terminal.ansi").open("w")
        self.frames = []
        (self.directory / "build.json").write_text(
            json.dumps(
                {
                    "jar_sha256": hashlib.sha256(
                        (artifact or JAR).read_bytes()
                    ).hexdigest(),
                    "started_unix": time.time(),
                    "columns": columns,
                    "rows": rows,
                },
                indent=2,
            )
            + "\n"
        )
        executable, arguments = command(self.directory, self.telemetry, data_dir)
        self.child = pexpect.spawn(
            executable,
            arguments,
            cwd="/tmp",
            env=dict(os.environ, TERM="xterm-256color", COLORTERM="truecolor"),
            encoding="utf-8",
            codec_errors="replace",
            dimensions=(rows, columns),
            timeout=1,
        )
        self.child.delaybeforesend = 0
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            self.pump(0.05)
            if (
                self.telemetry.exists()
                and "TURBO TIDES" in self.text()
                and self.screen.display[min(rows, 65) - 2].strip()
            ):
                self.pump(0.2)
                return
            require(self.child.isalive(), f"Startup failed: {self.raw[-2000:]}")
        raise AssertionError(f"Startup timed out: {self.raw[-2000:]}")

    def pump(self, duration):
        if not self.fast:
            return super().pump(duration)
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            try:
                data = self.child.read_nonblocking(
                    131072, timeout=min(0.01, max(0.001, deadline - time.monotonic()))
                )
                observed = time.monotonic()
                self.raw = (self.raw + data)[-16000:]
                self.raw_log.write(data)
                self.pending.append(data)
                self.output_bytes += len(data.encode("utf-8"))
                joined = self.carry + data
                count = joined.count("\x1b[?7h") - self.carry.count("\x1b[?7h")
                self.frame_times.extend([observed] * count)
                self.carry = joined[-8:]
                if "\x1b[6n" in data:
                    self.child.send("\x1b[1;1R")
            except pexpect.TIMEOUT:
                pass
            except pexpect.EOF:
                return

    def decode_pending(self):
        self.fast = False
        self.stream.feed("".join(self.pending))
        self.pending = []


def process_usage(pid):
    stat = Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()
    status = Path(f"/proc/{pid}/status").read_text().splitlines()
    memory = {
        line.split(":", 1)[0]: int(line.split()[1])
        for line in status
        if line.startswith(("VmRSS:", "VmHWM:"))
    }
    return {
        "cpu_seconds": (int(stat[11]) + int(stat[12])) / os.sysconf("SC_CLK_TCK"),
        "rss_mib": memory["VmRSS"] / 1024,
        "peak_rss_mib": memory["VmHWM"] / 1024,
        "state": stat[0],
    }


def visible_response(terminal, key, predicate):
    terminal.frame_times = []
    terminal.carry = ""
    terminal.fast = True
    started = time.monotonic()
    terminal.child.send(BINDINGS[key])
    while time.monotonic() - started < 3:
        terminal.pump(0.005)
        if not terminal.frame_times:
            continue
        completed = terminal.frame_times[-1]
        terminal.decode_pending()
        if predicate(terminal.text()):
            return {
                "ansi_response_ms": round((completed - started) * 1000, 2),
                "decoded_response_ms": round((time.monotonic() - started) * 1000, 2),
            }
        terminal.fast = True
    raise AssertionError(f"No visible response to {key}: {terminal.text()}")


def performance(duration, scenes=None, sizes=None):
    results = []
    for size in sizes or ["100x34", "180x65"]:
        columns, rows = map(int, size.split("x"))
        for scene in scenes or ["garage", "help", "paused", "racing"]:
            terminal = ObservedTerminal(f"{columns}x{rows}-{scene}", columns, rows)
            try:
                if scene in ["paused", "racing"]:
                    racing(terminal)
                    terminal.key("W", 0.5)
                    if scene == "paused":
                        terminal.key("Esc", 0.3)
                elif scene == "help":
                    terminal.key("?", 0.3)
                terminal.pump(2.0)
                terminal.save("before-sample")
                terminal.fast = True
                baseline = process_usage(terminal.child.pid)
                load_before = os.getloadavg()
                started = time.monotonic()
                samples = []
                while time.monotonic() - started < duration:
                    terminal.pump(0.05)
                    samples.append(process_usage(terminal.child.pid))
                elapsed = time.monotonic() - started
                final = samples[-1]
                frames = list(terminal.frame_times)
                byte_count = terminal.output_bytes
                # Freeze the actual race before decoding the retained sample.
                if scene == "racing":
                    terminal.child.send(BINDINGS["Esc"])
                    terminal.pump(0.3)
                terminal.decode_pending()
                terminal.save("after-sample")
                transitions = {
                    "garage": ("Right", lambda text: "Cinder Ring" in text),
                    "help": ("Esc", lambda text: "Driving in a terminal" not in text),
                    "paused": ("Enter", lambda text: "Race paused" not in text),
                    "racing": ("Enter", lambda text: "Race paused" not in text),
                }
                key, predicate = transitions[scene]
                latency = visible_response(terminal, key, predicate)
                terminal.save("response")
                intervals = [b - a for a, b in itertools.pairwise(frames)]
                result = {
                    "size": f"{columns}x{rows}",
                    "scene": scene,
                    "seconds": round(elapsed, 3),
                    "load_average_before": load_before,
                    "load_average_after": os.getloadavg(),
                    "java_cpu_percent_one_core": round(
                        (final["cpu_seconds"] - baseline["cpu_seconds"])
                        / elapsed
                        * 100,
                        2,
                    ),
                    "max_rss_mib": round(max(s["rss_mib"] for s in samples), 2),
                    "peak_lifetime_rss_mib": round(final["peak_rss_mib"], 2),
                    "completed_redraws": len(frames),
                    "redraws_per_second": round(len(frames) / elapsed, 2),
                    "max_observed_redraw_gap_ms": (
                        round(max(intervals) * 1000, 2) if intervals else None
                    ),
                    "ansi_kib_per_second": round(byte_count / 1024 / elapsed, 2),
                    "response_key": key,
                    **latency,
                    "frames": terminal.frames,
                }
                results.append(result)
                print(json.dumps(result), flush=True)
            finally:
                terminal.close()
            (REPORT / "performance.json").write_text(
                json.dumps(results, indent=2) + "\n"
            )
    return results


def job_control():
    results = []
    java_home = os.environ.get("TURBOTIDES_JAVA_HOME") or os.environ.get("JAVA_HOME")
    java = str(Path(java_home) / "bin/java") if java_home else "java"

    def command(directory, telemetry, data_dir):
        arguments = [
            java,
            "--enable-native-access=ALL-UNNAMED",
            "-jar",
            str(JAR),
            "--telemetry",
            str(telemetry),
            "--data-dir",
            str(data_dir),
        ]
        script = "\n".join(
            [
                f"stty -g > {shlex.quote(str(directory / 'stty-before.txt'))}",
                shlex.join(arguments),
                "game_status=$?",
                f"stty -g > {shlex.quote(str(directory / 'stty-after.txt'))}",
                'exit "$game_status"',
            ]
        )
        # Interactive bash gives the game a real foreground job, while the
        # command script avoids racing its prompt reader with the ANSI decoder.
        return "/bin/bash", ["--noprofile", "--norc", "-i", "-c", script]

    for scene in ["control-quit", "garage", "countdown", "racing", "paused", "help"]:
        terminal = ObservedTerminal(f"job-control-{scene}", command=command)
        try:
            if scene == "countdown":
                terminal.key("Enter", 0.3)
                terminal.wait_state(
                    lambda state: state["phase"] == "COUNTDOWN", "countdown"
                )
            elif scene in ["racing", "paused"]:
                racing(terminal)
                terminal.key("W", 0.3)
                if scene == "paused":
                    terminal.key("Esc", 0.3)
            elif scene == "help":
                terminal.key("?", 0.3)
            before = terminal.save("before")
            rendered_before = terminal.rendered_cells()
            java_pid = int(
                Path(f"/proc/{terminal.child.pid}/task/{terminal.child.pid}/children")
                .read_text()
                .split()[0]
            )
            if scene != "control-quit":
                terminal.child.sendcontrol("z")
            terminal.pump(0.7)
            process_state = process_usage(java_pid)["state"]
            stopped = process_state in ["T", "t"]
            if stopped:
                os.kill(java_pid, signal.SIGCONT)
                terminal.pump(0.3)
            after = terminal.save("after")
            require(not stopped, "Ctrl+Z unexpectedly suspended the game")
            require(
                before["phase"] == after["phase"]
                or before["phase"] == "COUNTDOWN"
                and after["phase"] == "RACING",
                "Ctrl+Z changed game phase unexpectedly",
            )
            require(before["help"] == after["help"], "Ctrl+Z changed help state")
            if scene in ["control-quit", "garage", "paused", "help"]:
                require(
                    terminal.rendered_cells() == rendered_before,
                    "Ctrl+Z changed a frozen rendered screen",
                )
            if scene == "racing":
                require(after["distance"] > before["distance"], "Race froze at Ctrl+Z")
        finally:
            terminal.close()
        require(
            terminal.child.exitstatus == 0, "Shell-launched game did not exit cleanly"
        )
        require(
            "\x1b[?1049l" in terminal.raw and "\x1b[?1004l" in terminal.raw,
            "Shell-launched game did not restore ANSI modes",
        )
        stty_before = (terminal.directory / "stty-before.txt").read_text().strip()
        stty_after = (terminal.directory / "stty-after.txt").read_text().strip()
        before_fields, after_fields = stty_before.split(":"), stty_after.split(":")
        semantic_restored = (
            before_fields[:2] + before_fields[3:] == after_fields[:2] + after_fields[3:]
        )
        require(
            semantic_restored,
            "Shell input/output/local flags or control characters changed",
        )
        control_flags_restored = (
            (int(before_fields[2], 16) ^ int(after_fields[2], 16))
            & ~(termios.CBAUD | termios.CIBAUD)
        ) == 0
        require(control_flags_restored, "Non-baud terminal control flags changed")
        result = {
            "scene": scene,
            "ctrl_z_stopped_process": stopped,
            "process_state_after_key": process_state,
            "phase_before": before["phase"],
            "phase_after": after["phase"],
            "distance_before": before["distance"],
            "distance_after": after["distance"],
            "input_output_local_controls_restored": semantic_restored,
            "control_flags_except_baud_restored": control_flags_restored,
            "exact_terminal_attributes_restored": stty_after == stty_before,
            "stty_before": stty_before,
            "stty_after": stty_after,
            "frames": terminal.frames,
        }
        results.append(result)
        print(json.dumps(result), flush=True)
        (REPORT / "job-control.json").write_text(json.dumps(results, indent=2) + "\n")
    return results


def offline(app):
    require(shutil.which("strace") is not None, "Offline test requires strace")
    denial = [
        "-f",
        "-qq",
        "-e",
        "trace=connect,sendto,sendmsg",
        "-e",
        "inject=connect,sendto,sendmsg:error=ENETUNREACH:when=1+",
    ]
    positive = subprocess.run(
        [
            "strace",
            *denial,
            "-o",
            str(REPORT / "network-denial-control.log"),
            "python3",
            "-c",
            'import socket; socket.socket().connect(("127.0.0.1", 9))',
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    require(
        positive.returncode != 0 and "Network is unreachable" in positive.stderr,
        "Network-denial positive control did not fail as expected",
    )

    def command(directory, telemetry, data_dir):
        return "strace", [
            *denial,
            "-o",
            str(directory / "network.log"),
            str(app),
            "--telemetry",
            str(telemetry),
            "--data-dir",
            str(data_dir),
        ]

    terminal = ObservedTerminal(
        "offline-installed",
        command=command,
        artifact=app.resolve().parent / "turbotides-tui.jar",
    )
    try:
        terminal.save("garage")
        racing(terminal)
        terminal.key("W", 1.2)
        require(
            terminal.state()["distance"] > 0, "Offline installed game did not drive"
        )
        terminal.save("racing")
        terminal.key("Esc", 0.3)
        terminal.wait_state(lambda state: state["phase"] == "PAUSED", "offline pause")
        require("Race paused" in terminal.text(), "Offline pause overlay is absent")
        terminal.save("paused")
        terminal.key("R", 0.3)
        terminal.wait_state(
            lambda state: state["phase"] == "COUNTDOWN", "offline retry"
        )
        terminal.save("retry")
        result = {
            "app": str(app),
            "installed_jar_sha256": hashlib.sha256(
                (app.resolve().parent / "turbotides-tui.jar").read_bytes()
            ).hexdigest(),
            "working_directory": "/tmp",
            "network_denial_positive_control": True,
            "denied_syscalls": ["connect", "sendto", "sendmsg"],
            "garage_race_drive_pause_retry": "passed",
            "frames": terminal.frames,
        }
    finally:
        terminal.close()
    require(terminal.child.exitstatus == 0, "Offline game did not quit cleanly")
    require(
        "\x1b[?1049l" in terminal.raw and "\x1b[?1004l" in terminal.raw,
        "Offline game did not restore ANSI modes",
    )
    result["exit_status"] = terminal.child.exitstatus
    (REPORT / "offline.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)
    return result


def main():
    global JAR, REPORT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--group",
        choices=["all", "performance", "job-control", "offline"],
        default="all",
    )
    parser.add_argument("--seconds", type=float, default=8)
    parser.add_argument("--jar", type=Path, default=JAR)
    parser.add_argument("--output-dir", type=Path, default=REPORT)
    parser.add_argument(
        "--scene", action="append", choices=["garage", "help", "paused", "racing"]
    )
    parser.add_argument("--size", action="append", choices=["100x34", "180x65"])
    parser.add_argument(
        "--installed-app", type=Path, default=Path.home() / ".local/bin/turbotides-tui"
    )
    args = parser.parse_args()
    JAR = args.jar.resolve()
    REPORT = args.output_dir.resolve()
    require(args.seconds >= 1, "Sample duration must be at least one second")
    REPORT.mkdir(parents=True, exist_ok=True)
    os.environ["JDK_JAVA_OPTIONS"] = "-Xms32m -Xmx384m"
    metadata = {
        "started_unix": time.time(),
        "jar_sha256": hashlib.sha256(JAR.read_bytes()).hexdigest(),
        "platform": platform.platform(),
        "cpu": next(
            line.split(":", 1)[1].strip()
            for line in Path("/proc/cpuinfo").read_text().splitlines()
            if line.startswith("model name")
        ),
        "logical_cpus": os.cpu_count(),
        "java_options": os.environ["JDK_JAVA_OPTIONS"],
        "telemetry_enabled": True,
        "decoder_during_timed_sample": False,
    }
    (REPORT / "environment.json").write_text(json.dumps(metadata, indent=2) + "\n")
    if args.group in ["all", "performance"]:
        performance(args.seconds, args.scene, args.size)
    if args.group in ["all", "job-control"]:
        job_control()
    if args.group in ["all", "offline"]:
        offline(args.installed_app)
    require(
        hashlib.sha256(JAR.read_bytes()).hexdigest() == metadata["jar_sha256"],
        "JAR changed during this audit",
    )


if __name__ == "__main__":
    main()
