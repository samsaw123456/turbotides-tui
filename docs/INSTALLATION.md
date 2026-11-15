# Install and launch

The one-shot installer uses a per-user directory and leaves your system Java
and shell configuration alone. It supports Linux (glibc) and macOS on x86-64
and ARM64. The game needs Java 25. A published release needs no compiler,
Gradle, Python, or Node. Java is downloaded privately when needed; missing OS
utilities are installed through your native package manager, which may request
your administrator password.

```sh
curl -fsSL https://raw.githubusercontent.com/samsaw123456/turbotides-tui/main/install.sh -o /tmp/turbotides-install.sh
sh /tmp/turbotides-install.sh
~/.local/bin/turbotides-tui
```

The installer downloads the latest GitHub release, checks its SHA-256 against
the release's `SHA256SUMS`, and selects an existing Java 25 runtime. If none is
available, it downloads a private Eclipse Temurin runtime for your OS and CPU,
verifies the checksum from Adoptium's HTTPS API, and keeps it inside the game
directory. Java updates are never installed globally. The built game works
offline after installation.

The installer uses existing `curl` or `wget`, `tar`, standard Unix utilities,
and `sha256sum`, `shasum`, or OpenSSL. If a required utility is absent, it installs
only the missing packages with apt, dnf, yum, pacman, zypper, or an existing
Homebrew installation. Linux elevation uses root, `sudo`, or `doas` only when a
package is missing. Linux also checks for a readable, nonempty standard CA
certificate store and installs `ca-certificates` when none exists; downloader
packages may only recommend it, so installing curl alone is insufficient on a
minimal system. Explicit `CURL_CA_BUNDLE`, `SSL_CERT_FILE`, or `SSL_CERT_DIR`
settings are preserved. Certificate verification stays enabled, and failure to
provide a trust store stops installation. macOS keeps its native trust store.
An existing working machine needs no administrator prompt.
Package-manager failures stop before the game is replaced and explain the
missing requirement. The installer never runs a Homebrew installation script:
a damaged macOS base installation without Homebrew must have its missing OS
utilities restored first. Linux needs a glibc distribution and one of the listed
package managers if utilities are missing.

If `curl` is absent before downloading the installer, use
`wget -O /tmp/turbotides-install.sh https://raw.githubusercontent.com/samsaw123456/turbotides-tui/main/install.sh`,
or save `install.sh` from GitHub in your browser, then run it with `sh`. The
installer itself can bootstrap a missing downloader once the script is local.

Use `sh /tmp/turbotides-install.sh --private-java` to always download the latest
Java 25 patch release into the game, even if your system already has Java 25.
The launcher prefers this private runtime; rerun with the same option to update
it. `TURBOTIDES_JAVA_HOME` remains an explicit launcher override.

Linux gets **Turbo Tides TUI** in the application menu, with the original orange,
cream, and teal Turbo Tides icon; the desktop entry opens your configured
terminal. In a graphical Linux session without a terminal emulator, the
installer adds `xterm` as a fallback. With neither a graphical session nor a
terminal emulator, it installs the command only and explains how to add the icon
by rerunning from a desktop session. `--no-desktop` always skips GUI dependencies.
macOS gets `~/Applications/Turbo Tides TUI.app`, which opens the game
in Terminal.app. Drag that app to your Dock to keep it there. A terminal that
supports true color and Unicode gives the best rendering.

The default game location is `$XDG_DATA_HOME/turbotides-tui/app` when
`XDG_DATA_HOME` is absolute; otherwise it is `~/.local/share/turbotides-tui/app`.
Empty and relative XDG values are ignored, matching the game's record storage.
Records stay in the parent `turbotides-tui` directory, outside app upgrades.
The command symlink lives in `~/.local/bin`. Rerun the installer to update or
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
`./turbotides-tui` is also a portable launcher inside the extracted release.
If Java 25 is missing, it automatically runs the bundled installer, then starts
the installed game with your original arguments. A source checkout similarly
bootstraps a full JDK if only a JRE or no Java is available. Later source launches
reuse that private JDK. This direct command installs without desktop integration;
use `./install.sh --local` for the icon. Installed copies retain the installer and
their custom command location so a later missing runtime can be repaired
automatically. An invalid explicit `TURBOTIDES_JAVA_HOME` is reported instead of
silently ignored. A source launch copies only the built JAR into a temporary
private directory so rebuilding the checkout cannot change a running game's
classes and assets. The copy is removed on normal quit, Ctrl+C, termination, or
startup errors. Installed launches use the installed JAR directly.
Both launchers work outside their own directory and with paths containing
spaces, quotes, backslashes, dollar signs, backticks, and percent signs.

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
python3 -m pip install -r tools/audit-requirements.txt
python3 -m unittest tools.test_install -v
# Optional integration checks: downloads Java and briefly opens a real terminal.
TURBOTIDES_TEST_DOWNLOAD=1 TURBOTIDES_TEST_DESKTOP=1 python3 -m unittest tools.test_install -v
# Linux + bubblewrap: hide host Java, download JRE/JDK, build in fresh isolated home.
TURBOTIDES_TEST_FIRST_USE=1 python3 -m unittest tools.test_install.InstallerTest.test_real_no_java_release_first_and_second_launch tools.test_install.InstallerTest.test_real_no_java_source_first_and_second_launch -v
shellcheck -x install.sh turbotides-tui scripts/java.sh
ruff check tools/package_release.py tools/test_install.py
```

The installer suite covers missing utilities and graphical terminals with
recording package-manager fixtures, elevation dispatch, download/hash alternatives,
first-use launch and repair, XDG fallbacks, and a live game surviving an install
repair before entering a race. A separate source-launch test rewrites the build
JAR while playing; the race continues from its private copy. Quit, Ctrl+C,
SIGTERM, and invalid-option exit paths verify cleanup and exit statuses.
Fixtures deliberately strip `PATH` and prevent
all real host package changes. Download verification also uses a `TMPDIR` with a
backslash, exercising GNU checksum filename escaping.

Integration checks include a real Temurin 25.0.5 download, starting the installed
game through `gio launch` and its generated desktop entry, reserved characters
in paths, repair, uninstall, and preservation of race records.
Invalid JARs, missing icons, bad release checksums, unrelated files, and symlink
destinations are rejected without replacing the existing app. The macOS test
exercises bundle creation and validates its plist and shell syntax on Linux;
it does not run macOS applications. Default test runs skip the opt-in real
runtime download, graphical desktop, and two no-Java first-use checks. The
first-use checks use Linux mount namespaces to hide the host's Java without
changing it, and verify that second launches reuse the private runtime.

On November 15, 2026, all 46 installer test methods passed across the suite and
focused integration runs. The final JAR
`fc5734af39bcc17ac9c91758a7518b612168860558dbce09546b0c112627a490`
passed installed repair while running, source-JAR rewrite while running, and
source-launch quit/interrupt/termination/error checks. Q returned 0, Ctrl+C
returned 130 through the source wrapper, SIGTERM returned 143, and an invalid
option returned 2; each restored the terminal and removed the temporary JAR.
The real cold source installation downloaded Java and Gradle, passed
`check fatJar`, and reused the private JDK on a second launch. The source snapshot
for that cold build preceded the final diagnostic-file change; final launch
checks used the exact JAR above. Detailed local logs and ANSI-derived frames
are retained under `build/installer-audit/`.

The CA dependency check was confirmed against local `apt-cache depends` output
and Debian's [wget](https://packages.debian.org/trixie/wget) and
[libcurl](https://packages.debian.org/trixie/libcurl4t64) package metadata:
`ca-certificates` is recommended, rather than required. Four isolated cases
cover missing/existing stores, preserving each explicit custom TLS setting,
and rejecting a package-manager success that still leaves no store.
A Linux mount-namespace check also hid the real system stores: curl failed
with certificate error 77, the installer requested only `ca-certificates`, and
HTTPS succeeded after a recording package-manager fixture restored the real
distro bundle inside the namespace. Host certificates and packages were
unchanged; the result is retained in `build/installer-audit/certificates.json`.
