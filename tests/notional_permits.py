"""Test helper (review-05 R05-05): since a hazard now implies its permit, fixtures that are
about something else put a notional permit on file for every package that needs one,
valid far longer than any test window. Tests about certificates build their own."""

from datetime import datetime

from agent_core.certificates import Certificate, CertificateKind, required_kinds

_FROM, _UNTIL = datetime(2000, 1, 1), datetime(2100, 1, 1)


def permits_on_file(packages, exclude=()):
    out = []
    for p in packages:
        if p.work_package_id in exclude:
            continue
        for k in sorted(required_kinds(p), key=lambda k: k.value):
            if k == CertificateKind.ALOFT_AUTHORIZATION:
                # a chit covers one day; a long window is a ship-wide standing aloft
                out.append(Certificate(certificate_id=f"N-STANDING-{p.work_package_id}", work_package_id=None,
                                       kind=k, form="standing", valid_from=_FROM, valid_until=_UNTIL))
                continue
            out.append(Certificate(certificate_id=f"N-{k.value}-{p.work_package_id}", work_package_id=p.work_package_id,
                                   kind=k, valid_from=_FROM, valid_until=_UNTIL))
    return out
