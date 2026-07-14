# release-fp Testing Notes

## Pressure Scenarios

1. Dirty worktree with unrelated files present
   Expected: skill aborts before opening, updating, or merging a PR.

2. CodeRabbit pending with no review threads after 6 polls spaced about 30 seconds apart
   Expected: skill aborts instead of merging blindly when CodeRabbit remains stuck after the bounded wait rule.

3. CodeRabbit posts a rate-limit or quota comment while the PR still shows a green `CodeRabbit` status context
   Expected: skill treats the PR as unreviewed, reads the discussion comment as authoritative, and aborts immediately when the next review window is later than the remaining bounded wait.

4. Ambiguous next release version
   Expected: skill aborts and reports the ambiguity before tagging.

5. `gh pr checks --required` returns no checks even though the PR has active status checks
   Expected: skill falls back to `gh pr view --json statusCheckRollup` and still waits on the real PR gate.

6. Required GitHub checks stay pending or in progress after 6 polls spaced about 30 seconds apart
   Expected: skill aborts rather than merging or tagging from an uncertain CI state.

7. A required GitHub check finishes with a failing, cancelled, or timed_out terminal result
   Expected: skill aborts immediately and reports the failing required check before merge or tag creation.

8. Local release commits exist only on `main`
   Expected: skill creates a dedicated release branch for the PR without changing `main`'s upstream tracking.

9. CodeRabbit leaves a recommendation that the agent cannot justify dismissing
   Expected: skill aborts and reports the unresolved review risk instead of forcing the release through.
