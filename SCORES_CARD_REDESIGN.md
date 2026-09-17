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
  the header). Everything else still matches the recolor version.
