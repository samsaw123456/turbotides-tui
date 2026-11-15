#!/usr/bin/env python3
"""Drive the real tui4j application with ANSI bytes and inspect decoded frames.

No race state is written by this harness. --telemetry is read-only observation;
all actions, including completing races, enter through the PTY. PNGs depict the
actual terminal output decoded with pyte, not a duplicate game renderer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path

import pexpect
import pyte
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build" / "ansi-audit"
BINDINGS = {
    "A": "a",
    "D": "d",
    "Left": "\x1b[D",
    "Right": "\x1b[C",
    "S": "s",
    "Down": "\x1b[B",
    "W": "w",
    "Up": "\x1b[A",
    "Space": " ",
    "B": "b",
    "C": "c",
    "R": "r",
    "P": "p",
    "Esc": "\x1b",
    "Enter": "\r",
    "Tab": "\t",
    "Shift+Tab": "\x1b[Z",
    "M": "m",
    "N": "n",
    "?": "?",
    "G": "g",
    "Q": "q",
    "Ctrl+C": "\x03",
    "FocusOut": "\x1b[O",
    "FocusIn": "\x1b[I",
}
DIFFICULTIES = ["EASY", "MEDIUM", "HARD", "SUPER_HARD"]
RESULTS: list[dict] = []


def require(condition: bool, explanation: str) -> None:
    if not condition:
        raise AssertionError(explanation)


def rgb(value: str, default: tuple[int, int, int]) -> tuple[int, int, int]:
    palette = {
        "black": "000000",
        "red": "cd0000",
        "green": "00cd00",
        "brown": "cdcd00",
        "blue": "0000ee",
        "magenta": "cd00cd",
        "cyan": "00cdcd",
        "white": "e5e5e5",
    }
    value = palette.get(value, value)
    return (
        tuple(bytes.fromhex(value))
        if re.fullmatch(r"[0-9a-fA-F]{6}", value)
        else default
    )


class Terminal:
    def __init__(
        self,
        name: str,
        columns: int = 120,
        rows: int = 40,
        record_dir: Path | None = None,
    ):
        self.directory = OUTPUT / name
        self.directory.mkdir(parents=True, exist_ok=True)
        self.telemetry = self.directory / "state.json"
        self.telemetry.unlink(missing_ok=True)
        data_dir = record_dir or self.directory / "data"
        if record_dir is None:
            shutil.rmtree(data_dir, ignore_errors=True)
        self.screen = pyte.Screen(columns, rows)
        self.stream = pyte.Stream(self.screen)
        self.raw = ""
        self.raw_log = (self.directory / "terminal.ansi").open("w")
        (self.directory / "build.json").write_text(
            json.dumps(
                {
                    "jar_sha256": hashlib.sha256(
                        (ROOT / "build/libs/turbotides-tui.jar").read_bytes()
                    ).hexdigest(),
                    "started_unix": time.time(),
                    "columns": columns,
                    "rows": rows,
                },
                indent=2,
            )
            + "\n"
        )
        self.frames: list[str] = []
        java_home = os.environ.get("TURBOTIDES_JAVA_HOME") or os.environ.get(
            "JAVA_HOME"
        )
        java = str(Path(java_home) / "bin/java") if java_home else "java"
        env = dict(
            os.environ, TERM="xterm-256color", COLORTERM="truecolor", LANG="C.UTF-8"
        )
        self.child = pexpect.spawn(
            java,
            [
                "--enable-native-access=ALL-UNNAMED",
                "-jar",
                str(ROOT / "build/libs/turbotides-tui.jar"),
                "--telemetry",
                str(self.telemetry),
                "--data-dir",
                str(data_dir),
            ],
            cwd=str(ROOT),
            env=env,
            encoding="utf-8",
            codec_errors="replace",
            dimensions=(rows, columns),
            timeout=1,
        )
        self.child.delaybeforesend = 0
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            self.pump(0.08)
            if self.telemetry.exists() and "turbo tides" in self.text().lower():
                self.pump(0.2)
                return
            if not self.child.isalive():
                raise AssertionError(f"Game exited during startup: {self.raw[-3000:]}")
        raise AssertionError(f"Game did not become ready: {self.raw[-3000:]}")

    def pump(self, duration: float) -> None:
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            try:
                data = self.child.read_nonblocking(
                    131072, timeout=min(0.025, max(0.001, deadline - time.monotonic()))
                )
                self.raw = (self.raw + data)[-16000:]
                self.raw_log.write(data)
                self.stream.feed(data)
                if "\x1b[6n" in data:
                    self.child.send("\x1b[1;1R")
            except pexpect.TIMEOUT:
                continue
            except pexpect.EOF:
                return

    def key(self, name: str, wait: float = 0.22) -> None:
        self.child.send(BINDINGS[name])
        self.pump(wait)

    def repeat(self, name: str, duration: float, period: float = 0.04) -> int:
        deadline = time.monotonic() + duration
        count = 0
        while time.monotonic() < deadline:
            self.key(name, period)
            count += 1
        return count

    def resize(self, columns: int, rows: int) -> None:
        self.screen.resize(lines=rows, columns=columns)
        self.child.setwinsize(rows, columns)
        self.pump(0.3)
        self.wait_state(
            lambda state: state["width"] == columns and state["height"] == rows,
            "terminal resize acknowledgement",
        )
        if columns >= 64 and rows >= 24:
            deadline = time.monotonic() + 4
            while (
                not self.screen.display[min(rows, 65) - 2].strip()
                and time.monotonic() < deadline
            ):
                self.pump(0.05)
            require(
                bool(self.screen.display[min(rows, 65) - 2].strip()),
                "Resize did not render the bottom status line",
            )

    def state(self) -> dict:
        deadline = time.monotonic() + 1
        while True:
            try:
                return json.loads(self.telemetry.read_text())
            except (FileNotFoundError, json.JSONDecodeError):
                if time.monotonic() > deadline:
                    raise
                self.pump(0.02)

    def wait_state(self, predicate, description: str, timeout: float = 3.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.state()
            if predicate(state):
                self.pump(0.08)
                return state
            self.pump(0.03)
        raise AssertionError(f"Timed out waiting for {description}: {self.state()}")

    def text(self) -> str:
        return "\n".join(self.screen.display)

    def rendered_cells(self) -> tuple:
        return tuple(
            (
                self.screen.buffer[y][x].data,
                self.screen.buffer[y][x].fg,
                self.screen.buffer[y][x].bg,
            )
            for y in range(self.screen.lines)
            for x in range(self.screen.columns)
        )

    def save(self, label: str) -> dict:
        state = self.state()
        (self.directory / f"{label}.json").write_text(
            json.dumps(state, indent=2) + "\n"
        )
        self.save_frame(label)
        return state

    def save_frame(self, label: str) -> None:
        """Capture presentation even when the diagnostic destination is unavailable."""
        (self.directory / f"{label}.txt").write_text(self.text() + "\n")
        image = Image.new(
            "RGB", (self.screen.columns * 8, self.screen.lines * 16), "black"
        )
        draw = ImageDraw.Draw(image)
        font_path = next(
            path
            for path in (
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
                Path("/System/Library/Fonts/Menlo.ttc"),
            )
            if path.exists()
        )
        font = ImageFont.truetype(str(font_path), 12)
        for y in range(self.screen.lines):
            for x in range(self.screen.columns):
                cell = self.screen.buffer[y][x]
                fg, bg = rgb(cell.fg, (230, 230, 230)), rgb(cell.bg, (0, 0, 0))
                if cell.reverse:
                    fg, bg = bg, fg
                draw.rectangle((x * 8, y * 16, x * 8 + 7, y * 16 + 15), fill=bg)
                if cell.data == "▀":
                    draw.rectangle((x * 8, y * 16, x * 8 + 7, y * 16 + 7), fill=fg)
                elif cell.data == "▄":
                    draw.rectangle((x * 8, y * 16 + 8, x * 8 + 7, y * 16 + 15), fill=fg)
                elif cell.data == "█":
                    draw.rectangle((x * 8, y * 16, x * 8 + 7, y * 16 + 15), fill=fg)
                elif cell.data.strip():
                    draw.text((x * 8, y * 16), cell.data, font=font, fill=fg)
        name = f"{label}.png"
        image.save(self.directory / name)
        self.frames.append(str((self.directory / name).relative_to(ROOT)))

    def close(self) -> None:
        if self.child.isalive():
            self.child.send("q")
            deadline = time.monotonic() + 3
            while self.child.isalive() and time.monotonic() < deadline:
                self.pump(0.05)
        if self.child.isalive():
            self.child.terminate(force=True)
        self.child.close()
        self.raw_log.close()


def check(terminal: Terminal, state: str, binding: str, expectation: str, exercise):
    slug = re.sub(
        r"[^a-z0-9]+", "-", f"{len(RESULTS):03d}-{state}-{binding}".lower()
    ).strip("-")
    row = {
        "state": state,
        "binding": binding,
        "expected": expectation,
        "status": "FAILED",
        "evidence": [],
    }
    start = len(terminal.frames)
    try:
        terminal.save(f"{slug}-before")
        exercise(terminal)
        terminal.save(f"{slug}-after")
        row["status"] = "PASSED"
    except Exception as error:
        row["error"] = str(error)
        terminal.save(f"{slug}-failed")
        raise
    finally:
        row["evidence"] = terminal.frames[start:]
        RESULTS.append(row)
        OUTPUT.mkdir(parents=True, exist_ok=True)
        (OUTPUT / "results.json").write_text(json.dumps(RESULTS, indent=2) + "\n")
        print(f"{row['status']}: {state} {binding}: {expectation}", flush=True)


def tap(terminal: Terminal, key: str, field: str, expected) -> None:
    before = terminal.rendered_cells()
    old_value = terminal.state()[field]
    terminal.key(key, 0.3)
    terminal.wait_state(lambda state: state[field] == expected, f"{field}={expected}")
    require(
        terminal.state()[field] == expected,
        f"{key}: expected {field}={expected}, observed {terminal.state()[field]}",
    )
    if old_value != expected:
        require(
            terminal.rendered_cells() != before,
            f"{key} changed diagnostics without changing rendered screen",
        )


def focus(terminal: Terminal, value: int) -> None:
    while terminal.state()["menuFocus"] != value:
        expected = (terminal.state()["menuFocus"] + 1) % 4
        terminal.key("Tab", 0.3)
        terminal.wait_state(
            lambda state, e=expected: state["menuFocus"] == e, f"focus {expected}"
        )


def stable(terminal: Terminal, key: str, fields: tuple[str, ...]) -> None:
    before = terminal.state()
    rendered = terminal.rendered_cells()
    terminal.key(key, 0.3)
    after = terminal.state()
    require(
        all(before[f] == after[f] for f in fields),
        f"Disabled {key} changed {[(f, before[f], after[f]) for f in fields if before[f] != after[f]]}",
    )
    if before["phase"] in ["GARAGE", "PAUSED", "FINISHED"] or before["help"]:
        require(
            terminal.rendered_cells() == rendered,
            f"Disabled {key} changed actual frozen rendered frame",
        )


def start(terminal: Terminal) -> None:
    if terminal.state()["phase"] == "GARAGE":
        focus(terminal, 3)
        terminal.key("Enter", 0.3)
    else:
        terminal.key("R", 0.3)
    terminal.wait_state(
        lambda state: state["phase"] == "COUNTDOWN", "countdown after start"
    )
    require(terminal.state()["phase"] == "COUNTDOWN", "Start must begin countdown")


def racing(terminal: Terminal) -> None:
    start(terminal)
    deadline = time.monotonic() + 6
    while terminal.state()["phase"] == "COUNTDOWN" and time.monotonic() < deadline:
        terminal.pump(0.1)
    require(terminal.state()["phase"] == "RACING", "Countdown never reached GO")


def garage_audit(terminal: Terminal) -> None:
    for key, delta in [
        ("Up", -1),
        ("W", -1),
        ("Down", 1),
        ("S", 1),
        ("Tab", 1),
        ("Shift+Tab", -1),
    ]:
        before = terminal.state()["menuFocus"]
        check(
            terminal,
            "garage",
            key,
            "Move visible menu focus, with wraparound",
            lambda t, k=key, expected=(before + delta) % 4: tap(
                t, k, "menuFocus", expected
            ),
        )
    for menu, field, values in [
        (
            0,
            "circuit",
            [
                "SUNSET",
                "CINDER",
                "SAN_FRANCISCO",
                "SILICON_VALLEY",
                "NEW_YORK",
                "CHICAGO",
            ],
        ),
        (1, "paint", list(range(5))),
        (2, "difficulty", DIFFICULTIES),
        (
            3,
            "circuit",
            [
                "SUNSET",
                "CINDER",
                "SAN_FRANCISCO",
                "SILICON_VALLEY",
                "NEW_YORK",
                "CHICAGO",
            ],
        ),
    ]:
        focus(terminal, menu)
        for key, delta in [("Left", -1), ("A", -1), ("Right", 1), ("D", 1)]:
            before = terminal.state()[field]
            expected = values[(values.index(before) + delta) % len(values)]
            check(
                terminal,
                f"garage-{menu}",
                key,
                f"Change visible {field}",
                lambda t, k=key, f=field, e=expected: tap(t, k, f, e),
            )
        if menu < 3:
            before = terminal.state()[field]
            expected = values[(values.index(before) + 1) % len(values)]
            check(
                terminal,
                f"garage-{menu}",
                "Enter",
                f"Activate focused {field}",
                lambda t, f=field, e=expected: tap(t, "Enter", f, e),
            )
    for key, field in [("P", "overview"), ("M", "muted"), ("N", "reducedMotion")]:
        before = terminal.state()[field]
        check(
            terminal,
            "garage",
            key,
            f"Toggle visible {field}",
            lambda t, k=key, f=field, e=not before: tap(t, k, f, e),
        )
        terminal.key(key, 0.3)
    for key in ["Space", "B", "C", "G", "R", "Esc"]:
        check(
            terminal,
            "garage-disabled",
            key,
            "Do not drive, restart or change menu settings",
            lambda t, k=key: stable(
                t,
                k,
                (
                    "phase",
                    "circuit",
                    "paint",
                    "difficulty",
                    "distance",
                    "throttle",
                    "drift",
                    "boost",
                    "rearView",
                ),
            ),
        )
    for key, delta in [
        ("Up", -1),
        ("W", -1),
        ("Down", 1),
        ("S", 1),
        ("Tab", 1),
        ("Shift+Tab", -1),
    ]:

        def nav_repeat(t, k=key, d=delta):
            before = t.state()["menuFocus"]
            count = t.repeat(k, 0.3, 0.07)
            t.wait_state(
                lambda state: state["menuFocus"] == (before + count * d) % 4,
                "repeated focus navigation",
            )
            require("▶" in t.text(), "Repeated navigation lost visible focus")

        check(
            terminal,
            "garage-repeat",
            key,
            "Repeated presses move focus once per event; release stops",
            nav_repeat,
        )
    focus(terminal, 0)
    for key, delta in [("Left", -1), ("A", -1), ("Right", 1), ("D", 1)]:

        def circuit_repeat(t, k=key, d=delta):
            before = CIRCUITS.index(t.state()["circuit"])
            count = t.repeat(k, 0.3, 0.07)
            t.wait_state(
                lambda state: state["circuit"] == CIRCUITS[(before + count * d) % 6],
                "repeated route navigation",
            )

        check(
            terminal,
            "garage-repeat",
            key,
            "Repeated presses cycle circuits once per event",
            circuit_repeat,
        )
    for key, field in [("P", "overview"), ("M", "muted"), ("N", "reducedMotion")]:
        check(
            terminal,
            "garage-repeat",
            key,
            "Fast repeated toggles debounce; separated tap returns",
            lambda t, k=key, f=field: repeat_check(t, k, f),
        )
    # Visit every route and every paint through the actual selector, retaining frames.
    focus(terminal, 0)
    for index in range(6):
        terminal.key("Right", 0.3)
        terminal.save(f"route-{index}-{terminal.state()['circuit']}")
    focus(terminal, 1)
    if terminal.state()["overview"]:
        terminal.key("P", 0.3)
    for index in range(5):
        terminal.key("Right", 0.3)
        terminal.save(f"paint-{index}-{terminal.state()['paint']}")
    # Return to a known visual paint without writing settings or simulation state.
    while terminal.state()["paint"] != 0:
        terminal.key("Right", 0.3)
    focus(terminal, 0)
    while terminal.state()["circuit"] != "SUNSET":
        terminal.key("Right", 0.3)
    focus(terminal, 3)
    check(
        terminal,
        "garage",
        "?",
        "Open readable help while staying in garage",
        lambda t: tap(t, "?", "help", True),
    )
    check(
        terminal,
        "garage-help",
        "Enter",
        "Close help without starting race",
        lambda t: tap(t, "Enter", "help", False),
    )
    check(terminal, "garage-start", "Enter", "Start a fresh countdown", start)


def countdown_audit(terminal: Terminal) -> None:
    drive = ["W", "Up", "S", "Down", "A", "Left", "D", "Right", "Space", "B", "C"]
    for key in drive:
        start(terminal)
        check(
            terminal,
            "countdown",
            key,
            "Cars stay stationary before GO",
            lambda t, k=key: stable(t, k, ("distance", "speed", "lane", "time")),
        )
    for key in ["P", "G", "Tab", "Shift+Tab", "Enter"]:
        start(terminal)
        check(
            terminal,
            "countdown-disabled",
            key,
            "No menu navigation or premature race start",
            lambda t, k=key: stable(
                t, k, ("phase", "menuFocus", "circuit", "distance")
            ),
        )
    for key, field, on, off in [
        ("M", "muted", "Muted", "Sound"),
        ("N", "reducedMotion", "Motion reduced", "Motion full"),
    ]:
        start(terminal)
        check(
            terminal,
            "countdown",
            key,
            "Preference toggles visibly during countdown",
            lambda t, k=key, f=field, a=on, b=off: visible_toggle(t, k, f, a, b),
        )
    start(terminal)
    terminal.pump(0.5)
    check(
        terminal,
        "countdown",
        "R",
        "Restart restores countdown and clears all driving modes",
        restart_check,
    )
    check(
        terminal,
        "countdown",
        "Esc",
        "Pause freezes countdown and clears controls",
        pause_check,
    )
    check(
        terminal,
        "paused-countdown",
        "Esc",
        "Resume the same countdown",
        lambda t: tap(t, "Esc", "phase", "COUNTDOWN"),
    )
    start(terminal)
    terminal.key("Esc", 0.3)
    terminal.wait_state(
        lambda state: state["phase"] == "PAUSED", "fresh paused countdown"
    )
    check(
        terminal,
        "paused-countdown",
        "Enter",
        "Resume countdown with alternate binding",
        lambda t: tap(t, "Enter", "phase", "COUNTDOWN"),
    )


def restart_check(terminal: Terminal) -> None:
    terminal.key("R", 0.3)
    state = terminal.state()
    require(
        state["phase"] == "COUNTDOWN" and state["countdown"] > 2.5,
        "Restart did not restore countdown",
    )
    require(
        state["distance"] == 0 and state["time"] == 0 and state["speed"] == 0,
        "Restart retained race progress",
    )
    require(
        not any(state[k] for k in ["throttle", "brake", "drift", "boost", "rearView"]),
        "Restart retained driving input",
    )
    require(
        state["pads"] == state["bumps"] == state["driftBonuses"] == 0,
        "Restart retained rewards or contacts",
    )


def pause_check(terminal: Terminal) -> None:
    terminal.key("Esc", 0.3)
    before = terminal.state()
    require(before["phase"] == "PAUSED", "Esc did not pause")
    terminal.pump(0.4)
    after = terminal.state()
    require(
        all(before[f] == after[f] for f in ["countdown", "time", "distance", "speed"]),
        "Paused race still advanced",
    )
    require(
        not any(after[k] for k in ["throttle", "brake", "drift", "boost", "rearView"]),
        "Pause retained driving input",
    )


def help_audit(terminal: Terminal) -> None:
    for close in ["?", "Esc", "Enter"]:
        origin = terminal.state()["phase"].lower()
        check(
            terminal,
            f"help-open-{origin}",
            "?",
            "Show controls and stop race",
            lambda t: tap(t, "?", "help", True),
        )
        for key, field, on, off in [
            ("M", "muted", "Muted", "Sound"),
            ("N", "reducedMotion", "Motion reduced", "Motion full"),
        ]:
            check(
                terminal,
                f"help-global-{close}",
                key,
                "Preferences toggle with help open",
                lambda t, k=key, f=field, a=on, b=off: visible_toggle(t, k, f, a, b),
            )
        for key in [
            "W",
            "Up",
            "S",
            "Down",
            "A",
            "Left",
            "D",
            "Right",
            "Space",
            "B",
            "C",
            "P",
            "R",
            "G",
            "Tab",
            "Shift+Tab",
        ]:
            check(
                terminal,
                f"help-close-{close}-disabled",
                key,
                "Help consumes gameplay/menu commands",
                lambda t, k=key: stable(
                    t,
                    k,
                    (
                        "phase",
                        "time",
                        "distance",
                        "throttle",
                        "drift",
                        "boost",
                        "rearView",
                        "menuFocus",
                        "help",
                    ),
                ),
            )
        check(
            terminal,
            "help-close",
            close,
            "Close help; race remains safely paused",
            lambda t, k=close: tap(t, k, "help", False),
        )


def player_screen_x(terminal: Terminal) -> int:
    """Find the actual painted sprite with its cream centre pixel, independently of lane."""
    colors = ["ff653b", "32b7ae", "f8ca55", "ebf0e8", "7888d4"]
    paint = colors[terminal.state()["paint"]]
    art_height = (min(terminal.screen.lines, 65) - 9) * 2
    pixel_y = 4 + art_height - 5

    def pixel(x):
        cell = terminal.screen.buffer[pixel_y // 2][x]
        return cell.fg if pixel_y % 2 == 0 else cell.bg

    candidates = [
        x
        for x in range(3, terminal.screen.columns - 3)
        if pixel(x) == "ffedce" and all(pixel(x + d) == paint for d in [-2, -1, 1, 2])
    ]
    require(
        len(candidates) == 1,
        f"Could not locate unique visible player sprite: {candidates}",
    )
    return candidates[0]


def moving(terminal: Terminal, rear: bool = False) -> None:
    racing(terminal)
    terminal.key("W", 1.3)
    if rear:
        terminal.key("C", 0.3)
    require(terminal.state()["speed"] > 22, "Need actual speed before steering")


def steering_check(terminal: Terminal, binding: str, direction: int) -> None:
    before = player_screen_x(terminal)
    terminal.repeat(binding, 0.48)
    after = player_screen_x(terminal)
    # Keep the same visible displacement requirement under host scheduling load.
    # Continue real key repeats while observing the sprite, never simulation time.
    deadline = time.monotonic() + 0.8
    while (after - before) * direction <= 2 and time.monotonic() < deadline:
        terminal.key(binding, 0.04)
        after = player_screen_x(terminal)
    require(
        (after - before) * direction > 2,
        f"{binding}: visible x {before} → {after}; expected screen {'left' if direction < 0 else 'right'}",
    )
    terminal.pump(0.35)
    require(
        terminal.state()["steer"] == 0,
        "Steering pulse did not expire after input stopped",
    )


def accelerating(terminal: Terminal, binding: str) -> None:
    before = terminal.state()
    visible_before = int(re.search(r"(\d+) km/h", terminal.text())[1])
    terminal.key(binding, 1.2)
    after = terminal.state()
    require(
        after["speed"] > before["speed"] + 15
        and after["distance"] > before["distance"],
        "Throttle did not accelerate and advance",
    )
    visible_after = int(re.search(r"(\d+) km/h", terminal.text())[1])
    require(visible_after > visible_before + 40, "Speedometer did not visibly rise")
    require(
        "THROTTLE" in terminal.text() and "km/h" in terminal.text(),
        "No visible throttle/speed feedback",
    )
    terminal.pump(0.35)
    require(terminal.state()["throttle"], "Throttle latch should remain on after tap")


def braking(terminal: Terminal, binding: str) -> None:
    before = terminal.state()
    visible_before = int(re.search(r"(\d+) km/h", terminal.text())[1])
    terminal.key(binding, 0.6)
    after = terminal.state()
    require(
        after["speed"] < before["speed"] - 10
        and after["brake"]
        and not after["throttle"],
        "Brake did not slow the car and cancel throttle",
    )
    visible_after = int(re.search(r"(\d+) km/h", terminal.text())[1])
    require(visible_after < visible_before - 25, "Speedometer did not visibly fall")
    require(
        not after["boost"] and "BRAKE" in terminal.text(),
        "Brake must cancel nitro and show feedback",
    )
    terminal.pump(0.8)
    require(terminal.state()["speed"] == 0, "Brake must stop without reverse")


def visible_toggle(
    terminal: Terminal, binding: str, field: str, text_on: str, text_off: str
) -> None:
    before = terminal.state()[field]
    terminal.key(binding, 0.3)
    require(terminal.state()[field] != before, f"{binding} did not toggle {field}")
    require(
        (text_off if before else text_on) in terminal.text(),
        f"{binding}: missing visible mode",
    )
    terminal.save(f"{len(RESULTS):03d}-{binding.lower()}-{field}-during")
    terminal.key(binding, 0.3)
    require(terminal.state()[field] == before, f"{binding} did not release mode")


def drift_check(terminal: Terminal) -> None:
    terminal.key("Space", 0.3)
    before = terminal.state()["driftBonuses"]
    require("Drift ON" in terminal.text(), "Drift mode invisible")
    # Repeat actual steering bytes; no simulation mutation or accelerated time.
    terminal.repeat("D", 0.56)
    during = terminal.save("drift-charging")
    require(
        during["drifting"] and during["driftCharge"] >= 0.45,
        "Drift failed to charge while steering",
    )
    terminal.key("Space", 0.3)
    require(
        not terminal.state()["drift"] and terminal.state()["driftBonuses"] > before,
        "Ending drift did not bank nitro",
    )
    require("Drift bonus" in terminal.text(), "Drift reward not rendered")


def boost_check(terminal: Terminal) -> None:
    before = terminal.state()
    terminal.key("B", 0.5)
    after = terminal.state()
    require(
        after["boosting"]
        and after["nitro"] < before["nitro"]
        and after["speed"] > before["speed"],
        "Nitro mode did not consume meter and accelerate",
    )
    require("Nitro ON" in terminal.text(), "Nitro mode not rendered")
    terminal.key("B", 0.3)
    require(
        not terminal.state()["boosting"] and not terminal.state()["boost"],
        "B did not stop boost",
    )


def race_audit(terminal: Terminal) -> None:
    for key in ["W", "Up"]:
        racing(terminal)
        check(
            terminal,
            "racing",
            key,
            "Throttle visibly accelerates and remains on after tap",
            lambda t, k=key: accelerating(t, k),
        )
    for key in ["S", "Down"]:
        moving(terminal)
        terminal.key("B", 0.3)
        check(
            terminal,
            "racing",
            key,
            "Brake visibly slows to stop, cancels throttle/nitro, never reverses",
            lambda t, k=key: braking(t, k),
        )
    for rear in [False, True]:
        for key, direction in [("A", -1), ("Left", -1), ("D", 1), ("Right", 1)]:
            moving(terminal, rear)
            check(
                terminal,
                "racing-rear" if rear else "racing-forward",
                key,
                "Visible player moves "
                + (
                    "screen-left"
                    if direction * (-1 if rear else 1) < 0
                    else "screen-right"
                )
                + "; pulse expires",
                lambda t, k=key, d=direction * (-1 if rear else 1): steering_check(
                    t, k, d
                ),
            )
    moving(terminal)
    check(
        terminal,
        "racing",
        "Space",
        "Drift charges with repeated steering and banks on explicit toggle off",
        drift_check,
    )
    moving(terminal)
    check(
        terminal,
        "racing",
        "B",
        "Nitro visibly accelerates, consumes meter, and toggles off",
        boost_check,
    )
    check(
        terminal,
        "racing",
        "C",
        "Rear view is labelled, mirrored and returns to forward view",
        lambda t: visible_toggle(t, "C", "rearView", "REAR VIEW", "Forward view"),
    )
    for key, field, on, off in [
        ("M", "muted", "Muted", "Sound"),
        ("N", "reducedMotion", "Motion reduced", "Motion full"),
    ]:
        check(
            terminal,
            "racing",
            key,
            "Toggle visible mode; physical audio checked separately",
            lambda t, k=key, f=field, a=on, b=off: visible_toggle(t, k, f, a, b),
        )
    for key in ["P", "G", "Tab", "Shift+Tab", "Enter"]:
        check(
            terminal,
            "racing-disabled",
            key,
            "No menu navigation or unintended command",
            lambda t, k=key: stable(
                t,
                k,
                ("phase", "menuFocus", "circuit", "paint", "difficulty", "overview"),
            ),
        )
    check(
        terminal,
        "racing",
        "Esc",
        "Pause freezes simulation and clears input",
        pause_check,
    )
    paused_audit(terminal)
    moving(terminal)
    check(terminal, "racing", "R", "Restart clears progress and modes", restart_check)
    racing(terminal)
    check(
        terminal,
        "racing-stopped",
        "A",
        "Steering cannot move a stopped car",
        lambda t: stable(t, "A", ("lane", "distance", "speed")),
    )
    check(
        terminal,
        "racing-stopped",
        "D",
        "Opposite steering also cannot move a stopped car",
        lambda t: stable(t, "D", ("lane", "distance", "speed")),
    )
    check(
        terminal,
        "racing-stopped",
        "Space",
        "Drift mode without speed cannot earn rewards",
        lambda t: stable(t, "Space", ("driftBonuses", "driftCharge", "speed")),
    )
    check(
        terminal,
        "racing-stopped",
        "B",
        "Boost without throttle cannot move or consume nitro",
        lambda t: stable(t, "B", ("speed", "distance", "boosting")),
    )
    moving(terminal)
    check(
        terminal,
        "racing",
        "A then D",
        "Opposing pulses use newest direction; recover without stuck steering",
        opposing_check,
    )
    for key, field in [
        ("Space", "drift"),
        ("B", "boost"),
        ("C", "rearView"),
        ("N", "reducedMotion"),
        ("M", "muted"),
    ]:
        check(
            terminal,
            "racing-repeat",
            key,
            "Fast repeat train produces one toggle; spaced taps toggle again",
            lambda t, k=key, f=field: repeat_check(t, k, f),
        )
    terminal.pump(0.3)
    check(
        terminal,
        "racing-repeat",
        "Esc",
        "Isolated Esc pauses; measured native repeat sequence retains pause; spaced release tap resumes",
        escape_repeat,
    )
    check(
        terminal,
        "racing-repeat",
        "R",
        "Fast R repeats restart once with cleared controls",
        restart_repeat,
    )
    check(
        terminal,
        "countdown-repeat",
        "?",
        "Fast help repeats open once, separated tap closes",
        lambda t: repeat_check(t, "?", "help"),
    )
    check(
        terminal,
        "racing-motion",
        "N",
        "Reduced motion visibly centres windshield lean while paused; toggle restores",
        motion_check,
    )
    edge_audit(terminal)


def opposing_check(terminal: Terminal) -> None:
    terminal.repeat("A", 0.4)
    terminal.pump(0.12)
    terminal.save("opposed-left")
    before = player_screen_x(terminal)
    terminal.repeat("D", 0.7)
    terminal.pump(0.12)
    terminal.save("opposed-right")
    require(
        player_screen_x(terminal) > before + 2,
        "Newest opposite direction did not move right",
    )
    terminal.pump(0.3)
    require(terminal.state()["steer"] == 0, "Opposing input stuck")


def repeat_check(terminal: Terminal, key: str, field: str) -> None:
    terminal.pump(0.3)
    before = terminal.state()[field]
    terminal.repeat(key, 0.5)
    require(terminal.state()[field] != before, "Rapid repeats should not flicker mode")
    terminal.pump(0.3)
    terminal.key(key, 0.3)
    require(terminal.state()[field] == before, "Spaced tap should end mode")


def motion_check(terminal: Terminal) -> None:
    moving(terminal)
    terminal.repeat("D", 0.4)
    terminal.key("Esc", 0.3)
    x = player_screen_x(terminal)
    art_height = (min(terminal.screen.lines, 65) - 9) * 2

    def region():
        result = []
        for py in range(4 + art_height - 9, 4 + art_height - 1):
            for px in range(max(0, x - 10), min(terminal.screen.columns, x + 11)):
                cell = terminal.screen.buffer[py // 2][px]
                result.append(cell.fg if py % 2 == 0 else cell.bg)
        return tuple(result)

    before = region()
    frozen_time = terminal.state()["time"]
    terminal.save("motion-lean")
    terminal.key("N", 0.3)
    terminal.save("motion-reduced")
    require(
        region() != before,
        "N changed flag without changing the rendered windshield lean",
    )
    require(
        terminal.state()["time"] == frozen_time,
        "Motion test must isolate frozen rendered frames",
    )
    terminal.key("N", 0.3)
    require(
        region() == before,
        "Turning motion back on did not restore frozen rendered lean",
    )


def escape_repeat(t: Terminal) -> None:
    # A physical hold begins with an isolated press and OS initial repeat delay.
    # An initial ESC ESC burst is Alt+Esc in tui4j, not two Escape key events.
    t.key("Esc", 0.5)
    require(
        t.state()["phase"] == "PAUSED", "Initial isolated Escape did not visibly pause"
    )
    t.save("escape-initial-pause")
    for _ in range(10):
        t.key("Esc", 0.04)
    t.pump(0.15)
    require(
        t.state()["phase"] == "PAUSED",
        "The observed even repeat sequence should decode to Alt+Esc and retain pause",
    )
    require(not t.state()["throttle"], "Escape hold retained accelerator")
    t.save("escape-native-repeat")
    t.pump(0.3)
    t.key("Esc", 0.3)
    t.wait_state(
        lambda state: state["phase"] == "RACING", "spaced Escape resume after release"
    )


def restart_repeat(t: Terminal) -> None:
    t.repeat("R", 0.6)
    require(
        t.state()["phase"] == "COUNTDOWN" and 2.4 < t.state()["countdown"] < 3.2,
        "R repeat restarted more than once or did not restart",
    )
    require(
        t.state()["distance"] == 0 and not t.state()["throttle"],
        "Repeat restart retained progress/input",
    )


def paused_audit(terminal: Terminal) -> None:
    for key in [
        "W",
        "Up",
        "S",
        "Down",
        "A",
        "Left",
        "D",
        "Right",
        "Space",
        "B",
        "C",
        "P",
        "Tab",
        "Shift+Tab",
    ]:
        check(
            terminal,
            "paused-disabled",
            key,
            "Simulation frozen and driving input ignored",
            lambda t, k=key: stable(
                t,
                k,
                (
                    "phase",
                    "time",
                    "distance",
                    "lane",
                    "speed",
                    "throttle",
                    "brake",
                    "drift",
                    "boost",
                    "rearView",
                    "menuFocus",
                ),
            ),
        )
    for key, field, on, off in [
        ("M", "muted", "Muted", "Sound"),
        ("N", "reducedMotion", "Motion reduced", "Motion full"),
    ]:
        check(
            terminal,
            "paused",
            key,
            "Visible preference remains available",
            lambda t, k=key, f=field, a=on, b=off: visible_toggle(t, k, f, a, b),
        )
    check(
        terminal,
        "paused-racing",
        "Enter",
        "Resume safely with cleared driving modes",
        lambda t: tap(t, "Enter", "phase", "RACING"),
    )
    terminal.key("Esc", 0.3)
    check(
        terminal,
        "paused-racing",
        "Esc",
        "Resume via alternate binding",
        lambda t: tap(t, "Esc", "phase", "RACING"),
    )
    terminal.key("Esc", 0.3)
    check(terminal, "paused", "R", "Restart race from pause", restart_check)
    terminal.key("Esc", 0.3)
    check(
        terminal,
        "paused",
        "G",
        "Return to garage",
        lambda t: tap(t, "G", "phase", "GARAGE"),
    )


def edge_audit(terminal: Terminal) -> None:
    moving(terminal)
    for key in ["Space", "B", "C"]:
        terminal.key(key, 0.3)
    terminal.key("A", 0.02)

    def focus_loss(t):
        t.key("FocusOut", 0.3)
        require(
            not t.state()["focus"] and t.state()["phase"] == "PAUSED",
            "Focus loss did not pause",
        )
        before = t.state()
        for key in [
            "W",
            "Up",
            "S",
            "Down",
            "A",
            "Left",
            "D",
            "Right",
            "Space",
            "B",
            "C",
            "R",
            "P",
            "G",
            "Esc",
            "Enter",
            "Tab",
            "Shift+Tab",
            "M",
            "N",
            "?",
        ]:
            check(
                t,
                "blurred-disabled",
                key,
                "Unfocused physical binding leaves modes and rendered frame unchanged",
                lambda game, k=key: stable(
                    game,
                    k,
                    (
                        "phase",
                        "time",
                        "distance",
                        "throttle",
                        "brake",
                        "drift",
                        "boost",
                        "rearView",
                        "muted",
                        "reducedMotion",
                        "help",
                        "menuFocus",
                    ),
                ),
            )
        require(
            t.state()["distance"] == before["distance"] and not t.state()["throttle"],
            "Unfocused input activated",
        )
        t.key("FocusIn", 0.3)
        require(
            t.state()["focus"] and t.state()["phase"] == "PAUSED",
            "Focus regain should stay paused",
        )
        require(
            not any(
                t.state()[f]
                for f in ["throttle", "brake", "drift", "boost", "rearView", "steer"]
            ),
            "Stuck input after focus regain",
        )
        t.key("Enter", 0.3)
        t.key("W", 0.5)
        require(t.state()["speed"] > 0, "Could not recover from focus loss")

    check(
        terminal,
        "racing-focus",
        "FocusOut / FocusIn",
        "Pause and clear all modes, ignore blurred driving, recover after resume",
        focus_loss,
    )

    def resize_check(t):
        t.resize(50, 18)
        require(
            t.state()["phase"] == "PAUSED" and "Resize to at least" in t.text(),
            "Small terminal did not safely pause",
        )
        for k in [
            "W",
            "Up",
            "S",
            "Down",
            "A",
            "Left",
            "D",
            "Right",
            "Space",
            "B",
            "C",
            "R",
            "P",
            "G",
            "Esc",
            "Enter",
            "Tab",
            "Shift+Tab",
            "M",
            "N",
            "?",
        ]:
            check(
                t,
                "undersized-disabled",
                k,
                "Small screen ignores commands and remains paused",
                lambda game, key=k: stable(
                    game,
                    key,
                    (
                        "phase",
                        "time",
                        "distance",
                        "throttle",
                        "drift",
                        "boost",
                        "rearView",
                        "muted",
                        "reducedMotion",
                        "help",
                    ),
                ),
            )
        t.save("undersized")
        t.resize(64, 24)
        t.save("minimum-paused")
        t.key("Enter", 0.3)
        t.key("W", 0.4)
        require(t.state()["phase"] == "RACING", "Minimum size cannot resume")
        t.save("minimum-racing")
        t.resize(180, 65)
        t.save("large-racing")
        t.resize(120, 40)

    check(
        terminal,
        "racing-size",
        "Resize",
        "Small screens pause; minimum and large sizes recover and render",
        resize_check,
    )
    # Drive onto grass, into barrier, and recover with genuine terminal input.
    moving(terminal)

    def barrier(t):
        start_bumps = t.state()["bumps"]
        t.repeat("A", 2.4)
        t.save("barrier-contact")
        require(
            t.state()["lane"] <= -9 and t.state()["bumps"] > start_bumps,
            "No visible barrier contact",
        )
        require(t.state()["speed"] < 32, "Grass/barrier did not reduce speed")
        t.repeat("D", 1.3)
        require(t.state()["lane"] > -8, "Cannot steer back onto road")
        t.key("W", 0.5)
        require(t.state()["distance"] > 0, "No recovery progress")

    check(
        terminal,
        "racing-physics",
        "A held then D held",
        "Grass slows, barrier contains, opposite steering recovers",
        barrier,
    )


def finish_audit(terminal: Terminal) -> None:
    for key in [
        "W",
        "Up",
        "S",
        "Down",
        "A",
        "Left",
        "D",
        "Right",
        "Space",
        "B",
        "C",
        "P",
        "Tab",
        "Shift+Tab",
    ]:
        check(
            terminal,
            "finished-disabled",
            key,
            "Results freeze progress and consume driving commands",
            lambda t, k=key: stable(
                t,
                k,
                (
                    "phase",
                    "time",
                    "distance",
                    "speed",
                    "throttle",
                    "brake",
                    "drift",
                    "boost",
                    "rearView",
                    "menuFocus",
                ),
            ),
        )
    for key, field, on, off in [
        ("M", "muted", "Muted", "Sound"),
        ("N", "reducedMotion", "Motion reduced", "Motion full"),
    ]:
        check(
            terminal,
            "finished",
            key,
            "Preference remains available at results",
            lambda t, k=key, f=field, a=on, b=off: visible_toggle(t, k, f, a, b),
        )
    check(
        terminal,
        "finished",
        "?",
        "Help opens without changing result",
        lambda t: tap(t, "?", "help", True),
    )
    terminal.key("?", 0.3)


CIRCUITS = [
    "SUNSET",
    "CINDER",
    "SAN_FRANCISCO",
    "SILICON_VALLEY",
    "NEW_YORK",
    "CHICAGO",
]


def race_playthrough(
    circuit: str,
    difficulty: str = "EASY",
    result_key: str = "Enter",
    slow: bool = False,
) -> dict:
    terminal = Terminal(f"race-{circuit.lower()}-{difficulty.lower()}", 100, 34)
    try:
        focus(terminal, 0)
        while terminal.state()["circuit"] != circuit:
            before = terminal.state()["circuit"]
            terminal.key("Right", 0.3)
            terminal.wait_state(
                lambda state, old=before: state["circuit"] != old, "circuit change"
            )
        if terminal.state()["difficulty"] != difficulty:
            focus(terminal, 2)
            while terminal.state()["difficulty"] != difficulty:
                terminal.key("Right", 0.3)
        require(
            terminal.state()["circuit"] == circuit,
            "Selector did not choose requested circuit",
        )
        terminal.save("garage")
        start(terminal)
        terminal.key("W", 0.3)
        terminal.save("countdown")
        deadline = time.monotonic() + 150
        last_lap = 0
        if slow:
            terminal.pump(15)
        while terminal.state()["phase"] != "FINISHED" and time.monotonic() < deadline:
            state = terminal.state()
            if state["phase"] == "COUNTDOWN":
                terminal.pump(0.05)
                continue
            # Aim for actual original pad lanes; read-only telemetry only supplies observation.
            progress = state["distance"] % state["length"]
            targets = [
                (state["length"] * (0.15 + i * 0.25), -3.6 if i % 2 == 0 else 3.6)
                for i in range(3)
            ]
            upcoming = min(targets, key=lambda p: (p[0] - progress) % state["length"])
            gap = (upcoming[0] - progress) % state["length"]
            target = upcoming[1] if gap < 85 else 0
            error = target - state["lane"]
            if abs(error) > 0.55:
                terminal.key("D" if error > 0 else "A", 0.04)
            else:
                terminal.pump(0.04)
            if state["nitro"] > 32 and not state["boost"] and not slow:
                terminal.key("B", 0.04)
            if state["nitro"] < 5 and state["boost"]:
                terminal.key("B", 0.04)
            if state["lap"] != last_lap:
                last_lap = state["lap"]
                terminal.save(f"lap-{last_lap}")
        terminal.pump(0.4)
        state = terminal.save("finished")
        require(state["circuit"] == circuit, "Race changed selected circuit")
        require(
            state["phase"] == "FINISHED",
            f"{circuit}: race did not finish within real-time limit",
        )
        require(
            "Finished" in terminal.text() and state["lap"] == 3,
            "Results not visible or laps wrong",
        )
        require(state["best"] is not None and state["best"] > 0, "Best time not saved")
        require(state["pads"] >= 1, f"{circuit}: no pad hit during genuine playthrough")
        if circuit == "SUNSET":
            finish_audit(terminal)
        if result_key in ["Q", "Ctrl+C"]:
            terminal.key(result_key, 0.1)
            deadline = time.monotonic() + 3
            while terminal.child.isalive() and time.monotonic() < deadline:
                terminal.pump(0.05)
            require(not terminal.child.isalive(), "Results quit did not exit")
            terminal.child.close()
            require(terminal.child.exitstatus == 0, "Results quit was unclean")
            RESULTS.append(
                {
                    "state": "finished",
                    "binding": result_key,
                    "expected": "Clean quit",
                    "status": "PASSED",
                    "evidence": terminal.frames[-2:],
                }
            )
            return {
                "circuit": circuit,
                "difficulty": difficulty,
                "time": state["time"],
                "position": state["position"],
                "pads": state["pads"],
                "bumps": state["bumps"],
                "status": "PASSED",
                "frames": terminal.frames,
            }
        expected = "GARAGE" if result_key in ["Esc", "G"] else "COUNTDOWN"
        check(
            terminal,
            "finished",
            result_key,
            f"Results command transitions to {expected}",
            lambda t: tap(t, result_key, "phase", expected),
        )
        return {
            "circuit": circuit,
            "difficulty": difficulty,
            "time": state["time"],
            "position": state["position"],
            "pads": state["pads"],
            "bumps": state["bumps"],
            "status": "PASSED",
            "frames": terminal.frames,
        }
    finally:
        terminal.close()


def quit_audit() -> None:
    for phase in [
        "GARAGE",
        "COUNTDOWN",
        "RACING",
        "PAUSED",
        "HELP",
        "SMALL",
        "BLURRED",
    ]:
        for binding in ["Q", "Ctrl+C"]:
            terminal = Terminal(f"quit-{phase.lower()}-{binding.lower()}", 80, 28)
            try:
                if phase in ["COUNTDOWN", "PAUSED"]:
                    start(terminal)
                if phase == "RACING":
                    racing(terminal)
                if phase == "PAUSED":
                    terminal.key("Esc", 0.3)
                if phase == "BLURRED":
                    terminal.key("FocusOut", 0.3)
                if phase == "HELP":
                    terminal.key("?", 0.3)
                if phase == "SMALL":
                    terminal.resize(50, 18)
                terminal.save("before-quit")
                terminal.key(binding, 0.1)
                deadline = time.monotonic() + 3
                while terminal.child.isalive() and time.monotonic() < deadline:
                    terminal.pump(0.05)
                require(
                    not terminal.child.isalive(), f"{binding} did not quit in {phase}"
                )
                terminal.child.close()
                require(
                    "\x1b[?1049l" in terminal.raw and "\x1b[?1004l" in terminal.raw,
                    "Quit did not restore alternate screen and focus mode",
                )
                require(
                    terminal.child.exitstatus == 0,
                    f"Unclean quit {terminal.child.exitstatus}",
                )
                RESULTS.append(
                    {
                        "state": phase,
                        "binding": binding,
                        "expected": "Clean quit and terminal restoration",
                        "status": "PASSED",
                        "evidence": terminal.frames,
                    }
                )
                print(f"PASSED: {phase} {binding}: clean quit", flush=True)
            finally:
                terminal.close()


def records_audit() -> None:
    prior_dir = OUTPUT / "race-sunset-easy" / "data"
    require(
        (prior_dir / "records.properties").exists(),
        "Run six-circuit campaign before records audit",
    )
    terminal = Terminal("records-reopen", 100, 34, record_dir=prior_dir)
    try:
        old_best = terminal.state()["best"]
        require(
            old_best is not None and "Best --" not in terminal.text(),
            "Saved record did not reload visibly",
        )
        terminal.save("loaded-best")
        # Change rival pace via real menu; its independent empty record must appear.
        focus(terminal, 2)
        check(
            terminal,
            "records",
            "Right",
            "Difficulty has an independent personal-best slot",
            lambda t: tap(t, "Right", "best", None),
        )
        terminal.key("Left", 0.3)
        require(
            terminal.state()["best"] == old_best,
            "Original record did not return when pace restored",
        )
        racing(terminal)
        terminal.key("S", 0.3)
        terminal.pump(8.0)
        terminal.key("W", 0.3)
        deadline = time.monotonic() + 150
        while terminal.state()["phase"] != "FINISHED" and time.monotonic() < deadline:
            state = terminal.state()
            if abs(state["lane"]) > 0.6:
                terminal.key("A" if state["lane"] > 0 else "D", 0.05)
            else:
                terminal.pump(0.05)
        terminal.pump(0.4)
        state = terminal.save("slower-finish")
        require(
            state["phase"] == "FINISHED" and state["time"] > old_best,
            "Need a genuinely slower completed race",
        )
        require(state["best"] == old_best, "Slower finish overwrote personal best")
        require(
            "Every finish counts" in terminal.text(), "Slower result message missing"
        )
        RESULTS.append(
            {
                "state": "records-slower-finish",
                "binding": "W / A / D",
                "expected": "Slower complete race preserves saved best",
                "status": "PASSED",
                "evidence": terminal.frames,
            }
        )
        terminal.key("Enter", 0.3)
        require(terminal.state()["phase"] == "COUNTDOWN", "Slower finish cannot retry")
        terminal.save("slower-retry")
    finally:
        terminal.close()


def contact_check(terminal: Terminal) -> None:
    moving(terminal)
    terminal.key("B", 0.3)
    terminal.save("approach")
    collided = padded = False
    deadline = time.monotonic() + 16
    while time.monotonic() < deadline and not (collided and padded):
        state = terminal.state()
        require(
            abs(state["lane"]) < 9,
            "Contact probe must stay on the road to distinguish barrier from rival",
        )
        error = -3.6 - state["lane"]
        if abs(error) > 0.5:
            terminal.key("D" if error > 0 else "A", 0.04)
        else:
            terminal.pump(0.04)
        if "Trading paint!" in terminal.text() and not collided:
            terminal.save("rival-impact")
            collided = True
        if "Turbo pad!" in terminal.text() and not padded:
            terminal.save("pad-pickup")
            padded = True
    require(
        collided and padded,
        "Expected both visible rival-impact and pad-pickup messages during real driving",
    )
    # The diagnostic file updates at 10 Hz; the visible frame can arrive first.
    terminal.wait_state(
        lambda s: s["bumps"] > 0 and s["pads"] > 0,
        "contact and pad counters after visible feedback",
    )
    require(
        terminal.state()["bumps"] > 0 and terminal.state()["pads"] > 0,
        "Visible rewards did not agree with simulation counters",
    )
    before = terminal.state()["distance"]
    terminal.pump(0.5)
    require(terminal.state()["distance"] > before, "Contact caused a softlock")
    terminal.save("recovered")


def errors_audit() -> None:
    target = OUTPUT / "invalid-records-target"
    if target.is_dir():
        shutil.rmtree(target)
    target.write_text("isolated invalid data-directory fixture\n")
    terminal = Terminal("record-errors", record_dir=target)
    try:

        def save_error(t):
            t.key("M", 0.3)
            t.wait_state(lambda state: state["saveError"], "save error feedback")
            require(
                "Cannot save records" in t.text(), "Failed save not visible in terminal"
            )
            require(t.state()["phase"] == "GARAGE", "Save failure broke game flow")

        check(
            terminal,
            "record-write-error",
            "M",
            "Filesystem error appears visibly; game remains usable",
            save_error,
        )
        target.unlink()
        target.mkdir()

        def recovery(t):
            t.key("M", 0.3)
            t.wait_state(lambda state: not state["saveError"], "save recovery")
            require(
                "Cannot save records" not in t.text(),
                "Successful recovery left error displayed",
            )
            require(
                (target / "records.properties").exists(),
                "Recovery did not persist settings",
            )

        check(
            terminal,
            "record-write-recovery",
            "M",
            "Retry after filesystem repair persists settings and clears error",
            recovery,
        )
    finally:
        terminal.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--smoke", action="store_true", help="Capture live garage and exit"
    )
    parser.add_argument(
        "--group",
        choices=[
            "all",
            "garage",
            "countdown",
            "race",
            "help",
            "quit",
            "races",
            "records",
            "errors",
            "contact",
            "tail",
        ],
        default="all",
    )
    parser.add_argument("--circuit", choices=CIRCUITS)
    parser.add_argument(
        "--difficulty",
        choices=DIFFICULTIES,
        help="Rival level for a six-circuit race campaign",
    )
    parser.add_argument(
        "--opposite-pace",
        action="store_true",
        help="Alternate the Easy/Medium campaign (legacy audit option)",
    )
    args = parser.parse_args()
    if args.difficulty and (args.group != "races" or args.opposite_pace):
        parser.error(
            "--difficulty requires --group races and cannot be combined with --opposite-pace"
        )
    if args.group == "tail":
        terminal = Terminal("controls-tail")
        try:
            moving(terminal)
            check(
                terminal,
                "racing-repeat",
                "Esc",
                "Isolated Esc pauses; measured native repeat sequence retains pause; spaced release tap resumes",
                escape_repeat,
            )
            check(
                terminal,
                "racing-repeat",
                "R",
                "Fast R repeats restart once with cleared controls",
                restart_repeat,
            )
            check(
                terminal,
                "countdown-repeat",
                "?",
                "Fast help repeats open once, separated tap closes",
                lambda t: repeat_check(t, "?", "help"),
            )
            check(
                terminal,
                "racing-motion",
                "N",
                "Reduced motion visibly centres windshield lean while paused; toggle restores",
                motion_check,
            )
            edge_audit(terminal)
            (OUTPUT / "tail-results.json").write_text(
                json.dumps(RESULTS, indent=2) + "\n"
            )
            previous = json.loads((OUTPUT / "all-progress-results.json").read_text())
            combined = [row for row in previous if row["status"] == "PASSED"] + RESULTS
            (OUTPUT / "all-results.json").write_text(
                json.dumps(combined, indent=2) + "\n"
            )
        finally:
            terminal.close()
        return
    if args.group == "contact":
        terminal = Terminal("contact", 100, 34)
        try:
            check(
                terminal,
                "racing-contact",
                "W / B / A / D",
                "Real rival collision and turbo strip have visible feedback, remain recoverable",
                contact_check,
            )
            (OUTPUT / "contact-results.json").write_text(
                json.dumps(RESULTS, indent=2) + "\n"
            )
        finally:
            terminal.close()
        return
    if args.group == "errors":
        errors_audit()
        (OUTPUT / "errors-results.json").write_text(
            json.dumps(RESULTS, indent=2) + "\n"
        )
        return
    if args.group == "records":
        records_audit()
        (OUTPUT / "records-results.json").write_text(
            json.dumps(RESULTS, indent=2) + "\n"
        )
        return
    if args.group == "quit":
        quit_audit()
        (OUTPUT / "quit-results.json").write_text(json.dumps(RESULTS, indent=2) + "\n")
        return
    if args.group == "races":
        from concurrent.futures import ThreadPoolExecutor

        circuits = [args.circuit] if args.circuit else CIRCUITS

        def run(c):
            i = CIRCUITS.index(c)
            return race_playthrough(
                c,
                args.difficulty
                or ("EASY" if (i % 2 == 0) != args.opposite_pace else "MEDIUM"),
                ["Enter", "Esc", "G", "R", "Q", "Ctrl+C"][i],
            )

        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(run, circuits))
        race_file = (
            f"races-{args.difficulty.lower()}.json"
            if args.difficulty
            else ("races-opposite.json" if args.opposite_pace else "races.json")
        )
        finish_file = (
            f"finish-{args.difficulty.lower()}-results.json"
            if args.difficulty
            else (
                "finish-results-opposite.json"
                if args.opposite_pace
                else "finish-results.json"
            )
        )
        (OUTPUT / race_file).write_text(json.dumps(results, indent=2) + "\n")
        (OUTPUT / finish_file).write_text(json.dumps(RESULTS, indent=2) + "\n")
        return
    terminal = Terminal("smoke" if args.smoke else "controls")
    try:
        terminal.save("garage")
        if args.smoke:
            print(terminal.text())
            print(json.dumps(terminal.state(), indent=2))
            return
        if args.group in ["all", "garage"]:
            garage_audit(terminal)
        if args.group in ["all", "countdown"]:
            countdown_audit(terminal)
        if args.group in ["all", "help"]:
            help_audit(terminal)
        if args.group in ["all", "race"]:
            race_audit(terminal)
        (OUTPUT / f"{args.group}-results.json").write_text(
            json.dumps(RESULTS, indent=2) + "\n"
        )
    finally:
        terminal.close()


if __name__ == "__main__":
    main()
