# Phase 4: Family-Scoped App Pages - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-29
**Phase:** 04-family-scoped-app-pages
**Areas discussed:** Tenant URL migration order, Picks and scores behavior, Standings/dashboard data boundaries, Profiles/players/message board privacy, Rules/settings display

---

## Tenant URL Migration Order

| Option | Description | Selected |
|--------|-------------|----------|
| Redirect legacy | Existing global app routes redirect signed-in users to their current/default family pool, reducing duplicate surfaces. | ✓ |
| Parallel routes | Keep global routes working while adding tenant routes, useful for lower risk but easier to leak global data accidentally. | |
| Tenant only | Make gameplay pages available only under family/pool URLs and return onboarding/picker elsewhere. | |

**User's choice:** Redirect legacy.
**Notes:** Signed-in gameplay pages should move into tenant context rather than maintaining global private surfaces.

---

## Picks And Scores Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Global games, pool overlays | NFL games/weeks stay global, but picks, pick counts, lock state, my pick, and pool-related overlays are scoped to the current pool. | ✓ |
| Fully duplicate per pool | Copy game/week display state per pool too, more isolated but much heavier and against the current model. | |
| Scores global, picks tenant-only | Scores stays mostly global while picks becomes tenant-scoped, simpler but leaves a split mental model. | |

**User's choice:** Global games, pool overlays.
**Notes:** This carries forward the v1 model where NFL reference data remains global.

---

## Standings/Dashboard Data Boundaries

| Option | Description | Selected |
|--------|-------------|----------|
| Family pool only | Show only current pool standings, weekly winners, pick status, family message preview, and member activity for that family/pool. | ✓ |
| Family plus global NFL context | Current pool data plus league-wide/public NFL stats, but no other family/member data. | |
| Mixed legacy dashboard | Keep some existing global league widgets while marking family-specific sections, fastest but highest leakage risk. | |

**User's choice:** Family pool only.
**Notes:** Tenant pages should not keep legacy global league widgets unless rewritten to current family/pool scope.

---

## Profiles, Players, And Message Board Privacy

| Option | Description | Selected |
|--------|-------------|----------|
| Family-private | Player lists, profiles, stats, posts, comments, and votes are visible only to active family members, scoped to that family/pool where applicable. | ✓ |
| Profiles semi-public | Profiles stay globally viewable, but picks/message board are family-private. | |
| Message board private only | Community content is family-private, but player/profile/stat pages remain mostly legacy-global for now. | |

**User's choice:** Family-private.
**Notes:** Phase 4 should treat profile/community surfaces as private family data and include negative tests for cross-family access.

---

## Rules/Settings Display

| Option | Description | Selected |
|--------|-------------|----------|
| Display only | Rules page reads current pool/family settings and shows them in tenant context; owner/admin editing stays Phase 5. | ✓ |
| Limited edit | Let owners/admins edit basic rules/settings now, while full member/admin management stays Phase 5. | |
| Static rules bridge | Keep the current rules content but move it under tenant URLs, no real settings integration yet. | |

**User's choice:** Display only.
**Notes:** Avoid pulling family admin/settings editing into Phase 4.

---

## the agent's Discretion

- Exact plan split and migration order.
- Exact route names, helper names, and template filenames.
- Exact dashboard widget composition, provided all data is current family/pool scoped.
- Exact compatibility redirect helper structure.

## Deferred Ideas

- Full owner/admin settings editing belongs to Phase 5.
- Full invite/member/role/admin management belongs to Phase 5.
- Cron/scoring hardening belongs to Phase 6.
