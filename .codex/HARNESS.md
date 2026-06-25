# Project Harness

## Active task

Store the active task in `tasks/active.md`. It must define the goal, acceptance criteria, scope exclusions, and required verification.

## State files

- `.codex/state/plan.md` — Planner output
- `.codex/state/progress.md` — Builder evidence and handoff
- `.codex/state/critique.md` — Critic verdict
- `.codex/state/handoff.md` — Finalizer closeout

## Completion gate

`LOOP_COMPLETE` may be written only after all required verification passes and the Critic records PASS.
