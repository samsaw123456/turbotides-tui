# Install and launch

The one-shot installer uses a per-user directory and leaves your system Java
and shell configuration alone. It supports Linux (glibc) and macOS on x86-64
and ARM64. The game itself needs Java 25; no compiler, Gradle, Python, Node,
package manager, or administrator password is required for a published release.

```sh
curl -fsSL https://raw.githubusercontent.com/samsaw123456/turbotides-tui/main/install.sh -o /tmp/turbotides-install.sh
sh /tmp/turbotides-install.sh
~/.local/bin/turbotides-tui
```

The installer downloads the latest GitHub release, checks its SHA-256 against
the release's `SHA256SUMS`, and selects an existing Java 25 runtime. If none is
available, it downloads a private Eclipse Temurin runtime for your OS and CPU,
verifies the checksum from Adoptium's HTTPS API, and keeps it inside the game
directory. Java updates are never installed globally. The download needs
`curl`, `tar`, standard Unix utilities, and either `sha256sum` or `shasum`.
If a basic OS utility is missing, the installer names it and exits without
changing an existing installation. The built game works offline.

Use `sh /tmp/turbotides-install.sh --private-java` to always download the latest
Java 25 patch release into the game, even if your system already has Java 25.
The launcher prefers this private runtime; rerun with the same option to update
it. `TURBOTIDES_JAVA_HOME` remains an explicit launcher override.

Linux gets **Turbo Tides TUI** in the application menu, with the original orange,
cream, and teal Turbo Tides icon; the desktop entry opens your configured
terminal. macOS gets `~/Applications/Turbo Tides TUI.app`, which opens the game
in Terminal.app. Drag that app to your Dock to keep it there. A terminal that
supports true color and Unicode gives the best rendering.

The default game location is `${XDG_DATA_HOME:-~/.local/share}/turbotides-tui/app`;
records stay in its parent `turbotides-tui` directory, outside app upgrades.
the command symlink lives in `~/.local/bin`. Rerun the installer to update or
repair the app. It refuses to replace directories and commands it does not own.
`--prefix /absolute/path` and `--bin-dir /absolute/path` customize the locations;
`--no-desktop` skips desktop integration. These options are useful on servers
and in isolated tests. `TURBOTIDES_JAVA_HOME` selects a particular Java 25
installation and is validated before use.

## Source checkout and extracted releases

```sh
./install.sh --local            # build, check, and install this checkout
./turbotides-tui                # build and play directly from the checkout
```

When installing a checkout, the installer selects or downloads a full JDK 25,
then runs the checked-in Gradle wrapper's `check fatJar` tasks. When installing
an extracted release, `./install.sh --local` uses its already built JAR.
`./turbotides-tui` is also a portable launcher inside the extracted release,
provided Java 25 is installed. Both launchers work outside their own directory
and with paths containing spaces.

To remove an installation, run the installer with the same location options:

```sh
sh /tmp/turbotides-install.sh --uninstall
```

This removes the managed game, command, and application launcher. Saved race
records are preserved. The installer never changes your default terminal or
Java installation.

## Release packaging

```sh
./gradlew check fatJar
python3 tools/package_release.py --skip-build
```

Upload `dist/turbotides-tui-<VERSION>.tar.gz` and `dist/SHA256SUMS` together to a
GitHub release tagged `v<VERSION>`. The universal archive contains the executable
JAR, launchers, icon assets, and notices. Runtime selection happens at install
time, so a single release serves all four supported OS/CPU combinations.

Linux installation and launcher validation are exercised locally. macOS app
generation can be syntax-checked on Linux; actual Finder, Terminal, Dock, and
Apple Silicon behavior requires a macOS machine and is not claimed verified.

## Installer verification

```sh
python3 -m unittest tools.test_install -v
# Optional integration checks: downloads Java and briefly opens a real terminal.
TURBOTIDES_TEST_DOWNLOAD=1 TURBOTIDES_TEST_DESKTOP=1 python3 -m unittest tools.test_install -v
shellcheck -x install.sh turbotides-tui scripts/java.sh
ruff check tools/package_release.py tools/test_install.py
```

All 18 installer cases passed on Linux, including a real Temurin 25.0.5 download,
starting the installed game through `gio launch` and the generated desktop
entry, paths with spaces and reserved characters, repair, uninstall, and preservation of race records.
Invalid JARs, missing icons, bad release checksums, unrelated files, and symlink
destinations are rejected without replacing the existing app. The macOS test
exercises bundle creation and validates its plist and shell syntax on Linux;
it does not run macOS applications. Default test runs skip the two opt-in network
and graphical-desktop checks.
