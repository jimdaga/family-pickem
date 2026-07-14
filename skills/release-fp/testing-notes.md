# release-fp Testing Notes

## Pressure Scenarios

1. Dirty worktree with unrelated files present
   Expected: skill aborts before opening, updating, or merging a PR.

2. CodeRabbit pending with no review threads for too long
   Expected: skill aborts instead of merging blindly when CodeRabbit remains stuck beyond a timeout window.

3. Ambiguous next release version
   Expected: skill aborts and reports the ambiguity before tagging.

4. Required GitHub checks never reach a terminal success state
   Expected: skill aborts rather than merging or tagging from an uncertain CI state.

5. CodeRabbit leaves a recommendation that the agent cannot justify dismissing
   Expected: skill aborts and reports the unresolved review risk instead of forcing the release through.
