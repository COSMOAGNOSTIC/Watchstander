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

from datetime import datetime
from enum import Enum
from typing import Iterable

from pydantic import BaseModel, model_validator

from agent_core import named_rules
from agent_core.intervals import uncovered
from agent_core.state import WorkPackageState


class CertificateKind(str, Enum):
    """One per `SafetyPermitsRequired` field, same names, same order."""

    HOT_WORK_PERMIT = "hot_work_permit"
    CONFINED_SPACE_ENTRY_PERMIT = "confined_space_entry_permit"
    FALL_PROTECTION_PLAN = "fall_protection_plan"
    MARINE_CHEMIST_CERTIFICATE = "marine_chemist_certificate"
    COMPETENT_PERSON_INSPECTION = "competent_person_inspection"


class CertificateIssue(str, Enum):
    MISSING = "missing"  # no certificate of this kind for this package at all
    NOT_COVERED = "not_covered"  # certificates exist but leave part of the window uncovered
    UNSCHEDULED = "unscheduled"  # package has no complete schedule, so coverage can't be verified


class Certificate(BaseModel):
    certificate_id: str
    work_package_id: str
    kind: CertificateKind
    valid_from: datetime
    valid_until: datetime

    @model_validator(mode="after")
    def _window_is_ordered(self) -> "Certificate":
        if self.valid_from > self.valid_until:
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
    return t.strftime("%Y-%m-%d %H:%M")


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
    findings: list[CertificateFinding] = []
    for kind in CertificateKind:
        if not getattr(pkg.permits_required, kind.value):
            continue
        matching = sorted(
            (c for c in certs if c.work_package_id == pkg.work_package_id and c.kind == kind),
            key=lambda c: (c.valid_from, c.certificate_id),
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
