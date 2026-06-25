# Error Log — ISSUE-021 Fixture 2026-06-23

## [ERR-20260623-007] generator-fixture-missing-industry

**Logged**: 2026-06-23T17:25:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
The new generated-view test omitted `industry_name`, which is required by the deterministic app shell generator.

### Error
```
KeyError: 'industry_name'
```

### Context
- `generate_java_project()` was invoked with a hand-built minimal planning fixture.

### Suggested Fix
Reuse a complete planning schema in generator tests, including display-only fields consumed by the app shell.

### Metadata
- Reproducible: yes
- Related Files: backend/tests/test_material_documents.py

### Resolution
- **Resolved**: 2026-06-23T17:25:00+08:00
- **Notes**: Added the required industry display name to the test planning fixture.

---
