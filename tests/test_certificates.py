"""Session 3: certificates with valid-from/valid-until checked against the whole work window.

All data here is notional -- no real ship, yard, or personnel data.
"""

from datetime import datetime as dt

import pytest

from agent_core.certificates import (
    Certificate,
    CertificateIssue,
    CertificateKind,
    check_certificates,
)
from agent_core.state import SafetyPermitsRequired, WorkPackageState

START, END = dt(2027, 1, 12, 7), dt(2027, 1, 12, 19)


def _pkg(start=START, end=END, **permits):
    return WorkPackageState(
        work_package_id="WP-1",
        description="notional hot work, frame 40-44",
        scheduled_start=start,
        scheduled_end=end,
        permits_required=SafetyPermitsRequired(**permits),
    )


def _cert(cid, frm, until, kind=CertificateKind.HOT_WORK_PERMIT, wp="WP-1"):
    return Certificate(certificate_id=cid, work_package_id=wp, kind=kind,
                       valid_from=frm, valid_until=until)


# --- Certificate model ------------------------------------------------------


def test_certificate_window_must_be_ordered():
    with pytest.raises(ValueError, match="valid_from"):
        _cert("C-1", END, START)


def test_kinds_match_every_permit_flag_on_the_package():
    # If a permit flag is added to SafetyPermitsRequired, it must get a certificate kind too,
    # or packages requiring it would be silently unchecked.
    assert {k.value for k in CertificateKind} == set(SafetyPermitsRequired.model_fields)


# --- coverage of the whole window -------------------------------------------


def test_no_permits_required_means_no_findings():
    assert check_certificates(_pkg(), []) == []


def test_single_certificate_covering_whole_window_passes():
    assert check_certificates(_pkg(hot_work_permit=True), [_cert("C-1", START, END)]) == []


def test_missing_certificate_is_flagged():
    [f] = check_certificates(_pkg(hot_work_permit=True), [])
    assert f.issue == CertificateIssue.MISSING
    assert f.kind == CertificateKind.HOT_WORK_PERMIT
    assert f.uncovered == [(START, END)]


def test_certificate_valid_at_start_but_expiring_mid_job_is_flagged():
    # The core Session 3 case: checking only the start time would pass this.
    [f] = check_certificates(_pkg(hot_work_permit=True), [_cert("C-1", START, dt(2027, 1, 12, 15))])
    assert f.issue == CertificateIssue.NOT_COVERED
    assert f.uncovered == [(dt(2027, 1, 12, 15), END)]
    assert f.certificate_ids == ["C-1"]


def test_certificate_not_yet_valid_at_start_is_flagged():
    [f] = check_certificates(_pkg(hot_work_permit=True), [_cert("C-1", dt(2027, 1, 12, 9), END)])
    assert f.uncovered == [(START, dt(2027, 1, 12, 9))]


def test_certificate_entirely_outside_window_is_flagged():
    [f] = check_certificates(
        _pkg(hot_work_permit=True), [_cert("C-1", dt(2027, 1, 10, 7), dt(2027, 1, 10, 19))]
    )
    assert f.issue == CertificateIssue.NOT_COVERED
    assert f.uncovered == [(START, END)]


def test_boundaries_are_inclusive():
    # valid_from == start and valid_until == end covers the window exactly.
    assert check_certificates(_pkg(hot_work_permit=True), [_cert("C-1", START, END)]) == []


def test_back_to_back_renewals_cover_the_window():
    certs = [
        _cert("C-1", START, dt(2027, 1, 12, 13)),
        _cert("C-2", dt(2027, 1, 12, 13), END),
    ]
    assert check_certificates(_pkg(hot_work_permit=True), certs) == []


def test_gap_between_renewals_is_reported_exactly():
    certs = [
        _cert("C-2", dt(2027, 1, 12, 14), END),
        _cert("C-1", START, dt(2027, 1, 12, 13)),
    ]
    [f] = check_certificates(_pkg(hot_work_permit=True), certs)
    assert f.uncovered == [(dt(2027, 1, 12, 13), dt(2027, 1, 12, 14))]
    assert f.certificate_ids == ["C-1", "C-2"]


def test_overlapping_certificates_merge():
    certs = [
        _cert("C-1", START, dt(2027, 1, 12, 15)),
        _cert("C-2", dt(2027, 1, 12, 10), END),
    ]
    assert check_certificates(_pkg(hot_work_permit=True), certs) == []


def test_multiple_gaps_all_reported_in_order():
    certs = [
        _cert("C-1", dt(2027, 1, 12, 8), dt(2027, 1, 12, 10)),
        _cert("C-2", dt(2027, 1, 12, 12), dt(2027, 1, 12, 18)),
    ]
    [f] = check_certificates(_pkg(hot_work_permit=True), certs)
    assert f.uncovered == [
        (START, dt(2027, 1, 12, 8)),
        (dt(2027, 1, 12, 10), dt(2027, 1, 12, 12)),
        (dt(2027, 1, 12, 18), END),
    ]


# --- matching ------------------------------------------------------------


def test_certificate_of_wrong_kind_does_not_count():
    certs = [_cert("C-1", START, END, kind=CertificateKind.CONFINED_SPACE_ENTRY_PERMIT)]
    [f] = check_certificates(_pkg(hot_work_permit=True), certs)
    assert f.issue == CertificateIssue.MISSING


def test_certificate_for_another_package_does_not_count():
    [f] = check_certificates(_pkg(hot_work_permit=True), [_cert("C-1", START, END, wp="WP-2")])
    assert f.issue == CertificateIssue.MISSING


def test_each_required_permit_is_checked_independently_in_stable_order():
    pkg = _pkg(hot_work_permit=True, marine_chemist_certificate=True, fall_protection_plan=True)
    certs = [_cert("C-1", START, END, kind=CertificateKind.MARINE_CHEMIST_CERTIFICATE)]
    findings = check_certificates(pkg, certs)
    assert [f.kind for f in findings] == [
        CertificateKind.HOT_WORK_PERMIT,
        CertificateKind.FALL_PROTECTION_PLAN,
    ]


# --- fail closed ---------------------------------------------------------


@pytest.mark.parametrize("start,end", [(None, None), (START, None), (None, END)])
def test_unscheduled_package_with_required_permit_cannot_be_verified(start, end):
    [f] = check_certificates(_pkg(start=start, end=end, hot_work_permit=True), [_cert("C-1", START, END)])
    assert f.issue == CertificateIssue.UNSCHEDULED


def test_duplicate_certificate_ids_raise():
    with pytest.raises(ValueError, match="duplicate"):
        check_certificates(_pkg(hot_work_permit=True), [_cert("C-1", START, END), _cert("C-1", START, END)])


def test_finding_message_names_the_gap():
    [f] = check_certificates(_pkg(hot_work_permit=True), [_cert("C-1", START, dt(2027, 1, 12, 15))])
    assert "hot_work_permit" in f.message
    assert "2027-01-12 15:00" in f.message


def test_check_does_not_mutate_the_package():
    pkg = _pkg(hot_work_permit=True)
    before = pkg.model_dump()
    check_certificates(pkg, [])
    assert pkg.model_dump() == before


def test_zero_length_window_outside_certificate_is_still_flagged():
    # start == end is a legal schedule; an uncovered instant must not read as "no gap".
    t = dt(2027, 1, 12, 7)
    [f] = check_certificates(
        _pkg(start=t, end=t, hot_work_permit=True), [_cert("C-1", dt(2027, 1, 11), dt(2027, 1, 11, 6))]
    )
    assert f.uncovered == [(t, t)]
    assert check_certificates(_pkg(start=t, end=t, hot_work_permit=True), [_cert("C-2", t, t)]) == []
