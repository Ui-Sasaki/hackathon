---
name: team-development
description: Apply this repository's shared workflow for planning, implementing, reviewing, testing, documenting, and handing off FastAPI changes. Use when Codex changes code or repository structure, fixes bugs, adds APIs or tests, updates dependencies or documentation, reviews a diff or pull request, or prepares work for another team member in this repository.
---

# Team Development

Work from the shared repository root and leave a reviewable, tested change that follows the project requirements and team rules.

## Gather context

1. Read `/AGENTS.md` completely.
2. Read the relevant sections of `/要件定義書.md` and `/docs/fastapi-coding-standards.md`.
3. Inspect `git status --short` before editing. Treat existing changes as team-owned and preserve them.
4. Inspect the implementation, tests, and documentation involved in the requested behavior.
5. Convert the request and applicable requirements into concrete acceptance checks. Ask only when an unresolved choice would materially change behavior or compatibility.

Paths beginning with `/` are relative to the repository root.

## Make changes

1. Keep the diff scoped to one purpose and follow the existing module responsibilities.
2. Never create a personal-name or branch-name directory at the repository root. Use a Git branch to isolate work.
3. Preserve public API compatibility unless a breaking change is explicitly accepted.
4. Update tests with behavior changes. Cover the success case and relevant validation, authorization, conflict, and state-transition failures.
5. Update README, requirements, imports, and configuration when paths or usage change.
6. Do not commit virtual environments, caches, generated metadata, credentials, tokens, or local environment files.

## Validate

1. Run the narrowest relevant checks during implementation.
2. Run the complete suite before handoff:

```bash
.venv/bin/python -m pytest -q
```

3. Inspect `git diff --check`, `git diff`, and `git status --short`.
4. Search for stale paths or names after moves and renames.
5. Report any check that could not run and the exact reason; do not imply unrun checks passed.

## Review

Review the resulting diff before declaring completion. Prioritize:

- requirement or acceptance-criteria violations;
- authentication, authorization, privacy, secret-handling, and injection risks;
- incorrect state transitions, error contracts, or API compatibility breaks;
- concurrency, retry, and idempotency problems;
- missing regression tests and stale documentation.

For a review-only request, do not modify files. Report findings first, ordered by severity, with file and line references. If there are no findings, say so and identify residual risks or untested areas.

## Hand off

State the outcome first. Summarize changed files and behavior, list validation commands and results, and call out remaining risks or follow-up work. Do not claim a code review unless the review step was completed.
