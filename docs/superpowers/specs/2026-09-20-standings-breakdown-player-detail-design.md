# Player detail on the standings "Detailed Breakdown" cards

**Date:** 2026-09-20

## Problem

The Detailed Breakdown cards (`standings.html:235`) are the only place on the
site that shows a member's full season week-by-week. Today a card carries an
avatar, a username, a point total, three badges, and an 18-week points grid.
Everything on it is a number.

Nothing on the card says *who the person is* — no favorite team, no tagline —
and nothing conveys form: two members on 142 points read identically whether
one has been climbing all season or collapsing. Being in the lead is not
something the card makes you feel, so it is not something you want to defend.

## Goal

Make each card read as a person with a season arc: identity (favorite team,
tagline), a trophy case (perfect weeks, weeks won, seasons won), and a visual
trend of correct-pick percentage over the season.

## Layout

Three bands per card. The existing 18-week grid is the third and is unchanged.

```
┌────────────────────────────────────────────────────────┐
│ ( )  JIMDAGA  [🏈 DAL]           #1   142 pts          │
│ AV   "Statistically, I'm due."                         │
│      👑 CHAMP  🏆 3W  ⭐ 2 PERFECT  🥇 2 SEASONS        │
├────────────────────────────────────────────────────────┤
│ ACCURACY   CORRECT   BEST WEEK    ___╱╲___╱‾‾╲__╱‾     │
│   68%       94/138      12 (W4)   weekly accuracy      │
├────────────────────────────────────────────────────────┤
│ W1  W2  W3  W4  W5  W6  W7 ... W18                     │
│  9  11🏆  8  12   7  10  11 ...  -                     │
└────────────────────────────────────────────────────────┘
```

1. **Identity strip** — avatar, username, favorite-team logo chip, tagline,
   then the badge row. The badge row keeps today's three badges (champ, weeks
   won, perfect weeks) and gains a seasons-won badge.
2. **Stat ribbon** — Accuracy, Correct, Best Week, with the sparkline.
   "Accuracy" is the season figure already returned as `stats['accuracy']`;
   "Correct" is `correct/total` over **graded** picks only, so the denominator
   never includes games that have not been played. "Best Week" is the highest
   single-week points total, read from the `week_N_points` fields already on
   the `userSeasonPoints` row (no query).

   Perfect weeks, weeks won and seasons won live in the badge row **only** —
   they are not repeated in the ribbon. The badge row is the trophy case; the
   ribbon is form and volume. Nothing appears in both.
3. **Weeks grid** — unchanged.

## Sparkline

Plots **weekly correct-pick percentage for the selected season**: one point per
week that has at least one graded pick. This matches the card's season context
and lines up conceptually with the 18-week grid directly below it.

Rendered as **inline SVG with no JavaScript and no charting library**. The page
already loads GSAP from a CDN for entrance animation; the sparkline must not
depend on it, so that a CDN failure or `prefers-reduced-motion` never costs the
reader data. Inline SVG also avoids adding a static asset, which on this project
means avoiding the `{% static %}` signed-URL hazards documented in CLAUDE.md.

**Accessibility:** the `<svg>` carries `role="img"` and a `<title>` naming the
trend in words (e.g. "Weekly accuracy, week 1 to week 7: 68% overall"). The
numeric accuracy sits adjacent as text in the ribbon, so the sparkline is never
the sole carrier of any fact. It is static, so reduced-motion needs no branch.

## Data layer

All four changes live in `pickem_homepage/views.py`.

### 1. `build_pool_standings_stats()` returns a weekly series

The function already runs a `(userID, gameWeek)` group-by annotating `correct`
and `total`, uses it only to count perfect weeks, and discards the rest. It will
be restructured to build both results from that one query, so **the sparkline
costs no additional queries**.

New key in each user's dict, alongside today's `correct` / `accuracy` /
`perfect_weeks`:

```python
'weekly_accuracy': [{'week': int, 'accuracy': int, 'correct': int, 'total': int}, ...]
```

ordered by week ascending.

Two corrections fall out of the restructure:

- The per-week query is **not** currently filtered to finished games, so `total`
  counts picks on games that have not been played. Harmless for the perfect-week
  count (which only ever reads complete weeks) but wrong for accuracy. Adding
  `pick_game_id__in=finished_ids` fixes it and is a **no-op for complete weeks**,
  since in a complete week every game is finished.
- The per-week query currently runs only inside `if scored_by_week:` — that is,
  only when a complete week exists. The series needs it whenever any finished
  game exists.

Perfect-week counts must not change. A regression test pins this.

Adding a key is backward compatible with the other caller (`views.py:1427`, the
lobby), which reads existing keys by name.

### 2. `build_user_profile_map(user_ids)` — new batched helper

Placed beside `build_user_display_maps`. Returns
`{userID(str): {'tagline': str|None, 'team': Teams|None}}` in **two queries**:
one `UserProfile` fetch for the ids, one `Teams` fetch for the distinct favorite
slugs found.

Deliberately **not** the `lookuplogo` template filter. That filter issues one
query per call (`pickem_homepage_extras.py:171`), and this page renders it once
per player — the exact N+1 shape that `picks.html` already carries a guard test
against.

`UserProfile.favorite_team` stores the full `Teams.teamNameSlug` (verified
against production data: `dallas-cowboys`, `philadelphia-eagles`,
`new-england-patriots`), so it joins directly with no normalization.

### 3. Seasons won

Counted from `userSeasonPoints.filter(pool__family=family, year_winner=True)`
grouped by `userID` — the same source the existing `prev_champion_ids` lookup
uses. Deliberately not `userStats.seasonsWon`, which the scheduled pipeline does
not reliably write per-pool (the same reason `build_pool_standings_stats` exists
at all).

### 4. `sparkline_points(series, width, height)` — pure helper

Maps a weekly-accuracy series to an SVG polyline `points` string. Takes and
returns plain values with no request, model, or ORM involvement, so it is
directly unit-testable.

Y-axis is fixed to **0–100**, not auto-scaled to the series range. Auto-scaling
would make a member who ranged 61–64% look as volatile as one who ranged
20–90%, and would make two cards on the same page mutually incomparable — the
opposite of what the feature is for.

## Privacy

Tagline and favorite team are attached **only on the tenant branch**
(`tenant_context` present), exactly as `first_names` already is.

This follows the decision that these details are visible to fellow pool members.
The non-tenant branch of `render_standings_page` spans every pool in the
install, and `views.py:4053` carries an explicit warning that it must never
carry personal data. Scoping to the tenant branch honors both.

Consistent with this, the sparkline and the seasons-won count are also
tenant-only — matching the existing behavior of `perfect_weeks` and
`prev_champion`, which are already computed only under `tenant_context`.

`UserProfile.private_profile` is **not** consulted here. It gates the public
profile page (`views.py:5090`); inside a pool, members see each other's tagline
and team.

## Edge cases

| Condition | Behavior |
|---|---|
| No graded picks yet (preseason) | Ribbon shows `—` for accuracy; sparkline omitted entirely |
| Exactly one graded week | A dot, not a line (a polyline of one point renders nothing) |
| Flat series (identical every week) | Straight horizontal line at that value |
| No tagline | Element omitted — no blank reserved space |
| No favorite team, or slug matches no `Teams` row | Chip omitted |
| `seasons_won == 0` | Badge omitted (matches how the other badges behave) |
| Non-tenant branch | No tagline, no team, no sparkline, no seasons badge |

## Testing

**Unit**
- `sparkline_points`: empty series, single point, flat series, normal series,
  and that the y-axis is fixed to 0–100 rather than auto-scaled.
- `build_pool_standings_stats`: `weekly_accuracy` has correct per-week values;
  weeks with no graded picks are absent; picks on unplayed games do not deflate
  a week's accuracy.
- **Regression:** perfect-week counts are identical before and after the query
  restructure, including the mid-week case the existing comment calls out (a
  lone 1/1 pick must not masquerade as a perfect week).

**Render**
- Tagline, favorite-team logo, and seasons-won badge appear on a tenant
  standings page.
- Sparkline `<svg>` is present and carries its accessible `<title>`.
- A member with no graded picks renders without error and without a sparkline.

**Privacy**
- The non-tenant branch carries no tagline, mirroring the existing
  `first_names` leak test.

**Performance**
- Query-count guard (`assertNumQueries`) proving the profile and team lookups
  stay batched and the sparkline adds no queries, in the style of the existing
  `test_tenant_picks_page_lock_filter_called_once_per_game` guard.

## Out of scope

- Changes to the 18-week grid.
- Any sparkline on the lobby or leaderboard rows.
- Against-the-spread stats (locked server-side, see CLAUDE.md).
- Backfilling `userStats.seasonsWon`.
