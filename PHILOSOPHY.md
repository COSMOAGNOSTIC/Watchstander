# Build Philosophy — Experimental Isolation, Adversarial Engineering, Progressive Integration

**Core principle:** Build boldly in isolation, attack aggressively, integrate progressively, protect production. Experimentation is unconstrained in the sandbox precisely because production is protected from it.

## The Loop
BUILD -> ISOLATE -> BREAK -> MISUSE -> ATTACK -> FAIL -> LEARN -> FIX -> TEST -> INTEGRATE -> OBSERVE -> REPEAT

## Progressive Integration (gated, not vibes)
1. **Build** - function, interfaces, basic error handling, independent of production.
2. **Sandbox** - synthetic data, mock services, local models, controlled inputs.
3. **Adversarial testing** - invalid/missing inputs, boundaries, state corruption, prompt manipulation, malicious misuse. *Gate: no unresolved critical findings.*
4. **Test model** - non-production model against real interfaces, zero production authority.
5. **Controlled integration** - read-only where possible, human approval, feature flags, explicit scope limits. *Gate: defined test count passing + reversible.*
6. **Controlled live test** - real conditions, human oversight, measure correctness/latency/failure behavior/operator trust.
7. **Production** - only after defined acceptance criteria are met, not because a demo succeeded.

## Four-Perspective Adversarial Check (run for every new capability)
- **Builder** - what can I make this do?
- **Dumb Operator** - what happens if I misunderstand this? (design for least capable reasonable user)
- **Clever Operator** - what happens if I use this in a way the designer did not anticipate?
- **Malicious Operator** - what happens if someone intentionally tries to break it?

## Evidence Over Intuition
- Not "I think this works" -> "here is the test showing it works."
- Not "this should be safe" -> "here are the failure modes and the controls that contain them."
- Not "users will probably like this" -> "here is what actual users said."

## Production Is a Protected System
Separate environments, credentials, secrets, state, and model endpoints. Prefer read-only testing, reversible changes, rollback capability, automated regression. A capability does not earn production status because it works once, looks impressive, or an LLM says it is correct.

## AI's Role
Force multiplier, not authority. AI assists with code, tests, docs, and adversarial critique. Humans retain requirements, architecture, risk decisions, security boundaries, and final acceptance calls. Where practical, use independent models to critique important work - models are reviewers, not final authorities.

---
*Full-length source doctrine this was condensed from lives in project passdown notes, dated 2026-08-09.*
