"""Builder's independent reproduction of review-02 (Session 7) findings S07-01..05.
Rebuilt from the reviewer's descriptions. Each probe is isolated; an exception is
reported as ERROR, never as fixed. Run from the repo root.
"""
import importlib
import sys
from datetime import date, datetime as dt, time

from agent_core.crews import Crew, Shift, ShiftCalendar
from agent_core.shift_suggester import CrewShiftOutcome, suggest_crew_shift
from agent_core.state import HazardCategory as H, SpatialCoordinates as SC, WorkPackageState as W

PATTERN = [("DAY", time(7), time(15, 30)), ("SWING", time(15, 30), time(0)), ("MID", time(0), time(7))]
CAL = ShiftCalendar.from_daily_pattern(date(2027, 1, 12), 3, PATTERN)
CREWS = [Crew(crew_id="CR-WELD", name="n"), Crew(crew_id="CR-TANK", name="n")]
results = {}


def d(h, m=0):
    return dt(2027, 1, 12, h, m)


def wp(pid, start, end, crew="CR-WELD", hz=(), sp=None, **kw):
    return W(work_package_id=pid, description="notional", hazard_categories=list(hz),
             spatial=sp if sp is not None else SC(compartment_id="TANK-4"),
             scheduled_start=start, scheduled_end=end, crew_id=crew, **kw)


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


@probe("S07-01")
def _():
    pkgs = [wp("WELD-1", d(7), d(8)),
            wp("PARTIAL", d(14), None, locked=True, lock_reason="notional fixed ongoing assignment")]
    s = suggest_crew_shift(pkgs, "WELD-1", crews=CREWS, calendar=CAL, certificates=[], max_shifts=1).suggestion
    return s is not None and [m.work_package_id for m in s.moves] == ["WELD-1"], \
        f"suggestion moves {None if s is None else [m.work_package_id for m in s.moves]} while locked PARTIAL (no end) is ignored"


@probe("S07-02")
def _():
    cal = ShiftCalendar(shifts=[Shift(shift_id="LONG", name="LONG", start=d(7), end=d(15)),
                                Shift(shift_id="SHORT", name="SHORT", start=d(15), end=d(16)),
                                Shift(shift_id="FOLLOWING", name="FOLLOWING", start=d(16), end=d(23))])
    s = suggest_crew_shift([wp("JOB", d(14), d(14, 30))], "JOB", crews=CREWS, calendar=cal,
                           certificates=[], max_shifts=1).suggestion
    m = s.moves[0]
    return s.to_shift_id == "SHORT" and m.suggested_start >= d(16), \
        f"to_shift_id={s.to_shift_id}, suggested {m.suggested_start.time()}-{m.suggested_end.time()} (SHORT ends 16:00)"


@probe("S07-03")
def _():
    aloft = wp("ALOFT", d(7), d(8), hz=[H.WORKING_ALOFT], sp=SC(is_aloft=True))
    other = wp("OTHER", d(15, 30), d(17), crew="CR-TANK")
    s = suggest_crew_shift([aloft, other], "ALOFT", crews=CREWS, calendar=CAL, certificates=[]).suggestion
    return s is not None, f"unlocated aloft job got suggestion {None if s is None else s.to_shift_id}"


@probe("S07-04")
def _():
    s = suggest_crew_shift([wp("WELD-1", d(7), d(8))], "WELD-1", crews=CREWS, calendar=CAL,
                           certificates=[], max_shifts=-1).suggestion
    return s is not None, f"max_shifts=-1 accepted; suggestion={None if s is None else s.to_shift_id}"


@probe("S07-05")
def _():
    sys.path.insert(0, "tests")
    t = importlib.import_module("test_shift_suggester")
    orig = t.run
    t.run = lambda *a, **k: CrewShiftOutcome(suggestion=None, rejected=[])
    passed = []
    try:
        for name in ("test_certificate_that_does_not_cover_the_new_shift_rejects_it",
                     "test_judgment_flag_on_a_moved_package_rejects_every_shift"):
            try:
                getattr(t, name)(); passed.append(name)
            except AssertionError:
                pass
    finally:
        t.run = orig
    return len(passed) == 2, f"tests passing with an empty outcome: {len(passed)}/2"


print(f"\nreproduced: {sorted(k for k, v in results.items() if v)}")
print(f"not reproduced: {sorted(k for k, v in results.items() if v is False)}")
print(f"errors: {sorted(k for k, v in results.items() if v is None)}")
