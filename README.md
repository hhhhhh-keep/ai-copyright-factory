# AI软著工厂 V1.0

AI软著工厂用于从软件名称、行业、软件类型和描述出发，生成可运行的 Java Demo 项目及软件著作权申报材料。

系统会先检索行业知识库，再由 Planner 生成结构化规划。用户确认规划后，系统生成并运行项目，启动在线 Demo 等待人工审查。只有用户确认 Demo 符合预期后，系统才会继续截图、文档、合规检查和 ZIP 打包。

## 当前能力

- 支持公安、政法、工业、教育四类行业知识库。
- 根据行业、软件类型、名称和描述自动生成相关业务模块。
- 在 Planning Review 中增删改模块、页面、字段、数据库表和 UI 结构。
- 生成 Java 17、Spring Boot 3、MyBatis Plus、MySQL、Vue 3、Element Plus 项目。
- 每个业务模块生成 Entity、DTO、VO、Mapper、Service、ServiceImpl、Controller、API、Vue 页面和 SQL 表。
- 自动执行前端生产构建、Maven 测试及项目运行验证。
- 使用 H2 Demo 配置启动在线演示，生产配置仍使用 MySQL。
- Demo 审查通过后自动截图并生成软著材料。
- Demo 不符合预期时，可通过自然语言修改规划并重新生成项目。
- 保存规划历史版本，支持查看和恢复旧版本。
- 历史任务支持查看、继续审查、启动 Demo、下载和删除。
- 生成一致性与合规报告、申请信息表及最终申报包。

## 核心流程

```text
填写软件信息
→ 检索行业知识库
→ AI 生成 planning.json
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
AI_PLANNER_MODE=auto
AI_PLANNER_BASE_URL=https://api.openai.com/v1
AI_PLANNER_API_KEY=你的密钥
AI_PLANNER_MODEL=实际可用的模型名称
AI_PLANNER_TIMEOUT=60

AI_CODEGEN_MODEL=
AI_CODEGEN_TIMEOUT=90
```

Planner 模式：

- `auto`：优先使用 LLM，调用失败时回退内置模板。
- `llm`：只使用 LLM，调用或结构校验失败则终止。
- `template`：只使用内置行业模板。

代码生成模式：

- `auto`：执行 AI Code Enhancer，验证失败时回滚到稳定模板。
- `llm`：强制执行代码增强，验证失败则终止任务。
- `template`：只使用确定性项目生成器。

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
