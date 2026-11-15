#!/usr/bin/env python3
"""Exercise four visible AI levels using ordinary PTY input and real race time."""

import argparse
import itertools
import json
import time
from concurrent.futures import ThreadPoolExecutor

from ansi_audit import (
    CIRCUITS,
    DIFFICULTIES,
    OUTPUT,
    RESULTS,
    Terminal,
    check,
    focus,
    require,
    start,
    tap,
)
from city_audit import select, visible

TITLES = dict(zip(DIFFICULTIES, ["Easy", "Medium", "Hard", "Super Hard"], strict=True))


def select_level(terminal, level):
    focus(terminal, 2)
    for _ in range(4):
        if terminal.state()["difficulty"] == level:
            visible(terminal, TITLES[level])
            return
        terminal.key("Right", 0.3)
    require(terminal.state()["difficulty"] == level, "Four-level selector did not wrap")


def menu_audit():
    terminal = Terminal("difficulty-menu", 64, 24)
    try:
        focus(terminal, 2)
        for key, direction in [
            ("Left", -1),
            ("A", -1),
            ("Right", 1),
            ("D", 1),
            ("Enter", 1),
        ]:
            for _ in range(4):
                before = terminal.state()["difficulty"]
                expected = DIFFICULTIES[(DIFFICULTIES.index(before) + direction) % 4]

                def change(t, binding=key, level=expected):
                    tap(t, binding, "difficulty", level)
                    require(
                        TITLES[level] in t.screen.display[0],
                        "Difficulty was clipped from minimum-width header",
                    )
                    require(
                        f"Difficulty < {TITLES[level]} >" in t.text(),
                        "Selected level missing from garage",
                    )

                check(
                    terminal,
                    f"difficulty-from-{before.lower()}",
                    key,
                    f"Select visible {TITLES[expected]} and wrap four choices",
                    change,
                )
        for level in DIFFICULTIES:
            select_level(terminal, level)

            def launch(t, selected=level):
                start(t)
                require(t.state()["difficulty"] == selected, "Race used wrong level")
                require(
                    TITLES[selected] in t.screen.display[0],
                    "Countdown hid selected difficulty",
                )
                t.key("Esc", 0.4)
                t.wait_state(lambda s: s["phase"] == "PAUSED", "paused countdown")
                visible(t, "Race paused")
                require(
                    TITLES[selected] in t.screen.display[0],
                    "Paused screen hid difficulty",
                )

            check(
                terminal,
                f"difficulty-start-{level.lower()}",
                "Enter / Esc",
                "Start selected level; keep it visible during countdown and pause",
                launch,
            )
            terminal.key("G", 0.3)
            focus(terminal, 2)
        profile = terminal.directory / "data"
    finally:
        terminal.close()
    reopened = Terminal("difficulty-reopen", 64, 24, record_dir=profile)
    try:
        require(
            reopened.state()["difficulty"] == "SUPER_HARD",
            "Selected difficulty was not restored",
        )
        visible(reopened, "Super Hard")
        reopened.save("restored-super-hard")
    finally:
        reopened.close()
    (OUTPUT / "difficulty-results.json").write_text(
        json.dumps(RESULTS, indent=2) + "\n"
    )


def observe(circuit, level):
    terminal = Terminal(
        f"difficulty-observe-{circuit.lower()}-{level.lower()}", 100, 34
    )
    try:
        select(terminal, circuit)
        select_level(terminal, level)
        terminal.save("selected")
        start(terminal)
        terminal.key("S", 0.3)
        deadline = time.monotonic() + 150
        samples = set()
        while time.monotonic() < deadline:
            state = terminal.state()
            for second in [2, 20, 35]:
                if state["time"] >= second and second not in samples:
                    terminal.save(f"rivals-{second}s")
                    samples.add(second)
            finishes = [state[f"rival{i}FinishTime"] for i in range(5)]
            if all(value is not None for value in finishes):
                break
            terminal.pump(0.05)
        else:
            raise AssertionError(
                f"{level} rivals did not finish in normal wall-clock time"
            )
        require(
            state["speed"] == 0 and state["distance"] == 0,
            "Observer must remain parked with real brake input",
        )
        terminal.save("field-finished")
        return {
            "circuit": circuit,
            "difficulty": level,
            "status": "PASSED",
            "leader_time": min(finishes),
            "last_time": max(finishes),
            "finish_times": finishes,
            "frames": terminal.frames,
        }
    finally:
        terminal.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=["all", "menu", "observe"], default="all")
    parser.add_argument("--circuit", choices=CIRCUITS, default="SAN_FRANCISCO")
    args = parser.parse_args()
    if args.group in ["all", "menu"]:
        menu_audit()
    if args.group in ["all", "observe"]:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(lambda level: observe(args.circuit, level), DIFFICULTIES)
            )
        for easier, harder in itertools.pairwise(results):
            require(
                harder["leader_time"] < easier["leader_time"] - 3,
                "Leader difficulty gap was not meaningful",
            )
            require(
                harder["last_time"] < easier["last_time"] - 3,
                "Backmarker difficulty gap was not meaningful",
            )
        (OUTPUT / "difficulty-observations.json").write_text(
            json.dumps(results, indent=2) + "\n"
        )
        print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    main()
