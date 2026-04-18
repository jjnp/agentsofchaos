---
name: merge
description: Create a GitHub pull request for the current branch and immediately merge it into main when safe. Use when the user wants the current branch landed quickly.
---

# Merge

Create a pull request from the current branch into `main`, then merge it if there are no conflicts or blocking issues.

## Requirements

- Use the `gh` CLI.
- Inspect `git status`, current branch, and remotes first.
- If the current branch is `main`, stop and ask the user to create or switch to a feature branch.
- If there are local changes, create a sensible commit first using a concise Conventional Commits-style subject.
- Push the current branch if needed.
- Create a concise PR title based on the branch changes.
- Create a short PR body with:
  - Summary
  - Validation
- Check the PR merge status after creation.
- Merge only when GitHub reports a clean merge state and there are no reported blocking checks.
- Prefer merging with `gh pr merge --merge --delete-branch`.
- After merging, check out `main` and update it from origin so the local repo is current.
- After finishing, report the commit, PR number, URL, and final merge result.

## Steps

1. Check `git status --short`.
2. Determine the current branch with `git branch --show-current`.
3. Confirm the GitHub repo via `gh repo view --json nameWithOwner,defaultBranchRef`.
4. If there are uncommitted changes, review the diff, stage the intended files, and commit them.
5. If the branch has no upstream or is not pushed, push it.
6. Review recent commits and/or diff against `main` to derive a title/body.
7. Create the PR against `main` with `gh pr create`.
8. Inspect the PR with `gh pr view` and/or `gh pr checks`.
9. If the merge state is clean and there are no blocking checks, merge it.
10. Check out `main` and fast-forward or pull from `origin/main`.
11. Report the outcome clearly.
