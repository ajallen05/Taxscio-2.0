---
name: implement
description: Implement a new feature or module end-to-end. Use when building something new — a route, service, component, or integration. Covers planning, coding, tests, and verification.
---

# Implement

You are implementing a production-grade feature. Follow this workflow exactly.

## Step 1 — Understand Before You Code

Before writing a single line:
1. Read the relevant existing files to understand current patterns.
2. Identify the files you'll need to create or modify.
3. Check if similar functionality already exists (don't duplicate).
4. Write a short plan to `plan.md`:
   - What you're building
   - Files to create / modify
   - Any edge cases or constraints
   - How you'll verify it works

Do NOT start coding until the plan exists.

## Step 2 — Implement

Follow the project's established patterns (read `CLAUDE.md` for specifics). In general:

- **Types first:** Define your data shapes / interfaces / schemas before logic.
- **Core logic before wiring:** Write the business logic, then the API layer on top.
- **Error paths matter as much as happy paths.** Handle them explicitly.
- **No magic numbers / hardcoded strings** in logic — use constants or config.
- **One responsibility per function.** If a function is doing two things, split it.

## Step 3 — Tests

Write tests that cover:
- [ ] Happy path (expected input → expected output)
- [ ] Edge cases (empty, null, boundary values)
- [ ] Error cases (invalid input, dependency failures)

Match the testing style in `tests/`. If no tests directory exists, ask before creating one.

## Step 4 — Verify

Run ALL of the following before marking done:
```bash
# Tests
[project test command from CLAUDE.md]

# Types / lint
[project typecheck command from CLAUDE.md]
```

If anything fails, fix it. Do not declare success with failing checks.

## Step 5 — Clean Up

- Delete any debug logs or `print` statements added during development.
- Remove commented-out code.
- Update `plan.md` — mark steps complete.
- If you made architectural decisions, add a note to `docs/` or inline comment explaining why.

## Quality Gates

Before finishing, verify:
- [ ] Tests pass
- [ ] Typecheck / lint clean
- [ ] No hardcoded secrets or env values
- [ ] Error handling in all external calls
- [ ] Matches existing code style
