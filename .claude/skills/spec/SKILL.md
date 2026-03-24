---
name: spec
description: Write a technical spec for a feature before implementation. Use at the start of any significant feature to clarify requirements, design decisions, and success criteria before a line of code is written.
---

# Spec

You are writing a technical spec to align on what to build before building it. This prevents wasted implementation effort.

## Process

1. **Interview mode first.** Ask targeted clarifying questions before writing anything. Focus on:
   - What problem does this solve? Who experiences it?
   - What does success look like? What metrics?
   - What are the hard constraints (performance, security, backwards compat)?
   - What's explicitly out of scope?
   - Are there existing patterns in the codebase to follow?

   Ask until you have enough clarity. Then say "I have enough to write the spec" and proceed.

2. **Write the spec to `docs/specs/[feature-name].md`.**

## Spec Template

```markdown
# [Feature Name]

**Status:** Draft | Review | Approved
**Author:** [name]
**Date:** [date]

## Problem

[2–3 sentences. What breaks or is missing today? Who is affected?]

## Goals

- [Measurable outcome 1]
- [Measurable outcome 2]

## Non-Goals

- [Explicitly out of scope — prevents scope creep]

## Design

### Data Model

[Schema changes, new tables/fields, type definitions]

### API / Interface

[Endpoints, function signatures, events — whatever the surface area is]

### Flow

[Step-by-step: what happens from trigger to outcome. Use a numbered list or ASCII diagram.]

### Error Handling

[What can go wrong? How does each failure surface to the user / caller?]

## Security & Permissions

[Auth requirements, data access rules, any PII handling]

## Performance Considerations

[Expected load, latency budget, caching strategy if needed]

## Testing Plan

[What must be tested? Unit? Integration? Manual QA steps?]

## Open Questions

- [ ] [Unresolved decision that needs input]

## Success Criteria

[How do we know this is done and working correctly?]
```

## Output

Write the spec file, then summarize the key design decisions and any remaining open questions that need stakeholder input before implementation starts.

Do NOT start implementation after writing the spec unless explicitly asked.
