# release-fp Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repo-tracked `/release-fp` skill that executes the Family Pickem PR, CodeRabbit, release-tag, and deploy-verification flow end to end.

**Architecture:** Create a new repo-local skill under `skills/release-fp/` with one main `SKILL.md` and a compact supporting reference for project-specific commands and stop conditions only if the main file would become too large. The skill will encode Family Pickem’s GitHub workflow conventions and explicitly halt on unsafe or ambiguous states instead of improvising.

**Tech Stack:** Codex skill authoring (`SKILL.md`), repo documentation, GitHub CLI (`gh`), Git, GitHub Actions conventions, CodeRabbit review flow.

---

## File Structure

- Create: `skills/release-fp/SKILL.md`
  Main project skill with discovery metadata, trigger conditions, execution workflow, stop conditions, and verification rules.
- Create: `skills/release-fp/testing-notes.md`
  Pressure scenarios and expected behavior for validating the skill without bloating the main skill.
- Modify: `.gitignore`
  Ignore `.worktrees/` if it is currently untracked and intended to remain local-only.
- Modify: `docs/superpowers/specs/2026-07-13-release-fp-skill-design.md`
  Only if a tiny clarification is needed during implementation; otherwise leave untouched.

### Task 1: Create the Skill Skeleton and Discovery Metadata

**Files:**
- Create: `skills/release-fp/SKILL.md`
- Test: `skills/release-fp/SKILL.md` (metadata self-check)

- [ ] **Step 1: Write the failing discovery checklist**

Add this temporary checklist to your working notes before writing the skill:

```markdown
- name uses only letters, numbers, hyphens
- description starts with "Use when..."
- description mentions Family Pickem release workflow triggers
- skill location is repo-tracked under skills/release-fp/
```

- [ ] **Step 2: Run the metadata check mentally against a missing file**

Run:

```bash
test -f skills/release-fp/SKILL.md
```

Expected: exit non-zero because the skill file does not exist yet.

- [ ] **Step 3: Write the minimal skill frontmatter and overview**

Create `skills/release-fp/SKILL.md` with at least:

```markdown
---
name: release-fp
description: Use when shipping Family Pickem changes through the project’s standard PR, CodeRabbit, release-tag, and deploy-verification workflow.
---

# release-fp

## Overview

Use this skill to execute the standard Family Pickem ship flow end to end. It is project-specific and should not be used as a generic GitHub release skill.
```

- [ ] **Step 4: Run the metadata check again**

Run:

```bash
python - <<'PY'
from pathlib import Path
text = Path('skills/release-fp/SKILL.md').read_text()
assert 'name: release-fp' in text
assert 'description: Use when' in text
assert 'Family Pickem' in text
print('metadata ok')
PY
```

Expected: prints `metadata ok`.

- [ ] **Step 5: Commit**

```bash
git add skills/release-fp/SKILL.md
git commit -m "feat(skill): scaffold release-fp skill"
```

### Task 2: Encode the Project-Specific Release Workflow

**Files:**
- Modify: `skills/release-fp/SKILL.md`
- Test: `skills/release-fp/SKILL.md`

- [ ] **Step 1: Write the failing workflow checklist**

Document the required sections to add:

```markdown
- preflight branch/worktree checks
- local verification step
- PR create or reuse flow
- GitHub checks wait flow
- CodeRabbit comments/threads inspection
- merge flow
- family-pickem release tag creation
- deploy verification via Publish Artifacts runs
```

- [ ] **Step 2: Verify the current skill text lacks those sections**

Run:

```bash
python - <<'PY'
from pathlib import Path
text = Path('skills/release-fp/SKILL.md').read_text()
required = [
    'Preflight',
    'CodeRabbit',
    'Publish Artifacts',
    'family-pickem-',
]
missing = [item for item in required if item not in text]
assert missing, missing
print('missing sections confirmed:', ', '.join(missing))
PY
```

Expected: prints that sections are missing.

- [ ] **Step 3: Add the execution workflow**

Expand `skills/release-fp/SKILL.md` with:

```markdown
## Workflow

1. Inspect branch state and dirty files.
2. Stop if unrelated changes are mixed into the intended release.
3. Run the expected local verification for the active change.
4. Commit only the intended files.
5. Push the branch and create or reuse a PR targeting `main`.
6. Wait for required GitHub checks to finish.
7. Inspect CodeRabbit PR comments and review threads, not just status text.
8. If actionable CodeRabbit feedback exists, fix it, push, and repeat checks/review.
9. Merge the PR.
10. Create the next `family-pickem-<version>` GitHub release.
11. Verify the `Publish Artifacts` workflows for both `main` push and release tag.
```

Also add the project-specific command references:

```markdown
## Project Conventions

- PR base branch: `main`
- Release tag format: `family-pickem-<version>`
- Deploy verification target: GitHub Actions runs named `Publish Artifacts`
- CodeRabbit verification source: PR comments and review threads
```

- [ ] **Step 4: Re-run the workflow presence check**

Run:

```bash
python - <<'PY'
from pathlib import Path
text = Path('skills/release-fp/SKILL.md').read_text()
for required in ['Preflight', 'CodeRabbit', 'Publish Artifacts', 'family-pickem-']:
    assert required in text, required
print('workflow sections ok')
PY
```

Expected: prints `workflow sections ok`.

- [ ] **Step 5: Commit**

```bash
git add skills/release-fp/SKILL.md
git commit -m "feat(skill): add release-fp workflow steps"
```

### Task 3: Add Hard Stop Conditions and Safety Rules

**Files:**
- Modify: `skills/release-fp/SKILL.md`
- Create: `skills/release-fp/testing-notes.md`
- Test: `skills/release-fp/SKILL.md`, `skills/release-fp/testing-notes.md`

- [ ] **Step 1: Write the failing safety checklist**

List the mandatory stop conditions from the spec:

```markdown
- unrelated dirty worktree changes
- ambiguous release version
- failed or non-terminal required checks
- actionable CodeRabbit findings that cannot be resolved confidently
- CodeRabbit stuck beyond timeout
```

- [ ] **Step 2: Confirm the current skill does not yet mention all stop conditions**

Run:

```bash
python - <<'PY'
from pathlib import Path
text = Path('skills/release-fp/SKILL.md').read_text()
needles = [
    'ambiguous release version',
    'unrelated dirty worktree changes',
    'stuck beyond a timeout window',
]
missing = [needle for needle in needles if needle not in text]
assert missing, missing
print('missing stop conditions confirmed')
PY
```

Expected: prints `missing stop conditions confirmed`.

- [ ] **Step 3: Add explicit stop conditions and testing notes**

Extend `skills/release-fp/SKILL.md` with:

```markdown
## Stop Conditions

Stop immediately if:

- the worktree contains unrelated dirty changes
- the next release tag cannot be determined unambiguously
- required GitHub checks fail or remain non-terminal
- CodeRabbit produces actionable findings that cannot be resolved confidently
- CodeRabbit remains stuck in a non-terminal state beyond the skill’s timeout window
```

Create `skills/release-fp/testing-notes.md` with pressure scenarios such as:

```markdown
# release-fp Testing Notes

## Pressure Scenarios

1. Dirty worktree with unrelated files present
   Expected: skill aborts before commit

2. CodeRabbit pending with no review threads for too long
   Expected: skill aborts instead of merging blindly

3. Ambiguous next release version
   Expected: skill aborts and reports the ambiguity
```

- [ ] **Step 4: Re-run the safety presence check**

Run:

```bash
python - <<'PY'
from pathlib import Path
text = Path('skills/release-fp/SKILL.md').read_text()
for required in [
    'unrelated dirty worktree changes',
    'ambiguous release version',
    'CodeRabbit remains stuck',
]:
    assert required in text, required
print('stop conditions ok')
PY
```

Expected: prints `stop conditions ok`.

- [ ] **Step 5: Commit**

```bash
git add skills/release-fp/SKILL.md skills/release-fp/testing-notes.md
git commit -m "feat(skill): add release-fp safety rules"
```

### Task 4: Add Project-Specific Command Reference and Verification Commands

**Files:**
- Modify: `skills/release-fp/SKILL.md`
- Test: `skills/release-fp/SKILL.md`

- [ ] **Step 1: Write the failing command-reference checklist**

Required commands:

```markdown
- git status --short --branch
- gh pr status / gh pr view
- gh pr checks --watch
- gh api graphql for CodeRabbit threads if needed
- gh release create family-pickem-<version>
- gh run list / gh run view
```

- [ ] **Step 2: Confirm command coverage is incomplete**

Run:

```bash
python - <<'PY'
from pathlib import Path
text = Path('skills/release-fp/SKILL.md').read_text()
required = ['gh pr checks --watch', 'gh api graphql', 'gh run list']
missing = [item for item in required if item not in text]
assert missing, missing
print('missing command refs confirmed')
PY
```

Expected: prints `missing command refs confirmed`.

- [ ] **Step 3: Add the project command reference**

Append a concise command section like:

```markdown
## Command Reference

- Branch/worktree: `git status --short --branch`
- PR status: `gh pr status`, `gh pr view <number> --json ...`
- Checks: `gh pr checks <number> --watch`
- CodeRabbit threads: `gh api graphql -f query='...'`
- Release creation: `gh release create family-pickem-<version> --target main --title ... --generate-notes`
- Workflow verification: `gh run list --limit 10`, `gh run view <run-id> --json ...`
```

- [ ] **Step 4: Re-run the command coverage check**

Run:

```bash
python - <<'PY'
from pathlib import Path
text = Path('skills/release-fp/SKILL.md').read_text()
for required in ['gh pr checks --watch', 'gh api graphql', 'gh run list']:
    assert required in text, required
print('command refs ok')
PY
```

Expected: prints `command refs ok`.

- [ ] **Step 5: Commit**

```bash
git add skills/release-fp/SKILL.md
git commit -m "feat(skill): add release-fp command reference"
```

### Task 5: Verify Skill Usability and Repo Hygiene

**Files:**
- Modify: `.gitignore`
- Test: `skills/release-fp/SKILL.md`, `.gitignore`

- [ ] **Step 1: Check whether `.worktrees/` should be ignored**

Run:

```bash
test -e .worktrees && printf '.worktrees exists\n' || printf 'no local .worktrees\n'
rg -n '^\\.worktrees/$|^\\.worktrees$' .gitignore || true
```

Expected: if `.worktrees/` is local-only and currently unignored, plan to add it.

- [ ] **Step 2: Add `.worktrees/` to `.gitignore` only if needed**

If untracked local worktrees are showing up in `git status`, add:

```gitignore
.worktrees/
```

- [ ] **Step 3: Run final skill verification**

Run:

```bash
python - <<'PY'
from pathlib import Path
skill = Path('skills/release-fp/SKILL.md').read_text()
assert 'Use when shipping Family Pickem changes' in skill or 'Use when' in skill
assert 'CodeRabbit' in skill
assert 'Publish Artifacts' in skill
assert 'family-pickem-' in skill
assert 'Stop immediately if:' in skill
print('skill verification ok')
PY
git diff --check
```

Expected:
- `skill verification ok`
- no diff hygiene issues

- [ ] **Step 4: Review final changed files**

Run:

```bash
git diff -- skills/release-fp/SKILL.md skills/release-fp/testing-notes.md .gitignore
```

Expected: only the new repo-tracked skill and optional `.gitignore` change appear.

- [ ] **Step 5: Commit**

```bash
git add skills/release-fp/SKILL.md skills/release-fp/testing-notes.md .gitignore
git commit -m "feat(skill): add release-fp project release workflow"
```

## Self-Review

- Spec coverage:
  - repo-tracked project skill: covered in Tasks 1 and 5
  - full PR/CodeRabbit/release/deploy flow: covered in Tasks 2 and 4
  - stop conditions: covered in Task 3
  - project-specific Family Pickem conventions: covered in Tasks 2 and 4
- Placeholder scan:
  - No TBD/TODO placeholders remain in task steps.
- Type consistency:
  - Skill path is consistently `skills/release-fp/SKILL.md`.
  - Skill name is consistently `release-fp`.
  - Release tag format is consistently `family-pickem-<version>`.
