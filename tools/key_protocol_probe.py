#!/usr/bin/env python3
"""Observe tui4j's actual key decoding for isolated Escape and repeated bytes.

This standalone probe uses the unmodified game JAR's tui4j classes. It changes
neither game input handlers nor game state. Set JAVA_HOME to JDK 25 first.
"""

import json
import os
import subprocess
import time
from pathlib import Path

import pexpect

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build" / "ansi-audit" / "key-protocol"


def main():
    java_home = os.environ.get("TURBOTIDES_JAVA_HOME") or os.environ.get("JAVA_HOME")
    java = str(Path(java_home) / "bin" / "java") if java_home else "java"
    javac = str(Path(java_home) / "bin" / "javac") if java_home else "javac"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    jar = ROOT / "build/libs/turbotides-tui.jar"
    subprocess.run(
        [
            javac,
            "-Xlint:all",
            "-Werror",
            "-cp",
            str(jar),
            "-d",
            str(OUTPUT),
            str(ROOT / "tools/KeyProbe.java"),
        ],
        check=True,
    )
    results = {}
    for name in ["tap", "fast-burst", "native-hold", "spaced-taps"]:
        log = OUTPUT / f"{name}.keys"
        log.unlink(missing_ok=True)
        child = pexpect.spawn(
            java,
            [
                "--enable-native-access=ALL-UNNAMED",
                "-cp",
                str(jar) + os.pathsep + str(OUTPUT),
                "KeyProbe",
                str(log),
            ],
            env=dict(os.environ, TERM="xterm-256color", COLORTERM="truecolor"),
            encoding="utf8",
            dimensions=(24, 80),
        )
        child.delaybeforesend = 0
        with (OUTPUT / f"{name}.ansi").open("w") as stream:
            child.logfile_read = stream
            try:
                child.expect("Keyboard probe ready", timeout=20)

                def pump(duration, process=child):
                    deadline = time.monotonic() + duration
                    while time.monotonic() < deadline:
                        try:
                            process.read_nonblocking(
                                65536,
                                timeout=min(
                                    0.02, max(0.001, deadline - time.monotonic())
                                ),
                            )
                        except pexpect.TIMEOUT:
                            pass
                        except pexpect.EOF:
                            return

                if name in ["tap", "native-hold", "spaced-taps"]:
                    child.send("\x1b")
                    pump(0.5 if name == "native-hold" else 0.3)
                if name in ["fast-burst", "native-hold"]:
                    for _ in range(10):
                        child.send("\x1b")
                        pump(0.04)
                if name == "spaced-taps":
                    child.send("\x1b")
                    pump(0.3)
                pump(0.3)
                child.send("q")
                child.expect(pexpect.EOF, timeout=3)
            finally:
                child.close(force=True)
        results[name] = [line.split(" ", 1)[1] for line in log.read_text().splitlines()]
        print(name, results[name])
    expected = {
        "tap": ["esc", "q"],
        "fast-burst": ["alt+esc"] * 5 + ["q"],
        "native-hold": ["esc"] + ["alt+esc"] * 5 + ["q"],
        "spaced-taps": ["esc", "esc", "q"],
    }
    (OUTPUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    if results != expected:
        raise AssertionError(
            f"Terminal key decoding differs from recorded Linux observation: {results}"
        )


if __name__ == "__main__":
    main()
