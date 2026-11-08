"""
Text daily brief (Session 10): one plain-text page a supervisor can read at the start
of a shift.

Deterministic end to end (AGENTS.md rule 7). It runs the same checks the graph runs
(deconfliction, judgment flags, certificate and schedule findings, the crew-shift
suggester, the project rollup) and prints what they found. No LLM is called, and the
brief never applies a suggestion or approves anything.

    dataset --> deconfliction --> judgment --> findings --+--> rollup per project --+
                                                          +--> shift suggestions ---+--> text
    decision log (optional) --> chain check + anchor check ------------------------+

It's a pre-review brief: every flagged package reads PENDING_REVIEW, because no human
has decided it yet. The decision-log section prints the log's head (seq and hash).
Recording that line outside the database is what lets a later brief detect the newest
entries being cut off (Session 9's known limit): pass it back as `anchor`.

    python -m agent_core.daily_brief --as-of 2027-03-15T06:00 [--db reviewer.db] [--anchor SEQ:HASH]
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from agent_core import named_rules
from agent_core.carrier_demo import CarrierDataset, load_carrier_dataset
from agent_core.certificates import CertificateFinding, check_certificates
from agent_core.crews import ScheduleFinding, check_schedule_constraints
from agent_core.decision_log import DecisionLog, LogTamperError
from agent_core.deconfliction import conflict_rule_ids, deconfliction_node
from agent_core.findings_gate import findings_node
from agent_core.judgment import JudgmentFlag, judgment_flags, judgment_node
from agent_core.projects import PackageStatus, ProjectRollup, package_status, rollup_project, sort_projects
from agent_core.shift_suggester import CrewShiftOutcome, suggest_crew_shift
from agent_core.state import WorkPackageState
from agent_core.validation import fmt_time

_RULE_ID = re.compile(r"WS-[A-Z]{2}-\d{3}")
TITLE = "WATCHSTANDER DAILY BRIEF -- NOTIONAL DATA, NOT FOR OPERATIONAL USE"


@dataclass
class CheckedRun:
    packages: list[WorkPackageState]  # after deconfliction, judgment and findings
    judgment_flags: list[JudgmentFlag]
    certificate_findings: list[CertificateFinding]
    schedule_findings: list[ScheduleFinding]
    shift_outcomes: dict[str, CrewShiftOutcome]
    rollups: list[ProjectRollup]

    def _findings_for(self, pid: str):
        return ([f for f in self.judgment_flags if pid in f.work_package_ids],
                [f for f in self.certificate_findings if f.work_package_id == pid],
                [f for f in self.schedule_findings if pid in f.work_package_ids])

    def rules_by_package(self) -> dict[str, set[str]]:
        by_id = {p.work_package_id: p for p in self.packages}
        out: dict[str, set[str]] = {}
        for p in self.packages:
            rules = {r for other in p.conflicts for r in conflict_rule_ids(p, by_id[other])}
            rules |= set(_RULE_ID.findall(p.conflict_rationale or ""))
            for group in self._findings_for(p.work_package_id):
                rules |= {f.rule_id for f in group}
            out[p.work_package_id] = rules
        return out

    def status_by_package(self) -> dict[str, PackageStatus]:
        return {p.work_package_id: package_status(
            p, certificate_findings=self.certificate_findings,
            judgment_flags=self.judgment_flags, schedule_findings=self.schedule_findings)
            for p in self.packages}


def run_checks(ds: CarrierDataset, as_of: Optional[datetime] = None) -> CheckedRun:
    """Every deterministic check over a fresh copy of the dataset. Never mutates `ds`."""
    calendar = ds.calendar
    run_inputs = {"certificates": [c.model_dump() for c in ds.certificates],
                  "crews": [c.model_dump() for c in ds.crews], "calendar": calendar.model_dump()}
    state = deconfliction_node({"work_packages": ds.fresh_packages()})
    state = judgment_node(state)
    state = findings_node({**state, "run_inputs": run_inputs})
    packages = state["work_packages"]

    originals = ds.fresh_packages()  # flags and findings read the inputs, as the graph's nodes do
    flags = judgment_flags(originals)
    cert = [f for p in originals for f in check_certificates(p, ds.certificates)]
    sched = check_schedule_constraints(originals, ds.crews, calendar)
    flagged = [p for p in packages if p.requires_hitl_review or p.conflicts or p.conflict_rationale]
    outcomes = {p.work_package_id: suggest_crew_shift(originals, p.work_package_id, crews=ds.crews,
                                                      calendar=calendar, certificates=ds.certificates)
                for p in flagged}
    as_of = as_of or datetime.combine(ds.first_day, datetime.min.time())
    rollups = [rollup_project(pr, packages, as_of, certificate_findings=cert,
                              judgment_flags=flags, schedule_findings=sched)
               for pr in sort_projects(ds.projects)]
    return CheckedRun(packages, flags, cert, sched, outcomes, rollups)


def _t(t: Optional[datetime]) -> str:
    return fmt_time(t) if t is not None else "unscheduled"


def _suggestion_line(out: CrewShiftOutcome) -> str:
    s = out.suggestion
    if s is None:
        why = "; ".join(f"{r.shift_id} ({', '.join(list(r.rule_ids) + list(r.reasons)) or 'no reason recorded'})"
                        for r in out.rejected)
        return (f"No crew-shift suggestion: {out.reason or 'every later shift was rejected'}"
                + (f" Rejected: {why}." if why else ""))
    moves = "; ".join(f"{m.work_package_id} {_t(m.suggested_start)} to {_t(m.suggested_end)}" for m in s.moves)
    return (f"Suggested, not applied: move crew {s.crew_id} from {s.from_shift_id} to {s.to_shift_id} "
            f"({moves}). Re-checked against every rule; a person must Apply it in the reviewer.")


def _log_section(log: Optional[DecisionLog], anchor: Optional[tuple[int, str]]) -> list[str]:
    if log is None:
        return ["  No decision log supplied (pass --db to include one)."]
    lines = []
    try:
        n = log.verify_chain()
        lines.append(f"  entries: {n}, chain verified")
    except LogTamperError as e:
        lines.append(f"  CHAIN DOES NOT VERIFY: {e}")
    head = log.head()
    lines.append(f"  head: {head[1]} (seq {head[0]})" if head else "  head: none (empty log)")
    if anchor is not None:
        try:
            log.verify_anchor(*anchor)
            lines.append(f"  anchor seq {anchor[0]}: matches")
        except LogTamperError as e:
            lines.append(f"  ANCHOR DOES NOT MATCH: {e}")
    lines.append("  Record the head line outside this database; pass it back as --anchor SEQ:HASH")
    lines.append("  next time to detect entries removed from the end of the log.")
    return lines


def render(ds: CarrierDataset, *, as_of: datetime, decision_log: Optional[DecisionLog] = None,
           anchor: Optional[tuple[int, str]] = None) -> str:
    run = run_checks(ds, as_of)
    status = run.status_by_package()
    rules = run.rules_by_package()
    needs = [p for p in run.packages if status[p.work_package_id] != PackageStatus.CLEARED]
    cleared = [p.work_package_id for p in run.packages if status[p.work_package_id] == PackageStatus.CLEARED]

    out = [TITLE, f"Site: {ds.site}", f"As of: {_t(as_of)}", "",
           "SUMMARY",
           f"  {len(run.packages)} packages: {len(cleared)} cleared, {len(needs)} need a person.",
           "  Nothing below has been applied or approved; the reviewer is where decisions are made.",
           "", "PROJECTS (priority, then due date)"]
    names = {pr.project_id: pr.name for pr in ds.projects}
    for r in run.rollups:
        due = _t(r.due_date) if r.due_date else "no due date"
        out.append(f"  [{r.priority.value.upper()}] {r.project_id}  {names[r.project_id]}  "
                   f"due {due}  status: {r.overall_status.value}")
        for s, ids in r.package_ids_by_status.items():
            if ids:
                out.append(f"      {s.value}: {', '.join(ids)}")
        if r.late_package_ids:
            out.append(f"      LATE (ends after due date): {', '.join(r.late_package_ids)}")
        if r.past_due:
            out.append("      PAST DUE")

    out += ["", "NEEDS A PERSON"]
    for p in needs:
        pid = p.work_package_id
        lock = f", locked ({p.lock_reason})" if p.locked else ""
        out.append(f"  {pid}  {status[pid].value}  {_t(p.scheduled_start)} to {_t(p.scheduled_end)}  "
                   f"crew {p.crew_id or 'none'}{lock}")
        out.append(f"    {p.description}")
        for rid in sorted(rules[pid]):
            rule = named_rules.get_rule(rid)
            out.append(f"    {rid} {rule.title}. Contact: {rule.contact_role}.")
        # review-04 S11-03: every routing note the graph carries, verbatim, so a reason
        # or contact that isn't a catalogue rule is never dropped.
        notes = [n.strip() for n in (p.conflict_rationale or "").split(" | ") if n.strip()]
        out += [f"    Why: {n}" for n in notes]
        if not notes and not rules[pid]:
            out.append("    Why: marked for review in its input; no reason was recorded. Ask the planner who flagged it.")
        if p.conflicts:
            out.append(f"    Conflicts with: {', '.join(p.conflicts)}")
        if pid in run.shift_outcomes:
            out.append(f"    {_suggestion_line(run.shift_outcomes[pid])}")

    out += ["", "JUDGMENT FLAGS (routed to a named person)"]
    out += [f"  {f.rule_id} {', '.join(f.work_package_ids)} -> {f.routed_to.role} "
            f"{f.routed_to.display_name} ({f.routed_to.person_id}): {f.reason}"
            for f in run.judgment_flags] or ["  none"]
    out += ["", "CERTIFICATES"]
    out += [f"  {f.rule_id} {f.work_package_id}: {f.message}" for f in run.certificate_findings] or ["  none"]
    out += ["", "SCHEDULE"]
    out += [f"  {f.message}" for f in run.schedule_findings] or ["  none"]
    out += ["", "CLEARED", f"  {', '.join(cleared) or 'none'}"]
    out += ["", "DECISION LOG"] + _log_section(decision_log, anchor)
    out += ["", "Generated by deterministic code only; no language model wrote any of this brief."]
    return "\n".join(out) + "\n"


def _anchor(s: str) -> tuple[int, str]:
    seq, _, h = s.partition(":")
    return int(seq), h


def main(argv: Optional[list[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Print the notional daily brief.")
    ap.add_argument("--as-of", type=datetime.fromisoformat, required=True)
    ap.add_argument("--dataset", default=None, help="dataset JSON (default: the notional carrier)")
    ap.add_argument("--db", default=None, help="reviewer database, to include its decision log")
    ap.add_argument("--anchor", type=_anchor, default=None, help="SEQ:HASH from an earlier brief")
    a = ap.parse_args(argv)
    log = DecisionLog(a.db) if a.db else None
    try:
        print(render(load_carrier_dataset(a.dataset), as_of=a.as_of, decision_log=log, anchor=a.anchor), end="")
    finally:
        if log:
            log.close()


if __name__ == "__main__":
    main()
