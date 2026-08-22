"""
Append-only audit trail for hazard-rule changes.

Companion to `rules_config.py`. A config file alone doesn't answer "who
changed this, and when, and why." This module does: every intentional
rule change gets one append-only JSONL record with who, when, which
field, the old and new value, and why.

Scope, stated plainly: this module does not build the rule-editing tool
itself (no GUI exists yet -- see rules_config.py's docstring and
ARCHITECTURE.md Known Debt). It's the audit primitive that tool is
expected to call on every edit it makes, and it's independently useful
right now for recording a manual, deliberate edit to
`case_data/hazard_rules_v1.json` (e.g. a future ADR changing the
fire-watch capacity limit, the way ADR-023 already did once before this
module existed).

Append-only by construction: `record_rule_change` only ever opens the
log file in append mode and never reads/rewrites existing lines. Nothing
in this module offers a way to edit or delete a past entry -- an audit
trail that can be quietly edited after the fact isn't one.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_DEFAULT_AUDIT_LOG_PATH = (
    Path(__file__).resolve().parent.parent / "case_data" / "hazard_rules_audit.jsonl"
)


@dataclass(frozen=True)
class RuleChangeRecord:
    """One audited change to one field of the hazard rules config."""

    timestamp: str  # ISO 8601, UTC -- caller supplies it (see record_rule_change)
    editor: str
    field: str
    old_value: Any
    new_value: Any
    reason: str


def record_rule_change(
    *,
    timestamp: str,
    editor: str,
    field: str,
    old_value: Any,
    new_value: Any,
    reason: str,
    path: Path = _DEFAULT_AUDIT_LOG_PATH,
) -> RuleChangeRecord:
    """
    Appends one audit record and returns it.

    `timestamp` is caller-supplied (ISO 8601, UTC) rather than computed
    inside this function -- keeps this module trivially testable without
    freezing the clock, and matches this codebase's existing convention
    of not calling wall-clock time from inside logic that should be
    deterministic given its inputs.

    `old_value`/`new_value` are stored as given (must be JSON-serializable
    -- a bare string, number, bool, or list/dict of those); this function
    does not interpret or validate them against `HazardRuleSet`'s schema,
    that's `rules_config.load_hazard_rules()`'s job on the next load.
    """
    record = RuleChangeRecord(
        timestamp=timestamp,
        editor=editor,
        field=field,
        old_value=old_value,
        new_value=new_value,
        reason=reason,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(record), sort_keys=True) + "\n")
    return record


def read_audit_log(path: Path = _DEFAULT_AUDIT_LOG_PATH) -> list[RuleChangeRecord]:
    """
    Reads every recorded change, oldest first. Returns an empty list if
    the log doesn't exist yet -- no changes have ever been recorded is a
    valid, unremarkable state, not an error.
    """
    if not path.exists():
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(RuleChangeRecord(**json.loads(line)))
    return records
