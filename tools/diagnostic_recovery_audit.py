#!/usr/bin/env python3
"""Repair an isolated diagnostic target and inspect the real PTY error recovery."""

import json

from ansi_audit import OUTPUT, Terminal, require


def main() -> None:
    directory = OUTPUT / "diagnostic-recovery"
    directory.mkdir(parents=True, exist_ok=True)
    sibling = directory / "state.json.tmp"
    sentinel = "unrelated sibling data must survive diagnostic writes\n"
    sibling.write_text(sentinel)
    terminal = Terminal("diagnostic-recovery")
    try:
        require(
            sibling.exists() and sibling.read_text() == sentinel,
            "Startup clobbered unrelated sibling",
        )
        terminal.save("before")
        terminal.telemetry.unlink()
        terminal.telemetry.mkdir()
        (terminal.telemetry / "keep").write_text(
            "isolated diagnostic failure fixture\n"
        )
        terminal.pump(0.5)
        require(
            "Diagnostics unavailable" in terminal.text(), "Failure was not rendered"
        )
        terminal.save_frame("failed")
        (terminal.telemetry / "keep").unlink()
        terminal.telemetry.rmdir()
        terminal.pump(0.5)
        state = terminal.save("recovered")
        require(state["phase"] == "GARAGE", "Recovery did not write valid diagnostics")
        require(
            "Diagnostics unavailable" not in terminal.text(), "Recovered error remains"
        )
        require(
            "Local records only" in terminal.text(), "Normal footer did not recover"
        )
        require(
            sibling.read_text() == sentinel,
            "Diagnostic retry clobbered unrelated sibling",
        )
        (OUTPUT / "diagnostic-recovery-results.json").write_text(
            json.dumps(
                {
                    "status": "PASSED",
                    "expected": "Diagnostic writes preserve unrelated siblings and recover with a cleared visible warning",
                    "evidence": terminal.frames,
                },
                indent=2,
            )
            + "\n"
        )
    finally:
        terminal.close()


if __name__ == "__main__":
    main()
