# ISSUE-024：白名单与生成器实际 class 失配,split_console / dashboard / Element Plus BEM 派生类未覆盖

- 状态：`已由 ISSUE-025/026 覆盖并落地`
- 优先级：`P0`
- 首次记录：2026-06-24
- 关联：ISSUE-023（已落地的白名单 + retry + actual_mode 修复，本次新发现其未覆盖的失配）
- 复现任务：`20260624095339-9d44c135`（涉案车辆管理系统，`public_security` 行业，`codegen_mode=auto`）

## 用户目标

- 5 个 UI 子步骤至少有 4 个 `status=completed`，避免 `codegen_actual_mode=partial` 仅靠 README 增强。
- AI 增强应能修改生成器**实际渲染**的 class（含 Element Plus BEM 派生类、响应式断点、`split_console` 壳层的 `.shell-split`/`.shell-main`），而不是只覆盖代码注释里出现的少量"白名单 class"。
- 白名单变更必须可审计、可回滚，避免一刀切放宽导致 LLM 越界写 `<router-view>` 等破坏壳层的代码。

## 当前实现与失败现场

ISSUE-023 已落地的关键事实：

- `_selector_matches_hints` 在 `UI_STEP_SELECTOR_HINTS[step_key]` + `GLOBAL_UI_SELECTOR_HINTS = (":root", "--ai-")` 内做前缀匹配。
- `ui_enhancement.json` / `status.json` 已能逐项记录每步 attempts / duration_ms / failure_reason / selectors。
- `codegen_actual_mode` 新增 `partial` 字面值：style.css 未改但 README 改了 → `partial`，jobId=20260624095339 命中此分支，任务继续停在 `awaiting_demo_review`。
- `_record_enhance_failure` 在 enhance_project 三个 return 路径前各调用一次；`backend/app/learning.py` 已自动写 `.learnings/ERRORS-20260624-enhance.md` ERR-20260624-049。

新回归（jobId=20260624095339-9d44c135）的 4 步失败：

| # | 子步骤 | attempts | duration_ms | 未授权选择器（实际 CSS 提取） | 根因分类 |
|---|---|---|---|---|---|
| 1 | shell | 2 | 284422 | `*`, `html`, `@media(max-width:900px)`, `.shell-split`, `.shell-main` | whitelist_strict |
| 2 | business | 2 | 550155 | `.el-card__header`, `.el-card__header span`, `.el-card__body`, `.el-button--success`, `.el-button--warning` | whitelist_strict |
| 3 | dashboard | 2 | 931375 | `.kpi-grid`, `.kpi-trend`, `.kpi-trend-down .kpi-trend`, `.kpi-spark`, `.dashboard-row` | whitelist_strict |
| 4 | responsive | 2 | 115000 | `.dashboard-row`, `.kpi-grid`(×2), `.module-dashboard`(×2) | whitelist_strict |

`theme` 步成功，`readme` 步成功。`status=awaiting_demo_review`、`run_validation` 全 passed、`run_status=stopped`（ISSUE-023 P1-3 worker 清理生效），但 `codegen_changed_files=["README.md"]`，`frontend/src/style.css` 实际未增强，`codegen_actual_mode="partial"`。任务未真失败，**但 style.css 未增强是用户可见的退化**。

## 根因分析（已逐条与代码核对）

### 根因 A：白名单与生成器实际 class 严重失配

`backend/app/project_generator.py` 实际生成的 CSS / 模板里出现的关键 class（grep 行号已核）：

| 实际生成器 class | 来源 | 出现在 |
|---|---|---|
| `kpi-card`, `kpi-trend-{trend_dir}`, `kpi-trend` | dashboard KPI 卡片 | [project_generator.py:2195](backend/app/project_generator.py#L2195), [project_generator.py:2198](backend/app/project_generator.py#L2198) |
| `kpi-row`, `kpi-grid` | dashboard 容器 | [project_generator.py:2205](backend/app/project_generator.py#L2205), [project_generator.py:2215](backend/app/project_generator.py#L2215), [project_generator.py:2224](backend/app/project_generator.py#L2224) |
| `dashboard-row` | dashboard 行容器 | [project_generator.py:2225](backend/app/project_generator.py#L2225), [project_generator.py:2229](backend/app/project_generator.py#L2229) |
| `module-dashboard` | module page dashboard 模式 | [project_generator.py:2311](backend/app/project_generator.py#L2311) |
| `shell-top` | top_workspace 壳层 | [project_generator.py:2274](backend/app/project_generator.py#L2274), [project_generator.py:2304](backend/app/project_generator.py#L2304) |
| `shell-split` | split_console 壳层 | [project_generator.py:2281](backend/app/project_generator.py#L2281), [project_generator.py:2311](backend/app/project_generator.py#L2311) |
| `shell-aside` | sidebar_admin 壳层（待 grep 复核） | 模板推断 |
| `@media(max-width:1000px)` | 内嵌响应式断点 | [project_generator.py:2311](backend/app/project_generator.py#L2311) |

当前白名单（[enhancer.py:50-87](backend/app/enhancer.py#L50-L87)）覆盖不到：

- `dashboard` 步 hint 用了 `".metric-grid" / ".kpi-card" / ".kpi-icon"`，但生成器实际是 `.kpi-grid` / `.kpi-trend` / `dashboard-row`。LLM 想覆盖 KPI 卡趋势箭头 → `.kpi-trend` / `.kpi-trend-down .kpi-trend` → 被拒。
- `dashboard` 步还列了 `".activity-panel" / ".status-panel"`，**生成器里没有这两个 class**——LLM 只能用近似 `.dashboard-row` 表达，但被拒。
- `responsive` 步补了 `.el-button` 等 Element Plus 基础类，但 dashboard 步没补；responsive 步 hints 没有 `.kpi-grid` / `.dashboard-row` / `.module-dashboard`，LLM 在 responsive 步也会用到这些。
- `shell` 步 hint 没有 `.shell-split` / `.shell-main`，split_console 壳层必然失败。
- `shell` 步 hint 没有 `@media`，但 split_console / top_workspace 模板都内嵌 `@media` 响应式断点；LLM 想覆盖 900px 屏宽就报"未授权 `@media(max-width:900px)`"。

### 根因 B：`html` 与 `*` 未进 GLOBAL_UI_SELECTOR_HINTS

LLM 表达"全局基础"几乎只能用 `html { font-family: ... }` 或 `* { box-sizing: border-box }`：

- 当前 `GLOBAL_UI_SELECTOR_HINTS = (":root", "--ai-")` 只覆盖 CSS 变量声明。
- `html` / `*` 是任何 UI 步都可能用到的"基础目标"，按"全局允许"语义应收录。
- ISSUE-023 没补这两条，导致 shell 步直接挂掉。

### 根因 C：Element Plus BEM 派生类未覆盖

生成项目里 `<el-card>` / `<el-button>` 会被 Element Plus 渲染成 `<div class="el-card"><div class="el-card__header">...<div class="el-card__body">...`，`<el-button type="success">` 会渲染成 `<button class="el-button el-button--success">`：

- 当前白名单仅覆盖了 Element Plus **基础类**（`.el-card` / `.el-button` / `.el-input` 等，ISSUE-023 P0-1 增量）。
- **派生类**（`.el-card__header` / `.el-card__body` / `.el-button--success` / `.el-button--warning` / `.el-button--danger` / `.el-button--info` / `.el-tag--success` / `.el-tag--warning` / `.el-table__row` / `.el-dialog__header` 等）未覆盖。
- LLM 想定制 Element Plus 主题色（如按钮 success/warning）会被业务步白名单拒。
- **风险**：Element Plus 派生类是无穷集合（每个组件 × 每个修饰符），完全放开等于放开整个 Element Plus；建议采用"前缀 + 通配 `__` 修饰符"白名单：`.el-card__*` / `.el-button--*` / `.el-tag--*` / `.el-table__*` / `.el-dialog__*` 等。

### 根因 D：dashboard / responsive 步 hints 与实际生成器 class 不对称

- `dashboard` hints 期望 `.metric-grid`，但生成器 `.kpi-grid`。
- `dashboard` hints 期望 `.trend-panel`，但生成器实际生成 `.trend-panel` ✓ 这个**有**；缺的是 `.kpi-row` / `.dashboard-row` / `.kpi-trend` / `.kpi-spark`。
- `responsive` hints 期望 `.module-dashboard`，但生成器实际也有 `.module-dashboard` ✓；缺的是 `.kpi-grid` / `.dashboard-row` / `.status-row` / `.analysis-workbench` / `.shell-split` 等小屏布局 class。

**核心问题**：白名单是**手写**的（按代码注释里的"理想 class"），而**生成器**才是 class 真正的来源。两者不同步时 LLM 必然踩坑。

## 修复方案（已由后续 ISSUE 覆盖落地）

本 ISSUE 最初只做问题收集，随后用户已授权继续处理，核心修复在 ISSUE-024 代码落地后又被 ISSUE-025/026 继续补齐：

- ISSUE-024：白名单与生成器实际 class 对齐、全局 `html` / `*`、Element Plus BEM 通配、`selector_audit.py` 和 CSS 字符扫描。
- ISSUE-025：补 Element Plus 全家族、LLM 自创派生类、自定义按钮和响应式 page-heading/actions。
- ISSUE-026：修正 daemon timeout 与空 CSS skipped 兜底。

以下为当时拟定方案，保留供追溯。

### P0-1 白名单与生成器 class 对齐

**文件**：`backend/app/enhancer.py`

按 `project_generator.py` grep 出的实际 class，逐个对齐 `UI_STEP_SELECTOR_HINTS`：

```python
"theme": (
    ":root", "--ai-", "body", "html", "*",
    ".login-page", ".hero", ".shell",
    ".el-header", ".el-aside", ".context-panel",
),
"shell": (
    ".login-page", ".login-brand", ".login-card", ".hero",
    ".shell-top", ".shell-top>header", ".shell-top nav",
    ".shell-aside", ".shell-aside .menu", ".el-aside",
    ".shell-split", ".shell-main",     # split_console 壳层
    ".page-heading", "body", "header",
    "@media",                            # 壳层响应式断点
),
"business": (
    ".el-card", ".el-card__header", ".el-card__body",   # Element Plus 派生
    ".el-table", ".el-table__row",
    ".el-button", ".el-button--primary", ".el-button--success",
    ".el-button--warning", ".el-button--danger", ".el-button--info",
    ".el-tag", ".el-tag--success", ".el-tag--warning", ".el-tag--danger",
    ".el-input", ".el-form", ".el-dialog", ".el-dialog__header", ".el-dialog__body",
    ".modal",
    ".filter-bar", ".toolbar", ".status-pill", ".kpi-card",
    ".module-page", ".master-detail-preview", ".tree-detail-preview",
    ".kanban-preview",
),
"dashboard": (
    ".kpi-grid", ".kpi-row",                # 实际生成器 class（替换 .metric-grid）
    ".kpi-card", ".kpi-trend", ".kpi-trend-up", ".kpi-trend-down", ".kpi-spark",
    ".dashboard-row", ".module-dashboard",  # 实际生成器 class
    ".trend-panel", ".trend-svg",
    ".bar-panel", ".bar-svg",
    ".donut-panel", ".donut-svg",
    ".activity-panel", ".status-panel",
    ".status-row", ".analysis-workbench",
    ".dashboard",
),
"responsive": (
    "@media", "body", "html", "*",
    ".shell-top", ".shell-aside", ".shell-split", ".shell-main",
    ".module-dashboard", ".module-page",
    ".kpi-grid", ".kpi-row", ".dashboard-row",
    ".status-row", ".analysis-workbench",
    ".toolbar", ".el-card", ".el-table",
    ".login-page", ".hero", ".dashboard",
    "input", "button", "select", "textarea",
    ":focus", ":hover",
    ".el-button", ".el-button--primary", ".el-input", ".el-tag",
    ".el-form", ".el-dialog",
),
```

`GLOBAL_UI_SELECTOR_HINTS` 补 `html` 与 `*`：

```python
GLOBAL_UI_SELECTOR_HINTS: Tuple[str, ...] = (":root", "--ai-", "html", "*")
```

`_selector_matches_hints` 的 `*` 匹配需特判：仅当 normalized 形如 `*` 或 `*::before` / `*::after` 等通用重置选择器时放行；避免 LLM 用 `*[attr]` 越界。

### P0-2 系统化白名单来源

**长期**：将白名单从"手写常量"改成"由 `project_generator.py` 自动扫描 Vue 模板生成"。

最小可用版本：

- 新建 `backend/app/selector_audit.py`，导出 `collect_real_selectors(project_root) -> Set[str]`，遍历 `generated_project/frontend/src/views/*.vue` 与 `*.html` 的 `class=` 属性 + `style.css` 的规则选择器，汇总。
- 在 `enhance_project` 入口调用一次，合并入 `UI_STEP_SELECTOR_HINTS[step_key]`。
- 用 hash 比对生成器版本（`project_generator.py` 的 git rev）与白名单集合，发现漂移则在 `.learnings/` 写一条告警。
- **风险**：扫描 `views/*.vue` 会引入大量 LLM 越界入口（如 `<router-view>` 内部 class），建议只扫描项目生成器**自身**模板里的 class，不扫 Vue 运行时注入的 class。

### P0-3 LLM 越界防御强化（不依赖白名单放宽）

放宽白名单的同时，必须保证 LLM 不能越界写：

- `UI_STEP_FORBIDDEN_SELECTORS`（[enhancer.py:94-98](backend/app/enhancer.py#L94-L98)）继续保留，新增：
  - `v-on:click` / `@click="` 等显式 Vue 事件绑定（防止 LLM 把 JS 混进 CSS）
  - `import ` / `export ` / `require(` 等 JS 关键字
  - `function(` / `=> {` 等函数体特征
  - `${...}` 等模板字符串（防止 LLM 写 CSS-in-JS）
- `_validate_ui_block` 增加"内容字符集合"扫描：只允许 `{}[]:;,.-_#%()abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 \n\t/*"` 之外直接拒绝。
- 这与放宽白名单**并行不悖**：白名单放宽解决"合法 class 被误拒"，禁片解决"非法 JS / Vue 代码被写入"。

### P1-1 `.learnings/` 自动记录已生效

`.learnings/ERRORS-20260624-enhance.md` ERR-20260624-049 已记录本次失败：

```
### ERR-20260624-049 · jobId=20260624095339-9d44c135 · codegen_mode=auto
- 失败子步骤：shell, business, dashboard, responsive
- 根因分类：whitelist_strict(shell, business, dashboard, responsive)
- fallback_reason：应用壳层：ValueError: UI 子步骤 shell CSS 内容包含未授权选择器: ['*', 'html', '@media(max-width:900px)', '.shell-split', '.shell-main']...
```

**ISSUE-023 P1-1 实施发现的小缺陷**：`learning.py` 写死的"修复建议"链接是 `../docs/ISSUE-022.md`，但 ISSUE-022 实际是截图抓拍时机。Issue-024 实施时应一并把链接改为 `../docs/ISSUE-024.md`，或参数化（让调用方传入相关 ISSUE 编号）。

### P1-2 测试覆盖

`backend/tests/test_enhancer.py` 新增 7 项：

1. `test_shell_allows_split_console_selectors` — `split_console` 壳层 CSS 含 `.shell-split`、`.shell-main`、`.shell-main>aside`、`.shell-split .menu`，全部 allowed。
2. `test_shell_allows_html_and_universal_selectors` — `html { ... }` 与 `* { box-sizing: border-box }` 通过 `GLOBAL_UI_SELECTOR_HINTS`。
3. `test_shell_allows_at_media_query` — `@media(max-width:900px) { .shell-top {...} }` 通过；`@media` 应在所有 5 步均允许（不止 responsive）。
4. `test_business_allows_element_plus_bem_modifiers` — `.el-card__header` / `.el-card__body` / `.el-button--success` / `.el-button--warning` / `.el-tag--danger` / `.el-dialog__header` 通过。
5. `test_dashboard_allows_real_generator_selectors` — `.kpi-grid` / `.kpi-trend` / `.kpi-trend-down .kpi-trend` / `.kpi-spark` / `.dashboard-row` 通过；`.metric-grid`（旧的错误命名）不再使用。
6. `test_responsive_allows_dashboard_layout_selectors` — responsive 步接受 `.kpi-grid` / `.dashboard-row` / `.module-dashboard` / `.status-row` / `.analysis-workbench`。
7. `test_forbidden_selectors_still_rejected_after_whitelist_expansion` — 放宽白名单后，`<router-view`、`@click="`、`import App from` 仍被 `UI_STEP_FORBIDDEN_SELECTORS` 拒。

调整既有 1 项：
- `test_responsive_allows_basic_selectors` 增补对 `*` 和 `html` 的断言（验证全局允许生效）。

### P1-3 文档同步（用户硬性约束，等「统一修改」命令落地）

按用户协议"任何流程/状态/ISSUE 变更必须同步 AGENTS.md、README.md、docs/ISSUES.md、docs/FLOW.md"：

- `AGENTS.md` 顶部说明 + 已完成升级加 ISSUE-024 条目；强调"白名单与生成器 class 对齐是 ISSUE-024 的核心"。
- `README.md` 顶部"实现状态说明"加 ISSUE-024 增量，列出新白名单范围与 `*` / `html` 全局允许。
- `docs/FLOW.md` enhance 阶段描述更新：明确白名单按生成器实际 class 维护，列举本次新增的关键 class 群（split_console 类、kpi-trend 类、Element Plus BEM 派生类）。
- `docs/ISSUES.md` 末尾追加 ISSUE-024 章节（与本 ISSUE 文件配套）。
- `docs/ISSUE-020.md` 追加"运行时回归修正（2026-06-24 第二次，ISSUE-024 关联）"小节，引用本 jobId。

### P1-4 系统化白名单后续（不在本次范围）

- 把白名单提取到 `backend/app/selector_audit.py`，由 CI 校验白名单漂移。
- 引入"白名单 / 黑名单"双清单机制：白名单 + 黑名单都做正则匹配，黑名单优先。
- 前端 `HomePage.vue` 需支持 `actual_mode=partial` 展示（ISSUE-023 已记录剩余风险，ISSUE-024 实施时可一并补）。

## 关键文件清单

| 文件 | 修改范围 |
|---|---|
| [backend/app/enhancer.py](backend/app/enhancer.py) | P0-1 全局白名单 + 4 步 hints 与生成器对齐；P0-3 `_validate_ui_block` 字符集合扫描；`UI_STEP_FORBIDDEN_SELECTORS` 增 Vue 事件/JS 关键字 |
| [backend/app/learning.py](backend/app/learning.py) | P1-1 把"修复建议"链接改为可参数化（ISSUE 编号由调用方传） |
| [backend/app/project_generator.py](backend/app/project_generator.py) | 不改业务；仅作为"实际 class 来源"的参考 |
| [backend/tests/test_enhancer.py](backend/tests/test_enhancer.py) | P1-2 新增 7 项 + 调整 1 项 |
| [docs/ISSUE-024.md](docs/ISSUE-024.md)（新建） | 本文档 |
| [docs/ISSUES.md](docs/ISSUES.md) | 末尾追加 ISSUE-024 章节 |
| [AGENTS.md](AGENTS.md) | 顶部说明 + 已完成升级（统一修改后同步） |
| [README.md](README.md) | 顶部实现状态说明（统一修改后同步） |
| [docs/FLOW.md](docs/FLOW.md) | enhance 阶段描述（统一修改后同步） |
| [docs/ISSUE-020.md](docs/ISSUE-020.md) | 第四次运行时回归修正小节（统一修改后同步） |

## 风险与依赖

1. **`*` 放行可能被滥用**：LLM 用 `* { display:none }` 等破坏性全局规则。缓解：禁片 + 字符集合扫描 + 单步 size 16000 + 实际生成的前端构建（破坏性 CSS 会让 `npm run build` 失败，回滚）。
2. **Element Plus BEM 派生类前缀放行风险**：建议用"前缀+通配符"（`.el-card__*`），而非逐个枚举。但 Python 端 `_selector_matches_hints` 是字面前缀匹配，需扩展为支持 `__*` 通配。
3. **`project_generator.py` 改 class 名时白名单同步滞后**：ISSUE-024 P0-2 的系统化白名单是长期方案，本次仅手动对齐。
4. **`actual_mode=partial` 仍是合法状态**：jobId=20260624095339 任务**未真失败**，`status=awaiting_demo_review`，用户可继续使用 Demo、生成材料。本次修复目标是让 `actual_mode` 回到 `llm` 而非 `partial`，但 `partial` 的兜底语义本身是正确的（ISSUE-023 P0-5 已落地）。
5. **`@media` 在 shell 步放开后 LLM 可能写到无意义媒体查询**：仍由 `_validate_ui_block` 的内容扫描 + 实际 style.css 构建验证兜底。

## 验收标准

- 复用本 job planning 跑一次新任务，5 个 UI 子步骤 `status=completed` 数 ≥ 4。
- `codegen_actual_mode` 回到 `llm`（不再是 `partial`）；`frontend/src/style.css` 含 ≥ 3 个 `AI UI Enhancer:` marker。
- `.learnings/ERRORS-YYYYMMDD-enhance.md` 不再出现 `whitelist_strict(shell|business|dashboard|responsive)` 条目（除非新类未覆盖）。
- 既有 18 项 `test_enhancer.py` 测试不退；新增 7/7 通过。
- 4 份交接文档（AGENTS.md / README.md / docs/ISSUES.md / docs/FLOW.md）与本 ISSUE 同步更新。
- 用户可看到 `frontend/src/style.css` 实际包含 AI 增强的 CSS 块（用浏览器开发者工具检查 `AI UI Enhancer: shell · ...` 注释）。

## 落地触发条件

按用户硬性约束"问题收集期不修业务代码，等用户'统一修改'命令"：

- 本 ISSUE**待执行**，先不入业务代码、不改 `AGENTS.md` / `README.md` / `docs/FLOW.md`。
- 用户给出"统一修改"命令后，按 P0-1 → P0-2 → P0-3 → P1-1 → P1-2 → P1-3 顺序落地。
- 每落地一项，跑 `python -m unittest discover -s tests` 一轮，失败立即停止。
- 全部 P0 + P1 完成后，跑端到端验证 + git diff --check + 4 份交接文档一致性检查。
