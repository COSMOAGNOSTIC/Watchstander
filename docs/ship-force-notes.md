# Ship's force, tag-outs and aloft: design notes (not built)

> Captured from Donnie, 2026-11-10/11, during review-05. Domain notes for a future part of
> the build. Nothing here is implemented yet; each ship's own instructions (CSOSS/aloft
> instruction, CO's standing orders) will be loaded per ship and are the authority.

## How aloft actually works

- Aloft is run through **eTagout**, the ship's **aloft instruction**, and an **aloft checklist**.
- **Zones.** The mast is divided into zones (for example, a lower zone at the O-11 level up to the
  top of the mast). Each zone requires specific radars and emitters to be secured and tagged;
  higher zones need more secured. "Full aloft" is its own case.
- **The aloft chit** is signed by the duty officer the morning of, after the set time agreed the
  day before. Setting aloft and people going aloft are different steps.
- **Daylight.** Without the CO's explicit written permission, aloft runs dawn to dusk only.
- **Securing.** Aloft is secured as soon as work on the mast and island is done for the day
  (it interferes with other ship evolutions), at dusk at the latest.
- **People.** Everyone going aloft, civilian or military, must be briefed, qualified, sign in,
  and have an approved harness (ship's force harnesses from the ship; others bring approved ones).
- **Blanket aloft.** In a yard period, once scaffolding fully envelops the mast, normal zone rules
  stop applying and a blanket aloft covers a set period. Who sets it and its rules vary case by
  case: the CO, the Combat Systems Officer, or the Combat Systems Maintenance Officer.
- Until the scaffolding fully envelops the mast (antenna depopulation, building scaffolding),
  all the normal aloft rules apply.

## The missing piece: ship's force in Watchstander

Watchstander so far models the shipyard side. Ship's force owns a large part of the safety
picture and isn't in it yet:

- **Tag-out authority** belongs to three watch stations, each for its own area, each using eTagout:
  - **CSOOW** (Combat Systems Officer of the Watch): combat systems, including aloft tags.
  - **EOW** (Engineering Officer of the Watch): engineering.
  - **Reactor Department**: reactor plant.
- A future build portion: bring these watch stations in as owners of their tag-outs and of
  the authorizations that depend on them (aloft chits, blanket aloft), with each ship's own
  instructions loaded as the rules.

## What's built today (review-05)

- An aloft authorization is either a **chit** (one job, one day) or a **standing/blanket aloft**
  (ship-wide, a date range). Zones, daylight, per-person qualifications and tag-outs are not
  checked; see ARCHITECTURE.md Known Debt.
