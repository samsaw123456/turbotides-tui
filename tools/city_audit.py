#!/usr/bin/env python3
"""Inspect city streetscapes through real ANSI input at normal simulation speed.

This supplements the complete control audit. It captures each city's preview,
quarter-lap scenes, rear view, pause/recovery and finish without changing state.
"""

import argparse
import json
import os
import time

from ansi_audit import OUTPUT, Terminal, focus, require, start

CITIES = ["SAN_FRANCISCO", "SILICON_VALLEY", "NEW_YORK", "CHICAGO"]


def visible(terminal, text):
    deadline = time.monotonic() + 3
    while text not in terminal.text() and time.monotonic() < deadline:
        terminal.pump(0.05)
    require(text in terminal.text(), f"Rendered text did not appear: {text}")


def select(terminal, circuit):
    focus(terminal, 0)
    for _ in range(6):
        if terminal.state()["circuit"] == circuit:
            return
        terminal.key("Right", 0.3)
    raise AssertionError(f"Could not select {circuit}")


def audit(circuit, columns, rows, previews_only=False):
    palette = os.environ.get("TURBOTIDES_COLOR", "truecolor")
    terminal = Terminal(
        f"city-{circuit.lower()}-{columns}x{rows}-{palette}", columns, rows
    )
    try:
        select(terminal, circuit)
        terminal.key("P", 0.4)
        require(not terminal.state()["overview"], "Preview did not open")
        terminal.save("street-preview")
        before = terminal.rendered_cells()
        terminal.pump(0.6)
        require(terminal.rendered_cells() == before, "Stationary scenery flickers")
        if previews_only:
            return {"circuit": circuit, "status": "PASSED", "frames": terminal.frames}

        start(terminal)
        terminal.key("W", 0.3)
        terminal.save("countdown")
        deadline = time.monotonic() + 180
        captured = set()
        pause_done = False
        while terminal.state()["phase"] != "FINISHED" and time.monotonic() < deadline:
            state = terminal.state()
            if state["phase"] == "COUNTDOWN":
                terminal.pump(0.05)
                continue
            fraction = state["distance"] / state["length"]
            sector = min(3, int(fraction * 4))
            if fraction < 1 and sector not in captured:
                terminal.save(f"district-{sector}")
                captured.add(sector)
            if fraction > 0.6 and not pause_done:
                terminal.key("C", 0.35)
                visible(terminal, "REAR VIEW")
                terminal.save("rear-streetscape")
                terminal.key("C", 0.35)
                terminal.key("Esc", 0.4)
                terminal.wait_state(lambda s: s["phase"] == "PAUSED", "pause")
                visible(terminal, "Race paused")
                terminal.save("paused")
                distance = terminal.state()["distance"]
                before = terminal.rendered_cells()
                terminal.pump(0.5)
                require(terminal.state()["distance"] == distance, "Paused race moved")
                require(terminal.rendered_cells() == before, "Paused scenery flickers")
                terminal.key("Enter", 0.3)
                require(not terminal.state()["throttle"], "Resume retained throttle")
                terminal.key("W", 0.3)
                terminal.save("resumed")
                pause_done = True
                continue
            # Read-only observation chooses normal steering pulses; no game mutation.
            targets = [
                (state["length"] * (0.15 + i * 0.25), -3.6 if i % 2 == 0 else 3.6)
                for i in range(3)
            ]
            progress = state["distance"] % state["length"]
            pad, lane = min(targets, key=lambda p: (p[0] - progress) % state["length"])
            target = lane if (pad - progress) % state["length"] < 85 else 0
            error = target - state["lane"]
            if abs(error) > 0.55:
                terminal.key("D" if error > 0 else "A", 0.04)
            else:
                terminal.pump(0.04)
            if state["nitro"] > 32 and not state["boost"]:
                terminal.key("B", 0.04)
            if state["nitro"] < 5 and state["boost"]:
                terminal.key("B", 0.04)
        terminal.pump(0.3)
        visible(terminal, "Finished")
        result = terminal.save("finished")
        require(result["phase"] == "FINISHED", "City race did not finish")
        require(result["lap"] == 3 and result["pads"] > 0, "Lap/pad loop incomplete")
        require(len(captured) == 4 and pause_done, "City scene coverage incomplete")
        terminal.key("Enter", 0.3)
        require(terminal.state()["phase"] == "COUNTDOWN", "Retry failed")
        terminal.save("retry")
        return {
            "circuit": circuit,
            "status": "PASSED",
            "time": result["time"],
            "position": result["position"],
            "pads": result["pads"],
            "frames": terminal.frames,
        }
    except Exception:
        terminal.save("failed")
        raise
    finally:
        terminal.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--circuit", choices=CITIES)
    parser.add_argument(
        "--size", default="100x34", choices=["64x24", "100x34", "180x65"]
    )
    parser.add_argument("--previews-only", action="store_true")
    args = parser.parse_args()
    columns, rows = map(int, args.size.split("x"))
    palette = os.environ.get("TURBOTIDES_COLOR", "truecolor")
    filename = f"cities-{args.circuit or 'all'}-{args.size}-{palette}.json"
    results = []
    for city in [args.circuit] if args.circuit else CITIES:
        result = audit(city, columns, rows, args.previews_only)
        results.append(result)
        print(json.dumps(result), flush=True)
        (OUTPUT / filename).write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
