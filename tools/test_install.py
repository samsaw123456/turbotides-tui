"""Exercise installation, desktop files, repair, launch, and safe removal."""

import hashlib
import importlib.util
import json
import os
import plistlib
import shlex
import shutil
import signal
import subprocess
import tarfile
import tempfile
import termios
import time
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="turbotides-package-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.release = self.root / "release with spaces"
        self.release.mkdir()
        for name in ("install.sh", "turbotides-tui"):
            shutil.copy2(ROOT / name, self.release / name)
        shutil.copytree(ROOT / "scripts", self.release / "scripts")
        shutil.copytree(ROOT / "assets", self.release / "assets")
        jar = ROOT / "build/libs/turbotides-tui.jar"
        if not jar.is_file():
            self.fail("Build the actual game first: ./gradlew check fatJar")
        shutil.copy2(jar, self.release / "turbotides-tui.jar")
        self.prefix = self.root / "game with spaces"
        self.bin = self.root / "bin with spaces"
        self.data = self.root / "desktop data"
        home = self.root / "isolated home"
        home.mkdir()
        self.env = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(self.data))
        self.env.pop("TURBOTIDES_JAVA_HOME", None)
        for name in ("CURL_CA_BUNDLE", "SSL_CERT_FILE", "SSL_CERT_DIR"):
            self.env.pop(name, None)
        self.java = Path(
            subprocess.check_output(
                [
                    "sh",
                    "-c",
                    '. "$1"; find_java_25; printf "%s" "$TURBOTIDES_JAVA"',
                    "sh",
                    str(ROOT / "scripts/java.sh"),
                ],
                env=self.env,
                text=True,
            )
        ).resolve()
        # A test must never install packages on the host, including headless CI.
        guard = self.root / "host-package-guard"
        guard.mkdir()
        for manager in (
            "apt-get",
            "dnf",
            "yum",
            "pacman",
            "zypper",
            "brew",
            "sudo",
            "doas",
        ):
            tool = guard / manager
            tool.write_text(
                "#!/bin/sh\nprintf 'Unexpected host package-manager call\n' >&2\nexit 99\n"
            )
            tool.chmod(0o755)
        if not any(
            shutil.which(name)
            for name in ("gnome-terminal", "xterm", "x-terminal-emulator", "konsole")
        ):
            terminal = guard / "xterm"
            terminal.write_text("#!/bin/sh\nexit 0\n")
            terminal.chmod(0o755)
        self.env["PATH"] = str(guard) + os.pathsep + os.environ["PATH"]

    def limited_path(
        self, missing=(), manager="apt-get", root=True, desktop=True, platform="Linux"
    ):
        """Real utilities + a recording package-manager fixture, no host mutations."""
        directory = self.root / "limited-path"
        directory.mkdir()
        utilities = (
            "sh",
            "uname",
            "tar",
            "gzip",
            "sed",
            "awk",
            "mktemp",
            "grep",
            "env",
            "head",
            "dirname",
            "readlink",
            "mkdir",
            "cp",
            "mv",
            "rm",
            "rmdir",
            "ln",
            "chmod",
            "cat",
            "id",
            "curl",
            "wget",
            "sha256sum",
            "shasum",
            "openssl",
        )
        for name in utilities:
            actual = shutil.which(name)
            if actual and name not in missing and name not in ("id", "uname"):
                (directory / name).symlink_to(actual)
        for name, body in {
            "id": f"printf '%s\n' {'0' if root else '1000'}",
            "uname": f"case $1 in -s) echo {platform};; -m) echo x86_64;; esac",
        }.items():
            tool = directory / name
            tool.write_text("#!/bin/sh\n" + body + "\n")
            tool.chmod(0o755)
        if desktop:
            terminal = directory / "xterm"
            terminal.write_text("#!/bin/sh\nexit 0\n")
            terminal.chmod(0o755)
        self.env["PATH"] = str(directory)
        self.env.pop("DISPLAY", None)
        self.env.pop("WAYLAND_DISPLAY", None)
        # Use a known working JDK without depending on java being in stripped PATH.
        self.env["TURBOTIDES_JAVA_HOME"] = str(self.java.parent.parent)
        log = self.root / "package-manager.log"
        self.env["PACKAGE_TEST_LOG"] = str(log)
        if manager:
            tool = directory / manager
            operations = [
                "#!/bin/sh",
                "set -eu",
                'printf \'%s\\n\' "$*" >> "$PACKAGE_TEST_LOG"',
            ]
            for name in missing:
                actual = shutil.which(name)
                if actual:
                    operations.append(
                        f"{shlex.quote(shutil.which('ln'))} -sf {shlex.quote(actual)} {shlex.quote(str(directory / name))}"
                    )
            if not desktop:
                operations.append(
                    f"{shlex.quote(shutil.which('ln'))} -sf {shlex.quote(shutil.which('true'))} {shlex.quote(str(directory / 'xterm'))}"
                )
            tool.write_text("\n".join(operations) + "\n")
            tool.chmod(0o755)
        return directory, log

    def install(self, *args, expected=0):
        result = subprocess.run(
            [
                "sh",
                str(self.release / "install.sh"),
                "--local",
                "--prefix",
                str(self.prefix),
                "--bin-dir",
                str(self.bin),
                *args,
            ],
            env=self.env,
            cwd=self.root,
            text=True,
            capture_output=True,
            timeout=90,
            check=False,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_automatic_missing_utilities_with_apt(self):
        directory, log = self.limited_path(
            missing=("curl", "wget", "tar", "sha256sum", "shasum", "openssl", "awk")
        )
        self.install("--no-desktop")
        calls = log.read_text().splitlines()
        self.assertEqual(
            calls,
            ["update", "install -y --no-install-recommends curl tar gawk coreutils"],
        )
        self.assertTrue((directory / "tar").is_symlink())
        self.assertTrue((self.prefix / "turbotides-tui.jar").is_file())
        # No package-manager call is repeated once those utilities exist.
        self.install("--no-desktop")
        self.assertEqual(log.read_text().splitlines(), calls)

    def ca_store_fixture(self, install_bundle=True):
        directory, log = self.limited_path()
        system = self.root / "fixture system"
        bundle = system / "etc/ssl/certs/ca-certificates.crt"
        installer = self.release / "install.sh"
        # Relocate only the standard trust-store paths in this copied installer.
        # Package commands remain fixtures, so host certificates cannot change.
        script = installer.read_text()
        for prefix in ("/etc/ssl/", "/etc/pki/", "/var/lib/ca-certificates/"):
            script = script.replace(prefix, str(system) + prefix)
        # Quote rewritten paths because the fixture root deliberately has spaces.
        script = script.replace(str(system), shlex.quote(str(system)))
        installer.write_text(script)
        apt = directory / "apt-get"
        if install_bundle:
            apt.write_text(
                apt.read_text()
                + 'if [ "$1" = install ]; then\n'
                + f"  mkdir -p {shlex.quote(str(bundle.parent))}\n"
                + f"  printf 'fixture CA store\\n' > {shlex.quote(str(bundle))}\n"
                + "fi\n"
            )
        return bundle, log

    def test_missing_linux_ca_store_installs_certificate_package(self):
        bundle, log = self.ca_store_fixture()
        self.install("--no-desktop")
        self.assertEqual(
            log.read_text().splitlines(),
            ["update", "install -y --no-install-recommends ca-certificates"],
        )
        self.assertTrue(bundle.is_file())
        self.assertTrue((self.prefix / "turbotides-tui.jar").is_file())

    def test_existing_ca_store_needs_no_packages(self):
        bundle, log = self.ca_store_fixture()
        bundle.parent.mkdir(parents=True)
        bundle.write_text("existing store\n")
        self.install("--no-desktop")
        self.assertFalse(log.exists())
        self.assertEqual(bundle.read_text(), "existing store\n")

    def test_explicit_custom_certificate_settings_are_preserved(self):
        bundle, log = self.ca_store_fixture()
        for setting in ("CURL_CA_BUNDLE", "SSL_CERT_FILE", "SSL_CERT_DIR"):
            with self.subTest(setting=setting):
                self.env[setting] = str(self.root / "caller managed trust")
                self.install("--no-desktop")
                self.assertFalse(log.exists())
                self.assertFalse(bundle.exists())
                self.env.pop(setting)

    def test_missing_ca_store_after_package_success_stops_installation(self):
        self.install("--no-desktop")
        original = (self.prefix / "turbotides-tui.jar").read_bytes()
        self.ca_store_fixture(install_bundle=False)
        result = self.install("--no-desktop", expected=1)
        self.assertIn(
            "trusted CA certificate store is still unavailable", result.stderr
        )
        self.assertIn("HTTPS verification remains enabled", result.stderr)
        self.assertEqual((self.prefix / "turbotides-tui.jar").read_bytes(), original)

    def test_native_package_manager_commands_and_elevation(self):
        for manager, expected in (
            ("dnf", "install -y tar"),
            ("yum", "install -y tar"),
            ("pacman", "-S --needed --noconfirm tar"),
            ("zypper", "--non-interactive install tar"),
        ):
            with self.subTest(manager=manager):
                directory, log = self.limited_path(
                    missing=("tar",), manager=manager, root=False
                )
                sudo = directory / "sudo"
                sudo.write_text(
                    '#!/bin/sh\nprintf \'sudo %s\\n\' "$*" >> "$PACKAGE_TEST_LOG"\nexec "$@"\n'
                )
                sudo.chmod(0o755)
                self.install("--no-desktop")
                self.assertEqual(
                    log.read_text().splitlines(),
                    [f"sudo {manager} {expected}", expected],
                )
                shutil.rmtree(directory)
                log.unlink()

    def test_existing_download_and_checksum_alternatives_need_no_packages(self):
        _, log = self.limited_path(missing=("curl", "sha256sum", "shasum"))
        self.install("--no-desktop")
        self.assertFalse(log.exists())

    def test_missing_terminal_is_installed_only_for_graphical_session(self):
        _, log = self.limited_path(desktop=False)
        self.env["DISPLAY"] = ":fixture"
        self.install()
        self.assertIn("install -y --no-install-recommends xterm", log.read_text())
        self.assertTrue((self.data / "applications/turbotides-tui.desktop").exists())

    def test_headless_install_does_not_add_gui_packages(self):
        _, log = self.limited_path(desktop=False)
        result = self.install()
        self.assertIn("installing the command only", result.stdout)
        self.assertFalse(log.exists())
        self.assertFalse(self.data.exists())

    def test_no_desktop_does_not_add_terminal_packages(self):
        _, log = self.limited_path(desktop=False)
        self.env["DISPLAY"] = ":fixture"
        self.install("--no-desktop")
        self.assertFalse(log.exists())
        self.assertFalse(self.data.exists())

    def test_missing_manager_is_actionable_and_preserves_app(self):
        self.install("--no-desktop")
        original = (self.prefix / "turbotides-tui.jar").read_bytes()
        self.limited_path(missing=("tar",), manager=None)
        result = self.install("--no-desktop", expected=1)
        self.assertIn("No supported package manager", result.stderr)
        self.assertEqual((self.prefix / "turbotides-tui.jar").read_bytes(), original)

    def test_missing_elevation_is_actionable(self):
        _, log = self.limited_path(missing=("tar",), root=False)
        result = self.install("--no-desktop", expected=1)
        self.assertIn("requires root, sudo, or doas", result.stderr)
        self.assertFalse(log.exists())
        self.assertFalse(self.prefix.exists())

    def test_failed_package_install_does_not_replace_app(self):
        self.install("--no-desktop")
        original = (self.prefix / "turbotides-tui.jar").read_bytes()
        directory, _ = self.limited_path(missing=("tar",))
        (directory / "apt-get").write_text("#!/bin/sh\nexit 47\n")
        result = self.install("--no-desktop", expected=1)
        self.assertIn("package manager could not install", result.stderr)
        self.assertEqual((self.prefix / "turbotides-tui.jar").read_bytes(), original)

    def test_macos_without_homebrew_reports_base_os_limit(self):
        self.limited_path(missing=("tar",), manager=None, platform="Darwin")
        result = self.install("--no-desktop", expected=1)
        self.assertIn(
            "Restore the macOS command-line utilities or install Homebrew",
            result.stderr,
        )
        self.assertFalse(self.prefix.exists())

    def test_existing_homebrew_installs_missing_macos_utility(self):
        directory, log = self.limited_path(
            missing=("tar",), manager="brew", platform="Darwin"
        )
        brew = directory / "brew"
        body = brew.read_text().replace(
            "set -eu\n",
            "set -eu\n"
            + f"if [ \"$1\" = --prefix ]; then printf '%s\\n' {shlex.quote(str(directory))}; exit 0; fi\n",
        )
        brew.write_text(body)
        self.install("--no-desktop")
        self.assertEqual(log.read_text().splitlines(), ["install gnu-tar"])
        self.assertTrue((self.prefix / "turbotides-tui.jar").is_file())

    def test_package_manager_success_must_actually_provide_missing_tool(self):
        directory, _ = self.limited_path(missing=("tar",))
        (directory / "apt-get").write_text("#!/bin/sh\nexit 0\n")
        result = self.install("--no-desktop", expected=1)
        self.assertIn("tar is still unavailable", result.stderr)
        self.assertFalse(self.prefix.exists())

    def test_relative_and_empty_xdg_paths_use_home(self):
        self.env["HOME"] = str(self.root / "isolated home")
        expected = Path(self.env["HOME"]) / ".local/share/turbotides-tui/app"
        for value in ("relative/path", ""):
            with self.subTest(value=value):
                self.env["XDG_DATA_HOME"] = value
                result = subprocess.run(
                    [
                        "sh",
                        str(self.release / "install.sh"),
                        "--local",
                        "--no-desktop",
                        "--bin-dir",
                        str(self.bin),
                    ],
                    env=self.env,
                    cwd=self.root,
                    text=True,
                    capture_output=True,
                    timeout=90,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue((expected / "turbotides-tui.jar").is_file())
                self.assertFalse((self.root / "relative").exists())

    def test_release_download_alternatives_and_backslash_tmpdir(self):
        archive = self.root / "release.tar.gz"
        with tarfile.open(archive, "w:gz") as stream:
            stream.add(self.release, arcname="turbotides-tui")
        checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
        checksum_file = self.root / "SHA256SUMS"
        checksum_file.write_text(f"{checksum}  turbotides-tui-0.1.0.tar.gz\n")
        temporary = self.root / "downloads \\with backslash"
        temporary.mkdir()
        self.env["TMPDIR"] = str(temporary)
        for missing in ((), ("sha256sum",), ("curl", "sha256sum", "shasum")):
            with self.subTest(missing=missing):
                directory, log = self.limited_path(missing=missing)
                downloader = directory / ("wget" if "curl" in missing else "curl")
                downloader.unlink()
                downloader.write_text(
                    "#!/bin/sh\nset -eu\n"
                    'while [ "$#" -gt 0 ]; do case "$1" in -o|-O) destination=$2; shift;; https:*) url=$1;; esac; shift; done\n'
                    'case "$url" in\n'
                    '*/releases/latest) printf \'%s\\n\' \'{"tag_name":"v0.1.0"}\' > "$destination";;\n'
                    f'*/SHA256SUMS) cp {shlex.quote(str(checksum_file))} "$destination";;\n'
                    f'*.tar.gz) cp {shlex.quote(str(archive))} "$destination";;\n'
                    "*) exit 22;;\nesac\n"
                )
                downloader.chmod(0o755)
                result = subprocess.run(
                    [
                        "sh",
                        str(self.release / "install.sh"),
                        "--no-desktop",
                        "--prefix",
                        str(self.prefix),
                        "--bin-dir",
                        str(self.bin),
                    ],
                    env=self.env,
                    cwd=self.root,
                    text=True,
                    capture_output=True,
                    timeout=90,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse(log.exists())
                self.assertTrue((self.prefix / "turbotides-tui.jar").is_file())
                self.assertEqual(list(temporary.iterdir()), [])
                shutil.rmtree(directory)

    def first_use_fixture(self, source=False):
        self.env["HOME"] = str(self.root / "first use home")
        Path(self.env["HOME"]).mkdir()
        helper = self.release / "scripts/java.sh"
        helper.write_text(
            helper.read_text().replace("find_java_25()", "find_existing_java_25()")
            + "\nfind_java_25() {\n"
            + f'    if [ "$app_dir" = {shlex.quote(str(self.release))} ]'
            + f" && [ ! -f {shlex.quote(str(self.data / 'turbotides-tui/app/.turbotides-tui-managed'))} ]"
            + (' && [ "${1:-jre}" = jdk ]' if source else "")
            + '; then return 1; fi\n    find_existing_java_25 "$@"\n}\n'
        )
        if source:
            self.fixture_jdk()
            jar = self.root / "compiled-game.jar"
            (self.release / "turbotides-tui.jar").rename(jar)
            gradlew = self.release / "gradlew"
            gradlew.write_text(
                "#!/bin/sh\nset -eu\n"
                f"printf '%s\\n' \"$*\" > {shlex.quote(str(self.root / 'gradle-arguments'))}\n"
                f"mkdir -p {shlex.quote(str(self.release / 'build/libs'))}\n"
                f"cp {shlex.quote(str(jar))} {shlex.quote(str(self.release / 'build/libs/turbotides-tui.jar'))}\n"
            )
            gradlew.chmod(0o755)

    def fixture_jdk(self):
        # These tests stub Gradle; do not download a JDK on a JRE-only test host.
        # The separate opt-in first-use test compiles with a real downloaded JDK.
        java_home = self.root / "fixture-jdk"
        (java_home / "bin").mkdir(parents=True)
        (java_home / "bin/java").symlink_to(self.java)
        compiler = java_home / "bin/javac"
        compiler.write_text(
            "#!/bin/sh\nprintf 'Unexpected compiler invocation in launcher fixture\\n' >&2\nexit 97\n"
        )
        compiler.chmod(0o755)
        self.env["JAVA_HOME"] = str(java_home)

    def test_first_use_extracted_launcher_installs_then_preserves_arguments(self):
        self.first_use_fixture()
        result = subprocess.run(
            [str(self.release / "turbotides-tui"), "--version"],
            env=self.env,
            cwd=self.root,
            text=True,
            capture_output=True,
            timeout=90,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Setting up Java 25", result.stdout)
        self.assertIn("Turbo Tides", result.stdout)
        self.assertTrue(
            (Path(self.env["HOME"]) / ".local/bin/turbotides-tui").is_symlink()
        )
        self.assertFalse((self.data / "applications").exists())

    def test_first_use_source_launcher_requests_checked_build(self):
        self.first_use_fixture(source=True)
        result = subprocess.run(
            [str(self.release / "turbotides-tui"), "--version"],
            env=self.env,
            cwd=self.root,
            text=True,
            capture_output=True,
            timeout=90,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "--no-daemon check fatJar", (self.root / "gradle-arguments").read_text()
        )
        self.assertIn("Turbo Tides", result.stdout)
        again = subprocess.run(
            [str(self.release / "turbotides-tui"), "--version"],
            env=self.env,
            cwd=self.root,
            text=True,
            capture_output=True,
            timeout=90,
            check=False,
        )
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertNotIn("Setting up Java 25", again.stdout)
        self.assertIn("--quiet fatJar", (self.root / "gradle-arguments").read_text())

    def test_managed_launcher_repairs_using_original_custom_bin_directory(self):
        self.install("--no-desktop")
        helper = self.prefix / "scripts/java.sh"
        once = self.root / "missing-java-probe"
        helper.write_text(
            helper.read_text().replace("find_java_25()", "find_existing_java_25()")
            + "\nfind_java_25() {\n"
            + f"    if [ ! -f {shlex.quote(str(once))} ]; then : > {shlex.quote(str(once))}; return 1; fi\n"
            + '    find_existing_java_25 "$@"\n}\n'
        )
        result = subprocess.run(
            [str(self.bin / "turbotides-tui"), "--version"],
            env=self.env,
            cwd=self.root,
            text=True,
            capture_output=True,
            timeout=90,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Setting up Java 25", result.stdout)
        self.assertIn("Turbo Tides", result.stdout)
        self.assertEqual((self.prefix / "bin.path").read_text().strip(), str(self.bin))
        self.assertTrue((self.bin / "turbotides-tui").is_symlink())

    @unittest.skipUnless(
        importlib.util.find_spec("pexpect") and importlib.util.find_spec("pyte"),
        "Install tools/audit-requirements.txt for the live PTY upgrade check",
    )
    def test_live_installed_game_survives_repair_and_loads_track(self):
        self.install("--no-desktop")
        self.exercise_live_replacement(
            self.bin / "turbotides-tui",
            lambda: self.install("--no-desktop"),
            "live-repair",
        )

    @unittest.skipUnless(
        importlib.util.find_spec("pexpect") and importlib.util.find_spec("pyte"),
        "Install tools/audit-requirements.txt for the live source rebuild check",
    )
    def test_live_source_game_survives_build_jar_rewrite(self):
        jar = self.source_launcher_fixture()
        replacement = self.root / "rebuilt.jar"
        # A valid changed archive has new offsets, as after rebuilding classes.
        with (
            zipfile.ZipFile(jar) as original,
            zipfile.ZipFile(replacement, "w") as rebuilt,
        ):
            rebuilt.writestr("build-marker.txt", "rebuilt while game is running\n")
            for member in original.infolist():
                rebuilt.writestr(member, original.read(member.filename))
        self.exercise_live_replacement(
            self.release / "turbotides-tui",
            lambda: shutil.copyfile(replacement, jar),
            "live-source-rebuild",
        )

    def source_launcher_fixture(self):
        self.fixture_jdk()
        jar = self.release / "build/libs/turbotides-tui.jar"
        jar.parent.mkdir(parents=True)
        (self.release / "turbotides-tui.jar").rename(jar)
        gradlew = self.release / "gradlew"
        gradlew.write_text("#!/bin/sh\nexit 0\n")
        gradlew.chmod(0o755)
        return jar

    @unittest.skipUnless(
        importlib.util.find_spec("pexpect") and importlib.util.find_spec("pyte"),
        "Install tools/audit-requirements.txt for source-launcher signals",
    )
    def test_source_launcher_ctrl_c_and_term_clean_up_private_jar(self):
        self.source_launcher_fixture()
        for binding in ("ctrl+c", "TERM"):
            with self.subTest(binding=binding):
                self.exercise_live_replacement(
                    self.release / "turbotides-tui",
                    lambda: None,
                    f"source-exit-{binding}",
                    exit_binding=binding,
                    expected_exit=130 if binding == "ctrl+c" else 143,
                )

    @unittest.skipUnless(
        importlib.util.find_spec("pexpect"),
        "Install pexpect for source-launcher exit status",
    )
    def test_source_launcher_propagates_error_status_and_removes_snapshot(self):
        import pexpect

        self.source_launcher_fixture()
        temporary = self.root / "source-launch-temp"
        temporary.mkdir()
        child = pexpect.spawn(
            str(self.release / "turbotides-tui"),
            ["--unknown"],
            env=dict(self.env, TMPDIR=str(temporary)),
            encoding="utf-8",
            timeout=20,
        )
        self.addCleanup(lambda: child.close(force=True))
        child.expect(pexpect.EOF)
        self.assertIn("Unknown option", child.before)
        child.close()
        self.assertEqual(child.exitstatus, 2)
        self.assertEqual(list(temporary.iterdir()), [])

    def exercise_live_replacement(
        self, launcher, replace, label, exit_binding="q", expected_exit=0
    ):
        import pexpect
        import pyte

        state = self.root / "live-upgrade.json"
        state.unlink(missing_ok=True)
        temporary = self.root / "source-launch-temp"
        temporary.mkdir(exist_ok=True)
        child = pexpect.spawn(
            str(launcher),
            [
                "--telemetry",
                str(state),
                "--data-dir",
                str(self.root / "isolated race records"),
            ],
            env=dict(
                self.env,
                TERM="xterm-256color",
                COLORTERM="truecolor",
                TMPDIR=str(temporary),
            ),
            encoding="utf-8",
            codec_errors="replace",
            dimensions=(40, 120),
            timeout=1,
        )
        self.addCleanup(lambda: child.close(force=True))
        terminal_modes = termios.tcgetattr(child.child_fd)
        screen = pyte.Screen(120, 40)
        stream = pyte.Stream(screen)
        raw = []
        evidence = ROOT / "build/installer-audit" / label
        evidence.mkdir(parents=True, exist_ok=True)

        def retain_failure():
            (evidence / "failure.ansi").write_text("".join(raw))
            (evidence / "failure.txt").write_text("\n".join(screen.display))
            if state.exists():
                shutil.copy2(state, evidence / "failure.json")

        def wait_for(phase):
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                try:
                    output = child.read_nonblocking(65536, timeout=0.1)
                    raw.append(output)
                    stream.feed(output)
                    if "\x1b[6n" in output:
                        child.send("\x1b[1;1R")
                except pexpect.TIMEOUT:
                    pass
                except pexpect.EOF:
                    retain_failure()
                    self.fail(
                        "Game exited across install repair: " + "".join(raw)[-3000:]
                    )
                if state.exists():
                    try:
                        visible = {
                            "GARAGE": ("start race", "local records only"),
                            "RACING": ("lap", "w/↑ gas"),
                            "PAUSED": ("race paused", "driving modes cleared"),
                        }[phase]
                        if json.loads(state.read_text())["phase"] == phase and all(
                            text in "\n".join(screen.display).lower()
                            for text in visible
                        ):
                            evidence = ROOT / "build/installer-audit" / label
                            evidence.mkdir(parents=True, exist_ok=True)
                            (evidence / f"{phase.lower()}.txt").write_text(
                                "\n".join(screen.display)
                            )
                            (evidence / "terminal.ansi").write_text("".join(raw))
                            (evidence / f"{phase.lower()}.ansi").write_text(
                                "".join(raw)
                            )
                            return
                    except json.JSONDecodeError:
                        pass
            retain_failure()
            self.fail(f"Game did not reach {phase}: " + "".join(raw)[-3000:])

        wait_for("GARAGE")
        self.assertIn("turbo tides", "\n".join(screen.display).lower())
        replace()
        child.send("\r")
        wait_for("RACING")
        self.assertIn("lap", "\n".join(screen.display).lower())
        child.send("w")
        time.sleep(0.3)
        child.send("\x1b")
        wait_for("PAUSED")
        child.send("g")
        wait_for("GARAGE")
        if exit_binding == "TERM":
            os.kill(child.pid, signal.SIGTERM)
        else:
            child.send("\x03" if exit_binding == "ctrl+c" else "q")
        child.expect(pexpect.EOF, timeout=10)
        raw.append(child.before)
        (evidence / "exit.ansi").write_text("".join(raw))
        self.assertEqual(
            termios.tcgetattr(child.child_fd)[3] & (termios.ECHO | termios.ICANON),
            terminal_modes[3] & (termios.ECHO | termios.ICANON),
            "Terminal echo/canonical input were not restored on exit",
        )
        self.assertIn("\x1b[?1049l", "".join(raw), "Alternate screen was not restored")
        child.close()
        self.assertEqual(child.exitstatus, expected_exit, "".join(raw)[-3000:])
        self.assertNotIn("Exception", "".join(raw))
        self.assertEqual(list(temporary.iterdir()), [])

    def test_install_launch_repair_and_uninstall(self):
        self.install()
        command = self.bin / "turbotides-tui"
        self.assertTrue(command.is_symlink())
        launched = subprocess.run(
            [str(command), "--version"],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        self.assertEqual(launched.returncode, 0, launched.stdout + launched.stderr)
        self.assertIn("Turbo Tides", launched.stdout)
        desktop = self.data / "applications/turbotides-tui.desktop"
        self.assertIn("Terminal=true", desktop.read_text())
        if shutil.which("desktop-file-validate"):
            subprocess.run(["desktop-file-validate", str(desktop)], check=True)
        self.install()
        self.assertTrue((self.prefix / "turbotides-tui.jar").is_file())
        self.assertFalse(list(self.root.glob(".turbotides-*")))
        record = self.data / "preserved-record.txt"
        record.write_text("personal best")
        self.install("--uninstall")
        self.assertFalse(self.prefix.exists())
        self.assertFalse(command.is_symlink())
        self.assertFalse(desktop.exists())
        self.assertEqual(record.read_text(), "personal best")

    def test_no_desktop(self):
        self.install("--no-desktop")
        self.assertFalse(self.data.exists())

    def test_installed_document_links_are_available(self):
        documents = self.release / "docs"
        documents.mkdir()
        (documents / "INSTALLATION.md").write_text("Install guide\n")
        (self.release / "README.md").write_text(
            "[Installation](docs/INSTALLATION.md)\n"
        )
        licenses = self.release / "licenses"
        licenses.mkdir()
        shutil.copy2(
            ROOT / "src/main/resources/art/PhippyRescue-MIT.txt",
            licenses / "PhippyRescue-MIT.txt",
        )
        self.install("--no-desktop")
        self.assertEqual(
            (self.prefix / "docs/INSTALLATION.md").read_text(), "Install guide\n"
        )
        self.assertIn("docs/INSTALLATION.md", (self.prefix / "README.md").read_text())
        self.assertIn(
            "MIT License", (self.prefix / "licenses/PhippyRescue-MIT.txt").read_text()
        )

    @unittest.skipUnless(shutil.which("gio"), "Gio desktop-entry loader unavailable")
    def test_desktop_exec_reserved_characters(self):
        self.prefix = self.root / 'game "quoted" $dollar `literal` %percent \\backslash'
        self.install()
        desktop = self.data / "applications/turbotides-tui.desktop"
        fixture = self.root / "version.desktop"
        # Execute the actual desktop command without opening another GUI terminal.
        fixture.write_text(
            "\n".join(
                line + " --version"
                if line.startswith("Exec=")
                else line.replace("Terminal=true", "Terminal=false")
                for line in desktop.read_text().splitlines()
            )
            + "\n"
        )
        result = subprocess.run(
            ["gio", "launch", str(fixture)],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Turbo Tides", result.stdout)

    def test_default_location_preserves_actual_records(self):
        records = self.data / "turbotides-tui" / "records.properties"
        records.parent.mkdir(parents=True)
        records.write_text("best.SUNSET.CRUISE=59.25\n")
        self.prefix = records.parent / "app"
        # Verify the installer default, not merely the test's explicitly set path.
        command = [
            "sh",
            str(self.release / "install.sh"),
            "--local",
            "--bin-dir",
            str(self.bin),
        ]
        for extra in ([], [], ["--uninstall"]):
            result = subprocess.run(
                command + extra,
                env=self.env,
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(records.read_text(), "best.SUNSET.CRUISE=59.25\n")
        self.assertFalse(self.prefix.exists())

    def test_refuses_unrelated_desktop_file(self):
        desktop = self.data / "applications/turbotides-tui.desktop"
        desktop.parent.mkdir(parents=True)
        desktop.write_text("[Desktop Entry]\nName=Other application\n")
        self.install(expected=1)
        self.assertEqual(
            desktop.read_text(), "[Desktop Entry]\nName=Other application\n"
        )
        self.assertFalse(self.prefix.exists())

    def test_broken_upgrade_preserves_existing_app(self):
        self.install()
        original = (self.prefix / "turbotides-tui.jar").read_bytes()
        (self.release / "turbotides-tui.jar").write_bytes(b"broken jar")
        result = self.install(expected=1)
        self.assertIn("existing installation was kept", result.stderr)
        self.assertEqual((self.prefix / "turbotides-tui.jar").read_bytes(), original)

    def test_missing_icon_does_not_replace_existing_app(self):
        self.install()
        original = (self.prefix / "assets/icon-512.png").read_bytes()
        (self.release / "assets/icon-512.png").unlink()
        result = self.install(expected=1)
        self.assertIn("missing icon-512.png", result.stderr)
        self.assertEqual((self.prefix / "assets/icon-512.png").read_bytes(), original)

    def test_bad_release_checksum_preserves_existing_app(self):
        self.install()
        original = (self.prefix / "turbotides-tui.jar").read_bytes()
        fakebin = self.root / "network-bin"
        fakebin.mkdir()
        curl = fakebin / "curl"
        curl.write_text(
            "#!/bin/sh\nset -eu\n"
            'while [ "$#" -gt 0 ]; do case "$1" in -o) destination=$2; shift;; https:*) url=$1;; esac; shift; done\n'
            'case "$url" in\n'
            '*/releases/latest) printf \'%s\\n\' \'{"tag_name":"v0.1.0"}\' > "$destination";;\n'
            f"*/SHA256SUMS) printf '%s\\n' {shlex.quote('0' * 64 + '  turbotides-tui-0.1.0.tar.gz')} > \"$destination\";;\n"
            '*.tar.gz) printf "corrupted download" > "$destination";;\n'
            "*) exit 22;;\nesac\n"
        )
        curl.chmod(0o755)
        self.env["PATH"] = str(fakebin) + os.pathsep + os.environ["PATH"]
        result = subprocess.run(
            [
                "sh",
                str(self.release / "install.sh"),
                "--prefix",
                str(self.prefix),
                "--bin-dir",
                str(self.bin),
            ],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Checksum mismatch", result.stderr)
        self.assertEqual((self.prefix / "turbotides-tui.jar").read_bytes(), original)

    def test_macos_app_generation(self):
        # Exercise macOS packaging without pretending Linux runs Finder/Terminal.
        fakebin = self.root / "platform-bin"
        fakebin.mkdir()
        uname = fakebin / "uname"
        uname.write_text(
            "#!/bin/sh\ncase $1 in -s) echo Darwin;; -m) echo arm64;; esac\n"
        )
        uname.chmod(0o755)
        self.env["PATH"] = str(fakebin) + os.pathsep + os.environ["PATH"]
        self.env["TURBOTIDES_APPLICATIONS_DIR"] = str(self.root / "Applications")
        self.install()
        contents = self.root / "Applications/Turbo Tides TUI.app/Contents"
        with (contents / "Info.plist").open("rb") as stream:
            plist = plistlib.load(stream)
        self.assertEqual(plist["CFBundleExecutable"], "TurboTides")
        subprocess.run(["sh", "-n", str(contents / "MacOS/TurboTides")], check=True)
        self.assertEqual(
            (contents / "Resources/launcher.path").read_text().strip(),
            str(self.prefix / "turbotides-tui"),
        )
        self.assertGreater(
            (contents / "Resources/turbotides.icns").stat().st_size, 1000
        )
        self.install("--uninstall")
        self.assertFalse(contents.exists())

    @unittest.skipUnless(
        os.environ.get("TURBOTIDES_TEST_DESKTOP") == "1",
        "opt-in visible Linux desktop launch",
    )
    def test_real_linux_desktop_launch(self):
        self.install()
        state = self.root / "desktop-launch-state.json"
        desktop = self.data / "applications/turbotides-tui.desktop"
        fixture = self.root / "launch-test.desktop"
        text = desktop.read_text()
        launcher = self.prefix / "turbotides-tui"
        text = text.replace(
            f'"{launcher}"',
            f'"{launcher}" --telemetry "{state}" --data-dir "{self.root / "test records"}"',
            1,
        )
        fixture.write_text(text)

        def close_test_game():
            processes = subprocess.check_output(["ps", "-eo", "pid,args"], text=True)
            for line in processes.splitlines():
                if " -jar " in line and str(state) in line:
                    try:
                        os.kill(int(line.split(None, 1)[0]), signal.SIGTERM)
                    except ProcessLookupError:
                        pass

        self.addCleanup(close_test_game)
        subprocess.run(["gio", "launch", str(fixture)], env=self.env, check=True)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if state.is_file():
                actual = json.loads(state.read_text())
                self.assertEqual(actual["phase"], "GARAGE")
                self.assertGreaterEqual(actual["width"], 64)
                return
            time.sleep(0.2)
        self.fail(
            "The installed desktop entry did not start the real game within 45 seconds"
        )

    @unittest.skipUnless(
        os.environ.get("TURBOTIDES_TEST_DOWNLOAD") == "1",
        "opt-in 60 MB real Java download",
    )
    def test_private_runtime_download_and_launch(self):
        self.install("--private-java", "--no-desktop")
        runtime = self.prefix / "runtime/bin/java"
        result = subprocess.run(
            [str(runtime), "-version"],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
        self.assertIn('version "25.', result.stderr)
        result = subprocess.run(
            [str(self.bin / "turbotides-tui"), "--version"],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
        self.assertIn("Turbo Tides", result.stdout)
        # A repair reuses the owned runtime without downloading it again.
        self.install("--no-desktop")
        self.assertTrue(runtime.is_file())
        self.assertFalse((self.prefix / "java.path").exists())
        self.install("--uninstall", "--no-desktop")

    def launch_without_host_java(self, source=False):
        if source:
            (self.release / "turbotides-tui.jar").unlink()
            for name in (
                "gradlew",
                "gradle",
                "build.gradle.kts",
                "settings.gradle.kts",
                "gradle.properties",
                ".editorconfig",
                "VERSION",
                "src",
            ):
                original = ROOT / name
                if original.is_dir():
                    shutil.copytree(original, self.release / name)
                elif original.is_file():
                    shutil.copy2(original, self.release / name)
        home = self.root / "no Java home"
        home.mkdir()
        temporary = self.root / "downloads"
        temporary.mkdir()
        command = [
            "bwrap",
            "--unshare-pid",
            "--die-with-parent",
            "--ro-bind",
            "/",
            "/",
            "--bind",
            str(self.root),
            str(self.root),
            "--dev",
            "/dev",
            "--proc",
            "/proc",
            "--tmpfs",
            "/usr/lib/jvm",
            "--setenv",
            "HOME",
            str(home),
            "--setenv",
            "XDG_DATA_HOME",
            str(self.data),
            "--setenv",
            "TMPDIR",
            str(temporary),
            "--setenv",
            "PATH",
            "/usr/bin:/bin",
            "--unsetenv",
            "JAVA_HOME",
            "--unsetenv",
            "TURBOTIDES_JAVA_HOME",
            "--setenv",
            "GRADLE_USER_HOME",
            str(home / ".gradle"),
            "--setenv",
            "JAVA_TOOL_OPTIONS",
            f'-Duser.home="{home}" -Djava.io.tmpdir="{temporary}"',
            "--chdir",
            str(self.root),
            "--",
            str(self.release / "turbotides-tui"),
            "--version",
        ]
        for attempt in range(2):
            result = subprocess.run(
                command, text=True, capture_output=True, timeout=600, check=False
            )
            evidence = ROOT / "build/installer-audit"
            evidence.mkdir(parents=True, exist_ok=True)
            kind = "source" if source else "release"
            (evidence / f"no-java-{kind}-{attempt + 1}.log").write_text(
                result.stdout + result.stderr
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Turbo Tides", result.stdout)
            if attempt == 0:
                self.assertIn(
                    f"private Eclipse Temurin Java 25 {'jdk' if source else 'jre'}",
                    result.stdout,
                )
            else:
                self.assertNotIn("Setting up Java 25", result.stdout)
        runtime = self.data / "turbotides-tui/app/runtime/bin/java"
        self.assertTrue(runtime.is_file())
        if source:
            self.assertTrue(runtime.with_name("javac").is_file())

    @unittest.skipUnless(
        os.environ.get("TURBOTIDES_TEST_FIRST_USE") == "1" and shutil.which("bwrap"),
        "opt-in real first-use download in a Linux mount namespace",
    )
    def test_real_no_java_release_first_and_second_launch(self):
        self.launch_without_host_java()

    @unittest.skipUnless(
        os.environ.get("TURBOTIDES_TEST_FIRST_USE") == "1" and shutil.which("bwrap"),
        "opt-in real JDK/Gradle first-use source build in a Linux mount namespace",
    )
    def test_real_no_java_source_first_and_second_launch(self):
        self.launch_without_host_java(source=True)

    def test_refuses_unmanaged_directory(self):
        self.prefix.mkdir()
        sentinel = self.prefix / "precious.txt"
        sentinel.write_text("unchanged")
        result = self.install(expected=1)
        self.assertIn("unmanaged", result.stderr)
        self.assertEqual(sentinel.read_text(), "unchanged")

    def test_refuses_unrelated_command(self):
        self.bin.mkdir()
        sentinel = self.bin / "turbotides-tui"
        sentinel.write_text("another program")
        result = self.install(expected=1)
        self.assertIn("unrelated command", result.stderr)
        self.assertEqual(sentinel.read_text(), "another program")
        self.assertFalse(self.prefix.exists())

    def test_refuses_symlink_directory(self):
        target = self.root / "elsewhere"
        target.mkdir()
        (target / ".turbotides-tui-managed").write_text("marker")
        self.prefix.symlink_to(target)
        self.install(expected=1)
        self.assertTrue(target.is_dir())

    def test_invalid_java_setting_is_reported(self):
        self.env["TURBOTIDES_JAVA_HOME"] = str(self.root / "missing java")
        result = self.install(expected=1)
        self.assertIn("TURBOTIDES_JAVA_HOME", result.stderr)
        self.assertFalse(self.prefix.exists())

    def test_unknown_option_and_relative_prefix(self):
        self.install("--unknown", expected=1)
        self.install("--prefix", "relative/path", expected=1)
        self.assertFalse(self.prefix.exists())


class JavaMetadataTest(unittest.TestCase):
    def test_source_reuses_private_jdk_with_normalized_xdg_location(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for xdg in (str(root / "data"), "", "relative/data"):
                with self.subTest(xdg=xdg):
                    data = (
                        Path(xdg) if Path(xdg).is_absolute() else root / ".local/share"
                    )
                    java_home = data / "turbotides-tui/app/runtime"
                    (java_home / "bin").mkdir(parents=True, exist_ok=True)
                    java = java_home / "bin/java"
                    java.write_text(
                        "#!/bin/sh\nprintf 'openjdk version \"25.0.5\"\\n' >&2\n"
                    )
                    java.chmod(0o755)
                    javac = java_home / "bin/javac"
                    javac.write_text("#!/bin/sh\nexit 0\n")
                    javac.chmod(0o755)
                    env = dict(os.environ, HOME=str(root), XDG_DATA_HOME=xdg)
                    env.pop("TURBOTIDES_JAVA_HOME", None)
                    result = subprocess.run(
                        [
                            "sh",
                            "-c",
                            '. "$1"; find_java_25 jdk; printf "%s" "$TURBOTIDES_JAVA"',
                            "sh",
                            str(ROOT / "scripts/java.sh"),
                        ],
                        env=env,
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    self.assertEqual(result.stdout, str(java))

    def test_macos_archive_selected_instead_of_installer(self):
        metadata = """[
  { "binary": {
    "installer": {
      "checksum": "wrong-pkg-checksum",
      "link": "https://github.com/adoptium/temurin25-binaries/releases/download/example/java.pkg"
    },
    "package": {
      "checksum": "archive-checksum",
      "link": "https://github.com/adoptium/temurin25-binaries/releases/download/example/java.tar.gz"
    }
  } }
]"""
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "metadata.json"
            path.write_text(metadata)
            result = subprocess.run(
                [
                    "sh",
                    "-c",
                    '. "$1"; read_temurin_package "$2"; printf "%s\\n%s\\n" "$java_url" "$java_checksum"',
                    "sh",
                    str(ROOT / "scripts/java.sh"),
                    str(path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "https://github.com/adoptium/temurin25-binaries/releases/download/example/java.tar.gz",
                "archive-checksum",
            ],
        )


if __name__ == "__main__":
    unittest.main()
