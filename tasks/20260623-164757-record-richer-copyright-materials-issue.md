# Task: Record richer copyright materials issue

## Goal

Record the observed gaps in generated design specifications and user manuals, identify the responsible generator paths, and freeze an implementation proposal for explicit user approval.

## Acceptance criteria

- [x] Reproduce the current screenshot and document coverage from source code.
- [x] Record a scoped ISSUE with root cause, non-goals, acceptance criteria, and verification plan.
- [x] Provide a non-copied template direction based on the supplied example and public template research.

## Scope exclusions

- Do not change material-generation business code, existing output tasks, or the user’s unrelated uncommitted work.

## Verification

```text
git diff --check
manual source inspection of capture_screenshots(), generate_documents(), and build_compliance_report()
```
