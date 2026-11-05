# Review NN: <scope>

**Reviewer:** <tool and model>  ·  **Reviewed:** `<base SHA>..<head SHA>` (`<branch>`)
**Builder responding:** <tool and model>  ·  **Response date:** <YYYY-MM-DD>

Rules: AGENTS.md, "Review loop". The reviewer's findings are never edited. The builder adds a response under each one. Every finding needs a verdict before any fix is written.

## Findings (reviewer)

| ID | Severity | File:line | Scenario | Reproduced or traced |
|---|---|---|---|---|
| R01 | high/med/low | `path:line` | Concrete failing input → observed result | reproduced / traced |

## Builder responses

### R01
- **Verdict:** CONFIRMED | AGREE-TRACED | DISPUTED
- **Evidence:** <what the builder ran and saw; for DISPUTED, the run or exact line that contradicts the claim>
- **Disposition:** fix | accept risk | defer to Known Debt | needs Donnie
- **Fix commit / regression test:** <SHA, test name>
- **Reviewer re-check:** pending | confirmed fixed | reopened (reason)

## Disputes for Donnie

<List every DISPUTED finding with both positions in one line each. Empty if none.>
