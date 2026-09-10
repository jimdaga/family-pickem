# Sideline opt-in + superadmin pool health

**Branch:** `feat/sideline-optin-and-pool-health` · **Opened:** 2026-09-10

Three items. One branch, one PR, one release. Finish and commit each before
starting the next.

`[ ]` not started · `[~]` in progress · `[x]` done+committed

---

## [x] 1. Sideline (AI recaps) runs only where enabled

`generate_weekly_summaries` currently runs for every active pool in the season
(`pickem_api/management/commands/generate_weekly_summaries.py:29`).

**Decision:** new `PoolSettings.ai_summaries_enabled`, **default False**. Jim
enables pools himself for now; this becomes the hook for a paid tier later.

**Safe to default off:** `FamilyPublication` currently holds **zero**
`ai_weekly_summary` rows in production, so no pool loses anything it has today.
No grandfathering needed.

- Command filters on the flag.
- Commissioner-visible? No — this is Jim's lever, so it goes in the superadmin
  pools matrix, not the family admin settings form.
- Tests: disabled pool is skipped; enabled pool still runs; default is off.

---

## [x] 2. Overview: abandoned + went-quiet pools

**Decision: two tiers** (Jim's choice).

- **Abandoned** — zero picks ever AND `created_at` older than 14 days.
  Grounded in live data: flags playground (53d), team-africa-2027 (29d),
  the-people-at-home (26d); correctly ignores haug-clan (6d), fambam (3d),
  ballantyne (1d), which are merely new.
- **Went quiet** — has picks historically, but none for the CURRENT week once
  that week's first game has kicked off.

Why not "no picks in N days": people pre-pick. charvat and sunday-funday last
picked ~17 days ago and are perfectly healthy — they submitted week 1 early. A
recency threshold would flag them; the current-week rule does not.

---

## [x] 3. Overview: newly created pools

Pools created in the last 30 days with family, creation date, member count and
picks so far, so a dead new signup is visible without cross-referencing.

---

## Finish

- [x] Full suite + `makemigrations --check`
- [x] `npm run build:prod`; commit `tailwind.css` only if genuinely changed
- [ ] ship-it: review → PR → CodeRabbit → merge → release → prd verify
