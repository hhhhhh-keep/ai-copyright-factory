# Error Log — Harness 2026-06-23

## [ERR-20260623-005] harness-state-file-locked

**Logged**: 2026-06-23T17:03:00+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
The existing Harness state file could not be deleted for replacement after the issue-recording task was initialized.

### Error
```
Failed to delete file .codex/state/plan.md
```

### Context
- The active task and its task-specific issue file already contain the scope, acceptance criteria, and implementation block.

### Suggested Fix
Do not overwrite an owned/locked state artifact when the durable task record already contains the required evidence; update it only through its owning Harness workflow.

### Metadata
- Reproducible: unknown
- Related Files: .codex/state/plan.md, tasks/active.md

### Resolution
- **Resolved**: 2026-06-23T17:03:00+08:00
- **Notes**: Preserved the existing state file and kept the new task evidence in `tasks/active.md` and `docs/ISSUE-021.md`.

---
