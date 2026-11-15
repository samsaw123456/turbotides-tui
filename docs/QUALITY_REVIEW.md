# Recent-session quality review

Reviewed November 15, 2026 against the published `v0.1.0` baseline
(`8398048`). This review reads the relevant user messages from the recent
local game sessions, then compares them with this repository and its retained
test evidence. It does not treat another assistant's assurance as a passed
test here. Private session logs and unrelated personal details are not copied
into this repository. All provenance times below are UTC.

## Guidance recovered

| Source session and user-message time | Applicable instruction |
| --- | --- |
| Build a fun Phippy game, November 14 at 23:13; November 15 at 01:17 | Check completion logic in the running game and investigate similar failures. An editor entry point should launch the game. |
| Build a Phippy game, November 15 at 06:51 and 07:10–07:12 | Test gameplay, physics and every control by watching its actual effect. The user specifically caught reversed left/right steering. Include readable track selection and previews. |
| Build a fun Phippy game, November 15 at 07:21 | Keep the original repository intact and reuse assets. Use JVM 25 and current Kotlin/Gradle. Provide simple README instructions, automatic dependencies on first use, Linux/macOS application launchers and a public repository. Consider low-resource machines, repeat adversarial review and dogfood the result. |
| Build Kotlin memory game, November 15 at 06:56, 07:10 and 08:16 | Use Kotlin/tui4j; navigate the mechanics through actual ANSI input. Test clean installation and smooth onboarding, review in parallel, and include automatic missing dependencies and an application icon. |
| Build Emberwood TUI game, November 15 at 07:35 | Preserve gameplay and available assets; inspect every command through real terminal input, test physics, provide one-shot installation and launcher icons on Linux/macOS, and apply the recent sessions' quality guidance. |
| Build Turbo Tides TUI, November 15 at 07:43 and 08:33 | Apply the same requirements to this port, including a great README, current JVM/Kotlin/Gradle/tui4j, public GitHub repository, automatic dependencies and terminal application launchers. |

The user's repository instructions make the evidence standard explicit:
inventory each physical binding in each distinct state, prove input → visible
effect → recovery, inspect actual frames, test successful and unsuccessful
play/retry, keep test data isolated, and disclose untested platforms or devices.

## Requirement, evidence and remaining work

This table records the review's starting point. A gap is not a claim that an
unexercised failure exists; it identifies missing behavior or missing proof.
The [verification record](VERIFICATION.md) identifies the tested executable.
The baseline gaps below are closed by the [follow-up resolutions](#follow-up-resolutions);
platform/device limits remain explicit.

| Requirement | Evidence in the baseline | Review result |
| --- | --- | --- |
| Preserve the original game and assets | Original race/track rules are reused; original art, audio, icon and notices are retained. [Design](DESIGN.md), [notices](../THIRD_PARTY.md), [port scope](../README.md#what-carries-over). | Covered. Terminal scenery, camera elevation and key-release differences are explicitly disclosed. |
| Visible left/right correctness for every alternate binding | [Eight inspected forward/rear steering pairs](screenshots/steering-audit.png), independent painted-pixel assertions, and separate A/D/arrow rows in the [control inventory](CONTROLS.md). | Covered on the tested terminal. Rear steering is deliberately mirrored and labelled. |
| Full core loop, completion, failure and retry | Twelve ordinary-speed three-lap races cover every circuit and pace. A slower third-place run and a manually driven sixth-place run exercise unsuccessful placement, retry and recovery. Reopened records preserve the faster result. [Evidence](VERIFICATION.md#real-races-and-recovery). | Covered. The original game has no elimination/death state; poor placement is its unsuccessful outcome. |
| Physics, contacts and visual geometry agree | Fixed 120 Hz original rules; tests for braking, drift, pads, grass, barriers, contacts and timing; actual pad/contact/recovery frames and all circuits completed. [Mechanics frames](screenshots/mechanics.png). | Covered by combined regression and real-play evidence; successful races alone are not used as control proof. |
| Every binding/state and interrupted input | 277 recorded rows cover alternate bindings, repeats, opposing steering, countdown, pause, help, results, blur, undersized windows, quit and recovery. [Complete inventory](CONTROLS.md). | Covered within documented ANSI semantics. Physical key releases and unsupported input devices cannot be claimed tested. Follow-up Ctrl+Z probes found no freeze in five tested contexts; see the terminal checks below. |
| Actual mute/unmute and pause audio | Fifteen captured game audio streams include seven silent and eight restored/enabled cases. [Audio evidence](AUDIO.md). | Covered at digital-output level. Physical speaker audibility remains unverified. |
| Responsive, readable presentation and accessibility | Inspected minimum 64×24, normal, maximum 180×65 and indexed-color frames; reduced-motion pixel comparison; real maps, paint/pace choices and visible input modes. [Screenshots and limits](VERIFICATION.md#presentation-and-control-evidence). | Covered for recorded sizes/palettes. The original target/heap limits were not performance proof. Follow-up measurements and JFR profiling below resolved that evidence gap and led to two focused optimizations. |
| Current dependencies and reproducible checks | JVM 25, Kotlin 2.4.21, Gradle 9.9.1, tui4j 0.3.5 and ktlint 14.2.0 are pinned; Gradle distribution checksum, lint, 34 regression tests and executable build are recorded. [Build instructions](../README.md#build-verify-contribute). | Covered for the documented release-date check; repeat dependency freshness checks when preparing a new release. |
| One-shot installation with automatic missing dependencies | Installer downloads and verifies a private JRE/JDK 25 as needed. Eighteen installer cases include actual runtime download, rollback, repair and records preservation. [Installation evidence](INSTALLATION.md#installer-verification). | Resolved: downloader/hash alternatives and native package-manager bootstrap now handle missing utilities on supported systems. The installer review exercises the missing-tool branches with isolated fixtures. |
| First-use source/portable launch without manual Java setup | Source and extracted-release launchers locate Java 25; the source launcher builds with the wrapper. The installer can supply Java. | Resolved: first launch bootstraps private Java when needed and reuses it afterward. Real isolated no-Java source/release checks passed; explicit invalid user overrides remain useful errors. |
| Application launcher and recognizable icon | Original orange/cream/teal PNG and macOS ICNS are packaged. Linux desktop entry was used to start the real game. macOS bundle/plist generation is tested. [Launcher behavior](INSTALLATION.md). | Linux is covered. Native macOS Finder/Terminal/Dock interaction is a platform verification gap, not proved by Linux bundle generation. |
| Useful entry points and clear README | README starts with install/play; source executable, installed command, Linux menu, macOS app, CLI help and editor play task exist. Documentation is copied into installed builds; links are tested. | Covered paths should remain synchronized after onboarding changes. The editor play task delegates to the same source launcher, so its missing-Java behavior is the same gap. |
| Updates and offline play preserve the experience | Existing installation survives rejected JAR/icon/checksum cases; records stay outside the replaced app directory. Installed game does not require the source checkout. | Resolved: live installed repair and source-JAR rewrite checks passed; the source launcher snapshots its JAR for each run. Network-denied installed startup also passed below. |
| Parallel adversarial review, clean evidence and honest limits | Separate gameplay/input, installer and review work; isolated profiles/prefixes; executable hashes; retained real-PTY tooling and curated frames. [Reproduction commands](VERIFICATION.md#reproduce-from-a-source-checkout). | Preserve these checks after fixes. A green build is insufficient; neither all-platform verification nor unmeasured performance should be implied. |
| Public repository and usable release | [Public source](https://github.com/samsaw123456/turbotides-tui) and [v0.1.0 release](https://github.com/samsaw123456/turbotides-tui/releases/tag/v0.1.0) provide sources and the packaged installer/assets. | Release packaging and its README must be refreshed together if behavior changes. |

## Peer findings used as adversarial test ideas

These are reports by the assistants working on the other games, not additional
user instructions and not independently reproduced findings about Turbo Tides
TUI. They identify concrete checks worth carrying across projects.

| Session, report time | Reported failure or lesson | Check here |
| --- | --- | --- |
| Build a Phippy game, November 15 at 08:31 | Hovering one route changed focus, but Enter started the previously selected route. | Displayed route, focus, preview and activated circuit must agree. This TUI has no mouse menu; check every keyboard selector. |
| Build a Phippy game, November 15 at 08:11–08:19 | A normal desktop session had low frame rates despite earlier checks; measured gameplay was needed. | Measure actual terminal update rate and process use, including large windows and static screens. Do not infer performance from the configured tick interval. |
| Build Kotlin memory game, November 15 at 07:39 | Title help advertised shortcuts that only worked after starting. | Reconcile help/footer promises with applicable states and the control inventory. |
| Build Kotlin memory game, November 15 at 07:40 and 08:16 | Runtime isolation exposed a launcher Ctrl+C regression; Ctrl+Z freezes, terminal restoration and rebuilds disrupting live games needed fixes. | Probe Ctrl+C/interrupt cleanup, job control, live upgrade, source rebuild and offline installed launch through a real terminal. |
| Build Emberwood TUI game, November 15 at 08:18 | Backslashes in installation paths broke checksum parsing. | Keep filename escaping and hostile-but-valid path cases in installer tests. |
| Build Emberwood TUI game, November 15 at 08:22 | Static screens did unnecessary work despite acceptable gameplay updates. | Compare garage/help/pause CPU with racing CPU and remove repeated expensive work if measurements justify it. |
| Build Emberwood TUI game, November 15 at 08:28 | Ctrl+C exited before the audit observer wrote its acknowledgement. | Assert process exit and terminal restoration directly; an observer timeout is not evidence the game failed to quit. |

The history review itself did not execute new gameplay or installer tests. The
follow-up runtime checks below exercise the review's concrete findings; the
executable-specific reports retain the actual results and unresolved limits.

## Dependency freshness recheck

On November 15, the follow-up checked the primary release sources again:
[Kotlin 2.4.21](https://kotlinlang.org/docs/releases.html),
[Gradle 9.9.1](https://gradle.org/releases/),
[tui4j 0.3.5](https://repo.maven.apache.org/maven2/com/williamcallahan/tui4j/maven-metadata.xml),
[ktlint Gradle plugin 14.2.0](https://plugins.gradle.org/m2/org/jlleitschuh/gradle/ktlint/org.jlleitschuh.gradle.ktlint.gradle.plugin/maven-metadata.xml)
and [Temurin 25.0.5+8](https://api.adoptium.net/v3/assets/latest/25/hotspot?architecture=x64&image_type=jre&os=linux&vendor=eclipse).
Kotlin's [compatibility table](https://kotlinlang.org/docs/gradle-configure-project.html)
lists Gradle 9.7.0 as the upper fully supported version for Kotlin 2.4.21, while
permitting newer releases with caveats. The requested current Gradle 9.9.1
combination passed this project's actual checks; those results do not expand
the vendor's stated support range. This distinction also appeared in the memory
game session's November 15, 08:16 dependency review.

The original `Race.kt` and `Track.kt` remain byte-identical to the original
game's current files. Linux and macOS CI builds, regression tests and real-PTY
smoke runs passed; this does not establish native macOS Finder/Dock/audio or
manually tested ARM hardware behavior.

## Measured runtime follow-up

The retained [runtime audit](https://github.com/samsaw123456/turbotides-tui/blob/main/tools/runtime_audit.py) starts real PTYs, sends
normal player keys and captures the actual ANSI output. Timed samples read Java
CPU and RSS from Linux `/proc`, count tui4j's completed redraw markers, and drain
output before decoding it into inspected frames. No game speed, physics, state
or user records are changed. Java runs with the launcher's `-Xms32m -Xmx384m`.
Read-only telemetry remains enabled, so these numbers include its overhead.

The host is an Intel i7-10610U with eight logical CPUs, running Linux x86-64.
Other user sessions were building and playing games throughout the checks;
one-minute load averages around 25–27 exceeded the available logical CPUs.
These are short, loaded-host observations, not a quiet-machine benchmark or a
guarantee for another computer. CPU percentages use **one logical core** as
100%; RSS includes JVM memory outside the Java heap.

The `v0.1.0` baseline showed 12.6–21.3% CPU on static screens despite sending no
new terminal output. A static-view cache was therefore justified by measurement.
At 100×34 the baseline raced at 29.54 completed redraws/second; at 180×65 it
managed 7.84. The unchanged racing path in the cache-only build still produced
7.71 at the larger size, so further work was based on profiling.

A Java Flight Recorder profile of the cache-only build captured 654 execution
samples. Of those, 543 were on `tui4j-Renderer-Thread`; 372 sampled stacks included
`GraphemeCluster.getFirstGraphemeCluster`, 350 included `StringWidth.stringWidth`,
and 159 included ICU `RuleBasedBreakIterator.next`. Only 24 included the game's
`TerminalRenderer.render`. Counts overlap when methods occur in the same stack.
This locates the main cost in terminal Unicode width processing, supporting the
small change to emit a background-colored ASCII space when both halves of a
painted cell have the same color. Its appearance must be checked against the
baseline frames; it changes neither geometry nor physics.

Raw profiles, decoded captures, hashes and measurements remain under
`build/ansi-audit/runtime*`. The baseline executable was preserved separately at
`build/runtime-baseline/turbotides-tui.jar` with SHA-256
`0fb51303f953457b92d44ce4b04ce1698f6d3530fe4ddcebebb90dc108878c61`.
The early baseline response timings included Python decoding and are not engine
input-latency measurements. The updated tool records receipt of a completed ANSI
response separately from the later decoded-frame assertion; both still include
host scheduling and PTY transport.

The installed baseline also started from `/tmp`, drove, paused, retried and quit
with Linux `strace` denying `connect`, `sendto` and `sendmsg`. An independent
socket attempt failed with injected `ENETUNREACH`, confirming that the denial was
active. Namespace-based network isolation was unavailable on this host; syscall
denial was the exercised alternative. This verifies offline play after installation,
not downloading dependencies or a release while offline.

### Optimized-build runtime measurements

All eight optimized-build samples ran for eight seconds on executable SHA-256
`9d1e428433d6d92a421682f9b8ce64db30137e19522605f6d4de2d893008a1e2`.
The optimized run's host load rose to 26–38. Treat before/after numbers as observations
under changing shared load, not a controlled speedup claim.

| Terminal / scene | CPU before → final (% of one core) | Final RSS (MiB) | Redraws/s before → final | Completed response (ms) |
| --- | ---: | ---: | ---: | ---: |
| 100x34 garage | 21.3 → 10.1 | 97.3 | 0.00 → 0.00 | 224.6 |
| 100x34 help | 20.5 → 9.8 | 94.7 | 0.00 → 0.00 | 152.5 |
| 100x34 paused | 15.1 → 9.1 | 111.7 | 0.00 → 0.00 | 48.0 |
| 100x34 racing | 46.0 → 40.6 | 204.5 | 29.54 → 23.61 | 28.1 |
| 180x65 garage | 19.9 → 9.4 | 95.0 | 0.00 → 0.00 | 441.2 |
| 180x65 help | 21.3 → 9.9 | 106.8 | 0.00 → 0.00 | 157.6 |
| 180x65 paused | 12.6 → 8.6 | 152.9 | 0.00 → 0.00 | 34.8 |
| 180x65 racing | 51.1 → 47.3 | 227.2 | 7.84 → 11.35 | 8.8 |

The table's “final” column refers to this renderer/performance candidate. A later
diagnostic-file cleanup fix required another executable; the final-build checks
are identified separately rather than attributing these timings to a different
JAR.

Static screens correctly produce zero redraws while unchanged. The one measured
response in each scene was Right to select a new circuit in the garage, Esc to
close help, or Enter to resume after pause. These are single samples, not latency
percentiles. Completed ANSI output is timestamped before Python decodes and
asserts the expected visible screen. The 180×65 final race's maximum observed
redraw gap was 170 ms; the comfortable 100×34 viewport remains preferable on a
busy machine. There is no claim that every hardware/terminal combination sustains
40 redraws per second.

Both 100×34 and 180×65 final garage captures are **pixel-for-pixel identical** to
the corresponding baseline captures. The final eight-scene montage and the full
180×65 racing frame were inspected: track, cars, colors, pause/help overlays and
footer remain intact. The pixel comparison is retained in
`build/ansi-audit/runtime-final/pixel-comparison.json`.

Reproduce the measurements on Linux with the audit dependencies installed and
`TURBOTIDES_JAVA_HOME` pointing at Java 25:

```sh
python3 tools/runtime_audit.py --group performance --seconds 8
python3 tools/runtime_audit.py --group job-control
python3 tools/runtime_audit.py --group offline --installed-app ~/.local/bin/turbotides-tui
```

For a focused JFR recording, use Java 25 and run:

```sh
JAVA_TOOL_OPTIONS='-XX:StartFlightRecording=filename=/tmp/turbotides-runtime.jfr,settings=profile,dumponexit=true' \
  python3 tools/runtime_audit.py --group performance --scene racing --size 180x65
```

Use `--jar PATH` and `--output-dir PATH` to compare preserved builds without
rebuilding either artifact. `--scene` and `--size` select focused measurements.
The offline check requires `strace`; timing and job-control checks use Linux
`/proc` and a real PTY.

### Additional terminal and installed-launch checks

On the same `9d1e4284…` executable, physical Ctrl+Z was sent separately in the
garage, countdown, racing, pause and help, with the game running as an interactive
Bash foreground job. It is an unbound key: all five checks passed, no process
suspended, racing visibly continued, and the static screens stayed pixel-identical.
Each process then quit through Q with exit status zero, restoring the alternate
screen and focus-reporting modes. A sixth no-Ctrl+Z control tested the same quit
path. Before/after ANSI-derived images were inspected.

Linux `stty -g` was captured before and after each shell-launched game. Input,
output and local flags, control characters, and non-baud control flags matched.
PTY baud bits changed (`c_cflag` from `f00bf` to `b0`), also in the no-Ctrl+Z
control. Shell commands continued to work. Exact byte-for-byte restoration of
all terminal attributes is therefore **not** claimed, nor is Ctrl+Z suspension
offered as a game command. Results and captures are retained in
`build/ansi-audit/runtime-final/job-control.json` and its adjacent scene folders.

The current installer created a separate installation containing the optimized
candidate under `build/ansi-audit/runtime-final-install/`. Its installed command
passed startup, driving, pause, retry, Q and ANSI cleanup with network syscalls
denied, using an isolated profile from working directory `/tmp`. The installed
JAR hash matched `9d1e4284…`. The first run's observer checked the telemetry file
too soon after Escape; the actual captured output already showed pause. Waiting
for the reported phase and visible overlay resolved the observer race, and the
unchanged game passed the repeated check. The successful report is
`build/ansi-audit/runtime-final/offline.json`.

### Final executable recheck

After the diagnostic-file fix, the final JAR was
`fc5734af39bcc17ac9c91758a7518b612168860558dbce09546b0c112627a490`.
The renderer source stayed unchanged. The earlier candidate JAR was not retained,
so byte-identical renderer classes across those two artifacts are not asserted.
The eight-sample table remains explicitly tied to `9d1e4284…`.

A fresh eight-second 100×34 racing sample on the final executable produced
**32.21 completed redraws/second**, 61.8% of one CPU, and 202.4 MiB maximum RSS,
with host load around 24. The largest observed redraw gap was 66 ms. The single
resume response completed its ANSI output after 37 ms; Python's subsequent
visible-frame assertion finished after 187 ms. These are the same short-sample
limitations as the preceding table. The actual racing frame was inspected.

All five Ctrl+Z contexts and the no-key quit control passed again on the final
JAR, with the same documented baud-bit difference. A fresh isolated installation
of the final JAR passed the network-denied startup/drive/pause/retry/quit sequence,
including visible pause and restored ANSI modes. The installed launcher, Java
helper and installer matched the then-tested repository files byte-for-byte. Final
100×34 garage pixels matched the original baseline exactly. Final evidence is
under `build/ansi-audit/runtime-release/`.

## Follow-up resolutions

| Finding | Result and verification |
| --- | --- |
| Missing system utilities and terminals | Installer selects curl/wget and available SHA-256 tools; missing packages use supported native managers. Graphical Linux gets a terminal fallback if needed, while headless installs stay command-only. Package-manager tests use isolated fixtures rather than changing the host. |
| Java missing on first launch | Source and extracted-release launchers install private Java on demand, preserve explicit override errors, and reuse the private JDK/runtime. Real no-Java first/second-launch tests passed, including a cold source build. Supported OS/package-manager limits are documented. |
| Running source game disrupted by a rebuild | Source launch takes a temporary JAR snapshot. Rewriting the build JAR no longer breaks the running race; quit, Ctrl+C, SIGTERM and invalid-option tests check status and cleanup. Installed live repair also passed. |
| Failed personal-best save silently lost | Pending records remain available for a later successful save, including settings changes after a repaired profile directory. Regression tests and actual finish/save/reopen checks cover recovery. |
| Diagnostic writes clobbering a sibling or retaining an old warning | Diagnostic output uses a unique temporary file with cleanup, preserves an unrelated `FILE.tmp`, and clears its error when writes recover. Regression tests and a direct terminal recovery audit cover the failure path. |
| Static-screen CPU and slow large redraws | Static views are cached with state/input/error invalidation. Uniform half-block cells become visually identical background-colored spaces, reducing the measured Unicode-width hotspot. Profiling, eight-scene measurements and independent image comparisons are retained above. |
| Missing HTTPS trust on minimal Linux | Package metadata confirmed CA roots are only recommended by downloader packages. The installer now detects a missing trust store and requests `ca-certificates`, preserving explicit certificate overrides. An isolated namespace reproduced certificate error 77 before restoration and successful HTTPS afterward. No host trust or packages changed. |
| Onboarding, launch paths and evidence drifting apart | README and installation notes describe automatic setup, source/portable/installed entry points, graphical versus headless behavior, updates, removal and real platform limits. The final installer review records 46 test methods and 39 Kotlin regressions pass with lint/build checks. See [installation evidence](INSTALLATION.md#installer-verification) and the [final gameplay verification](VERIFICATION.md). |

The native macOS GUI/audio and physical-speaker limits remain unverified here.
Performance figures remain hardware-, terminal- and workload-specific. These
limits are not hidden behind a blanket “everything tested” claim.
