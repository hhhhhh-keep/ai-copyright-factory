# Task: E2E minimal AI codegen run

## Goal

Run a minimal task with AI code enhancement from planning through final package, fixing and recording any blocking errors until a task completes successfully.

## Acceptance criteria

- [x] Minimal task runs from LLM planning through final copyright package.
- [x] AI code enhancement is enabled and final task reports `codegen_actual_mode=llm`.
- [x] Generated project validation passes frontend build, backend structure check, and Maven tests.
- [x] Screenshots, required DOCX documents, `generated_project.zip`, and `copyright_package.zip` are produced.
- [x] Blocking regressions discovered during the run are fixed and recorded in `docs/ISSUES.md`.

## Scope exclusions

- Do not redesign the product flow beyond fixes needed to complete this E2E run.
- Do not commit, push, or delete historical `outputs/` jobs.

## Verification

```text
python -m unittest tests.test_enhancer tests.test_project_generator tests.test_workflow_order -v
git diff --check
E2E job: 20260625123758-c69d4bcd
status=success; codegen_actual_mode=llm; screenshots=12
run_validation={"frontend_build":"passed","backend_structure":"passed","maven_test":"passed","maven_reason":null}
copyright_package.zip=5129279 bytes; generated_project.zip=124848 bytes
```

