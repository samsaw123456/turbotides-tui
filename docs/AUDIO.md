# Audio verification

The terminal port reuses all six original WAV assets: music, engine, go, bonus,
bump and finish. Java Sound plays a software PCM mix on its own worker thread;
the terminal update loop never waits for device playback. Engine pitch follows
speed. Muting and pausing clear cue voices and output zero PCM. Missing audio
devices leave the game playable with a visible unavailable status.

## Real device-output audit

Run on Linux with PipeWire and Temurin 25.0.5+8, 2026-11-15.
Final tested JAR SHA-256: `0fb51303f953457b92d44ce4b04ce1698f6d3530fe4ddcebebb90dc108878c61`.
The audit checks the artifact hash again at the end to reject a concurrent rebuild.

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
also completed a real three-lap Sunset Run in 45.84 seconds, first of six, with
three turbo pads and no collisions, then tested finished-screen mute and retry
countdown mute. Game state was observed through opt-in diagnostics; every action
entered through the terminal, with no simulation acceleration or state injection.

| Capture | Game phase | Samples | Peak absolute PCM | RMS |
| --- | --- | ---: | ---: | ---: |
| garage-on | GARAGE | 57,360 | 3060 | 487.548 |
| garage-muted | GARAGE | 40,191 | 0 | 0.0 |
| garage-restored | GARAGE | 36,663 | 3011 | 488.322 |
| countdown-on | COUNTDOWN | 35,487 | 3199 | 530.477 |
| racing-on | RACING | 34,546 | 2076 | 717.179 |
| racing-muted | RACING | 36,428 | 0 | 0.0 |
| racing-restored | RACING | 47,012 | 2427 | 767.813 |
| paused | PAUSED | 42,543 | 0 | 0.0 |
| paused-muted | PAUSED | 43,719 | 0 | 0.0 |
| paused-unmuted | PAUSED | 51,951 | 0 | 0.0 |
| resumed | RACING | 43,484 | 2424 | 777.911 |
| finished-on | FINISHED | 29,372 | 4536 | 1149.936 |
| finished-muted | FINISHED | 38,309 | 0 | 0.0 |
| finished-restored | FINISHED | 45,365 | 2989 | 504.517 |
| countdown-muted | COUNTDOWN | 40,191 | 0 | 0.0 |

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
