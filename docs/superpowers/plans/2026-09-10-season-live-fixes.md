# Season-live fixes — coordination plan

**Branch:** `fix/season-live-issues` · **Opened:** 2026-09-10

Five independent issues found once the season went live. One branch, one PR,
one release. Each item is self-contained: finish and commit before starting the
next, so an interruption never leaves two half-done.

**Status legend:** `[ ]` not started · `[~]` in progress · `[x]` done+committed

---

## [x] 1. Ranks are positional, not tie-aware

**Reported:** many users have 1 correct pick but are not all shown tied for
first; different pages disagree.

**Root cause:** `update_rankings` already computes correct standard-competition
ranks (1,1,3) into `userSeasonPoints.current_rank`
(`pickem_api/management/commands/update_rankings.py`). Almost nothing displays
it — the display sites each re-derive rank positionally with `enumerate()`:

| Site | File:line | Kind |
| --- | --- | --- |
| Lobby standings | `pickem_homepage/views.py:1171` | season |
| Full standings page | `pickem_homepage/views.py:3144` | season |
| Profile | `pickem_homepage/views.py:3227` | season |
| Lobby Week Points | `pickem_homepage/views.py:533` | weekly |

**Decision:** fix season *and* weekly (user chose "both").

**Approach:**
- Season sites read `current_rank` from the row rather than enumerating.
- Weekly has no stored rank, so add a shared tie-aware helper and use it for the
  Week Points list. Keep one helper so the two can't drift.
- Preserve the existing "hide ranks until the week/season has a scored game"
  behaviour — everyone is 0 before that and a rank would be meaningless.

**Tests:** N users on equal points all share rank 1 and the next distinct score
gets rank N+1; the same user shows the same rank on lobby, standings and
profile; weekly ties behave the same; pre-scoring hiding still works.

---

## [x] 2. Lobby games heading says "Week N Games" while showing one day

**Root cause:** `select_dashboard_snapshot_games` (`views.py:210`) narrows to a
single day on most weekdays, but `games_section_heading` (`views.py:1198`) is
computed from week-level status and doesn't know a subset was shown.

**Decision:** when a subset is displayed, heading becomes **"Today's Games"**
with the week retained as a subtitle (user chose heading + week context).

**Approach:** have the snapshot selector report whether it narrowed, and drive
the heading from that rather than inferring it.

**Tests:** full-week day → week heading; narrowed day → "Today's Games" plus the
week subtitle.

---

## [x] 3. Remove icons beside six lobby headings

Purely presentational. Remove the `<i class="fas ...">` beside exactly these,
in `pickem_homepage/templates/pickem/family_pool_home.html`:

| Heading | Icon | Line (pre-edit) |
| --- | --- | --- |
| Week Points | `fa-bolt` | 289 |
| Week N Games / Today's Games | `fa-broadcast-tower` | 338 |
| Pool Standings | `fa-trophy` | 441 |
| Recent Week Winners | `fa-star` | 478 |
| Message Board | `fa-comments` | 506 |
| Around the NFL | `fa-newspaper` | 552 |

**Leave every other icon alone** — explicitly in scope only for these six.

---

## [x] 4. Family switcher always lands on the lobby

**Root cause:** `_switcher_choice_for_membership`
(`pickem/context_processors.py:100`) always reverses `family_pool_home`.

**Decision:** preserve the current page type across the switch; fall back to the
target family's lobby when it can't be resolved (user chose silent fallback, no
notice).

**Approach:** map the current `request.resolver_match.url_name` to the same
tenant route in the target family/pool when that route exists and takes the same
kwargs; otherwise lobby. Never raise from a context processor — a bad mapping
must degrade to the lobby, not 500 every page.

**Tests:** scores → scores; standings → standings; lobby → lobby; an
admin-only page → lobby when the user lacks the role there; an unknown/non-tenant
page → lobby.

---

## [x] 5. Global leaderboard ranks on cross-pool points

**Reported:** a pool awarding 10 points per win dominates; multi-pool users
appear inflated.

**Findings:**
- `views.py:3420` sorts on `points` first — points are `Sum('total_points')`
  across pools, so scoring schemes are not comparable between pools.
- `correct` is **already de-duplicated by distinct game** for the cross-pool row
  (`update_stats.py:194`), so the correct-pick number is already right. Only the
  ranking signal is wrong.

**Decision:** rank by correct picks; tiebreak accuracy then weeks won; **drop the
Points column entirely** (user chose this).

**Tests:** a high-scoring pool no longer outranks on points; a user in two pools
who picked one game right counts once; ranking ties share a rank; the Points
column is gone from the page.

---

## Finish

- [x] Full suite + `makemigrations --check`
- [x] `npm run build:prod`; commit `tailwind.css` only if genuinely changed
- [ ] ship-it: review → PR → CodeRabbit → merge → release → prd verify
