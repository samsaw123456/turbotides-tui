#!/usr/bin/env python3
"""Prove Super Hard can be won through ordinary terminal controls.

Read-only diagnostics guide steering, pad approaches and drift banking. The game
runs at normal wall-clock speed; this tool never writes gameplay state. Output
uses a fresh directory so earlier control/campaign evidence remains intact.
"""

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import ansi_audit as audit
from ansi_audit import CIRCUITS, ROOT, Terminal, focus, require, start


def play(circuit):
    terminal = Terminal(f"expert-{circuit.lower()}", 100, 34)
    command_log = (terminal.directory / "commands.jsonl").open("w")

    def record(event, **values):
        state = terminal.state()
        command_log.write(
            json.dumps(
                {
                    "event": event,
                    "wall": time.time(),
                    "sim": state["time"],
                    "drift": state["drift"],
                    "charge": state["driftCharge"],
                    "banked": state["driftBonuses"],
                    **values,
                }
            )
            + "\n"
        )
        command_log.flush()

    def key(name, wait=0.035):
        record("key", key=name)
        terminal.key(name, wait)

    try:
        focus(terminal, 0)
        while terminal.state()["circuit"] != circuit:
            key("Right", 0.3)
        focus(terminal, 2)
        while terminal.state()["difficulty"] != "SUPER_HARD":
            key("Right", 0.3)
        key("P", 0.3)
        terminal.save("garage")
        start(terminal)
        key("W", 0.1)
        key("B", 0.1)
        key("Space", 0.1)
        desired_drift = True
        pending_toggle = True
        changed_sim = 0.0
        changed_wall = time.monotonic()
        last_time, last_lane, velocity = 0.0, -3.0, 0.0
        last_lap, last_bank, retries = 0, 0, 0
        recovery_pending = False
        deadline = time.monotonic() + 150

        while terminal.state()["phase"] != "FINISHED" and time.monotonic() < deadline:
            state = terminal.state()
            if state["phase"] == "COUNTDOWN":
                terminal.pump(0.04)
                continue
            stamp = state["time"]
            if stamp > last_time:
                velocity = (state["lane"] - last_lane) / (stamp - last_time)
                last_time, last_lane = stamp, state["lane"]
            targets = [
                (state["length"] * (0.15 + i * 0.25), -3.6 if i % 2 == 0 else 3.6)
                for i in range(3)
            ]
            pad, lane = min(
                targets, key=lambda p: (p[0] - state["distance"]) % state["length"]
            )
            gap = (pad - state["distance"]) % state["length"]
            target = lane if gap < 115 else 0.0
            direction = (target - state["lane"]) * 2.8 - velocity * 0.9
            key("D" if direction > 0 else "A")

            # Observe mode acknowledgement rather than assuming Space was accepted.
            # A delayed/debounced tap is retried only after fresh simulation output
            # and a safely spaced interval; input and physics remain ordinary.
            if pending_toggle:
                if state["drift"] == desired_drift:
                    pending_toggle = False
                    record("drift-mode-confirmed", desired=desired_drift)
                    if recovery_pending:
                        terminal.save(f"drift-mode-recovered-{retries}")
                        recovery_pending = False
                elif (
                    time.monotonic() - changed_wall > 0.65
                    and stamp - changed_sim > 0.25
                ):
                    retries += 1
                    terminal.save(f"drift-mode-retry-{retries}")
                    key("Space")
                    changed_wall = time.monotonic()
                    changed_sim = stamp
                    recovery_pending = True
            elif (desired_drift and state["driftCharge"] >= 0.55) or (
                not desired_drift and stamp - changed_sim > 0.3
            ):
                key("Space")
                desired_drift = not desired_drift
                pending_toggle = True
                changed_sim = stamp
                changed_wall = time.monotonic()
            if state["lap"] != last_lap:
                last_lap = state["lap"]
                terminal.save(f"lap-{last_lap}")
            if state["driftBonuses"] >= last_bank + 10:
                last_bank = state["driftBonuses"]
                terminal.save(f"drifts-{last_bank}")

        terminal.wait_state(lambda s: s["phase"] == "FINISHED", "expert finish")
        deadline = time.monotonic() + 3
        while "Finished" not in terminal.text() and time.monotonic() < deadline:
            terminal.pump(0.05)
        state = terminal.save("finished")
        require(
            state["position"] == 1, f"{circuit}: expert finished {state['position']}"
        )
        require("Finished 1/6" in terminal.text(), "First-place result is not visible")
        require(state["lap"] == 3 and state["pads"] > 0, "Race/pad loop incomplete")
        require(state["driftBonuses"] > 0, "Expert win did not bank actual drifts")
        require(
            f"Drifts {state['driftBonuses']}" in terminal.text(),
            "Banked drift total is not visible",
        )
        result = {
            "status": "PASSED",
            "circuit": circuit,
            "difficulty": state["difficulty"],
            "time": state["time"],
            "position": state["position"],
            "pads": state["pads"],
            "drifts": state["driftBonuses"],
            "bumps": state["bumps"],
            "mode_retries": retries,
            "frames": terminal.frames,
        }
    except Exception:
        terminal.save("failed")
        raise
    finally:
        command_log.close()
        terminal.close()
        (terminal.directory / "exit.json").write_text(
            json.dumps({"exit_status": terminal.child.exitstatus}, indent=2) + "\n"
        )
    require(terminal.child.exitstatus == 0, "Expert game did not exit cleanly")
    (terminal.directory / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--circuit", choices=CIRCUITS)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Fresh directory inside the checkout; relative paths use the repo root",
    )
    args = parser.parse_args()
    output = args.output_dir or Path("build/ansi-audit") / (
        "expert-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    )
    output = (ROOT / output).resolve()
    if not output.is_relative_to(ROOT):
        parser.error(
            "--output-dir must be inside the checkout for frame evidence links"
        )
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error("--output-dir already contains files; choose a fresh directory")
    try:
        output.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        parser.error(f"Cannot create --output-dir: {error}")
    audit.OUTPUT = output
    results = []
    for circuit in [args.circuit] if args.circuit else CIRCUITS:
        result = play(circuit)
        results.append(result)
        print(json.dumps(result), flush=True)
        (output / "summary.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
