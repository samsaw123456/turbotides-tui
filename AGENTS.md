# Turbo Tides TUI

Keep the original Turbo Tides repository untouched. Race.kt and Track.kt are the
authoritative rules and geometry; terminal input and rendering adapt to them.
The requested four AI difficulties extend the original rival behavior; preserve
the player's original physics and track geometry. Easy/Medium/Hard/Super Hard
must differ observably in real races, and Super Hard must remain beatable with
skilled normal input. Preserve orange, cream, teal and licensed art/audio.

Use JDK 25. Run `./gradlew ktlintFormat check fatJar` after Kotlin changes.
Run `tools/ansi_audit.py` through a real PTY after input/rendering changes;
inspect its ANSI-derived frames, not just diagnostics. Document every binding
and state in docs/VERIFICATION.md. Steering must move visibly screen-left/right
in the forward view; rear view is deliberately mirrored and labelled.

Ordinary ANSI has no key release events: throttle/brake and drift/boost/rear view
are explicit modes; steering pulses expire. Never pretend these are physical
key releases. Focus loss clears modes and pauses when the terminal reports it.
Keep test records isolated with `--data-dir`. Never speed up or mutate physics
for an audit. Installer tests must use isolated prefixes.
