"""Docs stay current: the README's status date keeps up with the session log (2026-11-09,
Donnie: "the information in the repo doesn't reflect the current status")."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_readme_status_date_is_not_behind_the_newest_passdown_entry():
    readme = (ROOT / "README.md").read_text()
    m = re.search(r"## Current status\s+> \*\*As of (\d{4}-\d{2}-\d{2})\.", readme)
    assert m, "README needs a '## Current status' block starting '> **As of YYYY-MM-DD.**'"
    passdown = (ROOT / "PASSDOWN.md").read_text()
    newest = max(re.findall(r"^## \d+\. Session Notes — (\d{4}-\d{2}-\d{2})", passdown, re.M))
    assert m.group(1) >= newest, f"README status is dated {m.group(1)}, newest PASSDOWN entry is {newest}"


def test_readme_does_not_describe_the_deleted_real_ship_visuals():
    readme = (ROOT / "README.md").read_text()
    assert not re.search(r"HAER|ACUSHNET|Turner Joy", readme)
