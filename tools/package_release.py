#!/usr/bin/env python3
"""Package a verified executable JAR and launchers, without duplicating assets."""

import argparse
import hashlib
import os
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-build", action="store_true", help="package an already verified fat JAR"
    )
    args = parser.parse_args()
    if not args.skip_build:
        subprocess.run([str(ROOT / "gradlew"), "check", "fatJar"], cwd=ROOT, check=True)
    version = (ROOT / "VERSION").read_text().strip()
    if not version or any(c not in "0123456789." for c in version):
        raise SystemExit("VERSION must contain a numeric release version.")
    files = {
        "turbotides-tui.jar": ROOT / "build/libs/turbotides-tui.jar",
        "licenses/PhippyRescue-MIT.txt": ROOT
        / "src/main/resources/art/PhippyRescue-MIT.txt",
        **{
            name: ROOT / name
            for name in (
                "turbotides-tui",
                "install.sh",
                "scripts/java.sh",
                "assets/icon.svg",
                "assets/icon-512.png",
                "assets/icon-128.png",
                "assets/icon.icns",
                "README.md",
                "LICENSE",
                "THIRD_PARTY.md",
                "VERSION",
            )
        },
    }
    # Keep README's local documentation and screenshots usable in extracted releases.
    for source in (ROOT / "docs").rglob("*"):
        if (
            source.is_file()
            and "evidence" not in source.relative_to(ROOT / "docs").parts
        ):
            files[str(source.relative_to(ROOT))] = source
    for source in files.values():
        if not source.is_file():
            raise SystemExit(f"Required release file missing: {source}")
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    archive = destination / f"turbotides-tui-{version}.tar.gz"
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))

    def metadata(info):
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        info.mtime = epoch
        return info

    with tarfile.open(archive, "w:gz") as bundle:
        for name, source in sorted(files.items()):
            bundle.add(source, arcname=f"turbotides-tui/{name}", filter=metadata)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (destination / "SHA256SUMS").write_text(f"{checksum}  {archive.name}\n")
    print(f"Packaged {archive} ({archive.stat().st_size / 1024**2:.1f} MiB)")
    print(f"SHA-256: {checksum}")


if __name__ == "__main__":
    main()
