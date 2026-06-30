# Migration Plan: Legacy Global League To Families/Pools

**Date:** 2026-06-28

## Existing Data Assumptions

- Existing data represents one global production league.
- `auth.User` rows are global user accounts.
- Existing `UserProfile.is_commissioner=True` users are global commissioners.
- `GamesAndScores`, `GameWeeks`, and `Teams` are NFL reference data and can remain global.
- `GamePicks`, `userSeasonPoints`, `userPoints`, `userStats`, message board rows, and banners are league-owned and must be assigned to a default legacy family/pool.
- Some records may reference users by email/string ID rather than FK, and some referenced users may be inactive or deleted.

## Default Legacy Family Strategy

Create:

- `Family(name="Legacy Family League", slug="legacy-family-league", created_by=<first superuser or configured admin>)`
- `Pool(family=legacy, name="<season> Pick'em", slug="<season>-pickem", season=currentSeason.season, competition="nfl")`
- `FamilyMembership` for every active non-superuser with existing picks, standings, stats, or message-board activity.
- Owner/admin membership for existing `UserProfile.is_commissioner=True` and superusers.

Backfill:

- Existing `GamePicks.pool = legacy_pool`.
- Existing `userSeasonPoints.pool = legacy_pool`.
- Existing `userPoints.pool = legacy_pool` if retained.
- Existing `userStats.pool = legacy_pool`, or copy into a new pool-scoped stats table.
- Existing message-board posts/comments/votes to `legacy_family`.
- Existing site banners either stay global or get `family=legacy_family` depending on product decision.

## Safe Migration Steps

1. Preflight production snapshot.
   - Take database backup.
   - Record app version and migration state.
   - Run row-count queries for all affected tables.

2. Add schema, nullable first.
   - Add new family/pool/membership/invite/audit tables.
   - Add nullable tenant FKs to existing tenant-owned tables.
   - Add indexes that do not require non-null data.

3. Backfill default family/pool.
   - Create legacy family and pool idempotently.
   - Create memberships from active users and referenced records.
   - Map commissioners to owner/admin roles.
   - Set tenant FK on all existing rows.

4. Deploy code that reads/writes tenant-aware data.
   - Continue supporting legacy fallback only where necessary.
   - Ensure new writes always include tenant keys.
   - Pause or update cron jobs during the transition to avoid unscoped writes.

5. Verify backfill.
   - Compare row counts.
   - Compare legacy global standings with new default pool standings.
   - Check for null tenant FKs.
   - Check duplicate rows before adding constraints.

6. Enforce constraints.
   - Make tenant FK fields non-null after all code paths write them.
   - Add tenant-scoped unique constraints.
   - Remove or block unscoped API writes.

7. Clean up legacy routes.
   - Redirect or retire global app routes.
   - Keep public landing page separate.

## Reversibility

- Schema-add migrations are reversible.
- Data backfills are technically reversible only if old columns remain untouched.
- Once non-null constraints and tenant-scoped uniqueness are enforced, rollback should be a database snapshot restore or roll-forward fix.
- Do not drop legacy fields or old routes in the same milestone that introduces tenant FKs.

## Verification Checks

Example checks to adapt for PostgreSQL table names:

```sql
-- No tenant-owned picks without pool
select count(*) from pickem_api_gamepicks where pool_id is null;

-- No tenant-owned standings without pool
select count(*) from pickem_api_userseasonpoints where pool_id is null;

-- Duplicate picks that would violate pool uniqueness
select pool_id, uid, pick_game_id, count(*)
from pickem_api_gamepicks
group by pool_id, uid, pick_game_id
having count(*) > 1;

-- Legacy pool pick count matches old global count for current season
select count(*) from pickem_api_gamepicks where gameseason = <season>;
select count(*) from pickem_api_gamepicks where gameseason = <season> and pool_id = <legacy_pool_id>;

-- All active users with picks have memberships
select distinct gp.uid
from pickem_api_gamepicks gp
left join pickem_api_familymembership fm
  on fm.user_id = gp.uid and fm.family_id = <legacy_family_id>
where gp.pool_id = <legacy_pool_id> and fm.id is null;
```

Application checks:

- Legacy family dashboard shows the same standings as pre-migration.
- A normal member can see only legacy family data.
- A non-member test user cannot access legacy family pages.
- Cron/scoring updates only the intended pool.
- Admin tools operate only inside legacy family.

## Backup And Rollback

Before migration:

- Take a database snapshot.
- Export affected tables if snapshot restore is slow.
- Record current container/image/chart versions.
- Disable or pause cron jobs during schema/data transition if code and schema are not deployed atomically.

Rollback options:

- Before enforcement: reverse migration or deploy previous code if old paths still work.
- After enforcement: restore database snapshot plus previous application version.
- If only a small data issue appears: roll forward with a corrective data migration after disabling writes to affected routes.

## Downtime Avoidance

- Use expand/backfill/contract.
- Avoid long table locks by adding nullable columns first.
- Add expensive indexes concurrently if using custom PostgreSQL migration operations.
- Keep old fields and legacy fallbacks until tenant-aware code is fully deployed.
- Pause cron writes during backfill/enforcement if needed.
