# Four rival difficulties

The garage's Difficulty row offers **Easy, Medium, Hard and Super Hard**, in that
order. Left/A move backward; Right/D and Enter move forward. The list wraps in
both directions. The selected level remains in the header during countdown,
racing, help, pause and results, including at the minimum 64×24 terminal size.

Easy rivals accelerate gently and slow more for bends. Medium raises their
normal pace. Hard accelerates faster, carries more speed through bends and
surges more often. Super Hard makes those advantages stronger again. Rival
performance is deterministic; it never changes according to the player's lead
or position. Speed is capped at 87 m/s, acceleration at 40 m/s², and braking at
46 m/s². Player handling, track geometry, collision recovery and nitro rules
remain the same on every level.

Super Hard rewards combining boost with drift banking and collecting mint pads.
The original rules allow a boosted drift: the boost speed cap takes priority
while the drift charges. End a sufficiently long drift to bank nitro, then
re-enter it when useful. The player's speed and acceleration limits provide
enough headroom to beat even the fastest rival.

## Balance evidence

All six courses were simulated through the authoritative 120 Hz race model.
The fastest and slowest rival each improve by at least three seconds between
adjacent levels. The table shows the fastest rival's complete three-lap time:

| Circuit | Easy | Medium | Hard | Super Hard |
| --- | ---: | ---: | ---: | ---: |
| Sunset Run | 63.78 s | 51.05 s | 42.39 s | 37.53 s |
| Cinder Ring | 60.69 s | 48.60 s | 40.27 s | 35.77 s |
| San Francisco | 67.40 s | 54.05 s | 44.96 s | 39.60 s |
| Silicon Valley | 69.95 s | 56.15 s | 46.75 s | 41.10 s |
| New York City | 70.26 s | 56.40 s | 46.90 s | 41.26 s |
| Chicago | 70.12 s | 56.29 s | 46.84 s | 41.18 s |

Four separate, normal-speed PTY sessions measured the actual San Francisco
rivals at the same times, using real brake input to remain parked while the
field raced. Their complete finish ranges were Easy 67.40–76.35 s, Medium
54.05–59.66 s, Hard 44.96–48.69 s and Super Hard 39.60–41.84 s. Actual ANSI
frames show the stronger rivals pulling away sooner. Read-only local diagnostics
recorded exact finish times; no live race state or simulation speed was changed.

The standard terminal driver collects pads and uses nitro without banking
drifts. It won all six courses on Easy and Medium, had mixed results on Hard,
and finished sixth on all six courses on Super Hard. Independent manual Sunset
play won Easy in **47.87 s** without using manual nitro or drift, then finished
sixth on Super Hard in **44.06 s** despite using both. The stronger rivals beat
the faster player run. [Manual comparison](screenshots/difficulty-comparison.png).

A separate expert driver beat Super Hard on every course through actual ANSI
input. It combined pads, boost and frequent banked drifts:

| Circuit | Player time | Place | Pads | Banked drifts |
| --- | ---: | ---: | ---: | ---: |
| Sunset Run | 35.68 s | 1st | 9 | 36 |
| Cinder Ring | 33.87 s | 1st | 9 | 34 |
| San Francisco | 37.66 s | 1st | 9 | 38 |
| Silicon Valley | 39.77 s | 1st | 9 | 35 |
| New York City | 39.90 s | 1st | 7 | 33 |
| Chicago | 40.03 s | 1st | 8 | 32 |

[All six expert finish screens](screenshots/super-hard-finishes.png) were
inspected. This driver reads local diagnostics to choose normal key input;
these are automated playtests, not claims of manual wins. The first four
successful probes used a scratch driver. The retained `tools/expert_audit.py`
uses the same steering/boost/drift policy and also confirms each drift toggle
was acknowledged before continuing. Its Silicon Valley and Chicago reruns
recovered missed taps and won. These are player-input retries; no simulation
state, speed, clock or rules were changed. An earlier scratch attempt on each
of those courses left drift off after an unacknowledged tap and did not win.

The regression suite also checks all rivals' speed/acceleration/distance bounds,
unchanged player handling between difficulties, no player-gap rubber banding,
refresh-rate independence, pause/reset and record compatibility. Real terminal
controls and completed player races are documented in [VERIFICATION.md](VERIFICATION.md).

## Existing records

Saved **Cruise** settings and best times appear under **Easy**. Saved **Race**
settings and best times appear under **Medium**. When both an old and new record
exist, the fastest valid positive finite time wins. Old keys are retained when
settings are saved. Opening a profile does not rewrite it. Hard and Super Hard
use separate record slots; failed-write recovery still keeps earned bests pending
until a successful save.

## Reproduce

Use JDK 25 and the Python environment from [VERIFICATION.md](VERIFICATION.md):

```sh
./gradlew ktlintFormat check fatJar
python tools/difficulty_audit.py
for level in EASY MEDIUM HARD SUPER_HARD; do
  python tools/ansi_audit.py --group races --difficulty "$level"
done
python tools/expert_audit.py
```

The menu audit sends each alternate binding separately through all four choices,
then starts and pauses each level at 64×24. The observation runs use normal wall
time. Campaigns drive the actual game through ANSI input and complete three laps
on every circuit/level combination; their standard driver seeks pads and uses
nitro without banking drifts. Test records are isolated from the user's profile.
