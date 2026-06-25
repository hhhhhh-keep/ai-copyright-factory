# ISSUE-020 实施说明：分阶段 AI UI 增强

> 交给 Claude 的执行说明。先阅读 `AGENTS.md`、`docs/HARNESS.md`、`docs/ISSUE-020.md` 和本文；完成后不要提交或推送，由 Codex 复审。

## 0. 当前现场与目标

目标不是恢复“单次生成完整 style.css”，而是把 AI UI 增强做成一个可运行 Demo 工程的分阶段工作流：每一步请求小、耗时可见、失败可恢复、最终不破坏生成项目。

当前工作区已有一次**未完成的 ISSUE-020 改动**，主要在 `backend/app/enhancer.py`：

- 已出现 `UI_ENHANCEMENT_STEPS`、UI 风格方案、CSS 子步骤请求、CSS 片段校验等代码。
- `enhance_project()` 已尝试调用 `_enhance_ui_steps()`。
- 但 `workflow.py` 仍按 `ALLOWED_FILES` 初始化并更新旧的“界面样式 / 项目说明”节点；`HomePage.vue` 也仍只按 `item.file` 展示，无法正确展示 UI 子步骤。
- 自动化测试没有覆盖完整的 UI 分阶段协议和状态同步。

**先审计现有改动并补全，不要删除或从头覆盖它。** 保留用户和其他 Agent 已有的未提交变更。

## 1. 允许修改范围

允许修改：

- `backend/app/enhancer.py`
- `backend/app/workflow.py`
- `frontend/src/pages/HomePage.vue`
- `frontend/src/settings.css`（仅当新增步骤状态样式需要）
- `backend/tests/test_enhancer.py`
- `backend/tests/test_workflow_order.py`
- `backend/.env.example`
- `README.md`
- `AGENTS.md`
- `docs/FLOW.md`
- `docs/ISSUE-020.md`
- 本实施说明文件

禁止修改：

- `App.vue`、`router.js`、`frontend/src/views/*`、前端 API、后端生成项目业务代码。
- `outputs/` 下既有任务、凭据、`.env`、Git 历史。
- 不执行 `git commit`、`git push`、`git reset`、`git checkout`、递归删除。

## 2. 最终行为

### 2.1 UI 阶段定义

AI UI 增强必须按固定顺序执行：

| key | 前端展示名 | LLM 返回内容 | 允许影响范围 |
| --- | --- | --- | --- |
| `ui_theme` | 界面风格方案 | JSON 风格令牌和设计摘要，不含 CSS | 无文件写入 |
| `ui_shell` | 应用壳层 | 小型 CSS 追加块 | 登录页、导航、Header、主背景、Hero |
| `ui_business` | 业务页面组件 | 小型 CSS 追加块 | 卡片、表格、筛选、表单、状态、弹窗 |
| `ui_dashboard` | 驾驶舱与图表 | 小型 CSS 追加块 | KPI、SVG 图表、图例、活动流、告警 |
| `ui_responsive` | 响应式与收尾 | 小型 CSS 追加块 | 小屏布局、hover/focus、可访问性 |
| `readme` | 项目说明 | 完整 README | README.md |

`ui_theme` 必须由 AI 返回，不得把本地哈希令牌标记为 AI 成功。可保留本地令牌仅作为请求提示或 `auto` 模式下失败后的明确降级信息。

### 2.2 事件与状态

每一步写入 `status.json.codegen_enhance_steps`。统一字段：

```json
{
  "key": "ui_shell",
  "name": "应用壳层",
  "kind": "ui",
  "status": "pending|running|retrying|completed|failed|skipped",
  "attempt": 0,
  "started_at": null,
  "finished_at": null,
  "elapsed_seconds": null,
  "summary": "",
  "failure_reason": ""
}
```

- 每次请求开始、重试、结束都通过现有 `progress_callback` 落盘并更新 `current_step`。
- `retrying` 必须说明第几次重试和原因；不得长时间停留 `running` 而没有更新时间。
- 在 `outputs/{job_id}/ui_enhancement.json` 保存模型、风格令牌、步骤结果、耗时、失败原因和生成时间。
- `enhancement.json` 同步包含 `ui_plan`、`ui_steps`；两份产物字段不应互相矛盾。

### 2.3 失败语义

- `auto`：单个 UI 子步骤失败只回滚该步骤追加的 CSS，后续独立步骤继续；页面显示“部分 AI 增强完成”。
- `llm`：任一 UI 子步骤最终失败，恢复增强前的 `style.css` 和 README，任务进入失败。
- `template`：不请求 AI，不创建 UI 子步骤运行记录。
- 所有 UI 步骤失败时，`auto` 保留固定生成器项目并继续验证；状态必须明确为 AI 增强失败/未完成，不能伪装为 AI 成功。

## 3. 后端实施步骤

### Step A：完成 `enhancer.py`

1. 审计现有 `UI_ENHANCEMENT_STEPS`、Pydantic 模型、`_request_ui_plan()`、`_request_ui_step()`、`_enhance_ui_steps()` 的类型、调用顺序和未使用函数。
2. 修正 key 与展示层统一为上表 `ui_*` 名称；不要再把 UI 子步骤伪装成 `frontend/src/style.css` 文件节点。
3. 风格方案请求只发送规划摘要、`ui_plan`、模块 key/name 和受控 token hint；禁止发送完整项目源码。
4. 每个 CSS 请求只发送：当前步骤、允许 selector hint、风格令牌、style.css 最多 2400 字符尾部上下文、规划摘要。响应上限 8000 字符。
5. 保留 JSON 修复一次、HTTP 429/5xx/529 与读超时重试、子进程硬超时。新增重试回调，使 UI 步骤可见 `retrying`。
6. 校验 CSS：禁止 Vue/JS/HTML/API 片段，校验 selector 白名单和长度；不要用脆弱的全局字符串匹配误伤合法 CSS。
7. 每个步骤写入独立 marker，例如 `/* AI UI Enhancer: ui_shell ... */`。步骤失败只恢复该步骤开始前的 style.css 内容，不能撤销已经成功的前序步骤。
8. README 增强保持独立，不得阻塞 UI 进度；建议在 UI 步骤之后执行 README，确保前端先显示 UI 进度。
9. 删除或停用 `_build_style_enhancement()` 的“本地风格增强成功”路径；若保留本地 token，只能作为 fallback 数据，状态必须为 `skipped` 或 `failed`，并写清原因。

### Step B：完成 `workflow.py`

1. `enhance_generated_project()` 不再只根据 `ALLOWED_FILES` 初始化节点；应初始化五个 UI 节点和 README 节点。
2. 更新进度回调以 `event.key` 为主键，而不是 `event.file`；兼容 README 文件事件。
3. 每次事件更新 `codegen_enhance_steps`、`current_step` 和更新时间。摘要截断为适合前端展示的长度，但完整错误放入 `ui_enhancement.json`。
4. `enhance_project()` 返回后，写入 `enhancement.json` 和 `ui_enhancement.json`，并把 `ui_plan` / `ui_steps` 写回任务状态的必要摘要字段。
5. 不改变主状态机顺序：`planning -> project -> enhance -> run -> demo -> awaiting_demo_review`。AI UI 增强结束后仍必须执行生成项目前端构建、Maven 测试和 Demo 审查门禁。

### Step C：前端展示

1. `HomePage.vue` 使用 `key` 而非 `file` 作为步骤唯一键，并兼容历史任务的旧 `file` 数据。
2. 每个节点显示：名称、状态、尝试次数、耗时、简短摘要/错误；`running` 和 `retrying` 必须有明显视觉区分。
3. `codegenStatus` 文案要区分：全量 AI 完成、部分 AI 完成、AI 全部失败后保留模板、template 未启用。
4. 如需样式，仅修改工厂前端 `settings.css`，不要修改生成项目的 Vue 页面。

## 4. 验证策略

不要对每一个 CSS 小步骤运行一次完整 `npm install` 或完整前端构建；这会把 5 步放大成无意义的长等待。正确策略是：

1. 每步写入前做 JSON、长度、selector 和禁用片段校验。
2. 全部 UI 步骤结束后，由现有 `run` 阶段对生成项目前端执行一次真实构建。
3. 若最终构建失败，沿用当前 `auto` 回滚逻辑恢复增强前文件并重新验证；`llm` 模式失败。

必须新增或更新以下测试：

### `backend/tests/test_enhancer.py`

- 模拟 UI plan + 五个 UI CSS 响应，断言请求顺序、每步 marker、LLM token 被使用、README 独立执行。
- 断言每步 progress 顺序包含 `pending/running/retrying/completed`，重试次数正确。
- 某一步超时/429/坏 JSON：`auto` 只回滚该步骤、前序成功 CSS 保留、后续步骤继续。
- `llm` 模式任一步失败：恢复 style.css 和 README，抛出明确错误。
- 非法 selector、Vue/JS 片段、超长 CSS 被拒绝且不写入。
- 不允许请求/修改 `App.vue`、`router.js`、`views/*`。

### `backend/tests/test_workflow_order.py`

- `enhance_generated_project()` 初始化 UI 五步骤 + README 的结构。
- progress callback 能以 `key` 更新对应节点，保留尝试次数、耗时和错误摘要。
- `ui_enhancement.json` 和 `enhancement.json` 产物写入并包含一致的 UI 步骤摘要。
- 保持 Demo 在截图之前、Demo 审查在材料生成之前的原有断言。

### 手工验收

1. 用 `auto` 创建一个新任务，确认前端依次显示 5 个 UI 节点和 README 节点，长请求时可见 `running/retrying`。
2. 确认生成 Demo 的菜单、模块页面和路由仍可访问。
3. 检查 style.css 只包含追加的分步骤 marker，没有模型返回的 Vue/JS/HTML。
4. 确认生成项目 `npm.cmd run build` 通过；流水线 Maven 验证通过后进入 `awaiting_demo_review`。

## 5. 完成顺序

1. 先运行当前测试，记录基线失败/通过情况。
2. 完成 enhancer 的数据模型、LLM 子步骤、回调与按步回滚。
3. 接入 workflow 状态与产物落盘。
4. 接入 HomePage 进度展示。
5. 补齐单测，先运行增强器和 workflow 定向测试。
6. 运行后端全量测试、工厂前端构建、`git diff --check`。
7. 做一次真实任务手工验收；不要删除既有 `outputs/`，使用新 job ID。
8. 更新 `README.md`、`docs/FLOW.md`、`docs/ISSUE-020.md`、`AGENTS.md` 的最终状态与验证结果。

## 6. Claude 完成报告格式

完成后只报告：

1. 修改文件及每个文件的行为变化。
2. UI 子步骤实际协议和 `auto` / `llm` 失败语义。
3. 运行过的测试和结果。
4. 手工验收情况，或未能完成的原因。
5. 剩余风险。

不得提交、推送或清理现有工作区改动。
