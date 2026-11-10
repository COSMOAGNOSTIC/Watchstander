"""
Certificates with validity windows, checked against a package's whole work window.

`SafetyPermitsRequired` on a WorkPackageState says *which* permits a job
needs; nothing previously said whether a permit actually existed or when
it was valid. A `Certificate` is that record: one permit of one kind, for
one work package, valid over the closed interval [valid_from, valid_until].

`check_certificates()` requires that, for every permit the package needs,
the union of matching certificates covers the package's entire scheduled
window [scheduled_start, scheduled_end] -- not just its start. A permit
valid when the shift begins but expiring at 1500 on a job scheduled to
1900 is a finding, with the exact uncovered interval reported.
Back-to-back renewals (a gas-free certificate reissued each shift) count
as continuous coverage when one ends at the instant the next begins.

Per ADR-031, a validity window is a hard constraint, not a schedule
preference: this module only reports, it never moves a window or a
schedule, and it never changes the package. It fails closed -- a package
that needs a permit but has no complete schedule cannot be verified, and
that is itself a finding rather than a pass.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Iterable, Literal, Optional

from pydantic import BaseModel, ConfigDict, model_validator

from agent_core import named_rules
from agent_core.intervals import uncovered
from agent_core.validation import NonBlankStr, fmt_time, instant, require_comparable
from agent_core.state import WorkPackageState


class CertificateKind(str, Enum):
    """One per `SafetyPermitsRequired` field, same names, same order."""

    HOT_WORK_PERMIT = "hot_work_permit"
    CONFINED_SPACE_ENTRY_PERMIT = "confined_space_entry_permit"
    FALL_PROTECTION_PLAN = "fall_protection_plan"
    MARINE_CHEMIST_CERTIFICATE = "marine_chemist_certificate"
    COMPETENT_PERSON_INSPECTION = "competent_person_inspection"
    # review-05 R05-05 (Donnie): working aloft is legal on an aloft chit signed by the CSOOW
    # for the day, or a standing aloft the CO authorizes for a date range. Zones: Known Debt.
    ALOFT_AUTHORIZATION = "aloft_authorization"


class CertificateIssue(str, Enum):
    MISSING = "missing"  # no certificate of this kind for this package at all
    NOT_COVERED = "not_covered"  # certificates exist but leave part of the window uncovered
    UNSCHEDULED = "unscheduled"  # package has no complete schedule, so coverage can't be verified


class Certificate(BaseModel):
    model_config = ConfigDict(extra="forbid")  # review-05 R05-04

    certificate_id: NonBlankStr
    work_package_id: Optional[NonBlankStr] = None  # None only for a ship-wide standing aloft
    kind: CertificateKind
    form: Optional[Literal["chit", "standing"]] = None  # aloft authorization only
    valid_from: datetime
    valid_until: datetime

    @model_validator(mode="after")
    def _shape(self) -> "Certificate":
        aloft = self.kind == CertificateKind.ALOFT_AUTHORIZATION
        if aloft and self.form is None:
            raise ValueError(f"{self.certificate_id}: an aloft authorization is a 'chit' or a 'standing' aloft")
        if not aloft and self.form is not None:
            raise ValueError(f"{self.certificate_id}: only an aloft authorization has a form")
        standing = aloft and self.form == "standing"
        if aloft and self.form == "chit" and instant(self.valid_until) - instant(self.valid_from) > timedelta(hours=24):
            # review-05 re-check (Donnie): a chit is signed for the day; a date range is a standing aloft.
            raise ValueError(f"{self.certificate_id}: an aloft chit covers one day (24 hours at most); "
                             "use a standing aloft for a date range")
        if standing and self.work_package_id is not None:
            raise ValueError(f"{self.certificate_id}: a standing aloft is ship-wide; it names no package")
        if not standing and self.work_package_id is None:
            raise ValueError(f"{self.certificate_id}: names no work package")
        return self

    def covers_package(self, pid: str) -> bool:
        return self.work_package_id is None or self.work_package_id == pid

    @model_validator(mode="after")
    def _window_is_ordered(self) -> "Certificate":
        require_comparable([("valid_from", self.valid_from), ("valid_until", self.valid_until)])
        if instant(self.valid_from) > instant(self.valid_until):
            raise ValueError(
                f"valid_from ({self.valid_from}) must be <= valid_until ({self.valid_until}) "
                f"for certificate {self.certificate_id}"
            )
        return self


class CertificateFinding(BaseModel):
    work_package_id: str
    kind: CertificateKind
    issue: CertificateIssue
    rule_id: str
    uncovered: list[tuple[datetime, datetime]]
    certificate_ids: list[str]
    message: str


def _fmt(t: datetime) -> str:
    return fmt_time(t)  # review-01 R14: seconds shown when they matter


def required_kinds(pkg: WorkPackageState) -> set[CertificateKind]:
    """
    review-05 R05-05 (Donnie's call): a hazard implies its authorization, so leaving the
    permits block out can't let hazardous work through with nothing on file.

        permits_required flag ----------------------------------+
        hot work (hazard) ------------> hot work permit --------+
        confined space (hazard or spatial flag) -> entry permit +--[OR]--> required
        working aloft (hazard or spatial flag) --> aloft auth --+

    A fall-protection hazard implies nothing per job: the fall protection plan is the
    ship's standing order (Donnie), so it's required only when a package asks for it.
    """
    from agent_core.state import HazardCategory as H
    hz = set(pkg.hazard_categories)
    req = {k for k in CertificateKind if getattr(pkg.permits_required, k.value)}
    if H.HOT_WORK in hz or H.HOT_WORK.value in hz:
        req.add(CertificateKind.HOT_WORK_PERMIT)
    if H.CONFINED_SPACE in hz or H.CONFINED_SPACE.value in hz or pkg.spatial.is_enclosed_or_confined:
        req.add(CertificateKind.CONFINED_SPACE_ENTRY_PERMIT)
    if H.WORKING_ALOFT in hz or H.WORKING_ALOFT.value in hz or pkg.spatial.is_aloft:
        req.add(CertificateKind.ALOFT_AUTHORIZATION)
    return req


def check_certificates(
    pkg: WorkPackageState, certificates: Iterable[Certificate]
) -> list[CertificateFinding]:
    """
    Return one finding per required permit that isn't covered for the whole
    work window, in `SafetyPermitsRequired` field order. Empty list means
    every required permit is covered. `certificates` may include
    certificates for other packages; only this package's are read.
    Raises ValueError on duplicate certificate IDs.
    """
    certs = list(certificates)
    seen: set[str] = set()
    for c in certs:
        if c.certificate_id in seen:
            raise ValueError(f"duplicate certificate_id: {c.certificate_id}")
        seen.add(c.certificate_id)

    start, end = pkg.scheduled_start, pkg.scheduled_end
    required = required_kinds(pkg)
    mine = [c for c in certs if c.covers_package(pkg.work_package_id) and c.kind in required]
    # Re-check R13: check every time this call could compare *before* any sort.
    # Re-check 2 N07: only certificates of required kinds -- the only ones compared.
    require_comparable([("scheduled_start", start), ("scheduled_end", end)]
                       + [(f"{c.certificate_id}.valid_from", c.valid_from) for c in mine]
                       + [(f"{c.certificate_id}.valid_until", c.valid_until) for c in mine])
    findings: list[CertificateFinding] = []
    for kind in CertificateKind:
        if kind not in required:
            continue
        matching = sorted(
            (c for c in certs if c.covers_package(pkg.work_package_id) and c.kind == kind),
            key=lambda c: (instant(c.valid_from), c.certificate_id),
        )
        ids = [c.certificate_id for c in matching]
        rule_id = named_rules.rule_for_certificate_kind(kind).rule_id

        if start is None or end is None:
            findings.append(CertificateFinding(
                work_package_id=pkg.work_package_id, kind=kind,
                issue=CertificateIssue.UNSCHEDULED, rule_id=rule_id, uncovered=[], certificate_ids=ids,
                message=f"{kind.value}: package has no complete schedule, "
                "so certificate coverage cannot be verified",
            ))
            continue

        gaps = uncovered(start, end, [(c.valid_from, c.valid_until) for c in matching])
        if not gaps:
            continue
        issue = CertificateIssue.NOT_COVERED if matching else CertificateIssue.MISSING
        spans = "; ".join(f"{_fmt(a)} to {_fmt(b)}" for a, b in gaps)
        what = "no certificate on file" if not matching else "not covered"
        findings.append(CertificateFinding(
            work_package_id=pkg.work_package_id, kind=kind, issue=issue, rule_id=rule_id,
            uncovered=gaps, certificate_ids=ids,
            message=f"{kind.value}: {what} for {spans}",
        ))
    return findings
