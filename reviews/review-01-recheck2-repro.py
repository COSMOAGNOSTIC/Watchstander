"""Builder's independent reproduction of review-01 re-check 2 items (R02 reopened via
the rollup; new N06, N07). Each probe is isolated; an exception is reported as ERROR,
never as fixed. Run from the repo root: python reviews/review-01-recheck2-repro.py
"""
from datetime import datetime as dt, timezone

from agent_core.certificates import Certificate, CertificateKind as K, check_certificates
from agent_core.deconfliction import deconfliction_node
from agent_core.projects import PackageStatus, Project, rollup_project
from agent_core.reasoning import reasoning_node
from agent_core.state import HazardCategory as H, SafetyPermitsRequired, SpatialCoordinates as SC, WorkPackageState as W

results = {}


def wp(pid="WP-1", hz=(), start=dt(2027, 1, 12, 7), end=dt(2027, 1, 12, 15), **kw):
    return W(work_package_id=pid, description="notional", hazard_categories=list(hz),
             spatial=SC(compartment_id="TANK-1"), scheduled_start=start, scheduled_end=end, **kw)


def probe(rid):
    def deco(fn):
        try:
            ok, obs = fn()
            results[rid] = ok
            print(f"{rid}: {'REPRODUCED' if ok else 'NOT REPRODUCED'} -- {obs}")
        except Exception as e:
            results[rid] = None
            print(f"{rid}: ERROR -- {type(e).__name__}: {e}")
        return fn
    return deco


@probe("R02")
def _():
    a = wp("A")
    b = wp("B", permits_required=SafetyPermitsRequired(hot_work_permit=True))
    shared = iter(check_certificates(b, []))
    kw = dict(judgment_flags=[], schedule_findings=[])
    ra = rollup_project(Project(project_id="PA", name="a", work_package_ids=["A"]), [a, b], as_of=dt(2027, 1, 10),
                        certificate_findings=shared, **kw)
    rb = rollup_project(Project(project_id="PB", name="b", work_package_ids=["B"]), [a, b], as_of=dt(2027, 1, 10),
                        certificate_findings=shared, **kw)
    return rb.overall_status == PackageStatus.CLEARED, f"A={ra.overall_status.value}, B={rb.overall_status.value}"


@probe("N06")
def _():
    state = deconfliction_node({"work_packages": [wp(hz=[H.HOT_WORK], fire_watch_id="F", hot_worker_count=5)]})
    brief = reasoning_node(state)["work_packages"][0].safety_brief
    invented = "overlapping work package" in brief.executive_summary
    wrong_fix = "reschedule one package" in brief.recommended_action
    return invented and wrong_fix, f"source={brief.source}; summary starts {brief.executive_summary[:110]!r}; action={brief.recommended_action[:90]!r}"


@probe("N07")
def _():
    p = wp(permits_required=SafetyPermitsRequired(hot_work_permit=True))
    certs = [Certificate(certificate_id="HW", work_package_id="WP-1", kind=K.HOT_WORK_PERMIT,
                         valid_from=dt(2027, 1, 12, 7), valid_until=dt(2027, 1, 12, 15)),
             Certificate(certificate_id="FP", work_package_id="WP-1", kind=K.FALL_PROTECTION_PLAN,
                         valid_from=dt(2027, 1, 12, 7, tzinfo=timezone.utc), valid_until=dt(2027, 1, 12, 15, tzinfo=timezone.utc))]
    try:
        f = check_certificates(p, certs)
        return False, f"assessed: {len(f)} findings"
    except ValueError as e:
        return True, f"refused because of an unrequired certificate: {str(e)[:90]}"


print(f"\nreproduced: {sorted(k for k, v in results.items() if v)}")
print(f"not reproduced: {sorted(k for k, v in results.items() if v is False)}")
print(f"errors: {sorted(k for k, v in results.items() if v is None)}")
