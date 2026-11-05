"""Builder's independent reproduction of review-01 re-check items (reopened R02, R06,
R09, R13, R14 and new N01-N05). Rebuilt from the reviewer's descriptions, run against
the current API. Each probe is isolated: an exception is reported as such, never
counted as "fixed". Run from the repo root: python reviews/review-01-recheck-repro.py
"""
import traceback
from datetime import datetime as dt, timedelta, timezone
from zoneinfo import ZoneInfo

from agent_core import events
from agent_core.certificates import Certificate, CertificateKind as K, check_certificates
from agent_core.deconfliction import check_conflict, deconfliction_node
from agent_core.projects import PackageStatus, Project, package_status, rollup_project
from agent_core.reasoning import reasoning_node
from agent_core.reschedule_suggestion import suggest_reschedule
from agent_core.state import HazardCategory as H, SafetyPermitsRequired, SpatialCoordinates as SC, WorkPackageState as W

LA = ZoneInfo("America/Los_Angeles")
results = {}


def wp(pid="WP-1", hz=(), sp=None, start=dt(2027, 1, 12, 7), end=dt(2027, 1, 12, 15), **kw):
    return W(work_package_id=pid, description="notional", hazard_categories=list(hz),
             spatial=sp or SC(compartment_id="TANK-1"), scheduled_start=start, scheduled_end=end, **kw)


def probe(rid):
    def deco(fn):
        try:
            ok, obs = fn()
            results[rid] = ok
            print(f"{rid}: {'REPRODUCED' if ok else 'NOT REPRODUCED'} -- {obs}")
        except Exception as e:
            results[rid] = None
            print(f"{rid}: ERROR (neither reproduced nor fixed) -- {type(e).__name__}: {e}")
        return fn
    return deco


@probe("R02")
def _():
    a = wp("A")
    b = wp("B", permits_required=SafetyPermitsRequired(hot_work_permit=True))
    certs = iter(check_certificates(b, []))  # B's real missing-permit finding, as a one-shot iterator
    sa = package_status(a, certificate_findings=certs, judgment_flags=[], schedule_findings=[])
    sb = package_status(b, certificate_findings=certs, judgment_flags=[], schedule_findings=[])
    return sb == PackageStatus.CLEARED, f"A={sa.value}, B={sb.value} with B's missing permit in a shared iterator"


@probe("R06")
def _():
    a = wp("X", [H.HOT_WORK])
    b = wp("X", [H.CONFINED_SPACE])
    return a is not b and check_conflict(a, b) is None, f"two distinct records both 'X': check_conflict={check_conflict(a, b)!r}"


def _two_day_overload():
    return [wp("A", [H.HOT_WORK], fire_watch_id="F", hot_worker_count=5),
            wp("B", [H.HOT_WORK], fire_watch_id="F", hot_worker_count=5,
               start=dt(2027, 1, 13, 7), end=dt(2027, 1, 13, 15))]


@probe("R09")
def _():
    out = {p.work_package_id: p for p in deconfliction_node({"work_packages": _two_day_overload()})["work_packages"]}
    b = out["B"]
    return b.cleared_for_execution and not b.requires_hitl_review, \
        f"A review={out['A'].requires_hitl_review}; B review={b.requires_hitl_review}, cleared={b.cleared_for_execution}"


@probe("R13")
def _():
    p = wp(permits_required=SafetyPermitsRequired(hot_work_permit=True))
    cs = [Certificate(certificate_id="C1", work_package_id="WP-1", kind=K.HOT_WORK_PERMIT,
                      valid_from=dt(2027, 1, 12, 7), valid_until=dt(2027, 1, 12, 11)),
          Certificate(certificate_id="C2", work_package_id="WP-1", kind=K.HOT_WORK_PERMIT,
                      valid_from=dt(2027, 1, 12, 11, tzinfo=timezone.utc), valid_until=dt(2027, 1, 12, 16, tzinfo=timezone.utc))]
    try:
        check_certificates(p, cs)
        return False, "no error"
    except TypeError as e:
        return True, f"bare TypeError: {e}"
    except ValueError as e:
        return False, f"descriptive ValueError: {str(e)[:80]}"


@probe("R14")
def _():
    p = wp(start=dt(2027, 1, 12, 9), end=dt(2027, 1, 12, 10), permits_required=SafetyPermitsRequired(hot_work_permit=True))
    cs = [Certificate(certificate_id="C1", work_package_id="WP-1", kind=K.HOT_WORK_PERMIT,
                      valid_from=dt(2027, 1, 12, 9), valid_until=dt(2027, 1, 12, 9, 15, 10, 2)),
          Certificate(certificate_id="C2", work_package_id="WP-1", kind=K.HOT_WORK_PERMIT,
                      valid_from=dt(2027, 1, 12, 9, 15, 10, 8), valid_until=dt(2027, 1, 12, 10))]
    [f] = check_certificates(p, cs)
    return "09:15:10 to 2027-01-12 09:15:10" in f.message, f"message={f.message!r}"


@probe("N01")
def _():
    seen = []
    orig = events.emit
    events.emit = lambda name, **kw: seen.append((name, kw))
    try:
        state = deconfliction_node({"work_packages": [wp(hz=[H.HOT_WORK], fire_watch_id="F", hot_worker_count=5)]})
        state = reasoning_node(state)
    finally:
        events.emit = orig
    result = [kw for n, kw in seen if n == "deconfliction_result"][0]
    p = state["work_packages"][0]
    return result["conflicts"] == [] and p.requires_hitl_review and p.safety_brief is None, \
        f"event conflicts={result['conflicts']}, review={p.requires_hitl_review}, brief={p.safety_brief}"


@probe("N02")
def _():
    p = wp(hz=[H.HOT_WORK], fire_watch_id="F", hot_worker_count=5)
    s = suggest_reschedule([p], "WP-1", step=timedelta(hours=1), max_shift=timedelta(days=1))
    return s is not None, f"suggestion={None if s is None else s.shift} for a package that overloads its watch at any time"


@probe("N03")
def _():
    start, end = dt(2026, 11, 1, 1, 45, tzinfo=LA), dt(2026, 11, 1, 1, 15, fold=1, tzinfo=LA)
    a = wp("A", [H.HOT_WORK], start=start, end=end)
    b = wp("B", [H.CONFINED_SPACE], start=start, end=end)
    s = suggest_reschedule([a, b], "A", step=timedelta(hours=1), max_shift=timedelta(hours=3))
    if s is None:
        return False, "no suggestion"
    inv = s.suggested_end.astimezone(timezone.utc) < s.suggested_start.astimezone(timezone.utc)
    return inv, f"suggested {s.suggested_start.isoformat()} -> {s.suggested_end.isoformat()}"


@probe("N04")
def _():
    s0, s1 = dt(2026, 11, 1, 1, 15, fold=1, tzinfo=LA), dt(2026, 11, 1, 1, 45, fold=1, tzinfo=LA)
    p = wp(start=s0, end=s1, permits_required=SafetyPermitsRequired(hot_work_permit=True))
    c = Certificate(certificate_id="C", work_package_id="WP-1", kind=K.HOT_WORK_PERMIT,
                    valid_from=dt(2026, 11, 1, 1, 15, tzinfo=LA), valid_until=dt(2026, 11, 1, 1, 45, tzinfo=LA))
    [f] = check_certificates(p, [c])
    return "09:15" in f.message and "+00" not in f.message and "UTC" not in f.message, f"message={f.message!r}"


@probe("N05")
def _():
    proj = Project(project_id="P", name="n", work_package_ids=["WP-1"])
    aware = wp(start=dt(2027, 1, 12, 7, tzinfo=timezone.utc), end=dt(2027, 1, 12, 15, tzinfo=timezone.utc))
    try:
        rollup_project(proj, [aware], as_of=dt(2027, 1, 10), certificate_findings=[], judgment_flags=[], schedule_findings=[])
        return False, "rolled up"
    except ValueError as e:
        return True, f"refused with no due date to compare: {str(e)[:70]}"


print(f"\nreproduced: {sorted(k for k, v in results.items() if v)}")
print(f"not reproduced: {sorted(k for k, v in results.items() if v is False)}")
print(f"errors: {sorted(k for k, v in results.items() if v is None)}")
