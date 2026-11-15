#!/usr/bin/env python3
"""Prove that an earned best survives a failed write and a later settings save.

The race runs at normal speed through the real PTY. Only an isolated profile's
filesystem is deliberately broken and repaired; gameplay state is never edited.
"""

import argparse
import json
import time

from ansi_audit import OUTPUT, RESULTS, Terminal, check, require, start


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--garage", action="store_true", help="Leave results before retrying the save"
    )
    args = parser.parse_args()
    suffix = "-garage" if args.garage else ""
    terminal = Terminal(f"finish-record-recovery{suffix}", 100, 34)
    destination = terminal.directory / "data" / "records.properties"
    try:
        destination.mkdir(parents=True)
        (destination / "keep").write_text("isolated failure fixture\n")

        def finish_with_failed_save(t: Terminal) -> None:
            start(t)
            t.key("W", 0.3)
            deadline = time.monotonic() + 150
            while t.state()["phase"] != "FINISHED" and time.monotonic() < deadline:
                state = t.state()
                if state["phase"] == "COUNTDOWN":
                    t.pump(0.05)
                    continue
                if abs(state["lane"]) > 0.55:
                    t.key("A" if state["lane"] > 0 else "D", 0.04)
                else:
                    t.pump(0.04)
                if state["nitro"] > 32 and not state["boost"]:
                    t.key("B", 0.04)
                if state["nitro"] < 5 and state["boost"]:
                    t.key("B", 0.04)
            t.wait_state(lambda state: state["phase"] == "FINISHED", "actual finish")
            t.wait_state(lambda state: state["saveError"], "failed finish save")
            require(t.state()["best"] is None, "Failed write claimed a saved best")
            require(
                "Personal best pending save" in t.text(), "Pending best not visible"
            )
            require("Cannot save records" in t.text(), "Save warning not visible")

        check(
            terminal,
            "finished-record-write-error",
            "Enter / W / A / D / B",
            "Actual completed race retains an unsaved earned best with visible warning",
            finish_with_failed_save,
        )
        finish_time = terminal.state()["time"]
        terminal.resize(64, 24)
        require(
            "Personal best pending save" in terminal.text(),
            "Minimum size hid pending result",
        )
        terminal.save("pending-minimum-terminal")
        terminal.resize(100, 34)
        if args.garage:
            terminal.key("G", 0.3)
            require(
                terminal.state()["phase"] == "GARAGE",
                "Results did not return to garage",
            )
            require(
                terminal.state()["saveError"],
                "Leaving results hid pending save failure",
            )
            terminal.save("pending-after-leaving-results")
        (destination / "keep").unlink()
        destination.rmdir()

        def recover(t: Terminal) -> None:
            t.key("M", 0.4)
            t.wait_state(lambda state: not state["saveError"], "successful save retry")
            require(t.state()["best"] == finish_time, "Settings retry lost earned best")
            if args.garage:
                require("Best --" not in t.text(), "Garage did not show saved best")
            else:
                require(
                    "New personal best!" in t.text(), "Result did not show saved best"
                )
            require("pending save" not in t.text(), "Recovered result still pending")
            require(
                "Cannot save records" not in t.text(), "Recovered error still visible"
            )
            require(
                t.state()["phase"] == ("GARAGE" if args.garage else "FINISHED"),
                "Recovery changed game state",
            )
            require(
                t.state()["time"] == (0 if args.garage else finish_time),
                "Recovery advanced race time",
            )

        check(
            terminal,
            "garage-record-write-recovery"
            if args.garage
            else "finished-record-write-recovery",
            "M",
            "Repair plus settings save persists the earned best and updates result feedback",
            recover,
        )
    finally:
        terminal.close()

    reopened = Terminal(
        f"finish-record-reopen{suffix}", 100, 34, record_dir=destination.parent
    )
    try:

        def confirm_persisted(t: Terminal) -> None:
            require(t.state()["best"] == finish_time, "Earned best did not reload")
            require(t.state()["muted"], "Recovery lost changed sound preference")
            require("Best --" not in t.text(), "Reloaded best not rendered")

        check(
            reopened,
            "garage-record-recovery-reopen",
            "Launch",
            "Recovered best and changed setting both load visibly in a new process",
            confirm_persisted,
        )
    finally:
        reopened.close()
    (OUTPUT / f"record-recovery{suffix}-results.json").write_text(
        json.dumps(RESULTS, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
