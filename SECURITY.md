# Security Policy

## Project Status

Watchstander is an active portfolio and research project demonstrating
functional-safety and SRE principles applied to agentic AI systems. It is
not a production system and is not deployed in any operational environment.
There is no versioned release schedule — `main` reflects the current state
of ongoing development.

## Supported Versions

Only the `main` branch is maintained. No prior tags or releases receive
security updates.

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security issue, vulnerability, or unsafe pattern in this
repository, please open a GitHub Issue with the label `security`, or
contact the repository owner directly via GitHub.

Please include:
- A description of the issue and its potential impact
- Steps to reproduce, if applicable
- Any suggested remediation, if you have one

As a solo-maintained research project, response time is best-effort rather
than SLA-bound. Reports will be acknowledged as soon as reasonably possible,
and credited in the fix commit or release notes unless you request
otherwise.

## Scope

Given the project's current stage, security review focuses primarily on:
- Safe handling of any authorization/scheduling logic (deconfliction,
  chit-expiration, hazard-pair checks)
- No hardcoded secrets, credentials, or real organizational data in the
  public repository
- Dependency hygiene (no known-vulnerable packages in `requirements.txt`)

Findings outside this scope are still welcome but may be triaged with
lower priority given the project's non-production status.
