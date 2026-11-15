#!/usr/bin/env python3
"""Capture only this game's real PipeWire playback while ANSI keys change sound.

The audit creates a recording stream linked to the test Java PID. It never
records a microphone or another application, changes the default audio device,
or changes speaker volume. Requires Linux PipeWire and audit-requirements.txt.
"""

from __future__ import annotations

import array
import hashlib
import json
import math
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

from ansi_audit import Terminal, require

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build/audio-audit"


def command(*arguments: str) -> str:
    return subprocess.check_output(arguments, text=True, timeout=10)


def objects() -> list[dict]:
    return json.loads(command("pw-dump"))


def properties(item: dict) -> dict:
    return item.get("info", {}).get("props", {})


def playback_port(process_id: int) -> int:
    snapshot = objects()
    clients = {
        item["id"]
        for item in snapshot
        if item["type"] == "PipeWire:Interface:Client"
        and str(properties(item).get("application.process.id")) == str(process_id)
    }
    nodes = {
        item["id"]
        for item in snapshot
        if item["type"] == "PipeWire:Interface:Node"
        and (
            properties(item).get("client.id") in clients
            or str(properties(item).get("application.process.id")) == str(process_id)
        )
        and properties(item).get("media.class") == "Stream/Output/Audio"
    }
    for item in snapshot:
        props = properties(item)
        if (
            item["type"] == "PipeWire:Interface:Port"
            and props.get("node.id") in nodes
            and props.get("port.direction") == "out"
            and props.get("audio.channel") in ("FL", "MONO")
        ):
            return item["id"]
    raise RuntimeError(f"No audio playback port belongs to test Java PID {process_id}.")


def capture_port(name: str) -> int | None:
    snapshot = objects()
    nodes = {
        item["id"]
        for item in snapshot
        if item["type"] == "PipeWire:Interface:Node"
        and properties(item).get("node.name") == name
    }
    return next(
        (
            item["id"]
            for item in snapshot
            if item["type"] == "PipeWire:Interface:Port"
            and properties(item).get("node.id") in nodes
            and properties(item).get("port.direction") == "in"
        ),
        None,
    )


def capture(terminal: Terminal, label: str) -> dict:
    filename = OUTPUT / f"{label}.pcm"
    node_name = f"turbotides-audio-audit-{os.getpid()}"
    output_port = playback_port(terminal.child.pid)
    with (OUTPUT / f"{label}.log").open("w") as log:
        recording = subprocess.Popen(
            [
                "pw-record",
                "--target",
                "0",
                "--rate",
                "22050",
                "--channels",
                "1",
                "--format",
                "s16",
                "--raw",
                "--properties",
                f"{{ node.name = {node_name} node.autoconnect = false }}",
                str(filename),
            ],
            stdout=log,
            stderr=log,
        )
        try:
            deadline = time.monotonic() + 5
            input_port = None
            while time.monotonic() < deadline:
                input_port = capture_port(node_name)
                if input_port is not None:
                    break
                terminal.pump(0.05)
            if input_port is None:
                raise RuntimeError("Isolated recording port did not appear.")
            command("pw-link", str(output_port), str(input_port))
            terminal.save(f"audio-{label}-before")
            terminal.pump(0.8)
            terminal.save(f"audio-{label}-after")
        finally:
            recording.send_signal(signal.SIGINT)
            try:
                recording.wait(timeout=3)
            except subprocess.TimeoutExpired:
                recording.kill()
                recording.wait(timeout=3)
    samples = array.array("h")
    samples.frombytes(filename.read_bytes())
    require(len(samples) >= 1000, f"Only {len(samples)} PCM samples in {label}.")
    return {
        "phase": terminal.state()["phase"],
        "samples": len(samples),
        "peak": max(abs(value) for value in samples),
        "rms": round(
            math.sqrt(sum(value * value for value in samples) / len(samples)), 3
        ),
        "nonzero": sum(value != 0 for value in samples),
        "file": str(filename.relative_to(ROOT)),
    }


def main() -> None:
    for tool in ("pw-record", "pw-link", "pw-dump", "wpctl"):
        require(shutil.which(tool) is not None, f"UNVERIFIED: {tool} unavailable.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    speaker_before = command("wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@")
    terminal = Terminal("audio-output")
    result: dict = {
        "jar_sha256": hashlib.sha256(
            (ROOT / "build/libs/turbotides-tui.jar").read_bytes()
        ).hexdigest(),
        "java_version": command(terminal.child.command, "--version").splitlines()[0],
    }
    try:
        terminal.pump(0.5)
        result["garage-on"] = capture(terminal, "garage-on")
        terminal.key("M", 0.5)
        result["garage-muted"] = capture(terminal, "garage-muted")
        terminal.key("M", 0.5)
        result["garage-restored"] = capture(terminal, "garage-restored")
        terminal.key("Enter", 0.15)
        terminal.key("W", 0.15)
        result["countdown-on"] = capture(terminal, "countdown-on")
        while terminal.state()["phase"] == "COUNTDOWN":
            terminal.pump(0.1)
        terminal.pump(1)
        result["racing-on"] = capture(terminal, "racing-on")
        terminal.key("M", 0.5)
        result["racing-muted"] = capture(terminal, "racing-muted")
        terminal.key("M", 0.5)
        result["racing-restored"] = capture(terminal, "racing-restored")
        terminal.key("Esc", 0.5)
        result["paused"] = capture(terminal, "paused")
        terminal.key("M", 0.5)
        result["paused-muted"] = capture(terminal, "paused-muted")
        terminal.key("M", 0.5)
        result["paused-unmuted"] = capture(terminal, "paused-unmuted")
        terminal.key("Enter", 0.2)
        terminal.key("W", 0.5)
        result["resumed"] = capture(terminal, "resumed")
        terminal.key("B", 0.1)
        finish_deadline = time.monotonic() + 110
        while terminal.state()["phase"] != "FINISHED":
            require(
                time.monotonic() < finish_deadline,
                "Race did not finish through real input.",
            )
            lane = terminal.state()["lane"]
            if lane < -0.5:
                terminal.key("D", 0.08)
            elif lane > 0.5:
                terminal.key("A", 0.08)
            else:
                terminal.pump(0.08)
        result["finished-on"] = capture(terminal, "finished-on")
        terminal.key("M", 0.5)
        result["finished-muted"] = capture(terminal, "finished-muted")
        terminal.key("M", 0.5)
        result["finished-restored"] = capture(terminal, "finished-restored")
        terminal.key("Enter", 0.1)
        terminal.key("M", 0.3)
        result["countdown-muted"] = capture(terminal, "countdown-muted")
        for label in (
            "garage-muted",
            "racing-muted",
            "paused",
            "paused-muted",
            "paused-unmuted",
            "finished-muted",
            "countdown-muted",
        ):
            require(
                result[label]["peak"] == 0,
                f"{label} emitted nonzero audio: {result[label]}",
            )
        for label in (
            "garage-on",
            "garage-restored",
            "countdown-on",
            "racing-on",
            "racing-restored",
            "resumed",
            "finished-on",
            "finished-restored",
        ):
            require(
                result[label]["peak"] > 200,
                f"{label} did not emit expected audio: {result[label]}",
            )
        speaker_after = command("wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@")
        require(
            speaker_before == speaker_after, "Speaker state changed during capture."
        )
        result["speaker_state_before_and_after"] = speaker_before.strip()
        require(
            result["jar_sha256"]
            == hashlib.sha256(
                (ROOT / "build/libs/turbotides-tui.jar").read_bytes()
            ).hexdigest(),
            "JAR changed during audio audit; rerun against the final artifact.",
        )
        result["status"] = "PASSED"
        result["limitation"] = (
            "Game-only playback PCM verified; physical loudspeaker audibility and macOS audio remain unverified."
        )
    except Exception as error:
        result["status"] = "FAILED"
        result["error"] = str(error)
        raise
    finally:
        terminal.close()
        (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
