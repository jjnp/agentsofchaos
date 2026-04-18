---
name: pr
description: Create a GitHub pull request for the current branch. Use when the user wants a PR opened from the current branch into main.
---

# PR

Create a pull request from the current branch into `main`.

## Requirements

- Use the `gh` CLI.
- Inspect `git status`, current branch, and remotes first.
- If there are unstaged or uncommitted changes, stop and ask the user what to do.
- If the current branch is `main`, stop and ask the user to create or switch to a feature branch.
- Push the current branch if needed.
- Create a concise PR title based on the branch changes.
- Create a short PR body with:
  - Summary
  - Validation
- After creating the PR, return the PR number and URL.

## Steps

1. Check `git status --short`.
2. Determine the current branch with `git branch --show-current`.
3. Confirm the GitHub repo via `gh repo view --json nameWithOwner,defaultBranchRef`.
4. If the branch has no upstream or is not pushed, push it.
5. Review recent commits and/or diff against `main` to derive a title/body.
6. Create the PR against `main` with `gh pr create`.
7. Report the result clearly.
