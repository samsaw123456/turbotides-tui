# Audio verification

The terminal port reuses all six original WAV assets: music, engine, go, bonus,
bump and finish. Java Sound plays a software PCM mix on its own worker thread;
the terminal update loop never waits for device playback. Engine pitch follows
speed. Muting and pausing clear cue voices and output zero PCM. Missing audio
devices leave the game playable with a visible unavailable status.

## Real device-output audit

Run on Linux with PipeWire and Temurin 25.0.5+8, 2026-11-15.
Final v0.1.3 JAR SHA-256: `2fe59158470d3d77e089e98c48e251e98708ae696219cf2fffbe17261c6e247a`.
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

The final run passed all assertions. Each mute and pause case produced exactly
zero-valued PCM samples; enabling sound and resuming restored nonzero output. The run
also completed a real three-lap Sunset Run on Easy in 49.63 seconds, first of six,
with 1 turbo pad and 4 bumps, then tested finished-screen mute and retry
countdown mute. Game state was observed through opt-in diagnostics; every action
entered through the terminal, with no simulation acceleration or state injection.

| Capture | Game phase | Samples | Peak absolute PCM | RMS |
| --- | --- | ---: | ---: | ---: |
| garage-on | GARAGE | 25,138 | 3011 | 485.521 |
| garage-muted | GARAGE | 32,429 | 0 | 0.0 |
| garage-restored | GARAGE | 26,314 | 3060 | 499.341 |
| countdown-on | COUNTDOWN | 28,666 | 3011 | 474.968 |
| racing-on | RACING | 26,314 | 2368 | 748.698 |
| racing-muted | RACING | 27,020 | 0 | 0.0 |
| racing-restored | RACING | 26,549 | 2315 | 770.128 |
| paused | PAUSED | 28,901 | 0 | 0.0 |
| paused-muted | PAUSED | 27,255 | 0 | 0.0 |
| paused-unmuted | PAUSED | 27,255 | 0 | 0.0 |
| resumed | RACING | 26,079 | 2393 | 754.995 |
| finished-on | FINISHED | 28,901 | 5624 | 1259.896 |
| finished-muted | FINISHED | 27,725 | 0 | 0.0 |
| finished-restored | FINISHED | 30,312 | 2991 | 507.78 |
| countdown-muted | COUNTDOWN | 27,725 | 0 | 0.0 |

Local reproducible evidence lives in `build/audio-audit/results.json`, the
adjacent raw 22,050 Hz signed 16-bit mono `.pcm` files, and
`build/ansi-audit/audio-output/` (before/after PNGs, text, diagnostics and raw
`terminal.ansi`). All 15 PCM files were independently checked against their recorded sample,
peak, RMS and nonzero counts. The full garage, racing, paused, finished and
muted-countdown frames were visually inspected, along with a contact sheet of
all 15 capture headers and sound-state footers (`build/audio-audit/frames-contact-sheet.png`). Generated
capture files are excluded from git; rerunning the script recreates them.

The final run recorded `Volume: 0.30` both before and after capture. These
results verify the game's actual playback stream, **not physical loudspeaker
audibility**. The user's speaker settings were deliberately left intact. macOS
audio and physical speaker output are unverified in this Linux environment.

An initial v0.1.3 attempt passed all 15 PCM and phase checks but failed the
speaker-state comparison. That tool version did not retain its before/after
speaker strings on failure, so the exact change cannot be reconstructed. The
audit now records both strings before making the same comparison; the equality
assertion and every PCM assertion remain unchanged. The single rerun above
passed. The initial raw PCM, frames and failed report remain under
`build/difficulty-audio-first-attempt/`. Neither attempt changed volume, mute,
default devices or other applications' audio links.

## Signal and mechanics regression checks

`AudioTest` decodes every original asset and exercises the same PCM mixer used
by the device worker. It proves mute/pause produce zero samples, clearing queued
cues allows clean recovery, engine speed changes the output samples, and each
cue changes the mixed waveform. These checks supplement the external playback
capture; neither a mute flag nor a mocked output sink establishes the device
result above.

The original player driving mechanics and track geometry are retained. Rivals
now have four tested levels: Easy, Medium, Hard and Super Hard. Difficulty tunes
rival pace, acceleration, cornering and speed bursts; player throttle, braking,
boost and drift rules stay consistent. The mechanics suite covers all six
circuits and all four levels, countdown, fixed-step timing,
boost caps, brakes taking priority, no reverse, grass slowdown, barrier and rival
contact recovery, drift charging, pads once per lap, pause, finish, late finishes
and restart. Additional edge tests cover stalled frames, contacts across the lap
seam, and bounded chaotic inputs. Physical ANSI controls and rendered movement
are independently covered in [VERIFICATION.md](VERIFICATION.md).
