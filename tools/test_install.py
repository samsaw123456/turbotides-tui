"""Exercise installation, desktop files, repair, launch, and safe removal."""

import json
import os
import plistlib
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
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
        self.env = dict(os.environ, XDG_DATA_HOME=str(self.data))
        self.env.pop("TURBOTIDES_JAVA_HOME", None)

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
        self.prefix = self.root / 'game "quoted" $dollar `literal` %percent'
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
