# release-fp Testing Notes

## Pressure Scenarios

1. Dirty worktree with unrelated files present
   Expected: skill aborts before opening, updating, or merging a PR.

2. CodeRabbit pending with no review threads after 6 polls spaced about 30 seconds apart
   Expected: skill aborts instead of merging blindly when CodeRabbit remains stuck after the bounded wait rule.

3. Ambiguous next release version
   Expected: skill aborts and reports the ambiguity before tagging.

4. Required GitHub checks stay pending or in progress after 6 polls spaced about 30 seconds apart
   Expected: skill aborts rather than merging or tagging from an uncertain CI state.

5. A required GitHub check finishes with a failing, cancelled, or timed_out terminal result
   Expected: skill aborts immediately and reports the failing required check before merge or tag creation.

6. CodeRabbit leaves a recommendation that the agent cannot justify dismissing
   Expected: skill aborts and reports the unresolved review risk instead of forcing the release through.
