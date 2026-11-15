# Verification record

Verified on Linux x86-64, November 15, 2026. The final executable is identified
by SHA-256 `0fb51303f953457b92d44ce4b04ce1698f6d3530fe4ddcebebb90dc108878c61`.
The build and final control/audio runs used Temurin 25.0.5+8; campaign checks also
exercised Ubuntu OpenJDK 25.0.4.1. The original Turbo Tides workspace was not edited.

## Results

- **34 regression tests passed**, with Kotlin lint and compilation passing.
  Tests cover original physics/rules, six circuits, both paces, collisions,
  drift/pads, fixed-step timing, input expiry, audio samples, records failure
  recovery, visible asphalt/car alignment, boundary clipping and time formatting.
- **277 ANSI coverage rows passed**: 235 main/tail control cases, 23 results-screen
  cases, 14 quit cases, two records cases, two save-error cases and one contact
  scenario. See the [complete binding/state table](CONTROLS.md).
- **12 complete three-lap races passed**: every circuit at both rival paces,
  through real PTY input and normal wall-clock simulation. No state injection,
  time acceleration or automatic driving exists in the game.
- **15 actual audio-stream captures passed**: seven muted/paused cases were
  exactly silent and eight enabled/restored cases produced PCM. See [audio
  evidence and hardware limits](AUDIO.md).
- **18 installer cases exercised successfully**, including real runtime download,
  repair, preserved records, rollback, unusual path characters and launching the
  actual game through the generated Linux desktop entry. See [installation
  verification](INSTALLATION.md).
- Python lint/format/syntax checks passed. The standalone Java key probe compiled
  with `javac -Xlint:all -Werror`. Nine CLI option/redirected-input cases passed.
  Actual profile saving also passed with empty and relative `XDG_DATA_HOME` values,
  correctly falling back to the user's absolute data directory.

## Real races and recovery

The repeatable campaign chooses steering keys using read-only diagnostics,
then sends ordinary ANSI input. The separate control audit measures actual
painted player pixels; a successful campaign alone does not prove steering.

| Circuit | Cruise time | Race time | Finish |
| --- | ---: | ---: | --- |
| Sunset Run | 41.55 s | 42.26 s | First in both |
| Cinder Ring | 40.43 s | 38.89 s | First in both |
| San Francisco | 45.71 s | 45.74 s | First in both |
| Silicon Valley | 47.33 s | 47.89 s | First in both |
| New York City | 48.10 s | 49.19 s | First in both |
| Chicago | 47.14 s | 46.71 s | First in both |

[Six finish screens](screenshots/six-finishes.png) were inspected. The campaign
picked up four to nine pads per race. A dedicated contact scenario visibly
caught a rival, triggered Trading paint, drove across a mint pad while it remained
visible under the car, and recovered. [Mechanics frames](screenshots/mechanics.png).

A separate slower run finished third in 56.75 s and retained the reopened 41.55 s
personal best; changing pace showed an independent record slot. Retry returned
to a fresh countdown. Direct manual terminal play also finished sixth in 90.74 s,
after barrier recovery, one banked drift, pause/resume and a subsequent retry/
garage cycle. At pause, the displayed 51.40 s remained frozen. There is no death
or elimination in the original rules; a slower finish is the failure/retry case.

## Presentation and control evidence

[Eight steering pairs](screenshots/steering-audit.png) demonstrate A and Left
moving screen-left, D and Right moving screen-right, and the deliberate mirror
in rear view. These assertions inspect painted car pixels independently of the
simulation's lane sign. Reduced motion changes the actual windshield lean pixels
in a frozen scene; changing it back restores the previous picture.

The [minimum 64×24 frame](screenshots/minimum-terminal.png),
[complete 180×65 frame](screenshots/large-terminal.png), and
[80×28 indexed-color fallback](screenshots/256-color.png) were inspected.
Resizing to 50×18 pauses; all 21 non-quit commands are ignored while undersized
or blurred. Focus regain does not restart movement. Resume clears driving modes.
An early large-screen capture stopped midway through the ANSI redraw; waiting
for the final bottom status line produced the complete frame above.

Every table row names before/after evidence under `build/ansi-audit/`. Full raw
ANSI, JSON state, PNGs and test reports stay local rather than bloating the source
repository. Curated images and the complete table are tracked. Re-running the
retained tools recreates the raw evidence. Each terminal session records its
executable hash in `build.json`.

## Reproduce from a source checkout

```sh
# Set JAVA_HOME to a JDK 25 installation first.
./gradlew ktlintFormat
./gradlew check fatJar
python3 -m venv .venv
.venv/bin/pip install -r tools/audit-requirements.txt
.venv/bin/ruff check tools
.venv/bin/ruff format --check tools
python3 -m py_compile tools/*.py
.venv/bin/python tools/ansi_audit.py --help
.venv/bin/python tools/ansi_audit.py --group all
.venv/bin/python tools/ansi_audit.py --group races
.venv/bin/python tools/ansi_audit.py --group races --opposite-pace
.venv/bin/python tools/key_protocol_probe.py
.venv/bin/python tools/audio_audit.py
.venv/bin/python -m unittest tools.test_install -v
```

Audio device capture needs the Linux PipeWire tools. Installer network and
visible-desktop cases are opt-in; their exact commands are in INSTALLATION.md.
Use the audit's help for targeted finish, record, contact, quit and tail cases.
Tests use isolated data and clean up their game processes; no user records or
speaker settings are modified.

## Design checklist

| Area | Assessment |
| --- | --- |
| Core loop | Passed: garage, countdown, 12 race/pace combinations, finish, retry, records |
| Physics | Passed: original fixed 120 Hz rules; braking, boost, drift, pads, grass, barriers, rival contacts; matching rendered boundaries |
| Interaction | Passed within documented ANSI semantics: every binding/state, repeats, opposing steering, disabled input and recovery |
| Navigation/camera | Passed: six reachable circuits, real maps, visible forward/rear steering; simplified terminal projection |
| State | Passed: countdown/race pause, reset, finish, blur, resize and resumed input clearing |
| Feel/accessibility | Passed on tested terminals: readable controls/colors, help, mute output, reduced motion and minimum size |
| Polish | Inspected: original assets, maps, road and car alignment, result/order/time labels, complete terminal frames |
| Robustness | Passed: repeated races, minimum/large sizes, record errors/retry, installer rollback, clean terminal/audio cleanup |
| Play evidence | Complete races plus manual slower finish/retry, independent adversarial reviews and rendered/PCM captures |
| Jump/combat/inventory | Not applicable: absent from original and port |
| Controller/mouse/touch/fullscreen | Not game commands; terminal owns fullscreen |

## Explicit limits

Ordinary ANSI cannot report physical key release or standalone Shift. Driving
modes and expiring steering pulses are intentional adaptations. Tap toggle keys;
held toggles are not reliably distinguishable from repeated taps. The Escape
probe established that rapid Escape bursts can decode as Alt+Esc and be ignored;
measured sequences and recovery are recorded in CONTROLS.md. Focus-loss behavior
requires a terminal that emits focus reports.

Native macOS Finder/Terminal/Dock behavior, ARM hardware, and physical speaker
audibility were **not verified on this Linux host**. macOS bundle generation and
runtime metadata selection were checked; the CI workflow also targets macOS.
Actual game PCM was captured without unmuting the user's speakers. There is no
claim that every terminal, keyboard firmware, audio device or platform has been
physically tested. The TUI deliberately simplifies 3D scenery and camera elevation.
