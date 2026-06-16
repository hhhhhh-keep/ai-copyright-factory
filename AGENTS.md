# AI软著工厂交接入口

本文件供新的 Codex 窗口、开发者或自动化代理快速接手项目。开始工作前按顺序读取：

1. `README.md`：当前产品能力、启动方式和使用流程。
2. `docs/ISSUES.md`：用户反馈、已完成升级、验证结果和剩余风险。
3. `docs/FLOW.md`：真实代码流程、状态机、接口和关键文件。

## 当前项目结论

- 首页已取消“需求澄清”和固定行业模块预选。
- Planner 完全由 LLM 驱动，直接根据软件名称、类型和描述生成模块；行业类型（公安/政法/工业/教育）仅作为普通提示信息和任务记录，Planner 不读取行业知识库、不做行业白名单校验、不回退模板。
- Planner 首次返回坏 JSON / 校验失败时自动修复一次；二次仍失败或 API 不可用时任务进入 `failed`，由用户在前端点击“重新生成规划”，使用原 job ID 复位步骤后重试。
- 返工对话 `propose_revision()` 同步 LLM-only，失败提示重试，不使用规则改写。
- 行业基础映射（内部编码 → 显示名）保留在 `backend/app/planner.py` 的 `INDUSTRY_DISPLAY_NAMES` 与 `industry_name_for()` 中，仅用于把行业提示从编码转换为显示名，不参与校验。
- Planning Review 是模块、页面、字段、数据库表和 UI 结构的唯一人工审核入口。
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
- REGRESSION-001：Maven 校验强制使用 JDK 17 环境，解决 `61.0 / 52.0` 类版本错误。

ISSUE-001 已被 ISSUE-002 取代，不应恢复旧的行业模块预选功能。

## 当前待修

- ISSUE-010（P1）：Dashboard 页面视觉表达不足，需增强数据驾驶舱图形化展示。
- ISSUE-011（P1）：源码材料原创性增强与业务化注释，需补 `project_fingerprint.json` / `originality_report.json` 和业务化注释策略。

## 最近验证

- 后端单元测试：86 项通过。
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
- 行业基础映射（保留供历史参考，Planner 不再导入）：`backend/app/industry_knowledge.py`
- 首页与 Demo 审查：`frontend/src/pages/HomePage.vue`
- Planning Review：`frontend/src/pages/PlanningReviewPage.vue`
- 历史任务：`frontend/src/pages/HistoryPage.vue`
- 行业基础映射文件：`industry_knowledge/*.json`
