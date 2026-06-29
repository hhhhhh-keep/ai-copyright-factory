# AI软著工厂交接入口

> 2026-06-25 端到端基线：最小化 AI 代码增强任务 `20260625123758-c69d4bcd` 已完整跑通，`codegen_actual_mode=llm`，运行验证 `frontend_build/backend_structure/maven_test` 均 passed，截图 12 张，5 份软著文档和 `copyright_package.zip` 已生成。本轮修复记录在 `docs/ISSUES.md` 的 ISSUE-028，涵盖 Planner JSON 形状优先提取、生成项目 `dashboard` 模块与首页路由冲突、daemon 子进程 JSON/Unicode 输出、Code Enhancer 重试倍增、UI 步骤超时 fallback、Windows 状态文件瞬时读取冲突、npm install 超时和本地 AI 超时配置。当前建议保持 MiniMax `AI_PLANNER_TIMEOUT=180`、`AI_CODEGEN_TIMEOUT=240`，`NPM_INSTALL_TIMEOUT` 默认 600 秒。

> ISSUE-020 当前实现覆盖说明：Code Enhancer 先由 LLM 执行 `theme`、`shell`、`business`、`dashboard`、`responsive` 五个 UI 子步骤，再执行独立 README 文档增强。每一步只追加通过实际选择器白名单校验的 CSS，独立超时、重试、按步回滚，并将状态、尝试次数、耗时和摘要写入 `codegen_enhance_steps`。任务 Worker 为 daemon 进程时，增强器改用独立 Python subprocess 执行 LLM HTTP 请求，并由 `subprocess.run(..., timeout=AI_CODEGEN_TIMEOUT+10)` 做硬截止；非 daemon 远端调用保留 `multiprocessing` 硬超时，本地 `127.0.0.1/localhost` 调用直接走传输层 timeout。`App.vue`、`router.js`、`views/*`、API 和后端业务代码仍由固定生成器控制，禁止 LLM 修改。**ISSUE-023 落地后补充**：`llm` 模式容忍最多 1 个 UI 子步骤失败（≥4/5 步成功仍视为 llm 增强成功），`max_attempts` 默认 3 并采用指数退避 + jitter；`EnhancementResult.actual_mode` 新增 `partial` 字面值，区分"完全增强"与"仅 README 增强"。**ISSUE-024/025 落地后补充**：白名单按生成器实际渲染 class 和真实 LLM 派生命名补齐，覆盖 Element Plus BEM 派生、自定义按钮、模块派生和 dashboard 派生；`selector_audit.py` 会扫描生成项目真实 class 并合并运行时 hints；`_validate_ui_block` 加 `_scan_css_chars` 兜底越界。**ISSUE-026 最新修正**：`workflow.py` 已补 logger；daemon timeout 不再使用 `ThreadPoolExecutor.shutdown(wait=False)`，避免后台线程泄漏；空 CSS 响应标 `skipped` 且不阻断任务。**ISSUE-027 最新修正**：Planner JSON 提取会优先选择包含规划关键字段的完整对象，避免 `<think>` 中的示例 JSON 遮挡最终规划。**ISSUE-021 最新修正**：源代码材料不再每 50 行插入硬分页，改由 Word/WPS 按版心自然分页。本说明优先于下文历史描述。

本文件供新的 Codex 窗口、开发者或自动化代理快速接手项目。开始工作前按顺序读取：

1. `README.md`：当前产品能力、启动方式和使用流程。
2. `docs/ISSUES.md`：用户反馈、已完成升级、验证结果和剩余风险。
3. `docs/FLOW.md`：真实代码流程、状态机、接口和关键文件。
4. `docs/HARNESS.md`：Codex、Claude 等 Agent 协作开发的门禁、职责和交接格式。

Claude 不由当前工厂进程或 Codex 会话包装执行。需要实施时，用户在新 Claude Code 窗口按 `AGENTS.md`、`docs/HARNESS.md` 和对应 ISSUE 文档接手；Claude 完成后由 Codex 复审 Git diff、测试和生成链路结果。

## 当前项目结论

- 首页已取消“需求澄清”和固定行业模块预选。
- Planner 完全由 LLM 驱动，直接根据软件名称、类型和描述生成模块；行业类型（公安/政法/工业/教育）仅作为普通提示信息和任务记录，Planner 不读取行业知识库、不做行业白名单校验、不回退模板。
- Planner 首次返回坏 JSON / 校验失败时自动修复一次；二次仍失败或 API 不可用时任务进入 `failed`，由用户在前端点击“重新生成规划”，使用原 job ID 复位步骤后重试。
- 返工对话 `propose_revision()` 同步 LLM-only，失败提示重试，不使用规则改写。
- 行业基础映射（内部编码 → 显示名）保留在 `backend/app/planner.py` 的 `INDUSTRY_DISPLAY_NAMES` 与 `industry_name_for()` 中，仅用于把行业提示从编码转换为显示名，不参与校验。
- Planning Review 是模块、页面、字段、数据库表和 UI 结构的唯一人工审核入口。
- Project Generator 会解析 `planning.api_list` 中的模块业务动作接口，并生成对应前端按钮、API、Controller 与 Service 方法。
- Code Enhancer 先执行五个 LLM UI 子步骤 `theme`、`shell`、`business`、`dashboard`、`responsive`，再独立增强 README。每步只追加经实际 CSS 选择器白名单校验的样式块，并记录 `codegen_enhance_steps` 的状态、尝试次数、耗时和摘要。`App.vue`、`router.js` 与 `views/*` 继续归固定生成器所有；`auto` 单步失败按步回滚并继续，`llm` 任一步失败整体回滚并终止。
- 生成项目完成运行验证后，必须先启动在线 Demo 并暂停在 `awaiting_demo_review`。
- 用户审查通过后，才生成截图、文档、合规报告和最终 ZIP。
- 用户可以通过自然语言提出返工意见；系统先展示新规划摘要，确认后才重新生成。
- 规划版本和返工建议均落盘，可从历史任务继续或恢复旧版本。
- 历史任务支持返回首页和受控删除。

## 当前 Git 状态

- 分支：`main`
- 当前基线提交：`00eceb78b1ea23891a377f547e4be7112610064e`
- 基线提交说明：`Update issue log with UI and workflow changes`
- 当前工作区包含尚未提交的本轮升级代码和文档，不要擅自回滚或覆盖。
- `outputs/` 是本地任务数据，已被 Git 忽略。不要为了测试删除已有任务。

接手后先执行：

```powershell
git status --short
git diff --check
```

## 已完成升级

- ISSUE-002：取消首页行业模块预选，改为 AI 规划 + Planning Review。
- ISSUE-003：第一阶段多原型 UI 体系，包含 3 种壳层和 6 种页面结构。
- ISSUE-004：Demo 人工审查、自然语言返工、规划版本和恢复。
- ISSUE-005：历史任务详情增加“返回首页”。
- ISSUE-006：历史任务增加安全删除。
- ISSUE-007：Planner 改为 LLM-only，取消行业知识库、模板回退和规划模式选择。
- ISSUE-008 L1：状态区分、人工恢复按钮、启动扫描、任务锁和恢复记录已由 Claude 实施完成，并通过 Codex 二次复审。
- ISSUE-009：模块字段上限放宽到 20，解决 13 个有效字段导致规划失败的问题。
- ISSUE-010：Dashboard 页面视觉增强，含 5 类 SVG 业务化图形（KPI 卡 / 环形 / 折线 / 柱状 / 状态标签）+ 行业关键词匹配的差异化 KPI 文案，并通过 Codex 审查。
- ISSUE-011：源码材料原创性增强，业务化中文注释（Java/Vue/SQL）+ project_fingerprint.json + originality_report.json，并通过 Codex 审查。
- ISSUE-012：Planner 数据库表数量容错，自动补齐/规范化 `database_tables` 并保存失败诊断。
- ISSUE-013：规划 `api_list` 中的业务动作落地为前端按钮、前端 API、后端 Controller/Service 和生成项目合约测试，解决审核操作只出现在规划文本、不出现在 Demo 页面的问题。
- ISSUE-014：Code Enhancer 拆分为逐文件多轮请求，默认超时提升到 180 秒，并在首页进度区展示 AI 增强成功、未启用或失败回退及逐文件节点。
- ISSUE-015：为 `App.vue` 增强增加结构守卫，防止增强后子菜单只剩占位页、无法进入具体模块功能。
- ISSUE-016：`status.json` / `enhancement.json` 带 UTF-8 BOM 时工厂后端状态轮询不再 ASGI 500，`_json_read()` 已兼容 `utf-8-sig`。
- ISSUE-017：Code Enhancer 对坏 JSON 自动修复一次，对 HTTP 429/5xx/529 和读超时自动重试；`auto` 模式失败回滚模板，`llm` 强制模式持续失败时按设计终止任务。
- ISSUE-018：收敛 Code Enhancer 边界，移除 `App.vue` LLM 整文件增强，`style.css` 改为追加样式块，README 保留 LLM 文档增强。
- ISSUE-019：`style.css` 远程增强仍频繁读超时，已改为本地风格追加生成器；专项记录见 `docs/ISSUE-019.md`。
- ISSUE-020：恢复 AI 驱动的界面风格增强，按 Demo 工程 5 个 UI 子步骤 + README 分阶段请求；已修正 UI/README 执行顺序、README 进度映射、实际 CSS 内容校验和可见重试事件，并通过 Codex 复审。详见 `docs/ISSUE-020.md` 与 `docs/ISSUE-020-IMPLEMENTATION.md`。
- ISSUE-022：截图抓拍时机早于 Element Plus 对话框动画完成；已加 `_wait_for_settle(page, kind)` 与 manifest 字段。第二轮追加 `_stretch_overlay_to_page(page)`：把 `.el-overlay` 从 `position: fixed` 改为 `absolute` 并撑满整页高度，避免 `full_page=True` 时视口下方的主页面表格裸露在截图里。`module_create` manifest 同步新增 `overlay_full_page` 字段。Codex 代码复审与截图单测通过，仍建议用真实生成任务做最终视觉确认。
- ISSUE-023：AI 增强几乎全部失败（jobId=20260623225150-e2f31fbd 复盘）。白名单补全 `:root`/`--ai-` 全局允许 + responsive 步加 Element Plus 基础选择器；`UI_STEP_MAX_BLOCK_CHARS` 8000→16000 + ValidationError 触发精简重试；抽 `_retry_with_backoff` helper，`max_attempts=3` + 指数退避 + jitter；`llm` 模式容忍最多 1 步 UI 失败（≥4/5 成功即视为 llm 增强）；`EnhancementResult.actual_mode` 新增 `partial` 字面值，区分"完全增强"与"仅 README 增强"；新增 `backend/app/learning.py` 自动写 `.learnings/ERRORS-YYYYMMDD-enhance.md`；`workflow.py` 在 `status=success` 但 `run_status=running` 时打 warning。详见 `docs/ISSUE-023.md`。
- ISSUE-024：白名单与生成器实际 class 失配（jobId=20260624095339-9d44c135 复盘）。`UI_STEP_SELECTOR_HINTS` 4 步按 `project_generator.py` 真值重写（`split_console` 壳层补 `.shell-split` / `.shell-main` / `@media`；dashboard 步把已废弃 `.metric-grid` / `.kpi-icon` 改为 `.kpi-grid` / `.kpi-trend*` / `.kpi-row` / `.dashboard-row`；business 步加 `.el-card__*` / `.el-button--*` / `.el-tag--*` / `.el-dialog__*` Element Plus BEM 派生通配；responsive 步补 `.kpi-grid` / `.dashboard-row` / `.module-dashboard` / `.status-row` / `.analysis-workbench`）。`GLOBAL_UI_SELECTOR_HINTS` 加 `html` 与 `*`（含 `*::before` / `*::after` 特判）。`_selector_matches_hints` 支持 `__*` / `--*` 通配与全局 `*` 重置特判。新建 `backend/app/selector_audit.py`：扫描生成项目 `frontend/src/` 真实 class（`style.css` 规则选择器 + `views/*.vue` `class=` 字面量），启发式分类合并入运行时 hints；`enhance_project` try/finally 恢复常量；漂移审计写 `.learnings/ERRORS-YYYYMMDD-selector-drift.md`。`_validate_ui_block` 加 `_scan_css_chars` 字符集合扫描兜底越界。`backend/app/learning.py` 修复建议链接改为参数化（`issue_id` / `issue_doc` 由调用方传），不再硬编码 `ISSUE-022.md`。`backend/tests/test_enhancer.py` 新增 8 项 + 调整 1 项，共 27 项。详见 `docs/ISSUE-024.md`。
- ISSUE-025：白名单仍漏 Element Plus 全家族 + 伪元素组合 + LLM 自创派生类（jobId=20260624140839-03bb66f7 复盘，ISSUE-024 落地后新回归）。业务步补 `.el-table--*` / `.el-pagination` / `.el-pager` / `.btn-prev` / `.btn-next` / `.el-checkbox--*` / `.el-radio--*` / `.el-select--*` / `.el-tooltip` / `.el-message` / `.el-notification` / `.el-popover` / `.el-dropdown` / `.el-menu` / `.el-upload` / `.el-tabs` Element Plus 全家族；业务步加 `.btn-primary` / `.btn-ghost` / `.btn-default` / `.btn-danger` / `.btn-success` / `.btn-warning` / `.btn-info` 自定义按钮；业务步加 `.module-*` / `.task-*` / `.form-*` 模块派生通配；dashboard 步加 `.dashboard-*` / `.m-*` / `.pattern-*` / `.trend-*` / `.stat-*` / `.metric-*` LLM 派生通配；responsive 步补 `.page-heading` / `.actions` / `.btn-primary` / `.btn-ghost`。`selector_audit.merge_with_hints` 关键字扩展。`backend/tests/test_enhancer.py` 新增 4 项，共 31 项。详见 `docs/ISSUE-025.md`。
- ISSUE-026：`backend/app/workflow.py` `continue_material_generation` 末尾 `logger.warning` 抛 `NameError` 阻断软著材料打包（ISSUE-023 P1-3 实施遗漏模块顶部 `import logging`）；daemon Worker 下 `_call_chat_completion_with_deadline` 改用独立 Python subprocess + `subprocess.run(..., timeout=AI_CODEGEN_TIMEOUT+10)`，真正杀掉卡在 SSL read 的请求子进程，避免 ThreadPool 后台线程泄漏；`_request_ui_step` 在 LLM 多次返回空 CSS 时返回 `UIStepResponse(block=None, skip_reason=...)`，调用方标 `skipped` 且 `success=True`，让响应式步空响应不再阻断任务。`backend/tests/test_enhancer.py` 现为 35 项通过。详见 `docs/ISSUE-026.md`。
- ISSUE-027：Planner JSON 提取器不再返回 `<think>` 推理文本里的第一个局部 JSON 示例；现在会优先选择包含规划关键顶层字段的完整对象，修复 jobId=`20260625095657-0ed4e081` 规划阶段误报缺少 `software_name/modules/...` 的问题。`backend/tests/test_planner.py` 34 项通过，且该 job 的 `planner_raw_repair.txt` 可被本地解析为 5 个模块。
- ISSUE-028：最小化 AI 代码增强端到端任务 `20260625123758-c69d4bcd` 已完整跑通，修复生成项目 dashboard 路由冲突、daemon 子进程 JSON/Unicode、Code Enhancer 重试倍增、UI 步骤超时 fallback、状态文件瞬时读取冲突和 npm install 超时等阻塞点；`codegen_actual_mode=llm`，运行验证全 passed，截图 12 张，最终 ZIP 已生成。详见 `docs/ISSUES.md`。
- REGRESSION-001：Maven 校验强制使用 JDK 17 环境，解决 `61.0 / 52.0` 类版本错误。

ISSUE-001 已被 ISSUE-002 取代，不应恢复旧的行业模块预选功能。

## 当前待修

- 验证 Demo 超时回收、失败日志和运行中任务删除限制。
- ISSUE-021：补跑一次新的临时生成项目的 npm/Maven/Playwright 全链路材料验证；实现与单元测试已完成，详见 `docs/ISSUE-021.md`。
- ISSUE-022：截图抓拍时机早于 Element Plus 对话框动画完成，已加 `_wait_for_settle(page, kind)` 与 manifest 字段；并补 `_stretch_overlay_to_page(page)` 把固定蒙层改为 absolute + 整页高度，消灭"主菜单与子菜单重叠"假象；代码复审通过，真实视觉效果仍需在新任务截图中最终确认。

## 最近验证

- 后端 focused 测试：Code Enhancer 35 项通过；材料文档、截图、合规和 workflow order 专项测试通过。
- Code Enhancer 单测覆盖 UI 分阶段顺序、README 状态映射、实际 CSS 选择器校验、增强恢复、坏 JSON 修复、HTTP 529 重试、daemon subprocess 硬超时、空 CSS skipped 和本地 mock 直连。
- 生成器临时产物检查：审核中心已生成“通过 / 驳回 / 快速审核 / 转交 / 退回补充”按钮、前端 API 和后端业务接口。
- 工厂前端：`npm.cmd run build` 通过。
- 生成项目前端：多壳层、多页面模式构建通过。
- 生成项目后端：JDK 17 环境 Maven 79 项测试通过。
- 浏览器检查：首页无行业模块预选；历史任务有删除；任务详情有返回首页。
- 用户已完成真实任务端到端链路验证，ISSUE-009 和 REGRESSION-001 已确认成功。

## 开发约束

- 用户指出新问题时，只允许复现、分析、讨论方案并记录 ISSUE，不得直接修改业务代码。
- 必须先与用户确认处理流程、修复范围和验收标准。
- 只有用户明确发布“统一修改”、明确要求实施某个 ISSUE，或给出等价的开发命令后，才能修改业务代码。
- 问题收集阶段允许更新 `docs/ISSUES.md` 和交接文档，但不得借记录问题之机提前实施修复。
- `planning.json` 是后续代码、截图和文档的单一可信源。
- ISSUE-007 实施后，Planner 不再做行业一致性校验与模板回退；行业类型仅作为普通提示信息和任务记录，不约束 LLM 输出。
- ISSUE-007 实施后，`industry_knowledge/*.json` 与 `backend/app/industry_knowledge.py` 暂时保留供历史参考，但 Planner 不再导入。
- UI 多样性必须来自壳层、首页和模块页面结构，不得只换配色。
- 返工先更新规划，再完整重新生成；不要直接在生成源码上做不可追踪修改。
- 删除任务必须校验 job ID 和 `OUTPUT_ROOT`，并先停止 Demo。
- 不要修改或删除与当前任务无关的用户文件和历史任务。
- 修改业务流程后，同步更新 `README.md`、`docs/FLOW.md` 和 `docs/ISSUES.md`。

## 常用命令

```powershell
# 一键启动本地开发环境
cd "C:\Users\whn\Documents\软著"
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1

# 后端测试
cd "C:\Users\whn\Documents\软著\backend"
python -m unittest discover -s tests -v

# 工厂前端构建
cd "C:\Users\whn\Documents\软著\frontend"
npm.cmd run build

# 启动后端
cd "C:\Users\whn\Documents\软著\backend"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 启动前端
cd "C:\Users\whn\Documents\软著\frontend"
npm.cmd run dev
```

## 关键位置

- HTTP 接口：`backend/app/main.py`
- 流程和任务状态：`backend/app/workflow.py`
- AI 规划与返工（含行业编码→显示名映射）：`backend/app/planner.py`
- 项目与 UI 生成：`backend/app/project_generator.py`
- AI Code Enhancer：`backend/app/enhancer.py`
- 行业基础映射（保留供历史参考，Planner 不再导入）：`backend/app/industry_knowledge.py`
- 首页与 Demo 审查：`frontend/src/pages/HomePage.vue`
- Planning Review：`frontend/src/pages/PlanningReviewPage.vue`
- 历史任务：`frontend/src/pages/HistoryPage.vue`
- 行业基础映射文件：`industry_knowledge/*.json`
