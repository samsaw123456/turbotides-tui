# Terminal design

Keep Turbo Tides recognizable: orange cars and curbs, warm cream text, mint
pads, teal coastal ground, original Phippy/Goldie portraits, sound and icon.
The game opens directly on circuit selection. The real track map and starting
grid preview occupy the center; four keyboard-selectable rows sit below.

Use ANSI true color and Unicode half blocks for portable two-pixel-high cells.
When both pixels have the same color, emit a background-colored space instead;
the picture is identical and tui4j avoids unnecessary Unicode grapheme analysis.
Older Apple terminals use xterm 256-color quantization; an environment override
selects either palette. Quantization is cached and never changes geometry.
Draw the road from the authoritative track's lateral geometry, with a fixed
road-centered forward camera. A positive lane must visibly move the car right.
The labelled rear camera mirrors the view while preserving driver-relative
steering. Scenery is schematic and track-specific. Do not imply that the
terminal projection reproduces the original 3D camera or elevation rendering.

Maintain the original 120 Hz physics and cap long-frame catch-up at 100 ms.
Presentation requests updates at 40 Hz; actual throughput depends on the terminal
and machine. Terminal output is bounded to 180x65. Static screens reuse their
rendered art while input, audio status, and errors continue updating.
Small windows pause the simulation. Keyboard modes replace unobservable ANSI
key releases; visible mode indicators are essential. No invisible auto-drive,
physics cheats, telemetry-driven input inside the game, or automated wins.

Testable invariants: three laps, five rivals, six routes; no reverse; grass
slows; barriers remain recoverable; brake wins over boost; drift banks only
with earned charge; turbo pads work once per lap; paused/countdown/finished
state transitions preserve intended timing; restarting clears driving modes;
per-circuit/per-pace records survive restarts and install updates. Verify every
binding against actual output, then inspect captured frames. See VERIFICATION.md.
