# Audio verification

The terminal port reuses all six original WAV assets: music, engine, go, bonus,
bump and finish. Java Sound plays a software PCM mix on its own worker thread;
the terminal update loop never waits for device playback. Engine pitch follows
speed. Muting and pausing clear cue voices and output zero PCM. Missing audio
devices leave the game playable with a visible unavailable status.

## Real device-output audit

Run on Linux with PipeWire and Temurin 25.0.5+8, 2026-11-15.
Final tested JAR SHA-256: `fc5734af39bcc17ac9c91758a7518b612168860558dbce09546b0c112627a490`.
The audit checks the artifact hash again at the end to reject a concurrent rebuild.
Each capture records the phase before and after its measured interval, rather
than sampling the phase later during recorder shutdown; both must match the
expected state. This avoids mislabelling a countdown that finishes afterward.

Reproduce with:

```sh
TURBOTIDES_JAVA_HOME=/path/to/jdk25 \
  .venv/bin/python tools/audio_audit.py
```

Install `tools/audit-requirements.txt` into the virtual environment first. The
audit drives the actual tui4j application through a PTY, sends normal ANSI key
bytes, and captures only the playback port belonging to that Java process. It
does not record a microphone, another application's output, or a global monitor.
It does not change volume, mute, default devices, or other applications' links.

The actual run passed all assertions. Each mute and pause case produced exactly
zero-valued PCM samples; enabling sound and resuming restored nonzero output. The run
also completed a real three-lap Sunset Run in 43.67 seconds, first of six, with
6 turbo pads and 0 collisions, then tested finished-screen mute and retry
countdown mute. Game state was observed through opt-in diagnostics; every action
entered through the terminal, with no simulation acceleration or state injection.

| Capture | Game phase | Samples | Peak absolute PCM | RMS |
| --- | --- | ---: | ---: | ---: |
| garage-on | GARAGE | 36,898 | 3199 | 555.983 |
| garage-muted | GARAGE | 30,077 | 0 | 0.0 |
| garage-restored | GARAGE | 28,196 | 2991 | 548.685 |
| countdown-on | COUNTDOWN | 32,664 | 3266 | 516.875 |
| racing-on | RACING | 33,605 | 2580 | 766.835 |
| racing-muted | RACING | 34,781 | 0 | 0.0 |
| racing-restored | RACING | 29,372 | 2321 | 780.672 |
| paused | PAUSED | 29,372 | 0 | 0.0 |
| paused-muted | PAUSED | 31,018 | 0 | 0.0 |
| paused-unmuted | PAUSED | 43,013 | 0 | 0.0 |
| resumed | RACING | 29,136 | 2410 | 779.101 |
| finished-on | FINISHED | 31,018 | 4337 | 1142.034 |
| finished-muted | FINISHED | 33,370 | 0 | 0.0 |
| finished-restored | FINISHED | 28,901 | 3028 | 529.331 |
| countdown-muted | COUNTDOWN | 25,608 | 0 | 0.0 |

Local reproducible evidence lives in `build/audio-audit/results.json`, the
adjacent raw 22,050 Hz signed 16-bit mono `.pcm` files, and
`build/ansi-audit/audio-output/` (before/after PNGs, text, diagnostics and raw
`terminal.ansi`). The full garage, racing and finished rendered frames were
visually inspected, along with a contact sheet of all 15 capture headers and
sound-state footers (`build/audio-audit/frames-contact-sheet.png`). Generated
capture files are excluded from git; rerunning the script recreates them.

The existing speaker state remained `Volume: 0.72 [MUTED]` throughout. These
results verify the game's actual playback stream, **not physical loudspeaker
audibility**. The user's speaker settings were deliberately left intact. macOS
audio and physical speaker output are unverified in this Linux environment.

## Signal and mechanics regression checks

`AudioTest` decodes every original asset and exercises the same PCM mixer used
by the device worker. It proves mute/pause produce zero samples, clearing queued
cues allows clean recovery, engine speed changes the output samples, and each
cue changes the mixed waveform. These checks supplement the external playback
capture; neither a mute flag nor a mocked output sink establishes the device
result above.

The original `Race.kt` and `Track.kt` rules were copied intact. The mechanics
suite covers all six circuits and both rival paces, countdown, fixed-step timing,
boost caps, brakes taking priority, no reverse, grass slowdown, barrier and rival
contact recovery, drift charging, pads once per lap, pause, finish, late finishes
and restart. Additional edge tests cover stalled frames, contacts across the lap
seam, and bounded chaotic inputs. Physical ANSI controls and rendered movement
are independently covered in [VERIFICATION.md](VERIFICATION.md).
