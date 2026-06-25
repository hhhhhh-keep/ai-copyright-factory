# ISSUE-025：白名单仍漏 Element Plus 全家族 + 伪元素组合 + LLM 自创派生类

- 状态：`已修正，Codex 代码复审通过`
- 优先级：`P0`
- 首次记录：2026-06-24
- 关联：ISSUE-024（白名单与生成器实际 class 对齐，**仍有 3 类盲区**）

## 用户目标

- 复用本 ISSUE 暴露的 jobId planning 跑一次新任务，5 个 UI 子步骤至少有 4 个 `status=completed`。
- `frontend/src/style.css` 实际被 AI 修改，`codegen_actual_mode` 为 `"llm"` 而非 `"partial"`。
- 任何业务步都能覆盖 Element Plus 全家族（`.el-pagination` / `.el-checkbox` / `.el-radio` / `.el-select` / `.el-tooltip` 等）、Element Plus 内部类（`.btn-prev` / `.btn-next`）、派生类 + 伪元素组合（`.el-table--border::after`）、LLM 自创派生（`.dashboard-trend-card` / `.btn-primary` / `.m-trend-up`），不再被白名单误拒。

## 失败现场（ISSUE-024 落地之后新回归）

jobId=`20260624140839-03bb66f7`（涉案车辆管理系统，`public_security` 行业，`codegen_mode=auto`，`ui_plan.shell="top_workspace"`），ISSUE-024 实施后跑出新失败：

| # | 子步骤 | status | attempts | duration_ms | 失败选择器（实际 CSS 提取） | 根因分类 |
|---|---|---|---|---|---|---|
| 1 | theme | completed | 1 | 38077 | - | - |
| 2 | shell | completed | 2 | 311703 | - | - |
| 3 | business | **failed** | 2 | 402655 | `.el-table--border::after`, `.el-pagination`, `.el-pagination .btn-prev`, `.el-pagination .btn-next`, `.el-pagination .el-pager li` | whitelist_strict |
| 4 | dashboard | **failed** | 2 | 100358 | `.m-trend-up`, `.dashboard-trend-card`, `.dashboard-task_dashboard`, `.pattern-dashboard` | whitelist_strict |
| 5 | responsive | **failed** | 2 | 669936 | `.page-heading`, `.page-heading h2`, `.page-heading .actions`, `.page-heading .actions .btn-primary`, `.page-heading .actions .btn-ghost` | whitelist_strict |
| - | readme | completed | 0 | 0 | - | - |

`.learnings/ERRORS-20260624-enhance.md` 已自动记录 `ERR-20260624-122`，含 jobId。

任务最终 `actual_mode="llm"`（shell 步成功改了 style.css），但 style.css 只追加了 shell 步的 CSS，business / dashboard / responsive 3 步失败，UI 增强实际只有 1/5 步成功。

## 根因分析（ISSUE-024 没修完的 3 类）

### 根因 A Element Plus 全家族遗漏

ISSUE-024 P0-1 仅列举了 `.el-card--*` / `.el-button--*` / `.el-tag--*` / `.el-dialog--*`，**漏了**：

- **`.el-table--border`** 等其它 Element Plus 组件的 `--*` 修饰符（不止 `.el-button` / `.el-tag`）
- **`.el-pagination`** 整个组件基础类（分页组件在前端非常常用）
- **`.el-checkbox` / `.el-radio` / `.el-select` / `.el-tooltip` / `.el-message` / `.el-notification` / `.el-popover` / `.el-dropdown` / `.el-menu` / `.el-upload` / `.el-tabs`** 等业务步常用组件
- **`.btn-prev` / `.btn-next` / `.el-pager`** 等 Element Plus 2.x 渲染 `<el-pagination>` 时注入的内部类（不是 `__` BEM 派生，是历史命名）

LLM 在 prompt 自由发挥时按"哪个组件最常见"覆盖，必然踩坑。

### 根因 B 派生类 + 伪元素组合未特判

`.el-table--border::after` 由"派生类 + 伪元素"组成。ISSUE-024 在 `_selector_matches_hints` 特判了 `*::before/after`（裸 `*` + 伪元素），但**未处理** `.X::after` / `.X::before` / `.X:hover` / `.X:focus`。

实际上 `.el-table--*` 通配**已能匹配** `.el-table--border::after`（因 normalize 后 `.el-table--border::after`.startswith(`.el-table--`) 为真），但前提是 `.el-table--*` 必须**在白名单**——ISSUE-024 没把 `.el-table--*` 列入业务步 hints，导致 `.el-table--border::after` 被拒。

### 根因 C LLM 自创派生类生成器里没有

`selector_audit.collect_real_selectors` 扫描生成项目模板里**已经写入**的 class，但 LLM 在自己的响应里自由发挥的派生类生成器里没有：

- `.dashboard-trend-card` / `.dashboard-task_dashboard` / `.pattern-dashboard` / `.m-trend-up`——LLM 按"模块名 + 功能"拼出的派生
- `.btn-primary` / `.btn-ghost`——LLM 自定义按钮类
- `.page-heading .actions .btn-primary`——复合选择器中 LLM 把 `.btn-primary` 套进 page-heading 后代

`merge_with_hints` 启发式分类太窄（只按 `kpi` / `dashboard` / `trend` 等有限关键字），未覆盖 `.btn-*` / `.module-*` / `.form-*` / `.m-*` / `.pattern-*` / `.task-*` / `.stat-*` / `.metric-*` 等 LLM 自由命名空间。

## 修复方案（Claude 实施 2026-06-24）

### P0-1 业务步补 Element Plus 全家族 + 自定义按钮 + 模块派生通配

`backend/app/enhancer.py` `UI_STEP_SELECTOR_HINTS["business"]` 增量：

```python
".el-table--*",                        # ISSUE-025 漏补
".el-pagination", ".el-pager",
".btn-prev", ".btn-next",
".el-checkbox", ".el-checkbox--*", ".el-checkbox__*",
".el-radio", ".el-radio--*", ".el-radio__*",
".el-select", ".el-select--*", ".el-select__*",
".el-tooltip", ".el-tooltip__*",
".el-message", ".el-message__*",
".el-notification", ".el-notification__*",
".el-popover", ".el-popper",
".el-dropdown", ".el-dropdown__*", ".el-dropdown-menu",
".el-menu", ".el-menu__*",
".el-upload", ".el-upload__*",
".el-tabs", ".el-tabs__*",
# 自定义按钮
".btn-primary", ".btn-ghost", ".btn-default", ".btn-danger",
".btn-success", ".btn-warning", ".btn-info",
".btn-link", ".btn-text",
# 模块派生通配
".module-*", ".task-*", ".form-*",
".page-heading", ".actions",
```

### P0-2 dashboard 步补 LLM 派生通配

`UI_STEP_SELECTOR_HINTS["dashboard"]` 增量：

```python
".dashboard-*", ".m-*", ".pattern-*",
".trend-*", ".stat-*", ".metric-*",
".el-card", ".el-card__*", ".el-tag", ".el-tag--*",
```

### P0-3 responsive 步补 page-heading / actions / btn-*

`UI_STEP_SELECTOR_HINTS["responsive"]` 增量：

```python
".page-heading", ".actions",
".btn-primary", ".btn-ghost", ".btn-default",
```

### P0-4 selector_audit 启发式关键字扩展

`backend/app/selector_audit.py` `merge_with_hints` 关键字扩展：

```python
business_keywords = (
    "el-card", "el-button", "el-table", "el-tag", "el-form",
    "el-dialog", "el-input", "el-pagination", "el-checkbox",
    "el-radio", "el-select", "el-tooltip", "el-message",
    "el-popover", "el-dropdown", "el-menu", "el-upload", "el-tabs",
    "module-page", "toolbar", "filter-bar", "status-pill",
    "master-detail", "tree-detail", "kanban",
    "btn-primary", "btn-ghost", "btn-default", "btn-danger",
    "module-", "task-", "form-",
)
dashboard_keywords = (
    "kpi", "dashboard", "trend", "donut", "bar-svg", "donut-svg",
    "trend-svg", "metric-grid", "activity-panel", "status-panel",
    "m-", "pattern-", "stat-", "metric-",
)
responsive_keywords = (
    "@media", "max-width", "min-width",
    "page-heading", "actions",
)
```

### P1 测试覆盖（`backend/tests/test_enhancer.py` 新增 4 项；后续 ISSUE-026 后总计 35/35 全过）

1. `test_business_allows_pagination_and_pseudo_element`——验证 `.el-table--border::after` + `.el-pagination` + `.btn-prev` 全部通过。
2. `test_dashboard_allows_llm_derived_selectors`——验证 `.dashboard-trend-card` + `.m-trend-up` + `.pattern-dashboard` + `.dashboard-task_dashboard` 通过。
3. `test_business_allows_custom_button_classes`——验证 `.btn-primary` / `.btn-ghost` / `.module-vehicle-archives .task-list` / `.form-search-bar` 通过。
4. `test_responsive_allows_page_heading_and_actions`——验证 `@media (max-width:768px)` + `.page-heading` + `.actions` + `.btn-primary` / `.btn-ghost` 通过。

### P2 文档同步（用户硬性约束）

- `AGENTS.md` 顶部说明 + 已完成升级加 ISSUE-025 条目。
- `README.md` 顶部"实现状态说明"加 ISSUE-025 增量。
- `docs/FLOW.md` enhance 阶段描述更新（ISSUE-025 在 ISSUE-024 之上）。
- `docs/ISSUE-020.md` 追加"运行时回归修正（2026-06-24 第二次，ISSUE-025 关联）"小节。

## 验证

```bash
cd "C:\Users\whn\Documents\软著\backend"
python -m unittest discover -s tests
```

预期：`Ran 153 tests in ~25s`（原 149 + ISSUE-025 新增 4 项）。

```bash
cd "C:\Users\whn\Documents\软著\frontend"
npm.cmd run build
```

预期：exit 0，无新增 warning。

```bash
cd "C:\Users\whn\Documents\软著"
git diff --check
```

预期：exit 0，无 trailing whitespace。

## 剩余风险

- LLM 仍可能写出"完全意料之外"的派生命名空间（白名单"白盒 + 启发式 + 通配"模式注定滞后）。当前缓解靠 `_ALLOWED_CSS_CHARS` 字符扫描 + `UI_STEP_FORBIDDEN_SELECTORS` 越界禁片 + 实际 `npm run build` 验证兜底。
- 大幅放宽白名单（`.dashboard-*` / `.m-*` / `.pattern-*` 等）可能掩盖 prompt 越界。需配合 `Issue-025` 的字符扫描与禁片一起生效，单靠白名单不够稳。
- `selector_audit.audit_drift` 当前只在 `.learnings/ERRORS-YYYYMMDD-selector-drift.md` 写漂移告警，未在 CI 中定期执行。

## 落地触发条件

按用户硬性约束"问题收集期不修业务代码，等用户'统一修改'命令"——本次由用户在 ISSUE-024 落地后报告"其他四个UI步骤还是有报错"，触发"立即修"指令，已一次性落地。
