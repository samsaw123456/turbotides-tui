"""Regenerate the control table from passed, matching-artifact PTY evidence."""

import hashlib
import json
from datetime import date
from pathlib import Path

from PIL import Image, ImageChops

root = Path(__file__).resolve().parents[1]
version = (root / "VERSION").read_text().strip()
out = root / "build/ansi-audit"
jar_hash = hashlib.sha256(
    (root / "build/libs/turbotides-tui.jar").read_bytes()
).hexdigest()
groups = [
    "all",
    "finish",
    "finish-results-opposite",
    "quit",
    "records",
    "errors",
    "contact",
    "record-recovery",
    "record-recovery-garage",
]
rows = []
for group in groups:
    filename = (
        "finish-results-opposite.json"
        if group == "finish-results-opposite"
        else group + "-results.json"
    )
    records = json.loads((out / filename).read_text())
    for record in records:
        assert record["status"] == "PASSED", (group, record)
        for evidence in record["evidence"]:
            image = root / evidence
            assert image.exists(), image
            build = json.loads((image.parent / "build.json").read_text())
            assert build["jar_sha256"] == jar_hash, (image, build["jar_sha256"])
            assert image.stat().st_mtime >= build["started_unix"], (
                "Stale frame",
                image,
            )
        rows.append(record)
old = (root / "docs/CONTROLS.md").read_text()
protocol = old.split("## Escape protocol finding", 1)[1].split("## Evidence", 1)[0]
header = f"""# Complete control audit

Frozen v{version} executable SHA-256: `{jar_hash}`. Audit date: {date.today()}.

**{len(rows)} passed rows** cover every advertised physical binding in each relevant state, repeated input, disabled commands, recovery, records and contacts. Both six-circuit race/pace campaigns are included. Alternate keys are exercised separately through the actual PTY.

Letters mean unshifted keys. Arrows, Tab, Shift+Tab, Enter, Escape, Space, `?`, and Ctrl+C were sent separately. Focus-out/in messages and window-size changes were exercised.

Ordinary ANSI has no key-up identity. Throttle/brake are modes, steering expires after180 ms without repeats, and Space/B/C are tap toggles. Repeat trains and explicit mode release were tested; physical key-release reporting and held mode-key behavior are not claimed. Standalone Shift, F11, controller, mouse and touch are not implemented game commands. [Additional Ctrl+Z and terminal-restoration probes](QUALITY_REVIEW.md) cover ignored job-control input in five game contexts and clean return to the shell.

## Escape protocol finding{protocol}## Evidence

Every inventory row below was rechecked on the frozen v{version} executable. Results come from actual terminal output, not a duplicate renderer. Steering assertions locate painted player pixels independently of lane signs; speed checks read the visible speedometer; disabled-input checks compare rendered cells. Audio effects were separately captured from the v0.1.1 playback stream in [AUDIO.md](AUDIO.md); the scenery update does not change audio.

Paths below are relative to `build/ansi-audit/`. The retained tools recreate raw ANSI, decoded text, PNGs, diagnostics, and JSON reports locally. Generated evidence is excluded from git; curated [steering](screenshots/steering-audit.png), [city streets](screenshots/city-streets.png), and [finish](screenshots/current-finishes.png) images show this build. Each session's `build.json` identifies its executable. Table generation rejects evidence from a different artifact.

The Actual result column compares captured images and reports selected state changes as supplementary evidence. The expected outcome is independently asserted by the corresponding live-interface test; a telemetry sign or successful automated win alone is not accepted as proof.

## Binding-by-binding results

| # | State | Physical binding | Expected observable effect | Actual result | Status | Local frame evidence |
| ---: | --- | --- | --- | --- | --- | --- |
"""
fields = [
    "phase",
    "help",
    "menuFocus",
    "circuit",
    "paint",
    "difficulty",
    "muted",
    "reducedMotion",
    "rearView",
    "throttle",
    "brake",
    "boost",
    "drift",
    "best",
    "saveError",
]


def esc(v):
    return str(v).replace("|", "\\|").replace("\n", " ")


def actual(row):
    paths = [root / p for p in row["evidence"]]
    if len(paths) == 1:
        return "Clean exit and terminal cleanup assertions passed"
    same = (
        ImageChops.difference(
            Image.open(paths[0]).convert("RGB"), Image.open(paths[-1]).convert("RGB")
        ).getbbox()
        is None
    )
    text = "Final pixels unchanged" if same else "Visible pixels changed"
    before = paths[0].with_suffix(".json")
    after = paths[-1].with_suffix(".json")
    if before.exists() and after.exists():
        a = json.loads(before.read_text())
        b = json.loads(after.read_text())
        changes = [
            f"{k}: {a.get(k)} → {b.get(k)}" for k in fields if a.get(k) != b.get(k)
        ]
        if changes:
            text += "; " + ", ".join(changes[:3])
    return text + "; outcome assertions passed"


lines = [header]
for i, row in enumerate(rows, 1):
    evidence = " → ".join(
        "`" + p.removeprefix("build/ansi-audit/") + "`" for p in row["evidence"]
    )
    lines.append(
        "| "
        + " | ".join(
            map(
                esc,
                [
                    i,
                    row["state"],
                    row["binding"],
                    row["expected"],
                    actual(row),
                    "Passed",
                    evidence,
                ],
            )
        )
        + " |\n"
    )
(root / "docs/CONTROLS.md").write_text("".join(lines).replace("after180", "after 180"))
print(f"Wrote {len(rows)} final-artifact control rows")
