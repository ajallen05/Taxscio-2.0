---
name: debug
description: Systematically diagnose and fix a bug. Use when something is broken and the cause is unknown. Produces a root cause analysis and a targeted fix.
---

# Debug

You are debugging a production issue. Be systematic. Don't guess.

## Process

### Step 1 — Reproduce

Before fixing anything, confirm you can reproduce the problem:
- What is the exact input / action that triggers it?
- What is the actual behavior vs. expected behavior?
- Is it consistent or intermittent?

If you can't reproduce it, say so. Don't fix what you can't confirm is broken.

### Step 2 — Isolate

Narrow the blast radius:
1. Read the error message + stack trace carefully. Start at the top frame in your code (skip library internals).
2. Identify the **exact line** where behavior diverges from expectation.
3. Check: is this a data problem, a logic problem, or an integration problem?

### Step 3 — Hypothesize

Form 1–3 candidate hypotheses ranked by likelihood. For each:
- What would cause this behavior?
- What evidence supports or refutes it?

Check the most likely hypothesis first. Use `grep`, `read_file`, and targeted test runs — don't read entire files speculatively.

### Step 4 — Fix

Once root cause is confirmed:
- Make the **minimal change** that fixes the root cause.
- Don't refactor or improve adjacent code while fixing a bug — that's a separate PR.
- If the fix is non-obvious, add a comment explaining the root cause.

### Step 5 — Verify + Prevent Regression

1. Run the full test suite.
2. Add a test that would have caught this bug. Name it `test_[what_broke]_[condition]`.
3. Check if the same pattern exists elsewhere in the codebase. If so, fix those too.

## Output

End with a brief post-mortem:
- **Root cause:** [one sentence]
- **Fix:** [what changed and why]
- **Regression test:** [file + test name]
- **Similar risk areas:** [other places to watch]
