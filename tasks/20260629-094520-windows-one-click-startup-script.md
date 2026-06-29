# Task: Windows one-click startup script

## Goal

Add a Windows one-click startup script for local deployment/dev use, and align README/env defaults with the timeouts that passed the latest E2E run.

## Acceptance criteria

- [x] `scripts/start-dev.ps1` checks required tools, prepares `.env`, installs dependencies, and starts backend/frontend.
- [x] README documents the one-click path and keeps manual startup as fallback.
- [x] `backend/.env.example` and settings defaults use planner 180s / codegen 240s / npm install 600s.
- [x] Script syntax and touched tests/checks pass.

## Scope exclusions

- Do not add Docker or a service manager.
- Do not commit secrets or generated `outputs/` data.
- Do not change the product runtime workflow.

## Verification

```text
$null = [scriptblock]::Create((Get-Content -Raw -LiteralPath 'scripts\start-dev.ps1')); Write-Output 'syntax ok'
python -m unittest tests.test_settings -v
git diff --check
```
