# Credits and licenses

- Original Turbo Tides race rules, track geometry, palette, icon, and generated
  WAV audio: [Turbo Tides](https://github.com/samsaw123456/turbo-tides), Apache-2.0.
  Race.kt and Track.kt preserve the original simulation. Terminal rendering,
  input adaptation, and packaging are part of this repository's Apache-2.0 code.
- Phippy and Goldie pixel art: Tingsters,
  [Phippy Gaming Workshop](https://github.com/Tingsters/Phippy-Gaming-Workshop),
  originally [PhippyRescue](https://github.com/Tingsters/PhippyRescue), MIT.
  The original files and [MIT notice](https://github.com/samsaw123456/turbotides-tui/blob/main/src/main/resources/art/PhippyRescue-MIT.txt)
  are bundled unchanged (`art/PhippyRescue-MIT.txt` inside the game JAR). Phippy and friends are CNCF characters; this independent
  game does not imply CNCF or Linux Foundation endorsement.
- [tui4j](https://github.com/WilliamAGH/tui4j): William Callahan and contributors,
  MIT; derived from Łukasz Grabski's Latte and inspired by Charm's Bubble Tea.
- [Kotlin](https://github.com/JetBrains/kotlin): JetBrains, Apache-2.0.
- [JLine](https://github.com/jline/jline3): BSD-3-Clause.
- [ICU4J](https://github.com/unicode-org/icu): Unicode license.
- [Apache Commons Text](https://commons.apache.org/proper/commons-text/) and
  [Commons Lang](https://commons.apache.org/proper/commons-lang/): Apache-2.0.
- [Gradle wrapper](https://github.com/gradle/gradle): Apache-2.0.
- Optional downloaded [Eclipse Temurin](https://adoptium.net/): OpenJDK GPLv2
  with Classpath Exception and bundled third-party notices. Runtime legal files
  remain with the private runtime. Java is downloaded from Adoptium, not shipped
  inside this repository.

The TUI uses your terminal's font; the original game's TrueType fonts and
OpenGL/libGDX libraries are not needed. The original editable SVG is retained
alongside PNG and macOS ICNS launcher exports. Dependency notices also remain
in the executable JAR's META-INF entries; additional notices are bundled under
`licenses/`.
