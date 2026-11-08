"""Build showcase/mockup.html: the template with a fresh snapshot of the real checks inlined.

    python -m showcase.build_mockup
"""

import json
from pathlib import Path

from showcase.export_snapshot import OUT as SNAPSHOT, snapshot

HERE = Path(__file__).resolve().parent


def build() -> Path:
    data = snapshot()
    SNAPSHOT.write_text(json.dumps(data, indent=1) + "\n")
    payload = json.dumps(data).replace("</", "<\\/")  # never close the script tag early
    page = (HERE / "mockup_template.html").read_text().replace("__SNAPSHOT_JSON__", payload)
    out = HERE / "mockup.html"
    out.write_text(page)
    return out


if __name__ == "__main__":
    print(f"wrote {build()}")
