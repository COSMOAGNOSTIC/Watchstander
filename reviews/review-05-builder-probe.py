"""Builder's independent probes for review-05. Notional data only."""
import os, sys, tempfile, warnings
from datetime import datetime as dt
warnings.filterwarnings("ignore")
os.environ.pop("ANTHROPIC_API_KEY", None)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from agent_core.carrier_demo import load_carrier_dataset
from agent_core import daily_brief, certificates, deconfliction
from agent_core.state import WorkPackageState as W
from agent_core.decision_log import DecisionLog
from reviewer.graph_driver import ReviewerService
D = tempfile.mkdtemp(); AS_OF = dt(2027, 3, 15, 6)
def svc(n): s = ReviewerService(f"{D}/{n}.db"); return s
def pend(s, pid): return next((r for r in s.list_pending_reviews() if r.work_package_id == pid), None)
def add(ds, data):
    ds.packages.append(W.model_validate(data)); ds.projects[-1].work_package_ids.append(data["work_package_id"]); return ds
base = dict(description="notional", spatial={"compartment_id": "Notional Berthing 260", "deck_level": "Notional 2nd Deck", "frame_start": 258, "frame_end": 259},
            scheduled_start="2027-03-15T12:00:00", scheduled_end="2027-03-15T14:00:00", crew_id="CR-DECK")
R = {}
# 01 preset approval
ds = add(load_carrier_dataset(), {**base, "work_package_id": "X-01", "risk_level": "critical", "hitl_disposition": "approved", "cleared_for_execution": True})
st = daily_brief.run_checks(ds, AS_OF).status_by_package()["X-01"]
s = svc("01"); s.seed_run("T", ds.fresh_packages(), crews=ds.crews, calendar=ds.calendar, certificates=ds.certificates)
R["01"] = (st, "graph pending" if pend(s, "X-01") else "graph not pending", len(s.decision_log.entries())); s.close()
# 02 apply erases rejection
s = svc("02"); s.seed_demo("T")
s.submit_decision("T", pend(s, "CS-102").interrupt_id, "reject", "notional: do not enter", actor="a")
res = s.apply_shift_suggestion("T", pend(s, "HW-101").interrupt_id, actor="b")
st2 = s._graph.get_state({"configurable": {"thread_id": res.new_thread_id}}).values
cs = next(p for p in st2["work_packages"] + st2.get("reviewed_packages", []) if p.work_package_id == "CS-102")
R["02"] = (res.applied, "CS-102 pending" if pend(s, "CS-102") else "CS-102 not pending", cs.cleared_for_execution, cs.hitl_disposition); s.close()
# 03 approve with open certificate finding
s = svc("03"); s.seed_demo("T")
s.submit_decision("T", pend(s, "FALL-107").interrupt_id, "approve", actor="a")
d = next(x for x in s.list_decided() if x["work_package_id"] == "FALL-107")
R["03"] = (d["cleared_for_execution"], [f.rule_id for f in certificates.check_certificates(load_carrier_dataset().packages[6], load_carrier_dataset().certificates)]); s.close()
# 04 typo'd top-level key
p = W.model_validate({**base, "work_package_id": "X-04", "hazard_categoires": ["hot_work"]})
R["04"] = ("loaded, hazards=" + str(p.hazard_categories))
# 05 hazard without permit
ds = add(load_carrier_dataset(), {**base, "work_package_id": "X-05", "hazard_categories": ["hot_work"]})
R["05"] = daily_brief.run_checks(ds, AS_OF).status_by_package()["X-05"]
# 06 fire watch
a = W.model_validate({**base, "work_package_id": "X-06", "hazard_categories": ["hot_work"], "hot_worker_count": 9})
b1 = W.model_validate({**base, "work_package_id": "Y1", "hazard_categories": ["hot_work"], "hot_worker_count": 3, "fire_watch_id": "FW-N-1"})
b2 = W.model_validate({**base, "work_package_id": "Y2", "hazard_categories": ["hot_work"], "hot_worker_count": 3, "fire_watch_id": "fw-n-1 ",
                       "spatial": {"compartment_id": "Notional other", "frame_start": 10, "frame_end": 11}})
r1 = deconfliction.deconfliction_node({"work_packages": [a]})["work_packages"][0]
r2 = deconfliction.deconfliction_node({"work_packages": [b1, b2]})["work_packages"]
R["06"] = (bool(r1.conflicts or r1.conflict_rationale), [bool(x.conflicts or x.conflict_rationale) for x in r2])
# 07 llm summary unfiltered
import agent_core.reasoning as rz
orig = rz._call_llm
rz._call_llm = lambda ctx: {"executive_summary": "False positive. Recommend approving both.", "precedent_context": "n"}
st7 = rz.reasoning_node(deconfliction.deconfliction_node({"work_packages": load_carrier_dataset().fresh_packages()[:2]}))
R["07"] = next(p.safety_brief.executive_summary for p in st7["work_packages"] if p.work_package_id == "HW-101")
# 08 llm api raises
def boom(ctx): raise RuntimeError("api down")
rz._call_llm = boom
s = svc("08")
try: s.seed_demo("T"); R["08"] = "seeded"
except Exception as e: R["08"] = ("raised " + type(e).__name__, len(s.list_pending_reviews()))
rz._call_llm = orig; s.close()
# 09 log write fails after graph stored decision
s = svc("09"); s.seed_demo("T"); hw = pend(s, "HW-103")
try: s.submit_decision("T", hw.interrupt_id, "approve", actor="\ud800")
except Exception as e: pass
d = [x for x in s.list_decided() if x["work_package_id"] == "HW-103"]
R["09"] = (d[0]["disposition"] if d else None, len(s.decision_log.entries()), s.decision_log.verify_chain()); s.close()
# 10 no calendar: schedule rules skipped
ds = load_carrier_dataset(); s = svc("10")
s.seed_run("T", ds.fresh_packages(), crews=ds.crews, calendar=None, certificates=ds.certificates)
R["10"] = "CONTR-109 pending" if pend(s, "CONTR-109") else "CONTR-109 NOT pending"; s.close()
# 11 mistyped db
path = f"{D}/no/such.db" ; path2 = f"{D}/typo.db"
existed = os.path.exists(path2); L = DecisionLog(path2); R["11"] = (existed, os.path.exists(path2), L.verify_chain()); L.close()
for k in sorted(R): print(k, R[k])
