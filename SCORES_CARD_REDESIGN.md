# Scores game-card redesign — blank-slate spec

Status: in progress on branch `redesign/scores-cards-v2`.
Fallback (the "recolor" version we liked): `redesign/scores-cards-recolor`
(and `redesign/scores-game-cards`), both pushed to origin. `git checkout
redesign/scores-cards-recolor` to return to it.

## Goal
Collapse the card from ~6 stacked full-width bands into **3 zones**:
status+matchup (hero) → picks (the point) → metadata (whisper). Retain ALL
current data. Converge with the lobby game-card language.

## Target structure (top → bottom of each card)
1. **Header row**: matchup context on the left (kickoff day/time or "Final"),
   ONE status chip on the right (live = green pulse dot + statusTitle;
   final = neutral; upcoming = kickoff time). Kill the full-width gradient
   status band and the separate LIVE/FINAL badge (badge already removed in
   this branch).
2. **Matchup (hero)**: two team rows — logo · name · record — score
   right-aligned. Winner: bold name + score + subtle left accent (keep the
   `winning-team` gradient). Loser: dim BOTH name and score (currently only
   the name dims). Keep quarter scores behind a small expand/detail toggle
   rather than always-on.
3. **Picks (elevate — the signature)**: instead of the bottom Player Picks
   grid, show pick avatars INLINE under each team ("who's on ATL"), colored
   correct/incorrect once final using the lobby's green-check / red-x
   language (see `attach_dashboard_pick_groups` viewer_pick + the lobby
   `family_pool_home.html` "Your pick" block). Keep the missing-picks list.
4. **Metadata (whisper)**: spread / O/U / weather / indoor as small muted
   chips in a quiet footer, de-emphasized. Optionally collapsible.

## Key files
- Markup: `pickem/pickem_homepage/templates/pickem/scores.html`
  - card container ~L373; status header ~L375; info/metadata bar ~L385;
    teams-matchup (away ~L447, home ~L504); player picks ~L590+;
    missing-picks ~L812+.
- Team-row CSS: `pickem/pickem_homepage/static/css/input.css` L98-115
  (`team-score-row`, `winning-team`, `quarter-score`).
- Rebuild CSS after edits: `npm run build:prod`. Never add `?v=` to
  `{% static %}`.

## Preserve / don't break
- Live SSE hooks: `data-scores-card`, `data-game-id`, `data-status-title`,
  `data-away-score`, `data-home-score`, the `scores-live-game` class, and the
  filter classes (`.filter-btn`, `data-scores-filter`). The scores JS updates
  these in place — keep the attributes.
- `points-leaderboard` / week-points list is separate (already redone).
- Full data to retain: team logo, name, record, total score, quarter scores,
  winner indicator, spread, O/U, temperature + weather icon, indoor flag,
  broadcast/TV, game-preview link, player picks per team, missing picks.

## Done so far on v2
- Removed the redundant centered LIVE/FINAL badge (status now lives only in
  the header).
- **All 3 zones implemented** (checkpoint tag `scores-v2-checkpoint-before-zones`
  marks the pre-zones state — `git reset --hard` it to revert):
  - Zone 2 (matchup hero): losing team's SCORE now dims too (`opacity-40`), not
    just the name. Per-quarter scores moved out of the always-on team rows into
    a collapsible `<details class="box-score">` below the matchup (native
    details = survives the SSE innerHTML swap with no JS state). The home team
    row got `team-score-row-divider` since the inline picks now sit between the
    two rows (old adjacent-sibling divider no longer applied).
  - Zone 3 (signature): the bottom Player Picks grid is gone; pick avatars now
    render INLINE under each team (`.team-picks-inline` / `.pick-chip`), ring
    green/red/yellow for correct/incorrect/in-progress. Username under each,
    tiebreaker as tiny text + in the hover title. "Your Pick" + "Missing Picks"
    sections kept as-is.
  - Zone 4 (whisper): spread / O-U / weather / indoor + TV + Game Preview all
    collapsed into ONE muted `.card-meta-footer` at the bottom (was a top info
    bar + a separate broadcast band).
- **Lobby "This Week's Games" language borrowed into the header** (converging
  with `family_pool_home.html` `data-lobby-game-card`): the full-width tinted
  status bar is now a soft rounded-full **status pill** — green + pulse dot
  (live), slate + check (final), blue + clock (upcoming); the date reads
  `Wed, Sep 9 · 8:20 PM` on the right. The winner's chunky chevron badge
  (`.winner-indicator`, now unused) became the lobby's small yellow
  `fa-trophy`. Kept the richer scores-only bits (48px logos, records, win-chance
  bars, inline pick avatars, box score).
- SSE contract preserved: `data-*-score`, `data-status-title`, `data-*-period`
  (now inside the box-score details, still queryable), `.total-score` /
  `.quarter-score` (poll diff), `scores-live-game`. Verified via the Django
  test client against `moran-relatives/pickem-pool` season 2627 wk 1 (finished
  games w/ picks): 16 cards, 256 pick chips (165 correct / 91 incorrect), 16
  box scores, 16 meta footers, no template errors. CSS rebuilt (`build:prod`).

## Local preview environment (for a fresh session)
- Dev server: http://localhost:8000. If not running, from `pickem/` with these
  env vars set (DB below): `uv run python manage.py runserver`.
- Env vars: `DEBUG=True`, `SECRET_KEY=<any>`, `DATABASE_HOST=127.0.0.1`,
  `DATABASE_PORT=5433`, `DATABASE_NAME=pickem`, `DATABASE_USER=postgres`,
  `DATABASE_PASS=localdev`. (The `settings.py` DATABASE_HOST branch triggers on
  DATABASE_HOST being set.)
- Local DB: docker container `pickem-local-db` (postgres:17-alpine, port 5433,
  postgres/localdev, db `pickem`), loaded from a prod `pg_dump`. If gone,
  recreate by streaming a dump from the prod pod:
  `ssh jim@192.168.1.222 'kubectl exec -n pickem-prd <django-pod> -c family-pickem
  -- bash -lc "PGPASSWORD=\$DATABASE_PASS pg_dump -h \$DATABASE_HOST -U \$DATABASE_USER
  -d \$DATABASE_NAME --no-owner --no-privileges -Fc"' > dump.pgc` then
  `pg_restore` into the container.
- Login: username `jimbo` / password `pickem123` (set locally via
  `user.set_password`; jimbo is superuser). Log in at /admin/ then browse.
- Preview note: the local `currentSeason` is 2627; today's `GameWeeks` row was
  set to weekNumber=1 so scored week-1 data shows on lobby/scores. Real prod
  tracks the live week.
- Verify renders without a browser via the Django test client:
  `Client(); c.force_login(User.objects.get(id=2)); c.get(<url>)`.

## Ship flow (when ready, not before user says)
Branch off main → PR → `gh pr merge --merge --admin` → `gh release create
family-pickem-0.0.<next>` (see latest tag) → workflow builds Docker+Helm+ArgoCD
→ `ssh jim@192.168.1.222` refresh `root` then `pickem-prd` argocd apps → verify
rollout to the new image + healthz 200.
