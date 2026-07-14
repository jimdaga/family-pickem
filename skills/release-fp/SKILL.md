---
name: release-fp
description: Use when shipping Family Pickem changes through the project's standard PR, CodeRabbit, release-tag, and deploy-verification workflow.
---

# release-fp

## Overview

Use this skill to execute the standard Family Pickem ship flow end to end. It is project-specific and should not be used as a generic GitHub release skill.

## Workflow

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

5. Inspect CodeRabbit feedback in the PR discussion itself.
   - Verify CodeRabbit by reading PR comments and review threads, not just the overall status text.
   - Resolve or explicitly account for outstanding CodeRabbit comments before merge.
   - Confirm no unresolved review threads remain on the PR.

6. Merge the PR after reviews and checks are clear.
   - Merge into `main` only after local verification, GitHub checks, and CodeRabbit review are all complete.
   - Prefer the repository's standard merge method rather than ad hoc history rewriting during release.

7. Create the next release tag from updated `main`.
   - Pull or otherwise verify the local `main` matches the merged remote state before tagging.
   - Create the next Family Pickem release using the tag format `family-pickem-<version>`.
   - Push the release tag only after confirming it points at the intended `main` commit.

8. Verify deployment workflows for both release triggers.
   - Confirm the `Publish Artifacts` workflow runs successfully for the push to `main`.
   - Confirm the `Publish Artifacts` workflow also runs successfully for the `family-pickem-<version>` release tag.
   - Treat release verification as incomplete until both workflow runs finish successfully.

## Project Conventions

- PR base branch: `main`
- Release tag format: `family-pickem-<version>`
- Deploy verification target: `Publish Artifacts`
- CodeRabbit verification source: PR comments and review threads
