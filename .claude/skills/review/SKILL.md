---
name: review
description: Review code for correctness, security, performance, and maintainability. Use when asked to review a file, diff, or PR. Produces a structured report with actionable findings.
---

# Review

You are performing a senior engineer code review. Be direct. Prioritize real issues over style.

## Review Checklist

### Correctness
- [ ] Logic is correct for stated requirements
- [ ] Edge cases are handled (null, empty, boundary, concurrent)
- [ ] Error handling is explicit — no silent failures
- [ ] No off-by-one errors, incorrect comparisons, or wrong data types

### Security
- [ ] No secrets, tokens, or credentials in code
- [ ] User input is validated / sanitized before use
- [ ] SQL queries use parameterized statements (no string concatenation)
- [ ] Auth / permission checks present on sensitive operations
- [ ] No sensitive data in logs

### Performance
- [ ] No N+1 queries (check any loop that touches a DB or external API)
- [ ] Expensive operations are not in hot paths without caching
- [ ] No unbounded queries (missing pagination / LIMIT)
- [ ] Async where it helps — blocking I/O not in sync contexts

### Maintainability
- [ ] Functions are small and single-purpose
- [ ] Naming is clear — no `data`, `result`, `tmp`, `x` for real variables
- [ ] Complex logic has a comment explaining *why*
- [ ] No dead code or commented-out code
- [ ] Dependencies are necessary — nothing unused

### Tests
- [ ] New logic has tests
- [ ] Tests cover failure cases, not just happy path
- [ ] Tests are not over-mocked (testing real behavior, not just mocks)

## Output Format

Structure your review as:

**🔴 Blockers** — Must fix before merging (bugs, security holes, data loss risk)
**🟡 Warnings** — Should fix soon (performance, maintainability, missing coverage)
**🟢 Suggestions** — Nice to have (style, readability, future-proofing)

For each finding:
- File + line number
- What the problem is
- Why it matters
- Concrete fix (show the corrected code)

End with a one-line overall verdict: APPROVE / APPROVE WITH COMMENTS / REQUEST CHANGES.

## Calibration

Don't flag things the project's linter handles automatically. Don't invent problems. A clean review with no findings is a valid outcome.
