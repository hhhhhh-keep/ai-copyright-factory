# AI软著工厂当前流程

> ISSUE-020 当前实现覆盖说明：Code Enhancer 先执行五个 AI UI 子步骤 `theme`、`shell`、`business`、`dashboard`、`responsive`，再执行独立 README 文档增强。每一步仅向 `style.css` 追加经过实际选择器白名单校验的 CSS，并独立记录 pending/running/retrying/completed/failed、请求次数、耗时和失败原因。LLM 不得修改路由、Vue 页面、API 或后端代码。
>
> **ISSUE-026（2026-06-24 落地）增量**（本说明优先于下文 ISSUE-025 / ISSUE-024 / ISSUE-023 / ISSUE-019）：
> - `backend/app/workflow.py` 补模块级 `import logging` 与 `logger = logging.getLogger(__name__)`，修复 `continue_material_generation` 末尾 `logger.warning` 触发的 `NameError`；
> - daemon Worker 下 `_call_chat_completion_with_deadline` 改走独立 Python subprocess，并由 `subprocess.run(..., timeout=AI_CODEGEN_TIMEOUT+10)` 做硬截止，超时会杀掉请求子进程，避免 ThreadPool 后台线程泄漏；
> - `_request_ui_step` 在 LLM 多次返回空 CSS 时返回 `UIStepResponse(block=None, skip_reason=...)`，调用方标 `status="skipped"` 且 `success=True`，让响应式步空响应不再阻断任务。
> - 源代码材料不再使用固定 50 行硬分页；`generate_source_document()` 只按视觉行宽拆行，分页交给 Word/WPS。
>
> **ISSUE-025（2026-06-24 落地）增量**：
> - 业务步补 Element Plus 全家族：`.el-pagination` / `.el-pager` / `.btn-prev` / `.btn-next` / `.el-checkbox--*` / `.el-radio--*` / `.el-select--*` / `.el-tooltip` / `.el-message` / `.el-notification` / `.el-popover` / `.el-popper` / `.el-dropdown` / `.el-menu` / `.el-upload` / `.el-tabs` 与各自派生；
> - 业务步补自定义按钮 `.btn-primary` / `.btn-ghost` / `.btn-default` / `.btn-danger` / `.btn-success` / `.btn-warning` / `.btn-info` / `.btn-link` / `.btn-text`；
> - 业务步补模块派生通配 `.module-*` / `.task-*` / `.form-*`；
> - dashboard 步补 LLM 派生通配 `.dashboard-*` / `.m-*` / `.pattern-*` / `.trend-*` / `.stat-*` / `.metric-*`；
> - responsive 步补 `.page-heading` / `.actions` / `.btn-*`；
> - `selector_audit.merge_with_hints` 关键字扩展覆盖以上模式。
>
> **ISSUE-024（2026-06-24 落地）增量**：
> - 白名单按生成器实际渲染 class 重写：`shell` 步补 `.shell-split` / `.shell-main` / `@media`（`split_console` 壳层 + 响应式断点）；`business` 步加 `.el-card__*` / `.el-button--*` / `.el-tag--*` / `.el-dialog__*` Element Plus BEM 派生通配；`dashboard` 步把已废弃的 `.metric-grid` / `.kpi-icon` 改为 `.kpi-grid` / `.kpi-trend*` / `.kpi-row` / `.dashboard-row`；`responsive` 步补 `.kpi-grid` / `.dashboard-row` / `.module-dashboard` / `.status-row` / `.analysis-workbench`；
> - `GLOBAL_UI_SELECTOR_HINTS = (":root", "--ai-", "html", "*")`，含 `*::before` / `*::after` 特判，任何步可写全局基础样式；
> - `_selector_matches_hints` 支持 `__*` / `--*` 通配与全局 `*` 重置特判；
> - 新建 `backend/app/selector_audit.py`：扫描生成项目 `frontend/src/` 真实 class（`style.css` 规则选择器 + `views/*.vue` `class=` 字面量），启发式分类合并入运行时 hints；`enhance_project` try/finally 恢复常量；漂移审计写 `.learnings/ERRORS-YYYYMMDD-selector-drift.md`；
> - `_validate_ui_block` 加 `_scan_css_chars` 字符集合扫描兜底越界（剥离注释后只允许合法 CSS 字符、ASCII 字母数字、空白与 Unicode）；
> - `backend/app/learning.py` 修复建议链接改为参数化（`issue_id` / `issue_doc` 由调用方传），不再硬编码 `ISSUE-022.md`。
>
> **ISSUE-023（2026-06-24 落地）增量**：
> - `max_attempts=3` + 指数退避 + jitter（`_retry_with_backoff` helper，`AI_CODEGEN_MAX_ATTEMPTS` 可覆盖）；
> - `UI_STEP_MAX_BLOCK_CHARS=16000`（`AI_CODEGEN_UI_BLOCK_MAX_CHARS` 可覆盖），超长时反馈模型精简后重试 1 次；
> - 白名单 `responsive` 步补 `:root` / `html` / `select` / `textarea` / `.el-button` 等 Element Plus 基础选择器；`GLOBAL_UI_SELECTOR_HINTS = (":root", "--ai-")` 全局允许 CSS 变量声明；
> - `llm` 模式容忍最多 1 个 UI 子步骤失败（≥4/5 步成功仍视为 llm 增强成功，≥2 步失败才整体回滚并抛 `RuntimeError`）；
> - `EnhancementResult.actual_mode` 新增 `partial` 字面值：style.css 未改但 README 改了 → `partial`；style.css 改了 → `llm`；都未改 → `template`；
> - enhance 阶段失败自动写 `.learnings/ERRORS-YYYYMMDD-enhance.md`（`backend/app/learning.py`）；
> - `workflow.py` 在 `status=success` 但 `run_status=running` 时打 warning log。

> 适用版本：2026-06-15 当前工作区。
> 本文描述实际代码逻辑，不是最初 ROADMAP。

> 研发协作门禁见 [HARNESS.md](HARNESS.md)。它不属于运行时流程，但所有状态机、生成器和 Demo 链路的改动都应按其验证与交接要求执行。

## 1. 系统组成

```text
Vue 3 SPA :5173
├─ HomePage：创建任务、进度、Demo 审查、返工和下载
├─ PlanningReviewPage：规划审核和 UI 结构编辑
└─ HistoryPage：历史任务、Demo、下载和删除
          │
          ▼
FastAPI :8000
├─ main.py：HTTP API、异步任务启动和安全校验
├─ planner.py：知识库约束的规划及自然语言返工
├─ workflow.py：状态落盘、生成流水线、Demo、截图和材料
├─ project_generator.py：Spring Boot + Vue 3 确定性生成器
├─ enhancer.py：受约束的 AI Code Enhancer
├─ compliance.py：一致性与软著合规检查
└─ industry_knowledge.py：四行业知识库读取
          │
          ▼
outputs/{job_id}/
├─ status.json
├─ planning.json
├─ planning_versions/
├─ revision_proposals/
├─ generated_project/
├─ demo_runtime.json
├─ screenshots/
├─ docs/
├─ logs/
└─ copyright_package.zip
```

## 2. 创建与规划

首页提交：

```text
software_name
description
software_type
industry_type
planner_mode
codegen_mode
document_template
申请信息
```

首页不再展示行业模块勾选，也不再调用需求澄清作为用户流程。

```text
POST /api/jobs
→ create_job()
→ 后台 Process(generate_planning_draft)
→ Planner 直接调用 LLM，根据 software_name / software_type / description 生成 planning.json
→ 行业类型仅作为信息写入 planning.json，Planner 不读取行业知识库
→ 首次 JSON 或 Pydantic 校验失败时自动修复一次；二次仍失败任务进入 failed
→ status = draft_planning
→ 前端进入 /planning-review/{jobId}
```

当前 Planner 行为（ISSUE-007 实施后）：

- 只走 LLM 路径，不再读取 `industry_knowledge/*.json`，不再做行业一致性校验。
- 不再有 `auto / llm / template` 模式与模板回退。
- `build_planning()` 在解析或修复成功后，用用户原始输入强制覆盖 `software_name` / `description` / `software_type` / `industry_type` / `industry_name`，避免 LLM 篡改任务基本信息。
- 行业内部编码（`public_security` 等）通过 `planner.industry_name_for()` 转成显示名（`公安` 等）后传给 LLM；编码 → 显示名基础映射保留在 `INDUSTRY_DISPLAY_NAMES` 中。
- JSON 容错保留：自动去除代码围栏，按平衡大括号扫描候选并用 `json.loads` 验证，取首个合法 JSON 对象。
- 首次 JSON 解析或 `Planning.model_validate()` 失败时，自动把错误摘要和原响应发回模型修复一次；二次仍失败则抛错，任务停留在 `failed`。
- `propose_revision()` 同步改为 LLM-only，使用相同的 JSON 容错和一次自动修复；失败时抛错，不回退到规则改写。
- 规划阶段失败（`failed_stage == "planning"`）可通过 `POST /api/planning/regenerate` 使用原 job ID 重试，会复位 `planning` 步骤并清理旧 `planning.json` / `planning_versions` / `revision_proposals`。
- 三个失败阶段分别记入 `failed_stage`：`planning` / `project` / `materials`，前端根据该字段决定是否提供"重新生成规划"按钮。

`planning.json` 主要包含：

```text
软件信息（含行业类型作为参考记录）
modules[]
database_tables[]
api_list[]
screenshots[]
document_outline[]
ui_plan
planner 元数据
```

每个模块与数据库表保持一一对应。模块包含页面、字段和页面结构模式。

`api_list` 还会被 Project Generator 解析为模块业务动作。当前支持识别形如
`PUT /api/{module_key}/{id}/approve`、`POST /api/{module_key}/{id}/quick_audit`
的接口，并生成对应前端按钮、前端 API 函数、后端 Controller 映射和 Service 方法。

## 3. Planning Review

页面：`/planning-review/{jobId}`

用户可以：

- 新增、删除、重命名模块。
- 修改模块描述、页面和字段。
- 修改对应数据库表。
- 修改应用壳层、首页模式和信息密度。
- 修改每个模块的页面、详情和编辑模式。
- 重新生成规划。
- 保存并确认规划。

确认时：

```text
PUT /api/planning/{jobId}
POST /api/jobs/{jobId}/confirm
→ 首次规划保存为 planning_versions/v1.json
→ status = confirmed
→ 后台 Process(run_job)
```

确认后的 `planning.json` 是代码、截图和文档的单一可信源。

## 4. 项目生成与 Demo 审查

`run_job()` 只执行到 Demo：

```text
project
→ enhance
→ run
→ demo
→ status = awaiting_demo_review
```

各步骤：

1. `project`：生成 Spring Boot、Vue 3、SQL 和第三方声明。
   - 通用 CRUD 默认生成。
   - `planning.api_list` 中的模块业务动作会增量生成，例如审核通过、驳回、快速审核、转交、退回补充。
2. `enhance`：按代码生成模式执行受约束 AI 增强。
   - `template` 模式不调用 Code Enhancer，页面显示“代码增强未启用”。
   - `auto` / `llm` 模式先执行 `theme`、`shell`、`business`、`dashboard`、`responsive` 五个 UI 阶段，再执行 `README.md` 文档阶段。
   - `App.vue`、`router.js` 和 `views/*` 归固定生成器所有，Code Enhancer 不允许覆盖，避免破坏路由壳层和子菜单页面功能。
   - 每个 UI 阶段通过 LLM 生成受阶段白名单约束的 CSS 追加块，独立请求、子进程硬超时、重试与按步回滚；实际 CSS 内容而非模型声明的 selector 列表决定是否允许写入。
   - **ISSUE-023**：白名单 `responsive` 步补 `:root` / `html` / `select` / `textarea` / `.el-button` 等 Element Plus 基础选择器；`GLOBAL_UI_SELECTOR_HINTS = (":root", "--ai-")` 全局允许 CSS 变量声明。`UI_STEP_MAX_BLOCK_CHARS` 默认 16000（`AI_CODEGEN_UI_BLOCK_MAX_CHARS` 可覆盖），超长时反馈模型精简后重试 1 次。
   - **ISSUE-023**：HTTP / 连接 / 读超时统一走 `_retry_with_backoff` helper，`max_attempts=3`（`AI_CODEGEN_MAX_ATTEMPTS` 可覆盖），`time.sleep(min(2 ** attempt, 8) + random.uniform(0, 1))` 指数退避 + jitter；HTTP 4xx 中除 429 外直接抛。daemon Worker 下 SSL read timeout 暂不改造（避免动 `multiprocessing`）。
   - **ISSUE-024**：白名单按生成器实际渲染 class 重写（`project_generator.py` 真值来源）。`shell` 步补 `.shell-split` / `.shell-main` / `@media`（`split_console` 壳层 + 响应式断点）；`business` 步加 `.el-card__*` / `.el-button--*` / `.el-tag--*` / `.el-dialog__*` Element Plus BEM 派生通配；`dashboard` 步把已废弃的 `.metric-grid` / `.kpi-icon` / `.activity-panel` 改为 `.kpi-grid` / `.kpi-trend*` / `.kpi-row` / `.dashboard-row` / `.module-dashboard` / `.status-row` / `.analysis-workbench`；`responsive` 步补 `.kpi-grid` / `.dashboard-row` / `.module-dashboard` / `.status-row` / `.analysis-workbench`。`GLOBAL_UI_SELECTOR_HINTS` 加 `html` 与 `*`（含 `*::before` / `*::after` 特判）。
   - **ISSUE-024**：新建 `backend/app/selector_audit.py` 在 `enhance_project` 入口扫描生成项目 `frontend/src/` 真实 class，启发式分类合并入运行时 hints，try/finally 恢复常量；漂移审计写 `.learnings/ERRORS-YYYYMMDD-selector-drift.md`。
   - **ISSUE-024**：放宽白名单同时，`_validate_ui_block` 加 `_scan_css_chars` 字符集合扫描兜底越界（剥离注释后只允许合法 CSS 字符、ASCII 字母数字、空白与 Unicode）。
   - **ISSUE-024**：`backend/app/learning.py` 修复建议链接改为参数化（`issue_id` / `issue_doc` 由调用方传），不再硬编码 `ISSUE-022.md`。
   - README 文档增强在 UI 阶段后独立执行，并使用 `readme` 进度节点；它同样走子进程硬超时和重试。
   - 每轮只允许模型返回当前目标文件，避免一次返回多个完整文件导致超时。
   - `auto` 模式下按文件隔离失败：单个文件增强失败会恢复该文件并继续后续文件；如果全部文件均失败，则回退稳定模板继续后续验证。
   - **ISSUE-023**：`llm` 模式容忍最多 1 个 UI 子步骤失败（≥4/5 步成功仍视为 llm 增强成功，≥2 步失败才整体回滚并抛 `RuntimeError`）；README 失败同样不阻断任务。
   - **ISSUE-023**：`EnhancementResult.actual_mode` 新增 `partial` 字面值——`"frontend/src/style.css" in changed_files` 为真 → `llm`；否则若 README 改了 → `partial`；否则 `template`。`partial` 时 `summary` 末尾追加"（仅 README 由 AI 增强，UI/CSS 增强全部失败回滚到模板）"。
   - **ISSUE-023**：enhance 阶段出现失败步时，`_record_enhance_failure()` 通过 `backend/app/learning.py` 的 `append_enhance_error()` 自动写 `.learnings/ERRORS-YYYYMMDD-enhance.md`，根因分类 8 类（empty_selectors / whitelist_strict / size_exceeded / daemon_ssl_read_timeout / missing_credentials / api_http_error / other / unknown）。
   - 模型返回坏 JSON 时会自动修复一次；HTTP 429/500/502/503/504/529、连接错误和读超时会自动重试，避免外部模型短时抖动直接刷屏。
   - 任务状态写入 `codegen_actual_mode`、`codegen_summary`、`codegen_fallback_reason` 和 `codegen_enhance_steps`；前端按这些字段展示增强成功、未启用或失败回退，以及逐文件节点。
3. `run`：执行前端安装/构建、项目结构检查和 Maven 测试。
4. `demo`：构建 JAR，启动 Spring Boot 和 Vite，写入 Demo 地址。

此时流水线暂停。不会自动截图、生成文档或打包。

Demo 运行状态位于 `demo_runtime.json`：

```text
queued → building → starting → running
                         └──→ failed
running → stopped
```

Demo 默认一小时超时回收。任务详情可查看 Demo、Swagger、前后端日志和启动错误。

## 5. 审查通过

```text
POST /api/jobs/{jobId}/review/approve
→ status = generating_materials
→ 后台 Process(continue_material_generation)
```

材料流水线：

```text
screenshot
→ analyze
→ source
→ docs
→ compliance
→ package
→ status = success
```

产物包括：

- 登录页、首页，以及每个确认模块的功能页和新增/编辑表单截图；截图清单写入 `screenshot_manifest.json`。
- 真实代码统计。
- 源代码材料：只选取可读的业务源码，排除压缩样式与生成标记；使用固定行宽、等宽字体和受控分页。
- 设计说明书：系统架构、功能目标、字段/API、处理流程、真实界面截图与截图索引；标题、正文、表格、图题和页眉页脚使用统一样式。
- 用户操作手册：每个菜单功能的用途、前置条件、逐条操作说明、结果说明和真实界面截图；不用流程表替代操作文字。
- `document_narratives.json`：LLM 受证据约束生成的模块文案及校验结果；未配置模型或校验失败时记录为 template 回退。
- 软件著作权申请信息表。
- 合规检查报告。
- `generated_project.zip`。
- `copyright_package.zip`。

## 6. 自然语言返工

用户在 `awaiting_demo_review` 阶段填写修改意见：

```text
POST /api/jobs/{jobId}/revision/propose
→ planner.propose_revision()
→ 读取当前 planning.json、行业基础映射（编码→显示名）和用户意见
→ 生成完整的新规划及变更摘要
→ 写 revision_proposals/{proposal_id}.json
→ 写 revision_proposal.json
→ status = revision_review
```

大模型不可直接修改生成源码。用户先查看摘要：

- 确认：`POST /revision/confirm`
- 取消：`POST /revision/cancel`

确认返工后：

```text
新规划覆盖 planning.json
→ 保存 planning_versions/vN.json
→ 停止当前 Demo
→ 清理本轮生成项目、截图、材料和日志
→ status = regenerating_project
→ 再次执行 run_job()
→ 再次停在 awaiting_demo_review
```

返工第一版采用完整重新生成，优先保证规划、代码、数据库、截图和文档一致。

## 7. 规划版本恢复

```text
GET  /api/jobs/{jobId}/revisions
POST /api/jobs/{jobId}/revisions/{version}/restore
```

可在以下状态恢复历史规划：

- `awaiting_demo_review`
- `revision_review`
- `failed`

恢复会创建新的规划版本记录，并完整重新生成项目。

## 8. 历史任务和删除

页面：`/history`

功能：

- 查看任务进度和状态。
- 进入 `/?jobId={job_id}` 继续任务。
- 启动或停止 Demo。
- 查看 Demo 和 Swagger。
- 下载材料。
- 删除任务。

历史详情页顶部提供“返回首页”，返回时清理旧任务轮询和页面状态。

删除接口：

```text
DELETE /api/jobs/{jobId}
```

安全规则：

- job ID 必须符合 `YYYYMMDDHHMMSS-xxxxxxxx`。
- 目标目录必须是 `OUTPUT_ROOT` 的直接子目录。
- 删除前停止 Demo 并清除启动锁。
- `generating`、`confirmed`、`regenerating_project`、`generating_materials` 禁止删除。
- 删除会永久移除该任务的源码、日志、截图、文档、版本记录和 ZIP。

## 9. 主任务状态机

```text
generating
  └─ 规划完成 → draft_planning
       └─ 确认 → confirmed
            └─ 项目生成与 Demo → awaiting_demo_review
                 ├─ 审查通过 → generating_materials → success
                 └─ 提出修改 → revision_review
                      ├─ 取消 → awaiting_demo_review
                      └─ 确认 → regenerating_project
                                   └─ 重新生成 → awaiting_demo_review

任一步骤异常 → failed
```

状态与修改记录都写入任务目录，浏览器关闭或后端重启后仍可从历史任务读取。

### 9.1 ISSUE-008 L1：任务中断恢复

服务启动与运行中引入 `interrupted` 状态和 `worker.lock` 任务级锁：

- `outputs/{job_id}/worker.lock` 记录 Worker 的 PID、ppid、task 名称与启动时间。
- `generate_planning_draft` / `run_job` / `continue_material_generation` 启动时调用 `_acquire_worker_lock()`；异常或正常退出时 `finally` 释放锁。
- 服务启动 `@app.on_event("startup")` 调用 `scan_for_interrupted_jobs()`：对 `confirmed`（≥10 分钟陈旧）、`generating`（≥30 分钟）、`regenerating_project`（≥30 分钟）、`generating_materials`（≥60 分钟）或 `worker.lock` 中 PID 已死的任务，标 `status=interrupted`，记录 `interrupted_at` / `interrupted_reason`，并清理残留 Demo。
- `POST /api/jobs/{job_id}/resume`：仅 `interrupted` 状态可被恢复；按 `failed_stage` 选恢复点（`confirmed`→project；`project/enhance`→清 generated_project 重 project；`run`→run；`demo`→停残留后 demo；`generating_materials`→清材料后 materials）；启动前先释放陈旧 lock，再用 `_has_active_worker_lock()` 防双跑。
- 状态机新增：`interrupted`；`failed_stage` 在恢复成功后清空。
- 前端 `HomePage` 与 `HistoryPage` 状态为 `interrupted` 时显示"恢复任务"按钮与恢复起点信息。

L1 已知风险（用户已接受）：不解决多 uvicorn 并存 / 杀子进程 hang API / 不改造 `multiprocessing` 调度。

## 10. UI 生成体系

`ui_plan` 当前支持：

应用壳层：

- `sidebar_admin`
- `top_workspace`
- `split_console`

首页模式：

- `metric_dashboard`
- `task_dashboard`
- `analysis_dashboard`

模块页面：

- `table_crud`
- `master_detail`
- `tree_detail`
- `workflow_timeline`
- `kanban`
- `dashboard`

Planner 根据软件类型和模块语义选择结构；Planning Review 允许人工调整；Project Generator 渲染真实不同的 Vue 页面结构。

对于 `api_list` 中声明的业务动作，模块页面会在操作列生成相应按钮。生成器会避开 Java 关键字，例如 `/return` 接口在 Java 方法中生成 `returnAction()`，但对外路径仍保持 `/return`。

## 11. 关键 API

| 功能 | 方法与路径 |
|---|---|
| 创建任务 | `POST /api/jobs` |
| 获取/保存规划 | `GET/PUT /api/planning/{jobId}` |
| 重新生成规划 | `POST /api/planning/regenerate` |
| 确认规划 | `POST /api/jobs/{jobId}/confirm` |
| 任务状态 | `GET /api/jobs/{jobId}` |
| 恢复中断任务（ISSUE-008 L1） | `POST /api/jobs/{jobId}/resume` |
| 历史任务 | `GET /api/history/jobs` |
| Demo 状态 | `GET /api/jobs/{jobId}/demo` |
| 启动/停止 Demo | `POST /api/jobs/{jobId}/demo/start`、`demo/stop` |
| 审查通过 | `POST /api/jobs/{jobId}/review/approve` |
| 提出返工 | `POST /api/jobs/{jobId}/revision/propose` |
| 确认/取消返工 | `POST /revision/confirm`、`revision/cancel` |
| 规划版本 | `GET /api/jobs/{jobId}/revisions` |
| 恢复版本 | `POST /api/jobs/{jobId}/revisions/{version}/restore` |
| 删除任务 | `DELETE /api/jobs/{jobId}` |
| 日志 | `GET /api/jobs/{jobId}/logs/{service}` |
| 预览/下载 | `GET /api/jobs/{jobId}/preview`、`download` |

## 12. 关键文件

| 关注点 | 文件 |
|---|---|
| API 与进程启动 | `backend/app/main.py` |
| 状态与流水线 | `backend/app/workflow.py` |
| AI 规划和返工 | `backend/app/planner.py` |
| 行业基础映射（编码→显示名，保留供历史参考） | `backend/app/industry_knowledge.py`、`industry_knowledge/*.json` |
| 项目/UI 生成 | `backend/app/project_generator.py` |
| AI Code Enhancer | `backend/app/enhancer.py`，逐文件增强并通过 `workflow.py` 写入 `codegen_enhance_steps` |
| 合规检查 | `backend/app/compliance.py` |
| 首页与审查 | `frontend/src/pages/HomePage.vue` |
| 规划确认 | `frontend/src/pages/PlanningReviewPage.vue` |
| 历史任务 | `frontend/src/pages/HistoryPage.vue` |
| 项目入口 | `README.md` |
| Issue 与交接 | `docs/ISSUES.md`、`AGENTS.md` |

## 13. 当前验证与剩余风险

已验证：

- 2026-06-25 最小化 AI 代码增强端到端任务 `20260625123758-c69d4bcd` 已完整跑通：规划、项目生成、AI 增强、运行验证、在线 Demo、自动截图、文档生成、合规检查和 ZIP 打包均完成；`codegen_actual_mode=llm`，运行验证 `frontend_build/backend_structure/maven_test` 均 passed，截图 12 张，最终生成 `copyright_package.zip`。
- 后端 113 项单元测试通过。
- 本轮端到端修复后，专项回归 `python -m unittest tests.test_enhancer tests.test_project_generator tests.test_workflow_order -v` 48 项通过。
- Code Enhancer 增强测试通过：覆盖 UI 优先顺序、README 节点映射、实际 CSS 选择器校验、坏 JSON、HTTP 529 重试和逐步回滚。
- ISSUE-013 临时产物检查通过：审核中心生成“通过 / 驳回 / 快速审核 / 转交 / 退回补充”按钮、前端 API 和后端业务接口。
- 工厂前端构建通过。
- 多壳层、多页面模式的生成项目前端构建通过。
- JDK 17 下生成项目 Maven 79 项测试通过。
- 浏览器确认首页无行业模块预选、历史任务有删除、详情有返回首页。
- 用户已完成真实任务端到端链路验证，包含规划、Planning Review、项目生成、Maven/npm 验证、Demo 审查、返工、材料生成和 ZIP 打包。

剩余风险：

- 最小化任务成功链路中，`shell` UI 子步骤因 LLM 返回空 CSS 被受控标记为 `skipped`，整体 `actual_mode` 仍为 `llm`；若后续要求五个 UI 子步骤全部 completed，需要继续调优 shell 步提示词。
- ISSUE-008 L1 已通过 Codex 二次复审：服务重载或重启后，后台 Worker 会通过 `worker.lock` 与 `updated_at` 判定是否中断，并允许人工恢复；多 uvicorn 并存、杀子进程 hang API 和 multiprocessing 调度缺陷仍属 L1 已接受风险。
- 验证 Demo 超时回收和运行中任务删除限制。
