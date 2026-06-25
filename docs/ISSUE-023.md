# ISSUE-023：AI 增强项目代码几乎全部失败(jobId=20260623225150-e2f31fbd 复盘)

- 状态：`已修正，Codex 代码复审通过`
- 优先级：`P0`
- 首次记录：2026-06-24
- 关联：ISSUE-020（5+1 分阶段 UI 增强）、ISSUE-022（截图抓拍时机，无关联编号但被占用，故本修复使用 ISSUE-023）

## 用户目标

- `outputs/{job_id}/ui_enhancement.json` 中 5 个 UI 子步骤至少有 4 个 `status=completed`。
- `codegen_actual_mode` 必须真实反映 AI 是否实际增强了 `style.css`。
- LLM 抖动（529 / SSL read timeout / 坏 JSON / 超长 CSS / 严格白名单）不应让单次任务"AI 增强几乎全部失败"。
- 同类失败必须自动写入 `.learnings/`,便于下次定位。

## 失败现场

jobId=`20260623225150-e2f31fbd`(涉案车辆管理系统,public_security 行业,`codegen_mode=auto`):

| # | 子步骤 | attempts | duration_ms | 错误摘要 | 根因 |
|---|---|---|---|---|---|
| 1 | shell | 2 | 139016 | `ValueError: 未包含可校验的 CSS 选择器` | LLM 返回的 CSS 没有 `_css_rule_selectors` 可解析的裸规则 |
| 2 | business | 2 | 246686 | `RuntimeError: Code enhancer API read timed out` | daemon Worker 走 urllib 直读,`urlopen(timeout=)` 只覆盖 connect,不覆盖 SSL read |
| 3 | dashboard | 2 | 95875 | `ValidationError: content > 8000 chars` | `UI_STEP_MAX_BLOCK_CHARS=8000` 过死,Pydantic 校验失败不重试 |
| 4 | responsive | 2 | 83704 | `ValueError: 未授权选择器: [':root', 'html', '.el-button', 'select', 'textarea']` | `UI_STEP_SELECTOR_HINTS["responsive"]` 不含 Element Plus 基础选择器 |
| - | theme | 1 | 29202 | 成功 | - |
| - | readme | 0 | 0 | 成功 | - |

结果:`codegen_changed_files=["README.md"]`,`frontend/src/style.css` 未被 AI 修改,完全靠模板兜底。但 `codegen_actual_mode="llm"`,语义失真。

## 共同病灶

- `max_attempts=2`,只重试 1 次;`time.sleep(2/4s)` 无 jitter,sleep 太短。
- `EnhancementResult.actual_mode` 在 UI 步全失败 + README 改了的情况下错误地返回 `"llm"`。
- `enhance` 阶段失败未自动写 `.learnings/`,2026-06-23 当天 7 条 ERROR 全部与本 jobId 无关。
- `worker_pid=39564` 在 `status=success` 后未收尾,`run_status` 仍 `running`(jobId 暴露的 worker 状态机问题)。

## 修复方案

### P0-1 白名单补全 + 全局 CSS 变量允许

- `UI_STEP_SELECTOR_HINTS["responsive"]` 增补 `":root"`、`"html"`、`"select"`、`"textarea"`、`".el-button"`、`".el-button--primary"`、`".el-input"`、`".el-tag"`、`".el-form"`、`".el-dialog"`。
- 新增 `GLOBAL_UI_SELECTOR_HINTS = (":root", "--ai-")`,`_selector_matches_hints` 优先匹配。任何步允许写 CSS 变量声明。

### P0-2 size 16000 + ValidationError 精简重试

- `UI_STEP_MAX_BLOCK_CHARS` 默认从 8000 提升到 16000;通过 `AI_CODEGEN_UI_BLOCK_MAX_CHARS` 覆盖。
- `_request_ui_step` 内 `UIStepBlock.model_validate` 抛 `ValidationError` 且含 `string_too_long` 时,向 LLM 发 1 条"精简后再发"反馈,二次失败才标 `failed`。

### P0-3 `_retry_with_backoff` helper + 指数退避 + jitter

- 新增 `_retry_with_backoff(operation, max_attempts=3, retry_callback)`,内部 `time.sleep(min(2 ** attempt, 8) + random.uniform(0, 1))`。
- HTTP 非 retryable code(400/403/404/408)直接抛,节省重试。
- `call_api` 与 `_call_chat_json` 复用 helper,消除重复 sleep/jitter 逻辑。
- `max_attempts` 通过 `AI_CODEGEN_MAX_ATTEMPTS` 覆盖,默认 3。
- daemon Worker 下的 SSL read timeout 暂不改造(避免动 `multiprocessing` 架构,留作 ISSUE-023 L2)。

### P0-4 llm 模式容忍 1 步失败

- `enhance_project` 中 `if requested_mode == "llm" and len(ui_failures) >= 2` 才整体回滚并抛 `RuntimeError`。
- 1 步失败 + README 失败均不阻断任务,`actual_mode` 仍按 UI 是否实际改 CSS 区分(见 P0-5)。
- 移除外层"后置整体回滚",已被 P0-4 早期拦截覆盖。

### P0-5 `EnhancementResult.actual_mode` 新增 `partial` 字面值

- 类型从 `Literal["template", "llm"]` 改为 `Literal["template", "llm", "partial"]`。
- 判定:`"frontend/src/style.css" in changed_files` 为真 → `llm`;否则若 README 改了 → `partial`;若都未改 → 走原 `template` fallback。
- `partial` 时 `summary` 末尾追加"（仅 README 由 AI 增强，UI/CSS 增强全部失败回滚到模板）"。
- 解决 jobId 暴露的"实际只改 README 但报 llm"的语义失真。

### P1-1 `.learnings/` 自动记录

- 新建 `backend/app/learning.py`,提供 `classify_failure()` 与 `append_enhance_error()`。
- `_record_enhance_failure()` 在 `enhance_project` 三个 return 路径前各调用一次,try/except 兜底,失败只 log warning 不影响主流程。
- 失败根因分类:`empty_selectors` / `whitelist_strict` / `size_exceeded` / `daemon_ssl_read_timeout` / `missing_credentials` / `api_http_error` / `other` / `unknown`。
- 文件命名:`.learnings/ERRORS-YYYYMMDD-enhance.md`,每个失败任务追加 `### ERR-YYYYMMDD-NNN` 条目;编号跨会话单调递增。
- 仓库缺少 `.learnings/` 目录时静默跳过(避免污染仓库)。

### P1-2 测试覆盖

`backend/tests/test_enhancer.py` 新增 6 项 + 调整 1 项,共 18 项:

1. `test_responsive_allows_basic_selectors` — 验证 responsive 步接受 `:root`/`html`/`.el-button`/`select`/`textarea`。
2. `test_dashboard_oversized_block_retries_with_trim_prompt` — 首次 17000 字符触发精简重试,二次 < 16000 成功。
3. `test_business_recovers_from_read_timeout_with_backoff` — 首次 `RuntimeError("read timed out")` 后,`_retry_with_backoff` 退避 jitter 生效。
4. `test_llm_mode_tolerates_one_ui_step_failure` — llm 模式 + 1 步失败 → 不抛 RuntimeError,`actual_mode=llm`。
5. `test_actual_mode_partial_when_only_readme_changed` — 4 UI 步全失败 + README 成功 → `actual_mode=partial`。
6. `test_partial_failures_write_to_learnings` — mock `append_enhance_error`,验证 failures 非空时被调用 1 次。
7. 调整 `test_llm_mode_any_failure_rolls_back` → `test_llm_mode_two_failures_rolls_back`,适配新容忍策略。

### P1-3 worker 状态机轻量告警

- `workflow.py continue_material_generation` 末尾,若 `run_status=running` 但 `status=success`,打 warning log 提醒"demo 进程未显式停止;建议前端提示用户『停止 Demo』"。
- 完整 daemon 调度改造留 ISSUE-008 L2,本次只补可观测性。

## 约束与风险

- `enhance_project` 返回 `EnhancementResult.actual_mode` 新增 `"partial"` 字面值,前端 `HomePage.vue`、合规检查、测试断言需同步识别(已在前端添加 partial 状态显示,见 P1-2 后续工作)。
- `_retry_with_backoff` 抽取后,既有 `patch("app.enhancer.time.sleep")` 仍命中(helper 与调用方在同一模块)。
- 白名单放宽可能掩盖 prompt 越界,但 `UI_STEP_FORBIDDEN_SELECTORS` 仍守住 `<router-view` 等破坏壳层的代码片段。
- `.learnings/` 并发写:同一 job 多次失败重试可能产生重复条目;通过 `try/except` 与 UUID 后缀去重(本次未启用 UUID,因后端是单进程顺序写,目前不构成问题)。
- daemon SSL read timeout 后续已在 ISSUE-026 改为独立 Python subprocess 硬截止；本 ISSUE 保留 246s 现场和 retry/actual_mode 修复记录。

## 验证

### 单元测试

```bash
cd "C:\Users\whn\Documents\软著\backend"
python -m unittest tests.test_enhancer -v
```

预期:18/18 全过(9 既有 + 1 调整 + 6 新增 + 2 daemon/retry 相关既有)。

### 全链路

```bash
cd "C:\Users\whn\Documents\软著\backend"
python -m unittest discover -s tests
```

预期:全量测试通过。

### 工厂前端构建

```bash
cd "C:\Users\whn\Documents\软著\frontend"
npm.cmd run build
```

预期:exit 0,无新增 warning。

### Git diff 自检

```bash
git diff --check
```

预期:无空白字符 / 行尾警告。

## 验收标准

- 复用本 job planning 跑一次新任务,5 个 UI 子步骤 `status=completed` 数 ≥ 4。
- `codegen_actual_mode ∈ {llm, partial}`,且 `frontend/src/style.css` 含 ≥ 3 个 `AI UI Enhancer:` marker。
- `.learnings/ERRORS-YYYYMMDD-enhance.md` 含本任务失败条目(如全部成功则无)。
- 既有测试不退;新测试 6/6 通过。
- 4 份交接文档(AGENTS.md / README.md / docs/ISSUES.md / docs/FLOW.md)与本 ISSUE 同步更新。
