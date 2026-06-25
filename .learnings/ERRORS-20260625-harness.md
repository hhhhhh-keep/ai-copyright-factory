## [ERR-20260625-001] codex_harness_active_task_not_finalized

**Logged**: 2026-06-25T00:00:00+08:00
**Priority**: medium
**Status**: pending
**Area**: docs

### Summary
`Start-CodexHarnessTask.ps1` refuses to start a new task when `tasks/active.md` lacks the harness completion marker, even if the file text says `Status: complete`.

### Error
```text
The active task is not complete. Finish it first, or pass -Force to intentionally replace it.
```

### Context
- Command attempted: `C:\Users\whn\.codex\Start-CodexHarnessTask.ps1 -TaskName "Fix ISSUE-021 design chart overflow"`
- Active task text described a completed E2E run, but it had not been finalized in the exact format expected by the harness script.
- Do not use `-Force` automatically in this situation because it may overwrite unrelated handoff state.

### Suggested Fix
Before starting a new harness task, inspect `tasks/active.md` and `.codex/state/handoff.md`; if the task is genuinely complete, finalize it through the expected harness path, otherwise record implementation evidence in the current issue document and avoid replacing active state.

### Metadata
- Reproducible: yes
- Related Files: tasks/active.md, .codex/state/progress.md

---
