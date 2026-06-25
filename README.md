# AI软著工厂 V1.0

> 2026-06-25 端到端验证说明：最小化 AI 代码增强任务 `20260625123758-c69d4bcd` 已完整跑通，`codegen_actual_mode=llm`，运行验证 `frontend_build/backend_structure/maven_test` 均 passed，截图 12 张，5 份软著文档和 `copyright_package.zip` 已生成。过程中修复了规划 JSON 误提取、业务模块 `dashboard` 与首页路由命名冲突、daemon 子进程 JSON/Unicode 输出、Code Enhancer 重试倍增、UI 步骤超时 fallback、Windows 状态文件瞬时读取冲突和 npm install 超时问题。当前本地 MiniMax 配置建议保持 `AI_PLANNER_TIMEOUT=180`、`AI_CODEGEN_TIMEOUT=240`，生成项目 npm 安装超时默认 600 秒。

> 2026-06-24 实现状态说明（优先于下文历史描述）：在 2026-06-23 五阶段 UI 增强基础上，**ISSUE-026 落地**：
> - `backend/app/workflow.py` 补模块级 `import logging` 与 `logger = logging.getLogger(__name__)`，修复 `continue_material_generation` 末尾 `logger.warning` 触发的 `NameError`，让"软著材料打包"阶段不再崩溃；
> - daemon Worker 下 `_call_chat_completion_with_deadline` 改走独立 Python subprocess，并由 `subprocess.run(..., timeout=AI_CODEGEN_TIMEOUT+10)` 做硬截止，超时会杀掉请求子进程，不再依赖 `ThreadPoolExecutor.shutdown(wait=False)` 留下后台线程；
> - `_request_ui_step` 在 LLM 多次返回空 CSS（纯注释 / `@media{}` 空体）时返回 `UIStepResponse(block=None, skip_reason=...)`，调用方 `_enhance_ui_steps` 标 `status="skipped"` 且 `success=True`（避免被下方 `if not success:` 覆盖为 failed），让响应式步空响应不再阻断任务；
> - `backend/tests/test_enhancer.py` 现为 35 项全过；端到端 AI 增强代码流程 PASS（4 completed + 1 skipped，`actual_mode=llm`）。
>
> **ISSUE-021 最新修正**：源代码材料不再每 50 行插入硬分页，改由 Word/WPS 按页面版心自然分页；保留 10.5pt 宋体、受控视觉行宽和 AI/LLM 标记过滤。
>
> **ISSUE-025 仍生效**：
> - 业务步补 Element Plus 全家族：`.el-pagination` / `.el-pager` / `.btn-prev` / `.btn-next` / `.el-checkbox--*` / `.el-radio--*` / `.el-select--*` / `.el-tooltip` / `.el-message` / `.el-notification` / `.el-popover` / `.el-popper` / `.el-dropdown` / `.el-menu` / `.el-upload` / `.el-tabs` 等；
> - 业务步补自定义按钮 `.btn-primary` / `.btn-ghost` / `.btn-default` / `.btn-danger` / `.btn-success` / `.btn-warning` / `.btn-info` / `.btn-link` / `.btn-text`；
> - 业务步补模块派生通配 `.module-*` / `.task-*` / `.form-*`；
> - dashboard 步补 LLM 派生通配 `.dashboard-*` / `.m-*` / `.pattern-*` / `.trend-*` / `.stat-*` / `.metric-*`；
> - responsive 步补 `.page-heading` / `.actions` / `.btn-*`；
> - `selector_audit.merge_with_hints` 关键字扩展覆盖以上模式。
>
> **ISSUE-024 仍生效**：
> - 白名单按 `project_generator.py` 实际渲染 class 重写：shell 步补 `.shell-split` / `.shell-main` / `@media`（split_console 壳层 + 响应式断点）；business 步加 `.el-card__*` / `.el-button--*` / `.el-tag--*` / `.el-dialog__*` Element Plus BEM 派生通配；dashboard 步把已废弃的 `.metric-grid` / `.kpi-icon` 改为 `.kpi-grid` / `.kpi-trend*` / `.kpi-row` / `.dashboard-row`；responsive 步补 `.kpi-grid` / `.dashboard-row` / `.module-dashboard` / `.status-row` / `.analysis-workbench`；
> - `GLOBAL_UI_SELECTOR_HINTS` 加 `html` 与 `*`（含 `*::before` / `*::after` 特判），任何步可写全局基础样式；
> - `_selector_matches_hints` 支持 `__*` / `--*` 通配与全局 `*` 重置特判；
> - 新建 `backend/app/selector_audit.py`：扫描生成项目真实 class（`style.css` 规则选择器 + `views/*.vue` `class=` 字面量），启发式分类合并入运行时 hints；`enhance_project` try/finally 恢复常量；漂移审计写 `.learnings/ERRORS-YYYYMMDD-selector-drift.md`；
> - `_validate_ui_block` 加 `_scan_css_chars` 字符集合扫描兜底越界（剥离注释后只允许合法 CSS 字符、ASCII 字母数字、空白与 Unicode）；
> - `backend/app/learning.py` 修复建议链接改为参数化（`issue_id` / `issue_doc` 由调用方传），不再硬编码 `ISSUE-022.md`。
>
> **ISSUE-023 仍生效**：
> - `frontend/src/style.css` 增强块单步上限 8000→16000 字符（`AI_CODEGEN_UI_BLOCK_MAX_CHARS` 可覆盖），超长时反馈模型精简后重试 1 次；
> - 抽 `_retry_with_backoff` helper，`max_attempts=3`（`AI_CODEGEN_MAX_ATTEMPTS` 可覆盖）+ 指数退避 + jitter；
> - `llm` 模式容忍最多 1 个 UI 子步骤失败（≥4/5 步成功仍视为 llm 增强成功；≥2 步失败才整体回滚并抛错）；
> - `EnhancementResult.actual_mode` 新增 `partial` 字面值，区分"完全增强"与"仅 README 增强"；
> - 白名单补 `responsive` 步的 `:root`/`html`/`.el-button`/`select`/`textarea` 等 Element Plus 基础选择器，`GLOBAL_UI_SELECTOR_HINTS = (":root", "--ai-")` 全局允许；
> - 新增 `backend/app/learning.py`，enhance 失败自动写 `.learnings/ERRORS-YYYYMMDD-enhance.md`，根因分类（empty_selectors/whitelist_strict/size_exceeded/daemon_ssl_read_timeout/missing_credentials/api_http_error/other）；
> - `workflow.py` 在 `status=success` 但 `run_status=running` 时打 warning log 提醒 demo 进程未显式停止。
> 2026-06-23 实现状态说明（仍生效）：Code Enhancer 先由 LLM 按 `theme`、`shell`、`business`、`dashboard`、`responsive` 五个 UI 子步骤追加受约束 CSS，随后独立增强 `README.md`。每个 UI 子步骤独立超时、重试和按步回滚，页面展示状态、尝试次数、耗时和摘要。后台 daemon Worker 使用网络读超时而不创建嵌套子进程；非 daemon 调用保留硬超时子进程。系统校验 CSS 实际选择器，不允许 LLM 修改 `App.vue`、路由、`views/*`、API 或后端业务代码。

AI软著工厂用于从软件名称、行业、软件类型和描述出发，生成可运行的 Java Demo 项目及软件著作权申报材料。

## 开发协作

本仓库使用 [开发 Harness](docs/HARNESS.md) 管理 Codex、Claude 等编码 Agent 的协作：问题先登记、方案与验收先确认、实施后运行验证、再由 Codex 复审并同步交接文档。该规范约束研发过程，不影响用户侧的软著生成流程。

Planner 完全由大模型驱动，直接根据软件名称、软件类型和软件描述生成结构化规划。行业类型（公安、政法、工业、教育）仅作为任务信息记录，不约束 LLM 输出。首次 JSON 解析或 Pydantic 校验失败时自动修复一次；二次仍失败任务进入 `failed`，由用户在前端点击"重新生成规划"使用原 job ID 重试。用户确认规划后，系统生成并运行项目，启动在线 Demo 等待人工审查。只有用户确认 Demo 符合预期后，系统才会继续截图、文档、合规检查和 ZIP 打包。

## 当前能力

- Planner 由 LLM 直接生成；行业作为普通提示信息；不读取行业知识库，不做行业白名单或一致性校验。
- 内部编码（`public_security` 等）通过 `planner.industry_name_for()` 转为显示名（"公安" 等）后传给模型。
- 首次返回坏 JSON / 结构校验失败时自动修复一次；二次仍失败任务停留在 `failed`，由用户重试。
- 返工对话 `propose_revision()` 同样 LLM-only，失败时提示重试。
- 在 Planning Review 中增删改模块、页面、字段、数据库表和 UI 结构。
- 生成 Java 17、Spring Boot 3、MyBatis Plus、MySQL、Vue 3、Element Plus 项目。
- 每个业务模块生成 Entity、DTO、VO、Mapper、Service、ServiceImpl、Controller、API、Vue 页面和 SQL 表。
- `planning.api_list` 中声明的模块业务动作会落地为前端按钮、前端 API、后端 Controller 与 Service 方法，例如审核通过、驳回、快速审核、转交和退回补充。
- 自动执行前端生产构建、Maven 测试及项目运行验证。
- 使用 H2 Demo 配置启动在线演示，生产配置仍使用 MySQL。
- Demo 审查通过后自动截图并生成软著材料；每个菜单模块覆盖功能页和新增/编辑表单。材料使用统一的标题、正文、表格、图题、页眉页脚与代码样式；用户手册以真实截图配合逐条操作说明，源码材料排除压缩样式和生成标记。
- Demo 不符合预期时，可通过自然语言修改规划并重新生成项目。
- 保存规划历史版本，支持查看和恢复旧版本。
- 历史任务支持查看、继续审查、启动 Demo、下载和删除。
- 生成一致性与合规报告、申请信息表及最终申报包。

## 核心流程

```text
填写软件信息（行业仅作信息记录）
→ Planner 直接调用 LLM 生成 planning.json
→ Planning Review 人工调整并确认
→ 生成 Spring Boot + Vue 3 项目
→ 前端构建与 Maven 测试
→ 启动在线 Demo
→ 等待用户审查
   ├─ 符合预期：截图 → 文档 → 合规检查 → ZIP 打包
   └─ 需要修改：自然语言反馈 → 查看变更摘要 → 确认新规划
                  → 重新生成项目 → 再次审查 Demo
```

Demo 启动后，任务会停留在 `awaiting_demo_review`。未经用户确认，不会提前生成截图、文档或最终软著包。

## UI 规划

`planning.json` 包含结构化 `ui_plan`。Planner 负责选择 UI 原型和参数，Project Generator 负责确定性生成代码。

生成器会读取 `api_list` 中形如 `PUT /api/{module}/{id}/approve` 的业务动作接口，并在对应模块页面的操作列生成可点击按钮，同时生成前端 API 和后端业务接口。通用 CRUD 仍默认生成，业务动作作为规划驱动的增量能力。

当前支持三种应用壳层：

- `sidebar_admin`：左侧导航管理后台。
- `top_workspace`：顶部导航业务工作台。
- `split_console`：对象树、工作区和详情区组成的分栏控制台。

当前支持六种模块页面结构：

- `table_crud`：查询、表格、分页和弹窗编辑。
- `master_detail`：列表与详情并列。
- `tree_detail`：树形目录与对象详情。
- `workflow_timeline`：流程步骤、时间线和处理记录。
- `kanban`：按阶段组织的业务看板。
- `dashboard`：指标、图表和业务明细联动。

UI 差异不仅来自配色，还来自导航方式、首页结构和模块交互模式。Planning Review 中可以人工修改这些选项。

## 技术架构

工厂应用：

- 前端：Vue 3、Vue Router、Vite
- 后端：FastAPI、Pydantic
- 自动化：Playwright
- 文档：python-docx
- 状态存储：`outputs/{job_id}` 文件目录

生成项目：

- Java 17
- Spring Boot 3
- MyBatis Plus
- MySQL
- Vue 3
- Element Plus
- H2，仅用于在线 Demo

## 环境要求

- Python 3.10+
- Node.js 18+
- JDK 17
- Maven 3.9+
- npm

可先检查：

```powershell
python --version
node --version
npm.cmd --version
java -version
mvn.cmd -version
```

## 模型配置

复制环境变量模板：

```powershell
Copy-Item "C:\Users\whn\Documents\软著\backend\.env.example" `
  "C:\Users\whn\Documents\软著\backend\.env"
```

填写 OpenAI-compatible API：

```env
AI_PLANNER_BASE_URL=https://api.openai.com/v1
AI_PLANNER_API_KEY=你的密钥
AI_PLANNER_MODEL=实际可用的模型名称
AI_PLANNER_TIMEOUT=60

AI_CODEGEN_MODEL=
AI_CODEGEN_TIMEOUT=180
AI_CODEGEN_DOC_TIMEOUT=90
AI_DOCUMENT_MODEL=
AI_DOCUMENT_TIMEOUT=90
```

Planner 运行方式：

- 当前代码为 LLM-only，不再支持 `auto`、`llm` 和 `template` 模式切换。
- Planner 不读取行业知识库，不做行业白名单校验，不回退固定模板。
- JSON 容错解析失败或结构校验失败时，携带错误让模型自动修复一次；仍失败则任务进入 `failed`，用户可在原任务上重新生成规划。

代码生成模式：

- `auto`：执行 AI Code Enhancer，验证失败时回滚到稳定模板。
- `llm`：强制执行代码增强，验证失败则终止任务。
- `template`：只使用确定性项目生成器。
- Code Enhancer 先执行 `theme`、`shell`、`business`、`dashboard`、`responsive` 五个 AI UI 子步骤，再独立增强 `README.md`。`App.vue`、`router.js` 与 `views/*` 归固定生成器所有，不交给 LLM 整文件重写。
- 每个 UI 子步骤只追加经实际选择器白名单校验的 CSS，独立超时、重试和按步回滚；README 事件使用稳定的 `readme` 节点键。
- 设置 `AI_DOCUMENT_MODEL` 后，材料生成会让 LLM 仅基于模块、页面、字段、接口和截图清单生成结构化说明；未配置或校验失败时回退固定文案，不影响材料生成。
- 任务进度区会展示状态、尝试次数、耗时、摘要和失败原因。`auto` 下单步失败只回滚该步并继续；`llm` 下任一步失败会回滚并终止任务。

也可以启动系统后，在首页“模型设置”中维护配置。后端接口不会向前端返回完整 API Key。

## 启动项目

### 1. 启动后端

```powershell
cd "C:\Users\whn\Documents\软著\backend"
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

后端地址：

- API：`http://127.0.0.1:8000`
- Swagger：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/api/health`

### 2. 启动前端

新开一个 PowerShell 窗口：

```powershell
cd "C:\Users\whn\Documents\软著\frontend"
npm.cmd install
npm.cmd run dev
```

浏览器访问：

```text
http://127.0.0.1:5173
```

## 使用说明

1. 填写软件名称、描述、软件类型和行业类型。
2. 选择 Planner、代码生成和文档模式，创建任务。
3. 等待系统生成规划并进入 Planning Review。
4. 检查模块、页面、字段、数据库表及 UI 结构。
5. 保存并确认规划，开始生成项目。
6. 在线 Demo 启动后，查看 Demo、Swagger 和运行日志。
7. 选择“符合预期，继续生成软著材料”，或填写自然语言修改意见。
8. 任务完成后下载源码或 `copyright_package.zip`。

历史任务页面支持：

- 查看任务详情。
- 继续处于 Demo 审查或规划返工状态的任务。
- 启动或停止 Demo。
- 下载已生成材料。
- 删除失败、测试或不再需要的任务。

删除任务会同时删除对应源码、日志、截图、文档和 ZIP，且无法恢复。正在生成材料或重新生成项目的任务禁止删除。

## 任务状态

- `draft_planning`：规划草稿等待用户编辑。
- `confirmed`：规划已确认。
- `generating_project`：正在生成并验证项目。
- `demo_starting`：正在启动在线 Demo。
- `awaiting_demo_review`：Demo 已就绪，等待用户审查。
- `revision_review`：修改方案已生成，等待用户确认。
- `regenerating_project`：正在根据新规划重新生成。
- `generating_materials`：正在生成截图和软著材料。
- `success`：材料生成并打包完成。
- `failed`：任务执行失败。

任务状态、规划和修改记录均会落盘。关闭浏览器或更换窗口后，可以从历史任务继续。

## 输出目录

每个任务输出到：

```text
outputs/{job_id}/
├─ status.json
├─ planning.json
├─ planning_versions/
├─ revision_proposals/
├─ generated_project/
│  ├─ backend/
│  ├─ frontend/
│  ├─ sql/
│  └─ THIRD_PARTY_NOTICES.md
├─ screenshots/
├─ screenshot_manifest.json
├─ docs/
├─ logs/
├─ code_stats.json
├─ compliance_report.json
├─ generated_project.zip
└─ copyright_package.zip
```

最终申报包默认位于：

```text
C:\Users\whn\Documents\软著\outputs\{job_id}\copyright_package.zip
```

## 开发验证

后端测试：

```powershell
cd "C:\Users\whn\Documents\软著\backend"
python -m unittest discover -s tests -v
```

工厂前端构建：

```powershell
cd "C:\Users\whn\Documents\软著\frontend"
npm.cmd run build
```

生成项目还会在任务流水线中自动执行：

```text
npm install
npm run build
mvn test
```

## Demo 故障排查

Demo 启动过程包括：

```text
queued → building → starting → running
```

如果长时间停留在“启动中”：

1. 查看任务页面中的 Demo 状态和错误信息。
2. 查看构建日志：`outputs\{job_id}\logs\demo_build.log`。
3. 查看运行日志：`outputs\{job_id}\logs\backend.log` 和 `frontend.log`。
4. 确认 `java -version` 为 JDK 17。
5. 确认 Maven 可用且与 JDK 17 匹配。
6. 检查工厂后端是否为最新启动的进程。

检查 8000 端口：

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
```

强制让某个生成项目重新构建 JAR：

```powershell
Remove-Item "outputs\{job_id}\generated_project\backend\target" -Recurse -Force
```

## 项目文档

- [跨窗口交接入口](AGENTS.md)
- [问题与升级记录](docs/ISSUES.md)
- [系统流程说明](docs/FLOW.md)

新窗口或新会话接手项目时，应先阅读 `AGENTS.md`，再按其中顺序查看 README、Issue 和流程文档。
