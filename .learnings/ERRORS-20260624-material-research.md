# Error Log — Material Research 2026-06-24

## [ERR-20260624-001] pypdf2-unavailable

**Logged**: 2026-06-24T09:20:00+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
The default PDF parser was unavailable while inspecting user-provided reference samples.

### Error
```
ModuleNotFoundError: No module named 'PyPDF2'
```

### Resolution
- **Resolved**: 2026-06-24T09:25:00+08:00
- **Notes**: Used the already installed PyMuPDF (`fitz`) in read-only mode; no dependency was installed.

---

## [ERR-20260624-002] test-patch-context

**Logged**: 2026-06-24T09:45:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
An initial test patch used stale assertion context and did not apply.

### Resolution
- **Resolved**: 2026-06-24T09:46:00+08:00
- **Notes**: Read the current test file and applied a narrower patch; no code was changed by the failed patch.

---

## [ERR-20260624-003] unicode-docx-path-inspection

**Logged**: 2026-06-24T15:35:00+08:00
**Priority**: low
**Status**: resolved
**Area**: diagnostics

### Summary
An inline Python inspection command passed a Chinese DOCX filename through a shell pipeline that replaced non-ASCII characters, so `python-docx` could not open the file.

### Error
```
OSError: [Errno 22] Invalid argument: '...\\?????.docx'
```

### Resolution
- **Resolved**: 2026-06-24T15:35:00+08:00
- **Notes**: Enumerated the ASCII parent directory in Python and opened each DOCX by discovered path. The follow-up inspection confirmed blank PAGE headers, the four-column operation tables, and source material structure without mutating output files.

---

## [ERR-20260624-004] full-backend-suite-interrupted

**Logged**: 2026-06-24T15:49:00+08:00
**Priority**: medium
**Status**: open
**Area**: regression verification

### Summary
The full backend unittest discovery run was interrupted by exit code 137 while executing an unrelated resume/interrupt test. Focused ISSUE-021 tests had already passed.

### Evidence
```
test_dead_lock_with_recent_updated_at_is_orphaned ... KeyboardInterrupt
Exit code: 137
```

### Follow-up
- Preserve the focused passing result for the material changes.
- Do not classify the full-suite interruption as an ISSUE-021 regression; reproduce the unrelated timeout/interrupt test separately before claiming a full-suite pass.

---
