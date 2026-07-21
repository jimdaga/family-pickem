# AI weekly recap: audit fixes, richer prompt context, persona

**Date:** 2026-07-20
**Status:** Approved for planning

## Background

`feat: add reviewable AI weekly recaps` (commit `9a11d69`, on `main`) added a
commissioner-reviewable AI recap feature: `pickem_api/ai_weekly_summaries.py`
builds tenant-scoped facts from scored games/picks/standings, sends them to
OpenAI's Responses API, and stores the draft as an unpublished
`FamilyPublication` for a commissioner to review and publish. It's wired into
the per-minute pipeline tick (`pickem_api/scheduler.py`,
`update_all.py`) as the `generate_weekly_summaries` step, gated by
`latest_complete_week()` (a week only counts once every game is `finished`
and `gameScored` — in practice, once Monday Night Football is final).

This spec covers: (1) fixes found during a correctness/security audit of that
feature, (2) enriching the facts/prompt with real game-rules context
(including season-champion awareness for week 18), and (3) a persona rewrite
of the recap voice. No new scheduling mechanism is needed — the existing
condition-triggered pipeline step already satisfies "runs weekly, after MNF,
after the week winner is set" for weeks 1–17; the gap is specifically the
week-18 season-champion case, fixed by a pipeline reorder below.

## Audit findings

**Security:** no issues found. The API key is encrypted at rest
(`AIProviderSettings.set_api_key`/`get_api_key`, Fernet-derived from
`SECRET_KEY`), excluded from string reprs/snapshots/audit diffs, and scrubbed
from error tracebacks via `@sensitive_variables('config')` /
`@sensitive_post_parameters('api_key')`. Facts are provably pool-scoped
(`test_facts_are_deterministic_and_pool_scoped`). Recap bodies render through
`safe_markdown`, which escapes before any markdown transform, so raw HTML/JS
in a body is never live. The `FamilyPublicationForm` only exposes
`title`/`body` — a commissioner can't spoof `source` to hijack the AI
publication slot. Writes go through the existing `FamilyAuditLog`.

**Bugs found:**

1. **Pipeline order bug (the one behind this feature's week-18 gap).**
   `generate_weekly_summaries` currently runs *before* `update_season_winners`
   in both `pickem_api/scheduler.py`'s `PIPELINE` and
   `pickem_api/management/commands/update_all.py`'s `PIPELINE`. On the
   season's final week, the recap is generated before `year_winner` is
   flagged, so there's no way for the facts (even after this spec's changes)
   to know a champion was just crowned in that same tick.
2. **Duplicated magic constant.** `FINAL_WEEK = 18` is defined only in
   `update_season_winners.py`. The new facts code needs the same value;
   duplicating it risks drift.
3. **Retry loop retries non-retryable errors.** `_provider_request`'s retry
   loop catches `requests.RequestException` broadly, which includes
   `HTTPError` raised by `response.raise_for_status()` on a 4xx. A bad API
   key or malformed request currently gets retried `retries + 1` times for no
   benefit, and there's no backoff between attempts (5xx or network errors
   retry immediately).

## Changes

### 1. Pipeline reorder

Move `generate_weekly_summaries` to after `update_season_winners` in:
- `pickem_api/scheduler.py`'s `PIPELINE` list
- `update_all.py`'s `PIPELINE` list and its ordering docstring

For weeks 1–17, `update_season_winners` is a cheap no-op
(`week_is_complete(season, 18)` is `False`), so this doesn't delay recap
generation. For week 18, it guarantees `year_winner` is finalized first.

### 2. Shared `FINAL_WEEK` constant

Move `FINAL_WEEK = 18` from `update_season_winners.py` into
`pickem_api/weekly_winners.py` (which already owns week-completion logic:
`week_is_complete`, `complete_weeks`, `latest_complete_week`). Both
`update_season_winners.py` and `ai_weekly_summaries.py` import it from there.

### 3. Provider retry fix

In `_provider_request`: only retry on a 5xx status or a network-level
exception (`requests.Timeout`, `requests.ConnectionError`). A 4xx fails
immediately without consuming retry budget. Add a small capped backoff
between retries (e.g. `0.5s`, `1s`) — bounded low enough that it doesn't
meaningfully worsen the latency of the synchronous "Regenerate" button in
`family_pool_admin_publications`, which calls `generate_weekly_summary`
inline within the request/response cycle.

### 4. Richer, per-pool-accurate facts

`build_summary_facts()` gains two new blocks, built the same way as existing
facts (deterministic DB reads, pool-scoped, no user-authored text):

- **`pool_rules`**: read from `PoolSettings` for this pool —
  `weekly_winner_points` (bonus value), `primary_tiebreaker`,
  `secondary_tiebreaker`, `allow_tiebreaker`, `missed_pick_policy`,
  `pick_type`. Pulled live per pool since these are commissioner-configurable
  and vary pool to pool — a fixed/generic rules blurb would describe some
  pools' rules incorrectly.
- **`season_champion`**: `null` unless `year_winner` is flagged on this
  pool/season's `userSeasonPoints` rows, in which case it's the list of
  champion member name(s) (plural entries mean co-champions from a tied
  total). `is_final_week`: `True` when `week == FINAL_WEEK`.

### 5. System prompt: rules context + persona + champion handling

The system prompt is rewritten to:
- Explain the actual mechanics using the new facts: 1 point per correct pick;
  a weekly bonus of `pool_rules.weekly_winner_points` points to the
  week's top scorer(s), resolved by the pool's actual configured
  tiebreaker(s) when tied; what a missed pick does under
  `pool_rules.missed_pick_policy`; and that the season champion is whoever
  has the most total points once week 18 finishes, with ties producing
  co-champions.
- Adopt this persona (approved copy):

  > Write like a loud, supremely confident sports-radio hype man narrating
  > the week — not a neutral recap-bot. Short, punchy sentences that hit
  > like declarations. Then, sometimes, one that runs long and breathless
  > when the moment calls for it. Open strong — no throat-clearing, no
  > "here's a look at week X." Talk with total, unearned-sounding swagger:
  > "that's a fact," "I said what I said," "nobody wants to hear this, but."
  > Treat picks and scores like hot sports takes, not data points. When
  > someone nails a pick or catches fire in the standings, go over the top —
  > crown them, hype them like they just won a title. When someone bombs,
  > rib them hard but with a wink — it's a friendly roast among family,
  > never cruel, never personal, no profanity or real insults. Use real
  > names, real scores, real numbers from the data with total conviction —
  > never invent a detail that isn't there. Rhetorical questions are fair
  > game ("You seeing this?" "How does that happen?"). Keep it fun and a
  > little unhinged, but always good-natured.

- Existing guardrails are kept as-is (no inside jokes/private facts/results
  not in the data, no profanity/insults/demeaning language, never compare
  pools, include the results-source line).
- When `season_champion` is present, add an explicit instruction: treat this
  recap as the season finale and close it as a bigger, more celebratory
  moment naming the champion(s) — same persona, turned up for the occasion.

The mock preview branch in `_provider_request` (used in `DEBUG` + mock-mode
local testing) is updated to match: same punchier phrasing, and a
champion-flavored variant when `facts.get('season_champion')` is truthy, so
the week-18 path is exercisable locally without a real API key.

## Testing

Extend `pickem_api/tests/test_ai_weekly_summaries.py`:
- `pool_rules` in facts matches the pool's actual `PoolSettings`.
- `season_champion` is `null`/absent before week 18 or before `year_winner`
  is flagged, and populated (including a co-champion case) once it is.
- Pipeline-order regression: `update_season_winners` precedes
  `generate_weekly_summaries` in `update_all.PIPELINE`.
- Retry behavior: a mocked 4xx response results in exactly one `requests.post`
  call; a mocked 5xx results in `retries + 1` calls.

## Out of scope

- No new cron/scheduling mechanism — the existing per-minute,
  condition-triggered pipeline check is sufficient and preferable to a fixed
  weekly time (games can be postponed/delayed).
- Playoff scoring (`include_playoffs`) is a locked, unimplemented setting
  elsewhere in the app; this spec doesn't touch it.
- No changes to the review/publish flow, encryption, or audit logging — the
  audit found these already sound.
