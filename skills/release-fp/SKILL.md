---
name: release-fp
description: Use when shipping Family Pickem changes through the project's standard PR, CodeRabbit, release-tag, and deploy-verification workflow.
---

# release-fp

## Overview

Use this skill to execute the standard Family Pickem ship flow end to end. It is project-specific and should not be used as a generic GitHub release skill.

## Workflow

### Preflight

1. Run preflight checks before opening or merging anything.
   - Confirm the current branch is the intended feature branch and the worktree is clean enough to ship.
   - Check `git status --short --branch` and `git worktree list` so you do not release from the wrong branch or a detached worktree.
   - If the branch already has an open PR, reuse it instead of creating a duplicate.

2. Run local verification before touching GitHub.
   - Execute the project's required local validation for the change set.
   - Do not open, update, or merge a PR until the local verification step passes or the failure is understood and explicitly accepted.

3. Create or reuse a pull request targeting `main`.
   - The PR base branch for Family Pickem releases is always `main`.
   - If a PR already exists for the branch, continue with that PR.
   - If no PR exists, create one against `main` with a release-ready title and summary.

4. Wait for GitHub checks to finish on the PR.
   - Do not rely on a stale status from a previous commit.
   - Re-check the live PR status after the latest push and wait until the required checks complete.
   - Use a bounded wait of 6 polls spaced about 30 seconds apart for required checks; stop only if a required check ends in a terminal failing state or is still non-terminal after poll 6.

5. Inspect CodeRabbit feedback in the PR discussion itself.
   - Verify CodeRabbit by reading PR comments and review threads, not just the overall status text.
   - Use the same bounded wait of 6 polls spaced about 30 seconds apart for CodeRabbit before treating it as stuck.
   - If actionable CodeRabbit feedback exists, fix it, push the follow-up commit, then repeat PR checks and CodeRabbit review until clear.
   - Resolve or explicitly account for outstanding CodeRabbit comments before merge.
   - Confirm no unresolved review threads remain on the PR.

6. Merge the PR after reviews and checks are clear.
   - Merge into `main` only after local verification, GitHub checks, and CodeRabbit review are all complete.
   - Prefer the repository's standard merge method rather than ad hoc history rewriting during release.

7. Create the next release tag from updated `main`.
   - Pull or otherwise verify the local `main` matches the merged remote state before tagging.
   - Derive the next version from existing `family-pickem-*` tags only, and stop if the next version is not unambiguous.
   - Create the next Family Pickem release using the tag format `family-pickem-<version>`.
   - Push the release tag only after confirming it points at the intended `main` commit.

8. Verify deployment workflows for both release triggers.
   - Confirm `.github/workflows/publish-artifacts-latest.yaml` runs successfully for the push to `main` even though its display name is `Publish Artifacts`.
   - Confirm `.github/workflows/publish-artifacts.yaml` runs successfully for the `family-pickem-<version>` release event even though its display name is also `Publish Artifacts`.
   - Treat release verification as incomplete until both workflow runs finish successfully.

## Project Conventions

- PR base branch: `main`
- Release tag format: `family-pickem-<version>`
- Deploy verification targets: `.github/workflows/publish-artifacts-latest.yaml` for push to `main`, `.github/workflows/publish-artifacts.yaml` for release publish
- CodeRabbit verification source: PR comments and review threads

## Command Reference

- Worktree and branch state: `git status --short --branch`
- PR discovery: `gh pr status`
- PR details and checks summary: `gh pr view <number> --json number,state,isDraft,reviewDecision,statusCheckRollup,comments,reviews`
- Live PR checks: `gh pr checks --watch` or `gh pr checks <number> --watch`
- CodeRabbit threads when comment state is unclear: `gh api graphql ...`
- Release creation from `main`: `gh release create family-pickem-<version> --target main --title <title> --generate-notes`
- Workflow discovery: `gh run list`
- Workflow run inspection: `gh run view <run-id> --json databaseId,status,conclusion,event,workflowName,headBranch,headSha,url`

## Stop Conditions

Stop immediately if:

- the worktree contains unrelated dirty worktree changes
- the next release tag cannot be determined because of an ambiguous release version
- required GitHub checks end in a terminal failing state, or remain non-terminal after 6 polls spaced about 30 seconds apart
- CodeRabbit produces actionable findings that cannot be resolved confidently
- CodeRabbit remains stuck in a non-terminal state after 6 polls spaced about 30 seconds apart
