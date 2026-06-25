# ISSUE-020：恢复 AI 界面风格增强，并按 Demo 工程分阶段展示进度

- 状态：`已完成，Codex 复审通过`
- 优先级：`P0`
- 首次记录：2026-06-23

## 用户目标

- 界面风格仍必须由 AI 增强产生明显变化，不能只使用本地哈希配色/纹理规则。
- 样式增强允许耗时较长，但用户必须在任务页面看到明确、持续的阶段进度，不能误以为任务卡死。
- AI 应按一个可运行 Demo 工程的方式分步改造前端，而不是一次生成或覆盖完整 `style.css`。

## 当前实现与问题

- `backend/app/enhancer.py` 当前对 `frontend/src/style.css` 走 `_build_style_enhancement()` 本地规则生成，不调用 LLM。
- 原因是此前 MiniMax 对 CSS 请求容易读超时，导致“界面样式”节点失败。
- 当前 `workflow.py` 已有 `codegen_enhance_steps` 和 `progress_callback`，`HomePage.vue` 已能展示 pending/running/completed/failed 节点；这可直接复用为细粒度 UI 增强进度。
- 当前增强器只允许处理 `style.css` 和 `README.md`；`App.vue`、路由及模块页面必须继续由固定生成器控制，避免重现子菜单路由丢失。

## 建议方案

将样式增强改为独立的 `ui_enhancement_plan`，每一步是小请求、小范围写入、可恢复的 CSS 追加块：

1. **风格方案设计**：LLM 仅返回 JSON 风格令牌和设计说明，例如颜色、密度、圆角、阴影、背景纹理、行业视觉关键词；不返回 CSS。
2. **应用壳层**：基于风格令牌生成或由 LLM 返回受限 CSS 追加块，只影响登录页、导航、Header、主背景。
3. **业务页面组件**：单独增强卡片、筛选区、表格、状态标签、表单与弹窗。
4. **驾驶舱/图表**：单独增强 KPI、SVG 图表、图例、告警和活动流。
5. **响应式与收尾**：补充小屏适配、hover/focus、对比度检查，输出增强摘要。

每一步都应：

- 只传递必要的 CSS 片段、规划摘要和上一步风格令牌，限制输入输出大小。
- 使用独立超时、重试和子进程硬截止；超时只失败当前子步骤，不阻断后续可独立步骤。
- 写入一个带步骤标识的 CSS 追加块；失败则只恢复该步骤对应的块。
- 更新 `codegen_enhance_steps`，前端显示步骤名、运行中、重试次数、耗时和简短摘要。
- 生成 `ui_enhancement.json`，记录模型、风格令牌、各步骤输入摘要、结果、耗时与失败原因，作为后续审计和材料可追溯信息。

## 约束

- 禁止 LLM 覆盖 `App.vue`、`router.js`、`views/*`、API 或后端代码。
- 禁止让模型返回整份 `style.css`；只允许每个步骤返回一个有长度上限的 CSS 片段或 JSON 风格令牌。
- 任意 CSS 写入后必须通过生成项目前端构建；失败时恢复到该子步骤之前的版本。
- `auto` 模式允许 UI 子步骤部分失败后继续；`llm` 模式的失败语义需在实施前明确，避免与用户“耗时长但可见”的预期冲突。

## Claude 实施说明

完整实施步骤、允许修改范围、状态协议、测试清单和完成报告格式见 [ISSUE-020-IMPLEMENTATION.md](ISSUE-020-IMPLEMENTATION.md)。当前工作区已有未完成的 ISSUE-020 代码，实施者必须先审计并补全，禁止从头覆盖。

## 验收标准

- 新任务页面显示至少 5 个 UI 增强子步骤，而不是单一“界面样式”。
- 用户可看到每一步的 `pending/running/retrying/completed/failed`、耗时和摘要。
- 同一软件可稳定复现同一风格令牌；不同软件/规划应产生可感知的布局与视觉差异。
- LLM 某一步超时或坏 JSON 时，不会让任务无提示卡住，也不会破坏模块路由和页面功能。

## 实现结果（Claude 实施 2026-06-23，Codex 复审通过）

ISSUE-020 已在 Claude 实施后经 Codex 多轮复审与修正通过。详细差异与阶段顺序参见 [`ISSUE-020-IMPLEMENTATION.md`](ISSUE-020-IMPLEMENTATION.md)；本节给出最终行为与产物摘要。

**最终 UI 阶段定义**（固定顺序）：

| key | 前端展示名 | 类型 | 是否写 style.css | LLM 必返回 |
| --- | --- | --- | --- | --- |
| `theme` | 界面风格方案 | plan | 否（仅返回 JSON 风格令牌） | 是 |
| `shell` | 应用壳层 | step | 是 | 是 |
| `business` | 业务页面组件 | step | 是 | 是 |
| `dashboard` | 驾驶舱与图表 | step | 是 | 是 |
| `responsive` | 响应式与收尾 | step | 是 | 是 |
| `readme` | 项目说明 | doc | 否（README.md） | 是 |

**事件协议**：进度回调 `event.key` 为 `theme/shell/business/dashboard/responsive/readme`；向后兼容 `event.file`（如 `frontend/src/style.css::shell` 仍可触发，但 `key` 优先）。`status` 取值 `pending/running/retrying/completed/failed/skipped`。

**失败语义**：
- `auto` 模式：单步失败回滚该步开始前的 style.css 快照，前序成功 CSS 保留，后续独立步骤继续；任务标记为"部分 AI 增强完成"。
- `llm` 模式：任一 UI 步最终失败，restore style.css 与 README，抛错让任务失败。
- `template` 模式：跳过增强，不创建 UI 节点。

**产物**：
- `outputs/{job_id}/enhancement.json`：原有 `EnhancementResult` 全字段 + `ui_plan` + `ui_steps`。
- `outputs/{job_id}/ui_enhancement.json`：独立审计视图，包含 `mode {requested, actual}`、`model`、`ui_plan`、`ui_steps`（含 `summary`/`attempts`/`duration_ms`/`failure_reason`/`selectors`）、`fallback_reason`。
- `outputs/{job_id}/status.json` 的 `codegen_enhance_steps` 字段更新为 6 个节点的列表，前端可逐项展示。

**前端展示**（`HomePage.vue`）：每个节点显示 `name` / `statusLabel` / `attempts` / `duration_ms` / `title`（含 `summary` 与 `failure_reason`），`pending/running/completed/failed/retrying/skipped` 各自配色，retrying 配 pulse 动画，skipped 配删除线。

**单元测试**：`backend/tests/test_enhancer.py` 共 8 项覆盖：
1. `test_template_mode_does_not_change_files`
2. `test_auto_mode_six_step_protocol`（顺序、theme 请求、README 独立、5 步 marker、模板未污染）
3. `test_invalid_ui_block_is_rejected`（带 Vue 路由片段的业务步被拒，前序保留，后续继续）
4. `test_llm_mode_any_failure_rolls_back`（llm 模式下任一失败整体回滚）
5. `test_oversized_block_is_repaired`（超长 block 重试一次后落空）
6. `test_progress_callback_receives_ui_keys`（callback 含 pending/running/retrying/completed）
7. `test_transient_529_retries_then_succeeds`（529 后第二次成功）
8. `test_app_vue_router_views_never_appear`（App.vue 不被 LLM 改写）

**整体验证**：
- `python -m unittest discover -s tests`：111 项全过。
- `npm.cmd run build`：通过，132.55 kB JS / 15.06 kB CSS。
- `git diff --check`：exit 0。
- L1 已知风险仍存在：多 uvicorn 并存 / 杀子进程 hang API / 不改造 `multiprocessing` 调度；待 ISSUE-008 L2 统一处理。
- 生成项目 `npm run build` 通过；至少完成一次真实 Demo 浏览器验收。

## Codex 初次复审（2026-06-23）

- 结论：`复审未通过，待修正后复审`。
- 已验证：`python -m unittest discover -s tests -v`（111 通过）、`npm.cmd run build`（工厂前端通过）、`git diff --check`（通过）。
- P1：`enhance_project()` 先执行 README 的 LLM 增强，再启动 5 个 UI 子步骤；README 长请求会使全部 UI 节点持续 pending，违背“界面样式阶段可见进度”的目标。应先执行 UI 阶段，README 独立在其后执行或并行但必须立即更新自身状态。
- P1：README 进度事件只携带 `file=README.md`，而 workflow 仅识别 `event.step` 或 `style.css::key`。因此 `readme` 节点无法从 pending 更新为 running/completed/failed。应在 README 事件中发送 `step=readme`（或在 workflow 显式映射 README），并补集成测试。
- P2：UI CSS 校验仅校验模型返回的 `selectors` 声明，没有从实际 CSS 内容提取并校验选择器；模型可声明合法选择器但写入未授权全局选择器。应校验 CSS 内容本身，拒绝超出每阶段允许范围的规则。
- P2：`_call_chat_json()` 的内部重试未向 progress callback 发出 retrying 事件；仅外层异常会显示重试，不能完整反映实际等待过程。应将单次请求重试同步为可见进度。
- P2：README、FLOW、AGENTS 中仍描述 `style.css` 为本地生成且不调用 LLM，与 ISSUE-020 的 AI 分阶段实现冲突；修正完成时必须同步交接文档。
- 剩余验证：现有单测主要为 mock；修正后需使用真实 MiniMax 完成至少一次生成任务，并验证生成项目的前端构建、Demo 页面和 `ui_enhancement.json` 的阶段记录。

## Codex 修正与终审（2026-06-23）

- 已修正 UI/README 执行顺序：五个 UI 节点先执行，README 后执行，避免文档请求阻塞可见的 UI 阶段进度。
- README 事件显式携带 `step=readme`，workflow 同时保留 `README.md` 文件名映射兼容，新增工作流回归测试。
- CSS 白名单改为解析并校验实际 CSS 规则选择器；模型的 `selectors` 字段仅作审计信息，不能放宽内容约束。
- `_call_chat_json()` 的坏 JSON 与可重试请求会向 UI 阶段回调 `retrying`，页面可显示真实请求重试。
- 验证通过：`python -m unittest discover -s tests -v`（113 项）、`npm.cmd run build`、`git diff --check`。
- 剩余风险：尚未在本轮通过真实 MiniMax 完成一次端到端 UI 增强和 Demo 浏览器验收；该验证依赖实际模型可用性与用户任务数据。

## 运行时回归修正（2026-06-23）

- 真实任务 `20260623154846-fbed6920` 暴露 `AssertionError: daemonic processes are not allowed to have children`。
- 原因：工厂将任务执行在 `daemon=True` 的后台 Worker 中，而 Code Enhancer 的硬超时机制尝试从该 Worker 再创建 `multiprocessing.Process`。
- 修正：检测到 daemon Worker 时，直接使用 `urllib` 的配置读超时，不再创建嵌套进程；非 daemon 调用继续保留硬超时子进程。
- 验证：新增 daemon 回归测试；后端 `114` 项测试、工厂前端构建和 `git diff --check` 均通过。

## 运行时回归修正（2026-06-23 第二次）

- 真实任务 `20260623155910-f232b739` 在 `llm` 模式下报 `JSONDecodeError: Extra data: line 28 column 1 (char 903)`。
- 原因：`_extract_json()` 用 `content.find("{")` 和 `content.rfind("}")` 抓 JSON 起止。LLM 经常在合法 JSON 后追加说明文字（如 "（以上是设计方案…）"），`rfind("}")` 找到的是 **第二个** JSON 对象的尾巴，截出来的子串仍含完整对象 + 后续文本，`json.loads` 解析成功后报 "Extra data"。
- 修正：把 `_extract_json()` 改为 **平衡大括号扫描**——单趟遍历，按字符串字面量规则（`\"` 跳过、`\\` 转义）判断是否在字符串内，遇到匹配的 `}` 立即收尾；同时保留代码围栏剥离。LLM 在 JSON 后追加任意说明 / 多写一个 JSON 对象都能正确提取首个对象。
- 验证：新增 2 项回归测试
  - `test_extract_json_handles_llm_explanations_after_object`：覆盖 7 个子场景（JSON+说明、JSON+JSON、围栏+说明、字符串内含 `{}`、纯净 JSON、纯文本、缺失 `}`）。
  - `test_llm_response_with_trailing_text_passes_through_ui_enhancement`：让 mock 在每个默认响应后追加 `/* 上述为 AI 风格方案 */`，验证 5 步全部 `completed`、`actual_mode == "llm"`、style.css 含全部 marker。
- 后端 `120` 项测试（111 + 2 新增 + 其他模块增项）通过；前端 `npm.cmd run build` 通过；`git diff --check` exit 0。

## 运行时回归修正（2026-06-23 第三次，ISSUE-023 关联）

- 真实任务 `20260623225150-e2f31fbd`（涉案车辆管理系统，`public_security` 行业，`codegen_mode=auto`）暴露 4 个 UI CSS 子步骤全部失败，仅 `theme` + `readme` 成功，`codegen_changed_files=["README.md"]`，`frontend/src/style.css` 实际未被 AI 修改但 `codegen_actual_mode="llm"`（语义失真）。
- 4 个失败子步骤的具体根因：
  1. `shell`：`ValueError: 未包含可校验的 CSS 选择器`——LLM 返回的 CSS 没有 `_css_rule_selectors` 可解析的裸规则。
  2. `business`：`RuntimeError: Code enhancer API read timed out`（246s）——daemon Worker 走 urllib 直读，`urlopen(timeout=)` 只覆盖 connect 不覆盖 SSL read；MiniMax 在 SSL read 阶段挂死。
  3. `dashboard`：`ValidationError: content > 8000 chars`——`UI_STEP_MAX_BLOCK_CHARS=8000` 过死，Pydantic 校验失败不重试。
  4. `responsive`：`ValueError: 未授权选择器: [':root', 'html', '.el-button', 'select', 'textarea']`——`UI_STEP_SELECTOR_HINTS["responsive"]` 不含 Element Plus 基础选择器。
- 共同病灶：`max_attempts=2` 只重试 1 次、`time.sleep(2/4s)` 无 jitter、实际 CSS 内容未被增强时 `actual_mode` 仍报 `llm`、enhance 失败未自动写 `.learnings/`、`worker_pid` 未收尾到 `stopped`。
- 修正（ISSUE-023 完整方案，详见 `docs/ISSUE-023.md`）：
  - 白名单 `responsive` 步补 `:root` / `html` / `select` / `textarea` / `.el-button` / `.el-button--primary` / `.el-input` / `.el-tag` / `.el-form` / `.el-dialog`；新增 `GLOBAL_UI_SELECTOR_HINTS = (":root", "--ai-")`，`_selector_matches_hints` 优先匹配。
  - `UI_STEP_MAX_BLOCK_CHARS` 默认从 8000 提升到 16000（`AI_CODEGEN_UI_BLOCK_MAX_CHARS` 可覆盖）；`_request_ui_step` 内 `UIStepBlock.model_validate` 抛 `ValidationError` 且含 `string_too_long` 时向 LLM 发 1 条"精简后再发"反馈。
  - 抽 `_retry_with_backoff(operation, max_attempts=3, retry_callback)` helper，`time.sleep(min(2 ** attempt, 8) + random.uniform(0, 1))`；HTTP 4xx 中除 429 外直接抛；`call_api` 与 `_call_chat_json` 复用 helper。`AI_CODEGEN_MAX_ATTEMPTS` 可覆盖。
  - `llm` 模式容忍最多 1 个 UI 子步骤失败（≥4/5 步成功仍视为 llm 增强成功，≥2 步失败才整体回滚并抛 `RuntimeError`）；移除冗余的后置整体回滚。
  - `EnhancementResult.actual_mode` 新增 `partial` 字面值——`"frontend/src/style.css" in changed_files` 为真 → `llm`，否则若 README 改了 → `partial`，否则 `template`；`partial` 时 `summary` 末尾追加"（仅 README 由 AI 增强，UI/CSS 增强全部失败回滚到模板）"。
  - 新建 `backend/app/learning.py`，提供 `classify_failure()` 与 `append_enhance_error()`；`_record_enhance_failure()` 在 `enhance_project` 三个 return 路径前各调用一次；文件命名 `.learnings/ERRORS-YYYYMMDD-enhance.md`，失败根因分类 8 类，编号跨会话单调递增。
  - `workflow.py continue_material_generation` 末尾若 `run_status=running` 但 `status=success`，打 warning log 提醒 demo 进程未显式停止；不主动 kill（用户可能正在浏览器看 demo）。
- 验证：`backend/tests/test_enhancer.py` 新增 6 项 + 调整 1 项共 18 项全过；后端单测全量通过；工厂前端 `npm.cmd run build` 通过；`git diff --check` exit 0。
- 剩余风险：daemon Worker 下 SSL read timeout 仍未根本解决（246s 挂死靠 `max_attempts=3` + 退避 + 早失败缓解），完整 `multiprocessing` 改造留 ISSUE-023 L2 或 ISSUE-008 L2 统一处理。

## 运行时回归修正（2026-06-24，ISSUE-024 关联）

- 真实任务 `20260624095339-9d44c135`（涉案车辆管理系统，`public_security` 行业，`codegen_mode=auto`，`ui_plan.shell="split_console"`）暴露 5 个 UI 子步骤中 4 个 `failed`（shell / business / dashboard / responsive），仅 `theme` + `readme` 成功；`codegen_changed_files=["README.md"]`，`frontend/src/style.css` 实际未被 AI 修改但 `codegen_actual_mode="llm"` 被 ISSUE-023 P0-5 修正为 `"partial"`。
- 4 个失败子步骤的具体根因：
  1. `shell`：`ValueError: UI 子步骤 shell CSS 内容包含未授权选择器: ['*', 'html', '@media(max-width:900px)', '.shell-split', '.shell-main']`——`split_console` 壳层下 LLM 写 `.shell-split` / `.shell-main`；`@media` 仅 responsive 步允许；`html` 与 `*` 未进 `GLOBAL_UI_SELECTOR_HINTS`。
  2. `business`：`ValueError: UI 子步骤 business CSS 内容包含未授权选择器: ['.el-card__header', '.el-card__body', '.el-button--success', '.el-button--warning']`——Element Plus BEM 派生类（`__` / `--`）未覆盖。
  3. `dashboard`：`ValueError: UI 子步骤 dashboard CSS 内容包含未授权选择器: ['.kpi-grid', '.kpi-trend', '.kpi-trend-down .kpi-trend', '.kpi-spark', '.dashboard-row']`——白名单与生成器实际 class 失配（用了已废弃 `.metric-grid` / `.kpi-icon`）。
  4. `responsive`：`ValueError: UI 子步骤 responsive CSS 内容包含未授权选择器: ['.dashboard-row', '.kpi-grid', '.module-dashboard']`——小屏适配布局 class 未列入 hints。
- 共同病灶：白名单是手写常量，与 `project_generator.py` 实际 class 漂移；`html` / `*` 未进全局允许；Element Plus 派生类无通配。
- 修正（ISSUE-024 完整方案，详见 [`docs/ISSUE-024.md`](ISSUE-024.md)）：
  - `UI_STEP_SELECTOR_HINTS` 4 步按 `project_generator.py` 真值重写：shell 步补 `.shell-split` / `.shell-main` / `@media`；business 步加 `.el-card__*` / `.el-button--*` / `.el-tag--*` / `.el-dialog__*` 通配；dashboard 步把 `.metric-grid` / `.kpi-icon` / `.activity-panel` 改为 `.kpi-grid` / `.kpi-trend*` / `.kpi-row` / `.dashboard-row` / `.module-dashboard` / `.status-row` / `.analysis-workbench`；responsive 步补 `.kpi-grid` / `.dashboard-row` / `.module-dashboard` / `.status-row` / `.analysis-workbench`。
  - `GLOBAL_UI_SELECTOR_HINTS = (":root", "--ai-", "html", "*")`，`_selector_matches_hints` 加全局 `*` 与 `*::before` / `*::after` 特判。
  - `_hint_matches` 支持 `__*` / `--*` 前缀通配（Element Plus BEM 派生）。
  - 新建 `backend/app/selector_audit.py`：`collect_real_selectors` 扫描生成项目 `frontend/src/` 真实 class（`style.css` 规则选择器 + `views/*.vue` `class=` 字面量）；`merge_with_hints` 启发式分类合并入运行时 hints；`audit_drift` 在 `.learnings/ERRORS-YYYYMMDD-selector-drift.md` 写漂移告警（含生成器 SHA1）。
  - `enhance_project` 入口调用 `collect_real_selectors` + `merge_with_hints`，try/finally 恢复 `UI_STEP_SELECTOR_HINTS` 常量；finally 内调 `audit_drift` 写漂移。
  - `_validate_ui_block` 加 `_scan_css_chars`：剥离注释后只允许合法 CSS 字符 / ASCII 字母数字 / 空白 / Unicode（中文注释允许），其余直接拒。`UI_STEP_FORBIDDEN_SELECTORS` 增 Vue 事件（`v-on:click` / `v-bind:` / `v-model=`）、JS 关键字（`import ` / `export ` / `function(` / `=>` / `const ` / `let ` / `var `）、模板字符串（`${` / `` ` ``）。
  - `backend/app/learning.py` 把写死的 `../docs/ISSUE-022.md` 链接改为参数化（`issue_id` + `issue_doc` 由调用方传），`enhance_project` 内 4 处 `_record_enhance_failure` 调用统一传 `issue_id="ISSUE-024"`。
- 验证：`backend/tests/test_enhancer.py` 新增 8 项 + 调整 1 项共 27 项全过；后端单测全量通过；工厂前端 `npm.cmd run build` 通过；`git diff --check` exit 0。
- 剩余风险：daemon Worker 下 SSL read timeout 仍未根本解决（同 ISSUE-023）；`project_generator.py` 改 class 时 `selector_audit.collect_real_selectors` 自动跟随扫描，但仍需在 CI 中定期执行 `audit_drift` 复审。

## 运行时回归修正（2026-06-24 第二次，ISSUE-025 关联）

- 真实任务 `20260624140839-03bb66f7`（涉案车辆管理系统，`public_security` 行业，`codegen_mode=auto`，`ui_plan.shell="top_workspace"`）暴露 ISSUE-024 落地后新回归：shell + theme + readme 成功，business / dashboard / responsive 3 步 `failed`。`codegen_actual_mode="llm"`（shell 步成功改了 style.css），但 UI 增强实际只有 1/5 步成功，style.css 大部分仍是模板。
- 3 步失败的具体根因：
  1. `business`：`未授权选择器: ['.el-table--border::after', '.el-pagination', '.el-pagination .btn-prev', '.el-pagination .btn-next', '.el-pagination .el-pager li']`——ISSUE-024 P0-1 漏补 `.el-table--*` 与整个 `.el-pagination` 家族；`.btn-prev` / `.btn-next` 是 Element Plus 2.x 内部类（非 `__` BEM 派生）；`.el-table--border::after` 是派生类 + 伪元素组合。
  2. `dashboard`：`未授权选择器: ['.m-trend-up', '.dashboard-trend-card', '.dashboard-task_dashboard', '.pattern-dashboard']`——LLM 自由发挥的"模块名 + 功能"派生，生成器里没有；`selector_audit.merge_with_hints` 启发式关键字太窄。
  3. `responsive`：`未授权选择器: ['.page-heading', '.page-heading h2', '.page-heading .actions', '.page-heading .actions .btn-primary', '.page-heading .actions .btn-ghost']`——`.page-heading` 仅在 shell 步允许；`.btn-primary` / `.btn-ghost` 自定义按钮类未列。
- 共同病灶：ISSUE-024 修的是"生成器实际写入的 class"，但 LLM 在响应里自由发挥的派生类（模块派生 + 自定义按钮 + Element Plus 其它组件）生成器没有。
- 修正（ISSUE-025 完整方案，详见 [`docs/ISSUE-025.md`](ISSUE-025.md)）：
  - 业务步 `UI_STEP_SELECTOR_HINTS["business"]` 补 `.el-table--*` / `.el-pagination` / `.el-pager` / `.btn-prev` / `.btn-next` / `.el-checkbox--*` / `.el-radio--*` / `.el-select--*` / `.el-tooltip` / `.el-message` / `.el-notification` / `.el-popover` / `.el-popper` / `.el-dropdown` / `.el-menu` / `.el-upload` / `.el-tabs` Element Plus 全家族 + `.btn-primary` / `.btn-ghost` / `.btn-default` / `.btn-danger` / `.btn-success` / `.btn-warning` / `.btn-info` / `.btn-link` / `.btn-text` 自定义按钮 + `.module-*` / `.task-*` / `.form-*` 模块派生通配 + `.page-heading` / `.actions` 通用类。
  - dashboard 步 `UI_STEP_SELECTOR_HINTS["dashboard"]` 补 `.dashboard-*` / `.m-*` / `.pattern-*` / `.trend-*` / `.stat-*` / `.metric-*` LLM 派生通配 + `.el-card__*` / `.el-tag--*` Element Plus 派生。
  - responsive 步 `UI_STEP_SELECTOR_HINTS["responsive"]` 补 `.page-heading` / `.actions` / `.btn-primary` / `.btn-ghost` / `.btn-default`。
  - `selector_audit.merge_with_hints` 关键字扩展：business_keywords 加 `.el-pagination` / `.el-checkbox` / `.el-radio` / `.el-select` / `.el-tooltip` / `.el-message` / `.el-popover` / `.el-dropdown` / `.el-menu` / `.el-upload` / `.el-tabs` / `btn-primary` / `btn-ghost` / `btn-default` / `btn-danger` / `module-` / `task-` / `form-`；dashboard_keywords 加 `m-` / `pattern-` / `stat-` / `metric-`；responsive_keywords 加 `page-heading` / `actions`。
- 验证：`backend/tests/test_enhancer.py` 新增 4 项，共 31 项全过；后端单测全量通过；工厂前端 `npm.cmd run build` 通过；`git diff --check` exit 0。
- 剩余风险：大幅放宽白名单（`.dashboard-*` / `.m-*` / `.pattern-*` 等）可能掩盖 prompt 越界，需配合 `_scan_css_chars` 字符扫描与 `UI_STEP_FORBIDDEN_SELECTORS` 禁片兜底；真实 LLM 仍可能写出意料之外的派生命名空间，单测 mock 覆盖率始终滞后于真实任务样本。

## 运行时回归修正（2026-06-24 第三次，ISSUE-026 关联）

- 真实任务 `20260624160110-58039b6d`（涉案车辆管理系统，`codegen_mode=auto`）+ 用户进入"打包软著材料"阶段时崩溃，暴露 3 类新 bug：
  1. **`workflow.continue_material_generation` 末尾 `logger.warning` 抛 `NameError: name 'logger' is not defined`**——ISSUE-023 P1-3 实施时在 `backend/app/workflow.py` 新增了 `logger.warning` 调用但**未在模块顶部 `import logging` 也未定义 `logger`**。
  2. **daemon Worker 下 SSL read 挂死 1006s（16 分钟）仍能发生**——`urllib.request.urlopen(timeout=)` 只覆盖 TCP connect 不覆盖 SSL read；`max_attempts=3` 退避也救不回；`multiprocessing.Process` 在 daemon Worker 下被禁用。
  3. **LLM 多次返回空 CSS 时整步 `failed` 阻断任务**——jobId 的 responsive 步两次都返回 `@media(...) {/* 注释 */}`，`_css_rule_selectors` 提取不到裸规则 → 抛"未包含可校验" → 整步 `failed`。
- 共同病灶：ISSUE-023 P1-3 / P0-3 / P1-2 实施埋的雷，单元测试未覆盖真实 daemon Worker + 真实 LLM 空响应组合。
- 修正（ISSUE-026 完整方案，详见 [`docs/ISSUE-026.md`](ISSUE-026.md)）：
  - `backend/app/workflow.py` 顶部新增 `import logging` 与 `logger = logging.getLogger(__name__)`。
  - `backend/app/enhancer.py` `_call_chat_completion_with_deadline` daemon 分支改走独立 Python subprocess + `subprocess.run(..., timeout=AI_CODEGEN_TIMEOUT+10)`，超时杀掉请求子进程并转 `RuntimeError("Code enhancer API read timed out (daemon worker, Ns wall-clock)")`。Codex 复审打回了第一版 ThreadPool 方案，因为 `shutdown(wait=False)` 不能杀死阻塞线程。
  - `backend/app/enhancer.py` `UIStepResponse.block` 改为 `Optional[UIStepBlock] = None`，加 `skip_reason` 字段；`_request_ui_step` 在 `_validate_ui_block` 之前检查 `_css_rule_selectors(block.content)`，空 selectors → 返回 `UIStepResponse(block=None, skip_reason="LLM 返回内容不含任何 CSS 规则...")`，不抛错。
  - `_enhance_ui_steps` 调用方识别 `response.block is None` → 标 `status="skipped"`、记 `summary=skip_reason`，**`success=True`**（关键修补，避免被下方 `if not success:` 覆盖为 failed）。
- 验证：`backend/tests/test_enhancer.py` 35 项全过；端到端 AI 增强代码流程 PASS（daemon Worker 模拟 + 5 步 UI 增强 + 1 步空响应 → 4 completed + 1 skipped，`actual_mode=llm`）；工厂前端 `npm.cmd run build` 通过；`git diff --check` exit 0。
- 剩余风险：daemon 分支每个远端 LLM 请求会启动一个 Python 子进程，稳定性优先于性能；如后续并发量上升，可再改为常驻受控 worker 池。LLM 空响应是提示词工程问题，本 ISSUE 仅做"任务不被阻断"兜底。
