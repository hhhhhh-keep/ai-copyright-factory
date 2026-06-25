# Error Log — ISSUE-021 View Path 2026-06-23

## [ERR-20260623-008] generator-view-path-assumption

**Logged**: 2026-06-23T17:28:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
The generated-view test assumed a `View.vue` suffix, while the generator emits `{Pascal}Page.vue`.

### Error
```
FileNotFoundError: .../src/views/ItemsView.vue
```

### Context
- Verifying that generated module buttons expose stable screenshot selectors.

### Suggested Fix
Base fixture paths on the generator’s actual `_frontend_files()` output convention.

### Metadata
- Reproducible: yes
- Related Files: backend/tests/test_material_documents.py, backend/app/project_generator.py

### Resolution
- **Resolved**: 2026-06-23T17:28:00+08:00
- **Notes**: Updated the test to read `ItemsPage.vue`.

---
