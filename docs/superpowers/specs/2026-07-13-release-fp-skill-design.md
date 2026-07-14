# release-fp Skill Design

## Goal

Add a repo-tracked `/release-fp` skill that executes the standard Family Pickem ship flow end to end when invoked, so the workflow does not need to be re-described manually each time.

## Approved Direction

The skill should be an execution skill, not a checklist. When invoked, it should perform the normal GitHub ship flow directly:

- verify local branch/worktree state
- run the expected local verification
- commit the intended changes
- push and open or update a PR
- wait for GitHub checks
- inspect CodeRabbit output
- fix actionable CodeRabbit feedback if needed
- merge the PR
- create the next production release tag
- verify the publish/deploy workflows

## Repository Placement

The skill should live in this repository so it persists across machines for the same project.

Recommended location:

- `skills/release-fp/SKILL.md`

Supporting files are allowed only if the main skill would otherwise become too large or if reusable scripts are justified.

## Scope

The first version should cover the Family Pickem release workflow only. It should not try to be a generic GitHub release skill.

Project-specific assumptions the skill may encode:

- PRs target `main`
- production release tags are `family-pickem-<version>`
- deploy verification is based on GitHub Actions workflow results
- CodeRabbit must be checked from PR comments/threads, not just the status line

## Execution Rules

The skill should execute the happy path automatically, but it must stop when continuing would be unsafe or ambiguous.

Required stop conditions:

- unrelated dirty worktree changes that are not part of the intended release
- ambiguous release version selection
- failed or non-terminal required checks
- actionable CodeRabbit findings that cannot be resolved confidently
- CodeRabbit stuck in a non-terminal state beyond a reasonable timeout window

## Workflow Shape

### 1. Preflight

- inspect branch state
- inspect dirty files
- determine whether the intended release diff is isolated
- confirm current tag/release baseline

### 2. Verification

- run the project’s expected local checks for the active change
- fail fast on local verification issues

### 3. PR Flow

- commit only the intended changes
- push the branch
- create or reuse the PR
- wait for GitHub checks

### 4. CodeRabbit Loop

- inspect CodeRabbit comments and review threads
- if actionable findings exist, fix them and push follow-up commits
- re-check until either:
  - CodeRabbit is satisfied, or
  - the skill reaches a stop condition

### 5. Merge and Release

- merge the PR to `main`
- determine the next `family-pickem-<version>` tag safely
- create the GitHub release

### 6. Deployment Verification

- verify that the `Publish Artifacts` runs start
- verify that the important release jobs complete successfully
- report the final release/deploy state clearly

## Safety Philosophy

The skill should optimize for reducing repetition, not for overriding judgment. It should be strict about isolation and review state so it does not accidentally ship unrelated work.

## Testing Expectations

Implementation should verify:

- the skill correctly identifies stop conditions
- the skill uses the right project-specific tag naming
- the skill checks CodeRabbit threads/comments, not just status text
- the skill verifies the relevant GitHub Actions runs after merge and release

## Non-Goals

The first version should not:

- handle arbitrary repositories
- infer project-specific release conventions dynamically
- bypass failed checks
- auto-merge through unresolved review findings
