# Verification record

Verified on Linux x86-64, November 15, 2026. The final executable is identified
by SHA-256 `fc5734af39bcc17ac9c91758a7518b612168860558dbce09546b0c112627a490`.
The build and final control/audio runs used Temurin 25.0.5+8; the v0.1.0 campaign
also exercised Ubuntu OpenJDK 25.0.4.1. The original Turbo Tides workspace was not edited.

## Results

- **39 regression tests passed**, with Kotlin lint and compilation passing.
  Tests cover original physics/rules, six circuits, both paces, collisions,
  drift/pads, fixed-step timing, input expiry, audio samples, records failure
  recovery, visible asphalt/car alignment, boundary clipping and time formatting.
  The checks also passed with ALSA configuration disabled. The cache regression
  distinguishes an unchanged idle view from legitimate asynchronous audio-status
  invalidation; an earlier CI assertion incorrectly conflated those cases.
- **306 ANSI coverage rows passed**: 235 main control cases, 46 results-screen
  cases across both pace campaigns, 14 quit cases, two records cases, two save-error
  cases, one contact scenario and six earned-record recovery cases. See the [complete binding/state table](CONTROLS.md).
- **12 complete three-lap races passed**: every circuit at both rival paces,
  through real PTY input and normal wall-clock simulation. No state injection,
  time acceleration or automatic driving exists in the game.
- **15 actual audio-stream captures passed**: seven muted/paused cases were
  exactly silent and eight enabled/restored cases produced PCM. See [audio
  evidence and hardware limits](AUDIO.md).
- **47 installer test methods exercised successfully**, including real runtime download,
  repair, preserved records, rollback, unusual path characters and launching the
  actual game through the generated Linux desktop entry. See [installation
  verification](INSTALLATION.md). Package-manager fixtures cannot change host packages;
  real isolated checks downloaded Java/JDK and Gradle, launched the desktop entry,
  and proved first/second launch, live rebuild/repair, signal cleanup and offline play.
  A namespace test also proved HTTPS failed without certificate roots and
  recovered after the installer requested the missing CA package.
- Python lint/format/syntax checks passed. The standalone Java key probe compiled
  with `javac -Xlint:all -Werror`. Nine CLI option/redirected-input cases passed.
  Actual profile saving also passed with empty and relative `XDG_DATA_HOME` values,
  correctly falling back to the user's absolute data directory. That profile-path
  check was retained from v0.1.0; installer XDG fallback tests were rerun in this review.

## Real races and recovery

The repeatable campaign chooses steering keys using read-only diagnostics,
then sends ordinary ANSI input. The separate control audit measures actual
painted player pixels; a successful campaign alone does not prove steering.

| Circuit | Cruise time | Race time | Finish |
| --- | ---: | ---: | --- |
| Sunset Run | 41.68 s | 42.31 s | First in both |
| Cinder Ring | 39.63 s | 40.03 s | First in both |
| San Francisco | 44.39 s | 44.11 s | First in both |
| Silicon Valley | 46.95 s | 46.99 s | First in both |
| New York City | 49.03 s | 47.69 s | First in both |
| Chicago | 46.01 s | 47.16 s | First in both |

[Six finish screens](screenshots/six-finishes.png) were inspected. The campaign
picked up five to nine pads per race. A dedicated contact scenario visibly
caught a rival, triggered Trading paint, drove across a mint pad while it remained
visible under the car, and recovered. [Mechanics frames](screenshots/mechanics.png).

A separate slower run finished fourth in 57.81 s and retained the reopened 41.68 s
personal best; changing pace showed an independent record slot. Retry returned
to a fresh countdown. Independent manual terminal play finished sixth in 78.69 s,
after grass/barrier recovery, braking to a stop, drift/nitro toggles, pause/resume,
and three pads. Enter retried, Esc/G returned to the garage, and Q exited cleanly.
That manually driven race banked no drift; the separate control audit proves
banking. Its actual command log and 20 inspected frames are retained under
`build/ansi-audit/manual-final/`. There is no death or elimination in the original
rules; poor placement is the unsuccessful outcome.

The review reproduced and fixed lost earned records after a failed disk write.
Two additional ordinary-speed races (45.79 s and 44.44 s) proved pending bests
survive until repair and a settings-save retry, both from results and after
returning to the garage. Fresh processes reloaded the saved best and setting.
Diagnostic failure/recovery was also exercised: its warning clears after repair,
an unrelated sibling `.tmp` file survives, and owned temporary files are cleaned.

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
Captures wait for the complete frame, including the bottom status line. A
fixed-duration steering probe once saw the correct two-pixel rear movement under
load; it now continues ordinary key repeats for up to another 0.8 s until the
unchanged greater-than-two-pixel assertion is met. The full inventory was rerun
and passed. No simulation timing or directional assertion was weakened.

Every table row names before/after evidence under `build/ansi-audit/`. Full raw
ANSI, JSON state, PNGs and test reports stay local rather than bloating the source
repository. Curated images and the complete table are tracked. Re-running the
retained tools recreates the raw evidence. Each terminal session records its
executable hash in `build.json`. `tools/control_report.py` rejects different-build
or stale frames before generating the binding table.

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
.venv/bin/python tools/record_recovery_audit.py
.venv/bin/python tools/record_recovery_audit.py --garage
.venv/bin/python tools/diagnostic_recovery_audit.py
.venv/bin/python tools/ansi_audit.py --group quit
.venv/bin/python tools/ansi_audit.py --group records
.venv/bin/python tools/ansi_audit.py --group errors
.venv/bin/python tools/ansi_audit.py --group contact
.venv/bin/python tools/control_report.py
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
runtime metadata selection were checked. Linux and macOS CI build, regression
tests and real PTY smoke checks passed for v0.1.0; v0.1.1 results are recorded
with the release. Native Finder/Dock interaction is a separate verification limit.
Actual game PCM was captured without unmuting the user's speakers. There is no
claim that every terminal, keyboard firmware, audio device or platform has been
physically tested. The TUI deliberately simplifies 3D scenery and camera elevation.

## Follow-up session review

[QUALITY_REVIEW.md](QUALITY_REVIEW.md) maps the recent sessions' actual user
guidance to evidence and fixes. It records profiling, the static-view cache,
pixel-identical solid-color spaces, dependency freshness and compatibility,
Ctrl+Z/terminal restoration, and actual installed operation with network calls
denied. A final 100×34 sample measured 32.21 complete ANSI redraws/s on a busy
shared host. Large-window and before/after measurements are explicitly labelled
with their candidate artifact and host-load limitations, rather than presented
as guaranteed frame rates. The original Race.kt and Track.kt remain unchanged.
