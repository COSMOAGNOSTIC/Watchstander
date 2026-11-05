"""Builder's independent reproduction of review-01 findings.
Originally run at 12d3873 with the old `package_status(p)` signature. Updated after the
re-check so it runs against the current API (findings are required arguments); at
12d3873 use the git history of this file. Each probe prints REPRODUCED or NOT REPRODUCED."""
import importlib
import sys
from datetime import datetime as dt, timezone
from zoneinfo import ZoneInfo

from agent_core import deconfliction, judgment, named_rules
from agent_core.certificates import Certificate, CertificateKind as K, check_certificates
from agent_core.deconfliction import check_conflict, conflict_rule_ids, find_all_conflicts
from agent_core.judgment import Roster, judgment_flags
from agent_core.projects import PackageStatus, package_status
from agent_core.state import HazardCategory as H, SafetyPermitsRequired, SpatialCoordinates as SC, WorkPackageState as W

T0, T1 = dt(2027, 1, 12, 7), dt(2027, 1, 12, 15)
NOF = dict(certificate_findings=[], judgment_flags=[], schedule_findings=[])
results = {}


def rec(rid, ok, obs):
    results[rid] = ok
    print(f"{rid}: {'REPRODUCED' if ok else 'NOT REPRODUCED'} -- {obs}")


def wp(pid="WP-1", hz=(), sp=None, start=T0, end=T1, **kw):
    return W(work_package_id=pid, description="notional", hazard_categories=list(hz),
             spatial=sp or SC(), scheduled_start=start, scheduled_end=end, **kw)


# R01
p = wp(); p.requires_hitl_review = True
rec("R01", package_status(p, **NOF) == PackageStatus.CLEARED, f"status after setting requires_hitl_review on live model = {package_status(p, **NOF).value}")

# R02
p = wp(hz=[H.HOT_WORK], permits_required=SafetyPermitsRequired(hot_work_permit=True))
c, j = check_certificates(p, []), judgment_flags([p])
s = package_status(p, certificate_findings=c, judgment_flags=j, schedule_findings=[])
rec("R02", s == PackageStatus.CLEARED and c and j, f"status={s.value}, cert={[f.issue.value for f in c]}, judgment={[f.rule_id for f in j]}")

# R03
la = ZoneInfo("America/Los_Angeles")
pdt0, pdt1 = dt(2026, 11, 1, 1, 15, tzinfo=la), dt(2026, 11, 1, 1, 45, tzinfo=la)
pst0, pst1 = pdt0.replace(fold=1), pdt1.replace(fold=1)
real_gap = pst0.astimezone(timezone.utc) - pdt1.astimezone(timezone.utc)
p = wp(start=pst0, end=pst1, permits_required=SafetyPermitsRequired(hot_work_permit=True))
cert = Certificate(certificate_id="C", work_package_id="WP-1", kind=K.HOT_WORK_PERMIT, valid_from=pdt0, valid_until=pdt1)
f = check_certificates(p, [cert])
rec("R03", f == [], f"permit ends {real_gap} (real time) before job starts; findings={len(f)}")

# R04
p = wp(permits_required={"hot_work_permti": True})
rec("R04", check_certificates(p, []) == [] and not p.permits_required.hot_work_permit,
    f"typo key accepted; hot_work_permit={p.permits_required.hot_work_permit}; findings={check_certificates(p, [])}")

# R05
try:
    p = wp(pid="", permits_required=SafetyPermitsRequired(hot_work_permit=True))
    cert = Certificate(certificate_id="", work_package_id="", kind=K.HOT_WORK_PERMIT, valid_from=T0, valid_until=T1)
    rec("R05", check_certificates(p, [cert]) == [], "blank package ID and blank certificate ID accepted; blank-to-blank join satisfied the permit")
except Exception as e:
    rec("R05", False, f"rejected: {e}")

# R06
a = wp("A", [H.HOT_WORK], SC(compartment_id="TANK-1"))
b = wp("A", [H.CONFINED_SPACE], SC(compartment_id="TANK-1"))
rec("R06", check_conflict(a, b) is None and judgment_flags([a, b]) == [],
    f"same-ID pair: check_conflict={check_conflict(a, b)!r}, judgment={judgment_flags([a, b])}")

# R07
a = wp("A", [H.HOT_WORK], SC(compartment_id="TANK-1"))
b = wp("B", [H.CONFINED_SPACE], SC(frame_start=1, frame_end=3))
ws = wp("C", [H.HOT_WORK], SC(compartment_id="   "))
rec("R07", check_conflict(a, b) is None and judgment_flags([a, b]) == [] and judgment_flags([ws]) == [],
    f"no common coordinate -> conflict={check_conflict(a, b)!r}, judgment={judgment_flags([a, b])}; whitespace compartment flags={judgment_flags([ws])}")

# R08
p = wp(sp=SC(is_enclosed_or_confined=True), permits_required=SafetyPermitsRequired(confined_space_entry_permit=True))
rec("R08", judgment_flags([p]) == [], f"entry by spatial flag + permit, no hazard list, no location -> flags={judgment_flags([p])}")

# R09
p = wp(hz=[H.HOT_WORK], fire_watch_id="FW-1", hot_worker_count=5)
out = find_all_conflicts([p])
peak, _ = deconfliction._fire_watch_peak_concurrency([p])
rec("R09", peak > deconfliction.MAX_CONCURRENT_HOT_WORKERS_PER_FIRE_WATCH and out[0].conflicts == [] and not out[0].conflict_rationale,
    f"peak={peak} > limit={deconfliction.MAX_CONCURRENT_HOT_WORKERS_PER_FIRE_WATCH}; conflicts={out[0].conflicts}, status={package_status(out[0], **NOF).value}")

# R10
a = wp("A", [H.HOT_WORK], SC(frame_start=10, frame_end=12, is_aloft=True))
b = wp("B", [H.CONFINED_SPACE], SC(frame_start=10, frame_end=12))
ids = conflict_rule_ids(a, b)
rec("R10", ids == ["WS-HZ-001"] and deconfliction._vertically_stacked(a, b), f"both predicates true; rule IDs={ids}")

# R11
try:
    r = Roster(people=[{"person_id": "", "display_name": "", "role": "Gas Free Engineer", "primary": True, "notional": True}])
    [f] = judgment_flags([wp(hz=[H.HOT_WORK])], roster=r)
    rec("R11", f.message.endswith("Gas Free Engineer  ()."), f"message tail={f.message[-30:]!r}")
except Exception as e:
    rec("R11", False, f"rejected: {e}")

# R12
pk = [wp("A+B", [H.CONFINED_SPACE], SC(compartment_id="T1")), wp("C", [H.CONFINED_SPACE], SC(compartment_id="T1")),
      wp("A", [H.CONFINED_SPACE], SC(compartment_id="T2")), wp("B+C", [H.CONFINED_SPACE], SC(compartment_id="T2"))]
fl = [f for f in judgment_flags(pk) if f.rule_id == "WS-JF-002"]
rec("R12", len(fl) == 2 and fl[0].flag_id == fl[1].flag_id, f"two independent flags, IDs={[f.flag_id for f in fl]}")

# R13
p = wp(permits_required=SafetyPermitsRequired(hot_work_permit=True))
cert = Certificate(certificate_id="C", work_package_id="WP-1", kind=K.HOT_WORK_PERMIT,
                   valid_from=dt(2027, 1, 12, 0, tzinfo=timezone.utc), valid_until=dt(2027, 1, 13, tzinfo=timezone.utc))
try:
    check_certificates(p, [cert]); rec("R13", False, "no error")
except TypeError as e:
    rec("R13", True, f"TypeError: {e}")

# R14
p = wp(start=dt(2027, 1, 12, 6), end=dt(2027, 1, 12, 8), permits_required=SafetyPermitsRequired(hot_work_permit=True))
cs = [Certificate(certificate_id="C1", work_package_id="WP-1", kind=K.HOT_WORK_PERMIT, valid_from=dt(2027, 1, 12, 6), valid_until=dt(2027, 1, 12, 7, 0, 10)),
      Certificate(certificate_id="C2", work_package_id="WP-1", kind=K.HOT_WORK_PERMIT, valid_from=dt(2027, 1, 12, 7, 0, 30), valid_until=dt(2027, 1, 12, 8))]
[f] = check_certificates(p, cs)
rec("R14", "07:00 to 2027-01-12 07:00" in f.message, f"message={f.message!r}")

# R15: mutate detector to always-None and run the agreement test
sys.path.insert(0, "tests")
tnr = importlib.import_module("test_named_rules")
orig = deconfliction._detect_conflict
deconfliction._detect_conflict = lambda a, b: None
try:
    tnr.test_rule_ids_and_rationale_match_independent_expectations(); passed = True
except AssertionError:
    passed = False
deconfliction._detect_conflict = orig
rec("R15", passed, f"agreement test passed with a detector that never detects: {passed}")

# R16: swap a contact role for a person's name and run the roles test
r0 = tnr.RULES[0]; old = r0.contact_role; r0.contact_role = "Riley Example"
try:
    tnr.test_contacts_are_roles_not_named_people(); passed = True
except AssertionError:
    passed = False
r0.contact_role = old
rec("R16", passed, f"roles test passed with contact_role='Riley Example': {passed}")

# R17: add a fourth judgment rule with no trigger
extra = named_rules.NamedRule(rule_id="WS-JF-099", title="untriggered", category="judgment", applies_to=[],
                              citations=[], contact_role="Gas Free Engineer", note="probe only")
named_rules.RULES.append(extra)
try:
    got = {f.rule_id for f in judgment_flags([wp(hz=[H.HOT_WORK])])}
    rec("R17", got == {"WS-JF-003"}, f"catalogue has WS-JF-099, preflight accepted it, flags emitted={sorted(got)}")
finally:
    named_rules.RULES.remove(extra)

print(f"\n{sum(bool(v) for v in results.values())}/{len(results)} reproduced")
