# AI 软著工厂 V1.0 - 问题与交接记录

> 用途：跨 Codex 窗口保留项目现状、用户反馈、实现结论和验证结果。
> 当前结论：ISSUE-002 至 ISSUE-013 已完成；其中 ISSUE-008 L1 已由 Claude 实施并通过 Codex 二次复审；REGRESSION-001 已完成验证。当前仍需回归：Demo 超时回收、失败日志和运行中任务删除限制。

## 问题处理约定

- 用户指出新问题后，先复现并分析原因，不直接修改业务代码。
- 与用户讨论并确认处理流程、修复范围、风险和验收标准后，再完善对应 ISSUE。
- 问题收集期间只更新 ISSUE 与交接文档。
- 只有用户明确发布“统一修改”、明确指定实施某个 ISSUE，或给出等价开发命令后，才进入代码修改和测试阶段。
- 未收到实施命令时，任何 ISSUE 均保持记录状态，不因原因已经明确而提前修复。

## 当前版本基线

- 仓库：`https://github.com/hhhhhh-keep/ai-copyright-factory.git`
- 分支：`main`
- 当前基线提交：`00eceb78b1ea23891a377f547e4be7112610064e`
- 提交说明：`Update issue log with UI and workflow changes`
- 基线时间：`2026-06-15 16:27:25 +0800`
- 记录创建日期：`2026-06-15`
- 当前工作区包含本轮 ISSUE 升级代码与文档的未提交修改，接手时先执行 `git status --short`，不得擅自回滚。

## 当前项目能力

- 前端：Vue 3，开发地址 `http://localhost:5173/`
- 后端：FastAPI，默认地址 `http://localhost:8000/`
- 生成项目：Java 17、Spring Boot 3、MyBatis Plus、MySQL、Vue 3、Element Plus
- 当前支持行业：公安、政法、工业、教育
- 核心流程：AI 规划 -> Planning Review -> 项目生成 -> 运行验证 -> 在线 Demo 人工审查 -> 通过后截图和材料生成，或对话返工后重新审查
- 已有页面：首页、规划确认页、历史任务页
- 任务产物位于：`outputs/{job_id}/`

## Issue 状态与实现记录

### ISSUE-001：需求澄清始终显示公安模块（已被 ISSUE-002 取代）

- 状态：`不单独修复`
- 取代关系：`ISSUE-002`
- 发现位置：首页“行业模块确认”区域
- 现象：更换软件名称或软件描述后，仍然显示警情管理、案件管理、车辆管理、视频巡查、布控预警、统计研判等公安模块。
- 原因：
  - 首页将 `form.industry_type` 默认写为 `public_security`。
  - 请求 `/api/clarifications` 时始终提交该显式行业值。
  - 后端优先信任显式行业，因此不会根据软件名称和描述重新识别行业。
- 处理结论：
  - 不再修补首页模块预选逻辑。
  - 按 `ISSUE-002` 整体删除“生成需求澄清”和“行业模块确认”。
  - 模块改由 Planner 根据用户选择的行业、软件类型、名称和描述生成。
  - 用户统一在 Planning Review 中审核和修改模块。
- 保留本条仅用于记录问题来源，不纳入独立开发任务和验收项。

### ISSUE-002：简化模块规划与审核流程

- 状态：`已实现`
- 优先级：`P0`
- 目标：取消首页的行业模块预选，由大模型生成模块，用户在 Planning Review 中统一审核。
- 目标流程：
  1. 用户填写软件名称、软件描述、行业类型和软件类型。
  2. Planner 必须先读取所选行业知识库。
  3. 大模型结合行业、软件类型、软件名称和描述，自动生成 3-8 个相关功能模块及页面、字段和数据库表。
  4. 系统生成 `planning.json` 并进入 Planning Review。
  5. 用户可在 Planning Review 中新增、删除、修改模块及相关设计。
  6. 用户确认后锁定 `planning.json`，后续代码、截图和文档统一以其为准。
- 首页调整：
  - 删除“生成需求澄清”按钮。
  - 删除“行业模块确认”及模块勾选区域。
  - 创建任务时不再要求至少勾选 3 个行业模块。
- Planner 调整：
  - 行业知识库仍是强制检索上下文，禁止完全脱离知识库自由生成。
  - 不再要求大模型输出首页预先确认的全部模块。
  - 应根据软件类型和描述，从行业知识库中选择最相关模块并形成规划。
- Planning Review 调整：
  - 作为唯一的模块审核入口。
  - 允许用户增加、删除、重命名模块，以及修改模块描述、页面、字段和数据库设计。
  - 用户保存的人工调整视为最终规划，不应再被首页模块白名单拦截。
- 验收标准：
  - 首页不再展示模块确认区域。
  - 同一行业下，不同软件名称、类型和描述能生成有差异的相关模块。
  - 用户可在 Planning Review 完成模块增删改并成功保存。
  - 确认后的项目、截图和文档与最终 `planning.json` 一致。
- 实现结果：
  - 首页已删除“生成需求澄清”和行业模块预选区域。
  - Planner 根据行业知识库、软件类型、名称和描述生成规划。
  - Planning Review 支持模块、页面、字段、数据库表和 UI 模式增删改。
  - 人工保存的规划不再被首页模块白名单拦截。
  - 模块与数据库表保持一一对应并进行模型校验。

### ISSUE-003：基于成熟开源项目建立多原型 UI 生成体系

- 状态：`已实现第一阶段`
- 优先级：`P1`
- 背景：当前生成项目共用同一套后台页面骨架，仅改变名称、模块和少量样式，导致不同项目的 UI、截图和操作方式高度相似。
- 原则：
  - 不让大模型自由生成整套 Vue 页面和 CSS。
  - 不直接复制一个完整后台项目作为所有项目的统一模板。
  - 借鉴成熟开源项目的布局、组件组织和交互模式，沉淀为本项目可测试的原型库。
  - 大模型只负责根据规划选择原型和填写结构化参数，生成器负责确定性渲染。

#### 调研参考

1. `pure-admin/vue-pure-admin`
   - 地址：`https://github.com/pure-admin/vue-pure-admin`
   - 技术：Vue 3、Vite、Element Plus、TypeScript、Pinia。
   - 许可证：MIT。
   - 用途：参考后台壳层、路由、菜单、标签页、响应式布局和精简项目结构。
   - 结论：与当前 Element Plus 技术栈最接近，可作为后台基础架构的主要参考，但不整仓复制。
2. `vbenjs/vue-vben-admin`
   - 地址：`https://github.com/vbenjs/vue-vben-admin`
   - 技术：Vue 3、Vite、TypeScript、Monorepo，并提供多 UI 方案。
   - 许可证：MIT。
   - 用途：参考布局配置化、主题系统、权限路由和组件分层。
   - 结论：架构成熟但整体较重，只参考设计，不作为 V1 直接模板。
3. `element-plus/element-plus`
   - 地址：`https://github.com/element-plus/element-plus`
   - 许可证：MIT。
   - 用途：表格、树、描述列表、时间线、步骤条、抽屉、对话框、标签页等基础页面模式。
4. `apache/echarts`
   - 地址：`https://github.com/apache/echarts`
   - 许可证：Apache-2.0。
   - 用途：指标驾驶舱、趋势分析、监控统计和专题分析页面。
5. `bcakmakoglu/vue-flow`
   - 地址：`https://github.com/bcakmakoglu/vue-flow`
   - 许可证：MIT。
   - 用途：案件流转、审批流程、设备拓扑和关系图页面。
6. `SortableJS/vue.draggable.next`
   - 地址：`https://github.com/SortableJS/vue.draggable.next`
   - 许可证：MIT。
   - 用途：任务看板、工单看板和阶段式业务流转。
7. `xaboy/form-create`
   - 地址：`https://github.com/xaboy/form-create`
   - 技术：支持 Vue 3 和 Element Plus，JSON 驱动表单。
   - 许可证：MIT。
   - 用途：复杂动态表单和不同字段布局。
8. `DataV-Team/DataV-Vue3`
   - 地址：`https://github.com/DataV-Team/DataV-Vue3`
   - 许可证：MIT。
   - 当前状态：README 标记为 WIP，且没有正式 Release。
   - 结论：仅作为大屏装饰效果参考，不作为 V1 核心依赖。

#### 推荐实现结构

生成器建立三个相互独立的模板层，而不是建立若干完整项目副本：

1. `shells`：应用整体壳层
   - `sidebar_admin`：左侧导航管理后台。
   - `top_workspace`：顶部导航业务工作台。
   - `split_console`：左侧对象树、中心工作区、右侧详情。
   - `fullscreen_monitor`：全屏监控或指挥大屏。
2. `page_patterns`：模块页面模式
   - `table_crud`：筛选区、表格、分页、弹窗编辑。
   - `master_detail`：列表与详情并列。
   - `tree_detail`：树形目录与内容详情。
   - `workflow_timeline`：流程步骤、时间线和办理记录。
   - `kanban`：分阶段拖拽看板。
   - `dashboard`：指标卡、图表和明细联动。
   - `form_wizard`：多步骤复杂表单。
   - `map_monitor`：地图或平面图、告警列表和浮层详情。
3. `widgets`：可复用业务组件
   - 指标卡、状态标签、时间线、详情描述、告警列表、图表、对象树、附件区、审批记录和动态表单。

#### Planning 数据结构

`planning.json` 增加结构化 UI 规划，不由大模型输出任意源码：

```json
{
  "ui_plan": {
    "shell": "top_workspace",
    "home_pattern": "task_dashboard",
    "navigation": "top",
    "density": "standard"
  },
  "modules": [
    {
      "key": "cases",
      "name": "案件管理",
      "page_pattern": "master_detail",
      "detail_pattern": "workflow_timeline",
      "edit_pattern": "form_wizard"
    }
  ]
}
```

#### 原型选择规则

- 普通档案、字典和基础数据优先使用 `table_crud`。
- 案件、工单和审批业务优先使用 `workflow_timeline` 或 `kanban`。
- 设备、组织和卷宗目录优先使用 `tree_detail`。
- 统计分析类模块优先使用 `dashboard`。
- 指挥、视频、告警和态势类项目可使用 `fullscreen_monitor` 或 `map_monitor`。
- 同一项目至少包含两种模块页面模式，避免所有模块都退化为 CRUD 表格。
- Planning Review 必须展示并允许用户修改整体壳层和每个模块的页面模式。

#### 工程实现

- 每个 `shell` 和 `page_pattern` 都是独立 Vue 模板组件，具有统一输入协议。
- 生成器根据 `ui_plan` 组合模板，不复制整个第三方仓库。
- 第一阶段只实现 3 个壳层和 6 个页面模式，形成可测试的有限集合。
- 每种组合提供固定示例数据和 Playwright 截图用例。
- 构建失败时只能回退到同类稳定页面模式，不能把所有项目统一回退成同一个 UI。
- 项目指纹用于稳定选择同类布局变体，但不能替代页面结构差异。

#### 许可证与原创性要求

- 引入第三方依赖前记录仓库、版本、许可证和使用范围。
- 生成包中加入 `THIRD_PARTY_NOTICES.md`，保留 MIT、Apache-2.0 等许可证要求的声明。
- 不直接复制开源项目的品牌、Logo、演示数据和完整页面。
- 参考架构和组件 API 后，使用本项目自己的模板、命名、样式和业务数据。
- 原创性报告区分“第三方依赖代码”和“本项目生成代码”，不能把依赖代码计入原创代码量。

#### 验收标准

- 至少提供 3 种明显不同的应用壳层。
- 至少提供 6 种页面结构模式。
- 同一行业生成两个不同软件时，导航结构、首页和核心模块页面至少有两项结构差异。
- 页面差异不能只依赖配色、圆角、阴影或字体。
- 所有模板组合通过 `npm run build` 和 Playwright 基础访问测试。
- 生成包包含完整第三方许可证清单。

- 实现结果：
  - `planning.json` 已增加 `ui_plan` 和模块级页面模式。
  - 已实现 `sidebar_admin`、`top_workspace`、`split_console` 三种应用壳层。
  - 已实现表格 CRUD、主从详情、树形详情、流程时间线、看板、数据驾驶舱六种页面结构。
  - Planner 模板模式会按软件类型和模块语义选择不同结构。
  - Planning Review 可修改壳层、首页模式、信息密度和模块页面模式。
  - 生成项目包含 `THIRD_PARTY_NOTICES.md`。

### ISSUE-004：增加在线 Demo 人工审查与对话式返工流程

- 状态：`已实现 V1`
- 优先级：`P0`
- 背景：在线 Demo 的目的不是单纯为自动截图提供运行环境，而是让用户在生成软著材料前判断项目是否符合预期。升级前的流水线启动 Demo 后会直接继续截图、生成文档和打包，缺少人工验收与返工环节。

#### 目标流程

```text
确认 planning.json
-> 生成项目
-> AI 增强
-> 运行验证
-> 启动在线 Demo
-> 暂停流水线，等待用户审查
   -> 审查通过：继续自动截图、文档、合规检查和打包
   -> 需要修改：进入修改对话，生成规划变更建议
      -> 用户确认变更
      -> 更新 planning.json 并记录版本
      -> 重新生成和验证项目
      -> 重新启动 Demo
      -> 再次等待用户审查
```

#### Demo 审查页

- 展示 Demo 地址、Swagger 地址、前后端日志和当前规划摘要。
- 提供两个明确操作：
  - `符合预期，继续生成软著材料`
  - `需要修改`
- 未经用户确认，不执行自动截图、文档生成、合规检查和 ZIP 打包。
- 审查等待期间保持任务可恢复，用户关闭浏览器或更换窗口后仍可从历史任务继续。

#### 对话式修改

- 点击“需要修改”后显示聊天窗口。
- 用户可用自然语言描述修改内容，例如：
  - “删除视频巡查，增加车辆轨迹分析。”
  - “案件详情改成时间线，首页增加待办事项。”
  - “整体改成顶部导航的数据分析平台。”
- 对话模型必须同时读取：
  - 当前 `planning.json`
  - 当前行业知识库
  - 当前 `ui_plan`
  - 用户修改意见
  - 最近一次生成与验证结果
- 模型输出结构化变更集，不直接修改源码：

```json
{
  "summary": "删除视频巡查并增加车辆轨迹分析",
  "changes": [
    {
      "operation": "remove_module",
      "module_key": "video_patrol"
    },
    {
      "operation": "add_module",
      "module": {
        "key": "vehicle_trajectory",
        "name": "车辆轨迹分析"
      }
    }
  ],
  "affected_areas": ["backend", "frontend", "database", "screenshots", "documents"]
}
```

- 用户必须先查看变更摘要并确认，系统才能更新规划和重新生成。
- 对话历史与每轮变更集需要落盘，保证任务可追溯。

#### 规划版本与回退

- `planning.json` 仍表示当前生效规划。
- 每次确认修改前保存历史版本，例如：
  - `planning_versions/v1.json`
  - `planning_versions/v2.json`
  - `planning_versions/v3.json`
- 记录版本号、用户意见、结构化变更、生成时间和审查结果。
- 支持回退到任一已确认规划版本后重新生成。
- 返工时不得覆盖上一版可运行项目，应保存版本对应关系或至少保留最近一个稳定版本。

#### 状态机调整

- 新增或明确以下任务状态：
  - `generating_project`：生成并验证项目。
  - `demo_starting`：启动在线 Demo。
  - `awaiting_demo_review`：等待用户审查。
  - `revision_chat`：收集和解析修改意见。
  - `revision_review`：等待用户确认规划变更。
  - `regenerating_project`：按新规划重新生成项目。
  - `generating_materials`：审查通过后生成截图和软著材料。
  - `success`：材料生成并打包完成。
- 后端进程重启后必须能从持久化状态恢复，不能只依赖内存线程状态。

#### 重新生成范围

- 第一版采用完整重新生成，保证代码、数据库、截图和文档与新规划一致。
- 后续可根据结构化变更集实现增量生成，但不得作为 V1 的必要条件。
- 每轮重新生成都必须重新执行前端构建、Maven 测试、API 可用性检查和 Demo 启动检查。

#### 验收标准

- Demo 启动成功后，流水线停在“等待用户审查”，不会提前生成最终材料。
- 用户点击“继续生成”后才执行截图、文档、合规检查和打包。
- 用户能通过自然语言提出模块、页面、字段和 UI 调整。
- 系统先展示结构化变更摘要，用户确认后才更新规划。
- 修改后可重新生成项目并进入第二轮 Demo 审查。
- 至少支持三轮规划版本，且可查看每轮意见和变更记录。
- 历史任务页可以继续处于审查或返工中的任务。
- 最终材料只引用最后一次审查通过的 `planning.json` 和项目版本。

- 实现结果：
  - 主流水线启动 Demo 后暂停为 `awaiting_demo_review`。
  - 用户审查通过后才启动截图、文档、合规检查和打包。
  - 支持自然语言修改意见，大模型优先生成新规划；未配置或失败时使用明确标记的规则回退。
  - 修改建议需用户确认后才覆盖当前规划并完整重新生成项目。
  - 每轮规划写入 `planning_versions/vN.json`，修改建议写入 `revision_proposals/`。
  - 支持查看规划版本并回退任一历史版本后重新生成。

### ISSUE-005：从历史任务进入任务详情后缺少返回首页入口

- 状态：`已修复`
- 优先级：`P1`
- 发现位置：历史任务列表点击“查看任务”后进入的首页任务详情状态，即 `/?jobId={job_id}`。
- 现象：用户从历史任务列表点击“查看任务”后，首页会加载该历史任务的详情和进度，但页面缺少“返回首页”或“新建任务”入口，无法方便地退出历史任务查看状态。
- 调整要求：
  - 当首页 URL 包含 `jobId`，并正在展示历史任务详情时，在顶部导航或任务详情区域增加“返回首页”按钮。
  - 点击后跳转到 `/`，不携带旧任务的 `jobId` 查询参数。
  - 返回首页后清除当前页面内已加载的历史任务、预览和轮询状态，恢复新任务创建状态。
  - 保留现有“历史任务”入口，两个按钮分别承担“回到新建首页”和“进入历史列表”的职责。
- 验收标准：
  - 从 `/history` 点击任一“查看任务”进入 `/?jobId=...` 后，可以一键返回普通首页。
  - 返回后地址严格为 `/`，不再显示该历史任务的进度、Demo 或生成结果。
  - 页面恢复为可创建新任务状态，且不会继续轮询旧任务。
- 实现结果：历史任务详情 `/?jobId=...` 顶部已增加“返回首页”，返回时停止旧任务轮询并清空详情状态。

### ISSUE-006：历史任务缺少删除功能

- 状态：`已实现`
- 优先级：`P1`
- 发现位置：历史任务列表操作区域。
- 现象：历史任务只能查看、启动 Demo 或下载材料，无法删除无效、失败或测试任务。
- 前端要求：
  - 每条历史任务增加“删除”按钮。
  - 删除前弹出二次确认，显示软件名称和任务编号。
  - 删除成功后立即从历史任务列表移除。
  - 删除失败时展示明确错误，不得先从页面隐藏。
- 后端要求：
  - 新增任务删除接口，例如 `DELETE /api/jobs/{job_id}`。
  - 校验任务编号，禁止删除 `outputs` 目录之外的路径。
  - 删除任务前停止该任务正在运行的 Spring Boot、Vite 和其他 Demo 子进程。
  - 清理内存中的 Demo 启动状态和任务锁。
  - 删除整个 `outputs/{job_id}/`，包括源码、日志、截图、文档、ZIP、规划版本和对话记录。
- 状态规则：
  - `success`、`failed`、`draft_planning`、`awaiting_demo_review` 等静止任务可以删除。
  - 正在生成或重新生成的任务默认禁止删除，或者必须先执行“取消任务”后才能删除。
  - 正在运行 Demo 的任务删除前必须先停止 Demo。
- 安全要求：
  - 必须使用任务存储层提供的受控删除函数，不允许由前端提交任意文件路径。
  - 后端解析后的目标路径必须确认位于 `OUTPUT_ROOT` 内。
  - 删除操作不可恢复，确认框需明确说明源码和软著材料会同时删除。
- 验收标准：
  - 用户可以删除失败任务和已完成任务。
  - 删除后任务列表、详情接口和下载接口均不再返回该任务。
  - 删除运行中 Demo 的任务后，对应端口和进程已释放。
  - 非法任务编号和路径穿越请求不能删除工作区其他文件。
- 实现结果：
  - 历史任务列表已增加删除按钮和不可恢复提示。
  - 后端新增受控删除接口，校验任务编号和目标路径。
  - 删除前停止 Demo 并清理启动锁。
  - 正在生成、重新生成或生成材料的任务禁止删除。

### ISSUE-007：规划模块未理解具体软件语义，模型失败后回退为通用行业模块

- 状态：`已实现并通过端到端验证`
- 优先级：`P0`
- 发现日期：`2026-06-15`
- 复现任务：`20260615173140-88f95700`
- 输入：
  - 软件名称：`监所管理系统`
  - 软件描述：`用于监所人员档案管理、案件关联、勤务管理和统计研判`
  - 软件类型：`管理系统`
  - 行业类型：`公安`
- 实际结果：
  - Planning Review 生成警情管理、案件管理、车辆管理、视频巡查、布控预警和统计研判。
  - 除通用案件与统计功能外，模块与监所人员档案、监室、勤务和值班等核心业务明显不相关。
  - 不同公安软件仍可能退化为同一组通用公安模块，未达到 ISSUE-002 的目标。
- 已确认原因（历史保留）：
  - 本次任务请求模式为 `auto`，实际模式为 `template`。
  - Planner 模型返回内容解析失败，错误为：
    `JSONDecodeError: Extra data: line 123 column 1 (char 3458)`。
  - `auto` 模式随后回退到固定模板。
  - 当前模板回退直接使用所选行业知识库中的全部模块，没有根据软件名称、软件类型和简介进行相关性筛选。
  - 当前公安知识库主要覆盖警情、案件、车辆、视频巡查、布控和统计，缺少监所监管细分领域知识。
- 最终产品决策（2026-06-15）：彻底简化 Planner
  - 用户明确决定取消“行业知识库 + 模板回退”两层运行逻辑，改为大模型直生成 + 用户自由增删。
  - 行业知识库、行业一致性校验、模板回退和 `auto/llm/template` 模式全部下线。
  - 返工对话同步改为 LLM-only 失败重试。
  - 行业字段继续保留，并作为普通上下文传给 LLM，但不再限制模块范围。
  - 此方案已写入业务代码并通过真实任务端到端验证。
- 新目标行为：
  - Planner 完全由大模型驱动，直接根据软件名称、软件类型和软件描述生成功能模块。
  - Planner 不再读取行业知识库，不再做行业一致性校验，不再区分 `auto/llm/template` 模式。
  - LLM 首次输出解析或 Pydantic 校验失败时，将错误摘要和原输出反馈给模型，自动请求修复一次。
  - 第二次仍失败或 API 调用失败时，不回退模板，任务进入 `failed`，由用户在前端点击“重新生成规划”。
  - 行业类型仅作为任务信息记录在 `planning.json` 和 `status.json` 中，不再约束规划内容。
  - 用户可在 Planning Review 自由增删改模块，不再受知识库白名单或主题校验拦截。
  - 对话式返工同样只走 LLM，失败即提示用户重试，不再使用规则改写回退。
- 新建议修复范围：
  1. `backend/app/planner.py`：
     - 删除 `template_planning()`、`_module_ui()`、`_ui_plan_for()`、`validate_planning_against_context()`、`_validate_llm_industry_alignment()`。
     - 移除 `from .industry_knowledge import planning_context` 等行业上下文依赖。
     - 简化 `_messages()`：只传软件名称、软件类型、软件简介和行业名称，不再注入知识库模块候选和行业校验语句。
     - 简化 `build_planning()`：仅走 LLM 路径，不再回退模板。
     - `_extract_json()` 必须正确处理代码围栏、前后说明文字和尾随文本，提取首个完整 JSON 对象。
     - 增加一次结构化修复请求：首次 JSON 解析或 `Planning.model_validate()` 失败后，将错误摘要、原响应和目标 schema 发给同一模型修复；最多自动修复一次。
     - 简化 `propose_revision()`：移除行业上下文与 `_rule_based_revision()`，仅保留 LLM 路径；返工响应也执行相同的 JSON 容错和一次自动修复。
  2. `backend/app/industry_knowledge.py`：保留全部函数与 `industry_knowledge/*.json` 四份文件，仅作历史参考，Planner 不再导入。
  3. `backend/app/main.py`：
     - 实际请求模型名为 `JobRequest`，删除其中 `planner_mode` 字段与相关模式处理。
     - 放宽 `POST /api/planning/regenerate`：允许 `draft_planning` 和“规划阶段失败”的 `failed` 任务使用原 job ID 重试。
     - 重试时清理规划错误、复位 planning step，并保留用户最初输入。
     - 不允许项目生成、Demo 审查或材料阶段失败误用“重新生成规划”。
  4. `backend/app/workflow.py`：
     - `create_job()` 不再保存 `planner_mode` / `planner_requested_mode`。
     - `generate_planning()` 不再写入模板回退信息。
     - 规划失败时记录可读的 `error`、失败阶段和重试资格，便于前端展示。
  5. `frontend/src/pages/HomePage.vue`：
     - 表单去掉 `planner_mode` 字段。
     - 设置面板去掉“默认模式”下拉，保留 API Base URL、模型、API Key、超时与代码增强相关项。
     - 任务详情不再展示 `已回退模板` 提示；保留 LLM 模型名等基础信息。
     - `industry_type` 选择器保留为信息记录字段。
     - 规划生成失败时显示明确错误和“重新生成规划”按钮；重试使用当前 job ID。
     - 重试期间恢复轮询，成功后仍进入 `/planning-review/{jobId}`。
  6. `backend/.env.example`：删除 `AI_PLANNER_MODE`，保留 `AI_PLANNER_BASE_URL` / `AI_PLANNER_API_KEY` / `AI_PLANNER_MODEL` / `AI_PLANNER_TIMEOUT`。
  7. 后端测试：
     - `tests/test_planner.py` 删除模板/回退/行业一致性相关用例。
     - 覆盖正常 JSON、代码围栏、JSON 前后说明、尾随文本、首次校验失败后修复成功、两次失败终止。
     - 覆盖返工规划的成功、自动修复和最终失败。
     - API 测试覆盖 `failed` 规划任务使用原 job ID 重试，以及非规划阶段失败禁止该重试。
     - `tests/test_industry_knowledge.py` 维持现状，验证 `industry_knowledge.py` 模块仍可独立使用。
  8. 文档同步：
     - `AGENTS.md` 移除“行业知识库是 Planner 的强制上下文，不能改为完全自由生成”约束；`当前项目结论` 改为 Planner 完全由 LLM 驱动。
     - `docs/FLOW.md` 更新 Planner 流程描述，去掉模板回退与行业一致性校验相关段落。
     - `README.md` `当前能力` 不再列“四类行业知识库”，改为“行业信息仅作为任务记录”。
     - `docs/ISSUES.md` 本条目按上述新方案落地后改状态为 `已实现` 并补 `实现结果`。
- 新验收标准：
  - 首页不再展示 Planner 模式选项；设置面板无 `auto/llm/template` 选择。
  - `planner_mode` 字段在后端/前端/`.env` 不再被读取或保存。
  - 行业类型字段保留、传给 LLM 且写入 `planning.json`，但不作为模块白名单或校验条件。
  - 用 `监所管理系统` + 行业 `公安` 测试：LLM 成功时直接生成人员档案、案件关联、勤务、统计研判等相关模块；未出现的车辆、视频巡查、接处警模块不被默认加入。
  - 模型返回 JSON 后附带说明文字时，系统能提取首个完整 JSON 对象。
  - 首次 JSON 或结构校验失败时自动修复一次；修复成功后正常进入 Planning Review。
  - 人为触发两次失败或 API 不可用时，任务停留在 `failed`，首页/历史任务详情提示明确错误和“重新生成规划”入口，不回退模板。
  - 点击重试使用原 job ID，复位规划步骤并重新轮询；不得创建重复历史任务。
  - 项目生成或材料生成阶段的 `failed` 任务不能使用规划重试接口。
  - 返工对话触发 LLM 失败时，同样提示用户重试，不调用规则改写。
  - `industry_knowledge/*.json` 四份文件保留；`backend/app/industry_knowledge.py` 模块仍可独立调用。
  - 后端 `python -m unittest discover -s tests -v` 全部通过；删去的模板/回退/行业一致性用例无残留。

#### 实现结果（Claude 实施 2026-06-15，Codex 复审并修正）

**代码变更：**

- `backend/app/planner.py`：删除 `template_planning` / `_module_ui` / `_ui_plan_for` / `validate_planning_against_context` / `_validate_llm_industry_alignment` / `_rule_based_revision`；移除 `from .industry_knowledge import planning_context`；改写 `_messages` / `build_planning` / `propose_revision` 为 LLM-only + JSON 容错 + 一次自动修复；`_extract_json` 走 `_first_json_object` 平衡大括号扫描 + 候选验证，支持代码围栏、前后说明、尾随文本。
- `backend/app/main.py`：`JobRequest` 移除 `planner_mode`；`/api/planning/regenerate` 允许 `failed + failed_stage=="planning"` 重试，清理旧 `planning.json` / `planning_versions` / `revision_proposals` 并复位步骤；`propose_revision` 输出移除 `actual_mode` / `fallback_reason`。
- `backend/app/workflow.py`：`create_job` 不再写 `planner_mode` / `planner_requested_mode` / `planner_fallback_reason`，新增 `failed_stage` 字段；`generate_planning_draft` 失败时 `failed_stage="planning"`，`run_job` 失败时 `failed_stage="project"`，`continue_material_generation` 失败时 `failed_stage="materials"`。
- `backend/app/settings.py`：`SETTING_KEYS` 与 `PlannerSettingsUpdate` 移除 `AI_PLANNER_MODE` / `mode` 字段；`public_planner_settings` 不再返回 `mode`。
- `backend/.env.example`：删除 `AI_PLANNER_MODE` 行；保留 `AI_PLANNER_BASE_URL` / `AI_PLANNER_API_KEY` / `AI_PLANNER_MODEL` / `AI_PLANNER_TIMEOUT` / `AI_CODEGEN_*`。
- `frontend/src/pages/HomePage.vue`：表单移除 `planner_mode` 字段；设置面板移除"默认模式"下拉；任务详情 planner-info 简化为 "Planner：LLM · {model}"；`status === 'failed' && failed_stage === 'planning'` 时显示"重新生成规划"按钮，使用原 job ID 调用 `/api/planning/regenerate`。
- `industry_knowledge.py` 与 `industry_knowledge/*.json`：**未删除**，保留供历史参考。

**测试结果：**

- 后端 `python -m unittest discover -s tests`：57 项全过。
- 前端 `npm.cmd run build`：通过，128.78 kB JS / 13.73 kB CSS。
- `git diff --check`：exit 0（仅 LF/CRLF 警告，非错误）。

**监所管理系统实测：**

用 `监所管理系统 / 公安 / 管理系统` 输入 Planner 端到端验证（model 设为 test-model 模拟 LLM 首次返回坏 JSON，第二次返回合法规划）：

```text
modules:
  - detainee_archives    在押人员档案   pattern=master_detail
  - duty_arrangement     勤务安排       pattern=workflow_timeline
  - cell_management      监室管理       pattern=tree_detail
  - statistics           统计研判       pattern=dashboard
database_tables: [detainee_archives, duty_arrangement, cell_management, statistics]
API call count: 2
First-call error path expected, second-call fix expected
```

不再退化为警情、案件、车辆、视频巡查、布控预警等通用公安模块。

**ISSUE-008 未修改确认：**

- 实施范围严格限制在 ISSUE-007 指定的 `planner.py` / `main.py` / `workflow.py` / `settings.py` / `HomePage.vue` / `.env.example` / 测试文件。
- 未触碰任何与"任务中断恢复"、"interrupted 状态"、"Worker 心跳"、"任务级锁"相关的代码或文档。
- `docs/ISSUES.md` 的 ISSUE-008 章节、AGENTS.md 的"当前待修"中 ISSUE-008 描述、`docs/FLOW.md` 的状态机章节均保持原状。

**最终验证：**

- Codex 复审反馈的 P0/P1/P2 问题均已修复。
- 用户已完成真实任务端到端链路验证。
- 旧任务中残留的 `planner_mode` 字段仅属于历史数据，当前代码不再读取；暂不做一次性迁移。

#### 复审修正（2026-06-15，Codex 复审反馈 5 条）

- **P0：大模型会覆盖任务基本信息**（已修）
  - 现象：`planner.py` 直接采用 LLM 返回的 `software_name` / `description` / `software_type` / `industry_type`，初次规划和重新规划都可能让用户输入被篡改。
  - 修复：新增 `_restore_user_input_fields()`，`build_planning()` 在解析或自动修复后强制用 `job` 字典中的原始输入覆盖以上字段；`propose_revision()` 故意不覆盖（保留用户主动重命名/换行业的能力）。
  - 新增 `test_user_input_fields_override_llm_response` 验证 LLM 返回篡改字段后被恢复为用户输入。
- **P1：行业传给模型的是内部编码**（已修）
  - 现象：当 job 中只有 `industry_type=public_security`、没有 `industry_name` 时，模型收到的提示是 `行业参考：public_security`。
  - 修复：在 `planner.py` 新增 `INDUSTRY_DISPLAY_NAMES` 基础映射（`public_security→公安` 等）和 `industry_name_for()` 函数；`_initial_messages` / `_repair_messages` / `_revision_messages` 改用 `_industry_hint_text()` 统一生成提示文本，模型只会看到"公安"等显示名。
  - 新增 `test_user_input_industry_code_is_converted_to_display_name`（断言模型请求体中含"公安"且不含"public_security"）和 `test_unknown_industry_code_leaves_industry_name_empty`。
- **P1：失败阶段可能残留**（已修）
  - 现象：`run_job` / `continue_material_generation` 启动时未清空 `failed_stage`，重跑成功路径下磁盘仍带旧值。
  - 修复：`run_job` 与 `continue_material_generation` 启动时显式 `_update(... failed_stage=None)`；`/api/planning/regenerate` 已在重置步骤时清空。
  - 新增 `tests/test_failed_stage_reset.py`，含 `test_run_job_clears_failed_stage_at_start` 和 `test_continue_material_clears_failed_stage_at_start`。
  - 同时新增 `test_failed_stage_clears_on_resubmit` 验证 `/api/planning/regenerate` 重试时 `failed_stage` 被清。
- **P1：跨窗口文档没有同步完成**（已修）
  - `README.md` line 5 / line 9 / 核心流程图 / `.env` 示例：删除"读取行业知识库" / `auto/llm/template` / `AI_PLANNER_MODE=auto` 等旧措辞。
  - `docs/FLOW.md` Planner 行为段：删除"当前仍读取行业知识库"旧描述，写入 ISSUE-007 实施后行为（LLM-only / 用户字段覆盖 / 行业编码→显示名 / 自动修复 / 失败阶段）。
  - `AGENTS.md` 当前项目结论、当前待修、关键位置、开发约束：删除"Planner 仍使用行业知识库" / `auto/llm/template` 旧措辞，写入"行业编码→显示名"映射保留方案。
  - `docs/ISSUES.md` 当前后续工作：删除"等待用户向 Claude 发布实施命令"旧段，更新为"ISSUE-007 已实施完成"。
- **P2：测试启动了真实后台进程**（已修）
  - 现象：`test_retry_planning.py` 调用 `client.post("/api/planning/regenerate")` 会真起 `multiprocessing.Process`，CI 中可能残留异步任务。
  - 修复：所有命中 202 路径的测试用例改用 `with patch("app.main.Process") as mock_process`，断言 `mock_process.assert_called_once()`；409 / 404 路径断言 `mock_process.assert_not_called()`。

#### Claude 实施顺序（历史记录）

Claude 收到 ISSUE-007 实施命令后，按以下顺序执行，不得同时修改 ISSUE-008：

1. **Planner 核心**
   - 先修改 `planner.py`，完成 LLM-only、JSON 首对象提取、Pydantic 校验和一次自动修复。
   - 单独补齐 Planner 单元测试并运行。
2. **任务状态与重试**
   - 修改 `JobRequest`、`create_job()`、规划失败状态和 `/api/planning/regenerate`。
   - 规划失败状态必须能与项目生成失败、材料生成失败明确区分。
   - 补 API 或工作流测试，证明只有规划阶段失败允许使用规划重试。
3. **前端与配置**
   - 删除首页和设置面板的 Planner 模式选择。
   - 增加规划失败错误展示和原任务重试入口。
   - 删除 `.env.example` 中的 `AI_PLANNER_MODE`。
4. **清理与回归**
   - 搜索并清理运行代码中的 `planner_mode`、模板回退提示和行业校验依赖。
   - 不删除 `industry_knowledge.py` 或四份 JSON。
   - 运行后端全量测试、前端构建和监所管理系统真实规划。
   - 完成后交由 Codex 复审，最终由文档记录验收状态。

Claude 交付时必须提供：

- 修改文件清单。
- 测试命令与结果。
- 监所管理系统实际生成模块。
- LLM 首次返回坏 JSON、自动修复成功的测试证据。
- 两次失败后原 job ID 可重试的测试证据。
- `git diff --check` 结果。
- 未修改 ISSUE-008 的确认。

### ISSUE-008：服务重载后后台任务中断，任务永久停留在 10%

- 状态：`已通过 Codex 二次复审`
- 优先级：`P0`
- 发现日期：`2026-06-15`
- 复现任务：`20260615173140-88f95700`
- 任务输入：`监所管理系统`
- 实际状态：
  - `status = confirmed`
  - `progress = 10`
  - `current_step = 规划已确认，准备生成项目`
  - `planning.json` 和 `planning_versions/v1.json` 已存在。
  - `generated_project/`、构建日志和 Demo 运行记录均未创建。
- 现场复现（2026-06-15 20:02 排查）：
  - 任务最后更新时间 `updated_at = 2026-06-15T17:41:02`，距当时已卡住 2 小时 21 分钟。
  - `outputs/20260615173140-88f95700/` 下不存在 `generated_project/`、`logs/`、`demo_runtime.json`。
  - 当前仍有一个孤儿 Python 进程 PID `30708`：
    - 启动时间 `2026-06-15T17:41:14`（恰好在确认规划 12 秒后被 `multiprocessing.spawn` 拉起）
    - 命令行：`python.exe -c "from multiprocessing.spawn import spawn_main; spawn_main(parent_pid=9988, pipe_handle=552)" --multiprocessing-fork`
    - 父进程 `9988` = 当前监听 8000 的 uvicorn 旧 worker（`uvicorn --reload` 启动于 17:28:09）
    - 工作集 3.7 MB，1 个线程，已用 CPU 时间 3.09 秒，状态 `Responding=True`
    - 网络连接：`64931 ↔ 64932` 形成 loopback 已建连 socket 对，两端均属 PID 30708；属 `multiprocessing.spawn` 父→子 IPC 握手通道。
    - 含义：Worker 仍卡在 spawn 阶段的“等父进程发送 GO 信号”位置，`run_job()` 主体从未执行，因此 `_update(status="generating")` 一次都没有被调用。
  - 另有孤儿进程 PID `34432`（17:46:04，parent_pid=17800），现象一致，疑似同根因下的二次触发（17:46 期间用户重新查询/操作页面时被同一 uvicorn 派生）。
  - 端口 8000 由 9988 监听，API `/api/health` 仍返回 200，新请求正常处理 —— 但服务对孤儿 Worker 没有任何感知。
- 现场复现（2026-06-15 20:05~20:25 清理与重启）：
  - 用户授权 `Stop-Process 30708, 34432`，并把 `status.json` 改为 `status=failed / current_step=后台进程中断 / error=含 PID`；新增 `worker_termination` 字段记录清理痕迹。
  - 杀完两个孤儿后，**后端 API 立即 hang 死**：`/api/health` 连续 8s/15s/20s 超时均 0 bytes received。
  - 排查发现 8000 端口上同时有两个 uvicorn 监听：`9988`（17:28:09 启动）和 `17800`（17:06:54 启动），两条都 `Responding=True`、CPU 接近 0、内存 ~12MB，均不再处理 HTTP 请求。
  - 推测链：杀 30708 后，9988 的请求处理协程在 `multiprocessing` 父端 pipe 句柄异常下进入死锁；17800 一直在并发绑 8000，Windows TCP 在两个 listener 之间被打乱；两者都活着但都不能继续服务 —— **本应只影响孤儿进程的清理动作，意外造成整站不可用**。
  - 用户授权重启后端：先 `Stop-Process 9988, 17800`，再以**无 `--reload`** 方式启动新 uvicorn（PID 27188，20:25:51 启动）；`/api/health` 立即恢复 200，`/api/jobs/20260615173140-88f95700` 返回 `failed` 状态正确。
- 已确认原因（与旧版本一致）：
  - 用户在 `2026-06-15 17:41:02` 确认规划后，后端通过 `multiprocessing.Process(target=run_job, daemon=True).start()` 启动生成任务（参见 `backend/app/main.py:264-269`）。
  - Uvicorn 使用 `--reload` 运行；`Process.start()` 在 Windows 上走 `multiprocessing.spawn`，子进程必须先与父进程完成 IPC 握手才能进入 `run_job()`。
  - 父 uvicorn worker 在子进程进入 `run_job()` 之前被 Reload 替换，新 uvicorn worker 没有该子进程的任何信息（无 PID、无管道句柄、无状态）。
  - 子进程此时两端 socket 仍在自己手中（父端已死），永远等不到 GO 信号，CPU 长期接近 0%。
  - 服务重新启动后只读取了落盘状态，没有扫描并恢复中断任务。
  - 状态仍保持 `confirmed`，既没有进入失败状态，也没有重新入队，因此前端长期显示 10%。
- 问题本质（精化）：
  - `status.json` 已持久化，但执行调度仍依赖当前 FastAPI 进程派生的临时子进程。
  - `multiprocessing.Process(daemon=True)` + Windows spawn + Uvicorn `--reload` 三者叠加，spawn 子进程成为失去父端 IPC 的孤儿，无法被新 worker 接管。
  - 系统有“任务状态持久化”，但没有“任务执行持久化”和“启动恢复协调器”。
  - 当前状态不能区分“正在由活跃 Worker 执行”和“状态显示执行中但 Worker 已消失”。
  - 服务对外仍可服务，但中间状态对用户完全黑盒。
- 新发现的子问题（2026-06-15 清理过程中暴露）：
  - **多 uvicorn 实例并存**：进程 9988（17:28）与 17800（17:06）同时监听 8000，原因大概率是 Reload 启动新 worker 时旧 worker 未被及时 kill；说明 `--reload` 下也没有进程级单例保证。
  - **杀子进程可拖垮整个 API**：删除 `multiprocessing.spawn` 派生的子进程会触发父 uvicorn 的 pipe 异常处理路径；与多 listener 共存叠加，造成 `/api/health` 长时间不可用。
  - 这两点都意味着 ISSUE-008 的修复必须把“服务进程单例 + 任务调度隔离 + 子进程生命周期托管”一起设计，单纯加“恢复任务”按钮不够。

#### 建议恢复机制

分为两个层级实施。

**第一层：人工恢复入口**

- 对 `confirmed`、`generating`、`regenerating_project` 和 `generating_materials` 等疑似中断状态提供“恢复任务”按钮。
- 后端增加受控恢复接口，例如：

```text
POST /api/jobs/{job_id}/resume
```

- 恢复前检查任务目录中的实际产物和步骤状态，而不是只看总进度。
- 选型记录（2026-06-15）：用户拍板 ISSUE-008 修复走 **L1 轻量方案**，只做“状态区分 + 人工恢复按钮 + 启动扫描 + 任务锁 + 恢复记录”，**不**改造 `multiprocessing` 调度、不解决多 uvicorn 并存、不解决杀子进程拖垮 API —— 接受这三条已知风险。
- 若项目尚未生成，如本次任务，则从 `project` 重新开始。
- 若前端构建或 Maven 测试未完成，则重新执行完整运行验证。
- 若已经处于 `awaiting_demo_review`，只恢复 Demo 状态，不自动进入材料生成。
- 若材料阶段中断，V1 建议从 `screenshot` 开始重新生成全部材料，避免半成品不一致。
- 恢复操作必须防止重复点击和重复 Worker。

**第二层：服务启动自动恢复**

- FastAPI 启动时扫描 `outputs/*/status.json`。
- 对处于执行中状态、但没有活跃 Worker 或有效 Demo 进程的任务标记为 `interrupted`。
- 推荐先标记和提示用户，不直接无条件恢复所有任务，避免服务重启后同时启动大量 Maven、npm 和 Java 进程。
- 可配置自动恢复策略：
  - `manual`：默认，仅标记中断，等待用户点击恢复。
  - `safe`：只自动恢复规划生成和尚未创建项目的任务。
  - `all`：自动恢复所有可恢复任务，不建议作为 V1 默认值。

#### 推荐状态与执行信息

- 新增主状态：`interrupted`，表示任务原本在执行，但 Worker 已失联。
- `status.json` 增加：
  - `worker_id`
  - `worker_pid`
  - `worker_started_at`
  - `worker_heartbeat_at`
  - `resume_count`
  - `interrupted_at`
  - `interrupted_reason`
- Worker 执行期间定期更新心跳。
- 服务判断 PID 不存在或心跳超时后，才能认定任务中断。
- 使用任务级锁文件或原子占用记录，保证同一 job 同时只有一个 Worker。

#### 步骤恢复策略

| 中断位置 | 推荐恢复点 | 原因 |
|---|---|---|
| `generating` 且规划未完成 | 重新生成规划 | 规划生成成本较低，避免读取半个 JSON |
| `confirmed` 且无项目目录 | 从 `project` 开始 | 本次任务属于该情况 |
| `project` / `enhance` | 清理生成项目后从 `project` 开始 | 避免部分源码混合 |
| `run` | 从完整运行验证开始 | npm/Maven 可重复执行 |
| `demo` | 停止残留进程后重新启动 Demo | 端口和 PID 不能直接复用 |
| `awaiting_demo_review` | 保持审查状态，按需重新启动 Demo | 不得越过人工审查 |
| `generating_materials` | 从截图和材料阶段整体重做 | 保证截图、文档和规划一致 |
| `success` | 不恢复 | 只允许重新启动 Demo |

#### 运行环境约束

- 开发环境使用 `uvicorn --reload` 时，文件修改会频繁触发重启，不能把长任务只挂在 Reload Worker 上。
- 生产环境不应使用 `--reload`。
- V1 可继续使用本地进程，但需要独立的任务恢复与锁机制。
- 后续任务量增加时，应考虑将执行器拆为独立 Worker 服务或使用可靠任务队列；这不作为本次 V1 修复的强制条件。

#### 前端要求

- 超过合理时间仍停留在执行状态时，显示“任务可能已中断”，而不是无限显示固定百分比。
- 提供“恢复任务”按钮，并展示系统判断的恢复起点。
- 恢复前提示可能重新执行项目生成、Maven 测试或材料生成。
- 恢复后继续轮询同一 job ID，不创建重复历史任务。

#### 验收标准

- 规划确认后主动重启后端，任务不再永久停留在 10%。
- 服务恢复后能将失联任务识别为 `interrupted`。
- 用户点击恢复后，该任务使用原 job ID 从安全步骤继续。
- 连续点击恢复不会启动两个生成进程。
- 在项目生成、运行验证、Demo 启动和材料生成阶段分别模拟中断，均按恢复策略得到一致产物。
- `awaiting_demo_review` 状态不会因服务重启而自动越过人工审查。
- `success` 任务不会被错误重新生成。
- 历史任务页能够显示中断原因、恢复入口和恢复次数。

#### 实现结果（Claude 实施 L1 2026-06-16）

**代码变更：**

- `backend/app/workflow.py`：
  - 新增 `INTERRUPTED_STATUS = "interrupted"` 与 `EXECUTING_STATUSES` / `INTERRUPT_AGE_SECONDS`（confirmed 10 分钟 / generating 30 分钟 / regenerating_project 30 分钟 / generating_materials 60 分钟）。
  - 新增 `_acquire_worker_lock(job_id, task)` / `_release_worker_lock` / `_worker_lock_path` / `_pid_alive` / `_has_active_worker_lock` / `_is_job_orphaned`。
  - `generate_planning_draft` / `run_job` / `continue_material_generation` 启动时 `_acquire_worker_lock`，写入 `worker_pid` / `worker_started_at` / `worker_heartbeat_at`，退出时 `finally` 释放锁。
  - `create_job` 初始化 L1 新字段（`worker_pid` / `worker_started_at` / `worker_heartbeat_at` / `interrupted_at` / `interrupted_reason` / `resume_count` / `recovery_from_step` / `resumed_at`）。
  - 新增 `scan_for_interrupted_jobs()`：扫描 `outputs/*/status.json`，对疑似失联任务标 `interrupted` 并清理残留 lock。
  - 新增 `resume_job(job_id)`：根据 `failed_stage` 选择恢复点（`confirmed` → project；`project/enhance` → 清 generated_project 重 project；`run` → 重跑 run；`demo` → 停残留后 demo；`generating_materials` → 清材料后 materials），防双跑检查活锁。
- `backend/app/main.py`：
  - 新增 `app.on_event("startup")` → `_scan_interrupted_on_startup()`，服务启动时自动扫描。
  - 新增 `POST /api/jobs/{job_id}/resume` 接口：`LookupError → 404`，`ValueError → 409`，`RuntimeError → 409`。
- `frontend/src/pages/HomePage.vue`：
  - 新增 `resumeJob()` 与 `canResumeJob` computed。
  - 状态为 `interrupted` 时显示恢复面板：含 `interrupted_reason`、恢复起点、已恢复次数与"恢复任务"按钮（带二次确认）。
- `frontend/src/pages/HistoryPage.vue`：
  - `statusText` 新增 `interrupted: '后台进程中断'`。
  - 历史任务操作区在 `status === 'interrupted'` 时显示"恢复任务"按钮，点击后跳首页继续轮询。

**测试结果：**

- 后端 `python -m unittest discover -s tests`：83 项全过（Planner 29 + Retry 11 + Failed Stage Reset 2 + Resume & Interrupt 26 + 既有 15）。
- 前端 `npm.cmd run build`：通过，130.70 kB JS / 13.73 kB CSS。
- `git diff --check`：exit 0。
- 仿真中断任务已写入 `outputs/20990101000000-deadbeef/`，可作为人工复测样本。

**恢复策略（与设计一致）：**

| 中断前状态 | 恢复点 | 清理动作 |
|---|---|---|
| `confirmed` | project | 无 |
| `generating` / `project` / `enhance` | project | 删除 `generated_project/` |
| `run` | run | 无 |
| `demo` | demo | 停残留 Demo 进程 |
| `generating_materials` | materials | 删除 `screenshots/ docs/ logs/ copyright_package.zip generated_project.zip` |

**L1 已知风险（用户已接受）：**

- 不解决多 uvicorn 并存：开发期仍用 `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`（无 `--reload`）。
- 不解决杀子进程拖垮 API：`Stop-Process` 孤儿 spawn 子进程仍可能让 uvicorn 协程死锁，触发现象时需重启整个后端。
- 不改造 `multiprocessing` 调度：仍使用 `multiprocessing.Process(daemon=True)`，依赖 worker.lock 做防双跑。

**首次复审待确认项（已在二次复审修正）：**

- 启动扫描的判定阈值（10/30/30/60 分钟）是否合理、是否需要做成环境变量。
- `awaiting_demo_review` 状态不自动 interrupted 的策略是否需要调整（例如长时间无心跳也应标）。
- `recovery_from_step` 字段是否需要写入 `planning.json` 或独立文件以便排查历史。
- 真实端到端测试（启动 → 模拟 Reload → 扫描命中 → 恢复成功）需 Codex 实际操作复现任务 `20260615173140-88f95700` 与新建仿真任务。

### ISSUE-009：规划模块字段轻微超限导致整个任务失败

- 状态：`已修复`
- 优先级：`P1`
- 发现日期：`2026-06-15`
- 复现任务：`20260615213307-7f5c18c2`
- 现象：模型生成的首个模块包含 13 个有效业务字段，超过原 Schema 的 12 项硬上限；自动修复后的响应仍为 13 项，规划任务最终失败。
- 修复：
  - `ModulePlan.fields` 上限由 12 调整为 20。
  - Planner 提示明确为“建议 6 到 12 个，最多 20 个”。
  - 保留最少 2 个字段的结构约束，不静默裁剪模型返回的有效业务字段。
  - 新增 13 个字段可通过 Pydantic 校验的回归测试。
- 验证：
  - Planner 单元测试 30 项通过。
  - 后端全量单元测试 57 项通过。
  - `python -m compileall app tests` 通过。
  - `git diff --check` 无错误，仅显示现有 LF/CRLF 转换警告。
  - 用户已在真实任务中确认该问题不再复现。
- 不包含：Planner 网络超时重试、ISSUE-008 中断恢复机制。

#### ISSUE-008 L1 复审修正（2026-06-16，Codex 复审反馈 2 条）

- **Bug 1：会误判活跃 Worker 为中断**（已修）
  - 现象：`_is_job_orphaned()` 优先按 `updated_at` 是否超时判定，超时即返回 True，没先看 `worker.lock` 中 PID 是否仍活。模拟"旧 updated_at + 当前进程活锁"会得到 `active_old_orphaned=True`，服务重启扫描时可能误杀仍在跑的长任务。
  - 修复：把 `worker.lock` 检查提到第一位
    - 活锁 → 不算孤儿（不论 updated_at 多旧）
    - 死锁 → 算孤儿
    - 坏锁（JSON 损坏） → 算孤儿
    - 无锁 + updated_at 超时 → 兜底算孤儿
  - 新增 3 项测试：
    - `test_active_lock_with_old_updated_at_is_not_orphaned`：活锁 + 旧 updated_at → False
    - `test_dead_lock_with_recent_updated_at_is_orphaned`：死锁 + 新 updated_at → True
    - `test_corrupt_lock_is_orphaned`：坏锁 → True
- **Bug 2：材料阶段恢复会把步骤状态重置错**（已修）
  - 现象：`target = "materials"` 不在 `STEPS` 中（STEPS 只有 screenshot/analyze/source/docs/compliance/package），结果 `next(...)` 默认返回 0，planning/project/enhance/run/demo/screenshot 全部被重置为 pending，状态短暂写 `regenerating_project`，最终 `continue_material_generation` 不会重跑这些步骤，状态机不一致。
  - 修复：
    - 材料阶段的内部 `target` 改为 `"screenshot"`（STEPS 中第一个材料步骤），确保仅重置 screenshot 及之后
    - 状态直接进入 `"generating_materials"`，不再短暂写 `regenerating_project`
    - `recovery_from_step = "screenshot"`，UI 可结合 `status="generating_materials"` 显示"材料阶段"
    - 同步修 `target_idx` 的 fallback：`project` 默认 1（project 在 STEPS index 1），避免原 `target == "materials"` 时退到 0
  - 强化 `test_resume_interrupted_materials_clears_artifacts`：
    - 断言 `recovery_from_step == "screenshot"`
    - 断言 `status == "generating_materials"`
    - 断言 planning/project/enhance/run/demo 保留 completed（不被错误重置）
    - 断言 screenshot/analyze/source/docs/compliance/package 全部 pending
- **回归测试结果**：
  - `python -m unittest discover -s tests`：86 项全过（原 83 + 复审 3 项）
  - `npm.cmd run build`：通过
  - `git diff --check`：exit 0
- **Codex 二次复审结论**：
  - 活 Worker + 旧 `updated_at` 不再被误判为中断。
  - 材料阶段恢复会从 `screenshot` 重新开始，仅重置截图及后续材料步骤，保留 planning/project/enhance/run/demo 为 completed。
  - `python -m unittest tests.test_resume_and_interrupt -v`：29 项通过。
  - `python -m unittest discover -s tests -v`：86 项通过。
  - `npm.cmd run build`：通过。
  - `git diff --check`：无错误，仅 LF/CRLF 换行提示。

### ISSUE-010：Dashboard 页面视觉表达不足

- 状态：`已通过 Codex 审查`
- 优先级：`P1`
- 发现日期：`2026-06-16`
- 复现任务：`20260615221651-0b963954`
- 发现位置：生成结果截图中的数据驾驶舱 / 大屏模块页面。
- 现象：
  - 当前 Dashboard 页面主要是简单数字卡片、蓝色柱条和表格。
  - 缺少清晰的图例、趋势、占比、状态分布和风险等级表达。
  - 图形与业务语义绑定弱，像普通 CRUD 页面上方加了装饰条。
  - 用于软著截图时，系统真实感、差异化和展示说服力不足。
- 建议目标：
  - 将 `dashboard` 页面模式升级为独立模板，不再复用普通表格页结构。
  - 增加 KPI 指标卡、环形占比图、趋势折线图、分组柱状图、状态分布标签、最近动态 / 预警列表。
  - 优先使用 CSS/SVG 实现，避免新增重型图表依赖。
  - 根据模块名称、字段和软件主题生成业务化指标文案，例如“在押人数”“风险预警”“审批通过率”“勤务完成率”。
  - 截图时 Dashboard 页面应优先展示图形区，而不是把表格作为主体。
- 验收标准：
  - 至少 3 类 Dashboard 视觉组件同时出现。
  - 不同业务模块生成的指标名称、数据分组和图形文案明显不同。
  - 生成项目仍可通过前端构建。
  - 自动截图中 Dashboard 首屏能看到主要图形信息。
- 实现结果（Claude 实施 2026-06-16，已通过 Codex 审查）：
  - `backend/app/project_generator.py` 新增 5 类 SVG 业务化图形组件：`_svg_donut`（环形占比）、`_svg_line_trend`（折线趋势）、`_svg_bar_groups`（分组柱状）、`_kpi_icon_svg`（4 类 KPI 图标）。
  - 首页 dashboard 升级：每种 home_pattern（metric_dashboard / task_dashboard / analysis_dashboard）都有 KPI 卡片行 + 折线 + 环形 + 柱状 + 状态标签 + 最近动态列表。
  - 业务化 KPI 文案：`_kpi_indicators_for_planning` 按 `_BUSINESS_KEYWORDS` 行业关键词匹配，监所→在押人数/今日新收/风险预警，案件→案件总数/在办案件/已结案件，勤务→值班人次/排班冲突/勤务完成率 等。
  - 状态分布：`_status_distribution_for_planning` 按行业返回 4 类分布（监所含"高危"，案件含"在办"，车辆视频含"异常"，通用含"待办"等）。
  - 趋势序列：`_trend_series_for_planning` 用软件名 hash 产出稳定 7 日序列。
  - 7 日活动：`_recent_activities_for_planning` 包含办理/新增/审核/归档/告警/导出 6 种动作类型。
  - 模块级 dashboard（page_pattern=dashboard）也升级为含 SVG 折线 + 业务化标签 + 业务化字段 KPI。
  - 端到端实测：监所管理系统的 DashboardPage.vue 同时含 donut-svg / trend-svg / bar-svg / kpi-card / activity-，KPI 标签为"在押人数"等业务化文案。
- Codex 审查修正：
  - 将 Python 内置 `hash()` 替换为基于 `hashlib.sha256` 的 `_stable_seed()`，确保同一软件跨进程生成相同趋势序列、KPI 数字和 fingerprint seed。
  - 新增跨 Python 进程稳定性测试，防止后续回退。

### ISSUE-011：源码材料原创性增强与业务化注释

- 状态：`已通过 Codex 审查`
- 优先级：`P1`
- 发现日期：`2026-06-16`
- 复现任务：`20260615221651-0b963954`
- 发现位置：`docs/源代码材料.docx` 及生成项目源码。
- 当前现状：
  - 已有 Planner 模块差异、字段差异、页面模式差异和可选 Code Enhancer。
  - `generate_source_document()` 只是按源码文件抽取内容并生成源码材料。
  - 当前没有 `project_fingerprint.json`、`originality_report.json`。
  - 当前没有代码命名变体、业务化注释变体、源码材料专用原创性说明。
- 问题：
  - 生成项目中仍存在大量模板化结构，源码材料观感容易重复。
  - 缺少业务化中文注释、模块专属说明和差异化来源记录。
  - “噪声备注”不应作为无意义填充，应改为可解释、可维护的业务化注释。
- 建议目标：
  - 在 Java、Vue、SQL 生成阶段加入少量业务化中文注释，注释来自软件名称、模块名、字段名和业务流程。
  - 为不同模块生成不同注释模板，例如：
    - `// 监区人员档案查询条件组装`
    - `// 勤务排班状态变更前置校验`
    - `// 统计研判指标按业务口径聚合`
  - 生成 `project_fingerprint.json`，记录模块命名、字段组合、页面模式、注释风格和差异化参数。
  - 生成 `originality_report.json`，说明原创性来源、模板复用范围、第三方依赖与本项目生成代码边界。
  - 源码材料仍只抽取项目自身源码，继续排除 `node_modules`、`target`、`dist` 等目录。
- 验收标准：
  - 生成项目中 Java、Vue、SQL 至少各有一类业务化注释。
  - 注释内容与当前软件名称和模块语义相关，不是随机噪声。
  - 输出 `project_fingerprint.json` 和 `originality_report.json`。
  - 源码材料中能看到业务化注释，但不影响项目编译、前端构建和 Maven 测试。
  - 合规报告或材料说明中能区分第三方依赖、模板生成代码和本项目差异化生成内容。
- 实现结果（Claude 实施 2026-06-16，已通过 Codex 审查）：
  - `backend/app/project_generator.py` 新增 4 类业务化注释 helper：
    - `_module_business_comment(module, kind)`：返回 entity/repository/service/controller/vue_page/sql_table 六类的纯文本业务化注释（不含语言前缀）。
    - `_controller_method_comment(module, method)`：list/detail/create/update/delete 5 类方法级注释。
    - `_field_business_comment(module_name, field, kind)`：按字段名关键词（name/code/type/status/remark/amount/time × 中英文）匹配业务角色，fallback 是"业务属性"。
  - 注释注入点：
    - Java Entity：类级 Javadoc + 字段 Javadoc（含"业务主名称/业务编号或识别码/业务分类/当前业务状态/业务发生时间"等业务角色）。
    - Java DTO：类级 Javadoc + 字段 Javadoc。
    - Java Service：类级 Javadoc + 方法体内业务化中文注释（分页查询/新增/更新/删除/详情）。
    - Java ServiceImpl：类级 + 5 个方法的方法体注释。
    - Java Controller：类级 + 5 个方法的 Javadoc。
    - SQL DDL：表级注释（"在押人员档案：数据库表结构..."）+ 字段级注释。
    - Vue Page：HTML 注释 + 脚本注释双行（<!-- ... --> + // ...）。
  - 新增 `project_fingerprint.json`：记录软件信息、UI 计划、模块命名、字段组合、页面模式、注释风格、差异化参数（确定性 hash 种子）。生成到 `generated_project/project_fingerprint.json`。
  - 新增 `originality_report.json`：记录原创性来源（业务化 KPI / 业务化注释 / Dashboard 视觉组件 / UI 壳层变体）、模板复用范围（确定性 vs 业务个性化）、第三方依赖（Spring Boot 3 / Vue 3 / Element Plus / MyBatis Plus 等）、边界划分、验证清单。生成到 `generated_project/origity_report.json`。
  - `generate_java_project` 末尾统一写入 fingerprint 和 originality_report，保持 `THIRD_PARTY_NOTICES.md` 不变。
  - 端到端实测：监所管理系统生成的 DetaineeArchivesEntity 含 5 条字段 Javadoc，命中"业务编号或识别码/业务主名称/业务发生时间/当前业务状态"等业务角色；init.sql 含表级 + 字段级业务注释；DashboardPage.vue 同时含 donut-svg / trend-svg / bar-svg / kpi-card / activity- / 在押人数 KPI；project_fingerprint.json 与 originality_report.json 校验通过。
  - 端到端测试：13 项新单元测试（`test_dashboard_and_originality.py`）全部通过：5 项 dashboard 视觉、5 项 Java/Vue/SQL 注释、3 项 fingerprint + originality_report。
- Codex 审查修正：
  - `project_fingerprint.json` 中的模块 `table` 改为读取 `planning.database_tables[index]`，缺失时才 fallback 为 `ed_{module_key}`，确保指纹记录与实际 SQL / Entity 表名一致。
  - 新增 fingerprint 使用真实数据库表名的回归测试。
- 验证：
  - `python -m unittest tests.test_dashboard_and_originality -v`：15 项通过。
  - `python -m unittest discover -s tests -v`：104 项通过。
  - `python -m compileall app tests`：通过。

### ISSUE-012：Planner 返回模块数与数据库表数不一致导致规划失败

- 状态：`已修复`
- 优先级：`P0`
- 发现日期：`2026-06-16`
- 复现任务：`20260616094630-40b7d690`
- 任务输入：
  - 软件名称：`涉案物品数据系统`
  - 软件类型：`数据平台`
  - 行业类型：`公安`
  - 软件描述：`用于涉案物品信息、案件关联、关联人员的数据图谱发掘、案件提审证物提供和统计研判`
- 现象：
  - 任务在规划阶段失败，前端显示：
    `ValidationError: 1 validation error for Planning Value error, 每个功能模块必须对应一个数据库表`
  - `status.json` 中 `failed_stage="planning"`，未生成 `planning.json`。
  - 失败任务目录仅保留 `status.json`，当前没有保存 LLM 首次响应和修复响应，无法复盘模型到底少了哪个表。
- 当前代码判断：
  - `backend/app/planner.py` 的 `Planning.tables_match_modules()` 要求 `len(database_tables) == len(modules)`。
  - `_initial_messages()` 只要求 modules 数量、字段、截图和 UI 模式，没有明确写出 `database_tables 必须与 modules 一一对应，数量相同，顺序一致`。
  - `_repair_messages()` 会把校验错误发回模型修复一次，但修复提示也没有把该硬约束提升为单独规则。
  - `_generate_with_repair()` 第二次仍校验失败后直接抛错，任务进入 `failed`。
- 问题本质：
  - LLM-only 后没有模板兜底，规划阶段必须增强结构容错。
  - 对“表数量缺失”这类可自动补全的问题，直接失败会降低任务成功率。
  - 当前不保存原始 LLM 响应，排错成本偏高。
- 建议修复范围：
  1. 提示词层：
     - `_initial_messages()` 和 `_repair_messages()` 明确要求：
       `database_tables 必须与 modules 数量相同、顺序一致，每个模块对应一个 snake_case 表名，优先使用模块 key 或 module_key_records 形式。`
  2. 解析后规范化层：
     - 在 `Planning.model_validate()` 前或失败后增加确定性补全逻辑：当 `database_tables` 数量少于 `modules` 时，根据缺失模块 key 自动补齐表名；当数量多于 modules 时可截断或重新按 modules key 生成。
     - 自动补全必须记录到后续诊断信息，不应静默隐藏。
  3. 诊断层：
     - 规划失败时保存 `planner_raw_initial.txt`、`planner_raw_repair.txt` 或等价 JSON 诊断文件，至少包含错误摘要、模型名、请求阶段和截断后的原始响应。
- 验收标准：
  - 新增单测覆盖：`database_tables` 少于 modules 时可补齐并通过。
  - 新增单测覆盖：`database_tables` 多于 modules 或顺序不一致时有明确处理策略。
  - 新增单测覆盖：两次规划失败时会落盘可排查的 LLM 原始响应或诊断文件。
  - 复现任务同类输入重新生成规划时能进入 Planning Review，不再直接卡在规划失败。
  - 保留现有约束：模块 key 唯一、表名 snake_case 且不重复。
- 修复内容：
  - `_initial_messages()` 与 `_repair_messages()` 明确要求 `database_tables` 与 `modules` 数量相同、顺序一致。
  - 新增 `_normalize_database_tables()`：在 Pydantic 校验前按模块顺序补齐、截断并规范化表名；缺表时使用模块 key，非法或重复表名自动转为合法唯一 snake_case。
  - 新增 `PlannerValidationError`：两次规划校验失败时携带首次响应、修复响应和错误摘要。
  - `generate_planning_draft()` 捕获该异常后写入 `planner_diagnostics/planner_raw_initial.txt`、`planner_raw_repair.txt` 和 `planner_diagnostics.json`。
- 验证：
  - `python -m unittest tests.test_planner -v`：32 项通过。
  - `python -m unittest tests.test_workflow_order -v`：4 项通过。
  - `python -m unittest discover -s tests -v`：89 项通过。
  - `python -m compileall app tests`：通过。

### ISSUE-013：规划业务动作未落地为 Demo 页面操作按钮

- 状态：`已修复`
- 优先级：`P0`
- 发现日期：`2026-06-16`
- 复现任务：`20260616094630-40b7d690`
- 发现位置：任务详情页规划版本 v3 与在线 Demo 审核中心页面。
- 用户反馈：
  - v3 规划中明确提出审核中心需要行级审核入口、快速审核抽屉和审核详情页操作按钮。
  - 在线 Demo 页面中未看到“通过 / 驳回 / 转交 / 退回补充”等审核操作按钮。
- 排查结论：
  - `planning_versions/v3.json` 与当前 `planning.json` 已包含 `PUT /api/audit_center/{id}/approve`、`reject`、`quick_audit`、`transfer`、`return` 等接口。
  - 任务确实按 v3 重新生成，生成项目文件时间晚于 v3 规划时间。
  - 生成器原逻辑只生成通用 CRUD：前端操作列只有“编辑 / 删除”，前端 API 只有 page/get/create/update/delete，后端 Controller/Service 也只有 5 个通用接口。
  - 因此问题不在 Planner 或用户描述，而在 Project Generator 未读取 `planning.api_list` 里的业务动作。
- 修复内容：
  - `backend/app/project_generator.py` 新增 `api_list` 业务动作解析，识别形如 `PUT /api/{module}/{id}/approve` 的模块动作接口。
  - 为对应模块生成 `business_actions`，包含动作编码、中文标签、HTTP 方法、Java 方法名、前端函数名和 Spring Mapping 注解。
  - 前端 API 文件新增业务动作方法，例如 `approveAuditCenter()`、`rejectAuditCenter()`、`quickAuditAuditCenter()`、`transferAuditCenter()`、`returnActionAuditCenter()`。
  - Vue 页面操作列新增业务按钮，点击后弹出确认框并调用对应 API，成功后刷新列表。
  - 后端 Service / ServiceImpl / Controller 新增对应动作方法，执行动作时写入可识别的状态、结果、意见、节点或操作类字段，并更新时间。
  - Java 关键字防护：`return` 动作不会生成非法 Java 方法 `return()`，而是生成 `returnAction()`，接口路径仍保持 `/return`。
  - 生成项目自带 Controller/Service 合约测试不再固定断言 5 个接口 / 方法，而是按规划业务动作动态增加。
  - `metadata/*Operation.java` 与前端 config 的 `operations` 同步包含规划业务动作。
- 验收标准：
  - 含审核动作的规划生成项目后，审核中心页面操作列应包含“通过 / 驳回 / 快速审核 / 转交 / 退回补充”按钮。
  - 前端 API 文件应生成对应业务动作函数。
  - 后端 Controller 应生成对应 REST 接口，Service / ServiceImpl 应生成对应业务方法。
  - 生成项目合约测试不能因业务接口超过 5 个而失败。
  - 通用 CRUD 模块不受影响，仍保留查询、新增、编辑、删除能力。
- 验证：
  - `python -m unittest tests.test_project_generator -v`：通过。
  - `python -m compileall app tests`：通过。
  - `python -m unittest discover -s tests -v`：104 项通过。
  - 临时产物检查：审核中心 Vue 页面已生成“通过 / 驳回 / 快速审核 / 转交 / 退回补充”按钮；前端 API 已生成 `approveAuditCenter` 与 `returnActionAuditCenter`；后端 Controller 已生成 `@PutMapping("/{id}/return")` 与 `returnAction()`。
  - 受限环境中未完成生成项目 Maven 实测：当前 PowerShell 找不到 `mvn.cmd`，此前同类生成项目 Maven 验证由流水线和用户端端到端覆盖。

## 本轮验证结果

- 后端：`python -m unittest discover -s tests -v`，104 项通过。
- 临时生成项目：审核中心业务动作按钮、前端 API 和后端 Controller 文本检查通过。
- 工厂前端：`npm.cmd run build` 通过。
- 临时生成项目前端：包含顶部工作台、分析驾驶舱、主从详情、流程时间线和模块驾驶舱，`npm.cmd run build` 通过。
- 临时生成项目后端：JDK 17 环境执行 Maven，79 项测试通过。
- 浏览器：首页确认不再显示行业模块预选。
- 浏览器：历史任务确认显示删除按钮。
- 浏览器：历史任务详情确认显示“返回首页”。
- 服务：`http://127.0.0.1:8000/api/health` 返回正常，`http://127.0.0.1:5173/` 返回 200。
- 用户已完成真实任务端到端链路验证：规划、Planning Review、项目生成、Maven/npm 验证、Demo 审查、返工、材料生成和 ZIP 打包流程已跑通。

## 历史反馈与回归项

以下问题在前序开发中出现过。当前代码声称已有相应处理，但统一修复版本发布前需要重新回归验证。

### REGRESSION-001：生成项目 Maven 测试失败

- 历史错误：生成的 `ControlMetadata.java` 第 70 行附近编译失败。
- 2026-06-15 新复现：任务 `20260615213307-7f5c18c2` 在运行验证阶段报
  `类文件具有错误的版本 61.0，应为 52.0`。本机 `JAVA_HOME` 指向 JDK 8，
  而生成项目要求 Java 17；`run_generated_project()` 调用 Maven 时遗漏了
  `_maven_subprocess_env()`，导致已有的 Java 17 自动探测没有生效。
- 修复：运行验证的 Maven 子进程显式传入 `_maven_subprocess_env()`；新增测试
  断言 `mvn test` 使用该环境。对复现任务生成的后端使用 Java 17 实测，
  Maven 79 项测试通过，构建成功。
- 回归结果：用户已确认真实任务成功，`61.0 / 52.0` 类版本错误不再复现。

### REGRESSION-002：在线 Demo 缺少可点击入口或出现顺序错误

- 期望流程：运行验证 -> 在线 Demo -> 用户审查 -> 审查通过后自动截图和文档生成。
- 期望页面：首页和历史任务页均能查看或重新启动 Demo，并能查看 Swagger 和日志。
- 回归要求：确认 Demo 在截图前启动，且未经用户审查通过不会提前生成材料；任务完成后仍有明确入口。

### REGRESSION-003：Demo 长时间停留在“启动中”

- 回归要求：
  - 验证 `queued`、`building`、`starting`、`running`、`failed` 状态能正确刷新。
  - 启动失败时必须展示错误和日志入口，不能无限显示“启动中”。
  - 验证超时回收和重新启动行为。

### REGRESSION-004：历史任务入口

- 期望：首页可进入历史任务列表。
- 回归要求：历史任务可查看任务状态、Demo、Swagger、日志、源码和软著包。

## 当前后续工作

1. 验证 Demo 超时回收、失败日志和运行中任务删除限制。
2. 验收通过后提交本轮修改，并把提交号和发布结果补充到本文档。

## 新窗口接手说明

新会话开始时，按以下顺序读取：

1. `AGENTS.md`：当前结论、工作区状态、开发约束和快速命令。
2. `README.md`：启动方式、产品能力和用户操作流程。
3. `docs/ISSUES.md`：需求来源、实现状态、验证结果和剩余风险。
4. `docs/FLOW.md`：当前代码的真实流程、状态机、接口和关键文件。

新窗口必须以文件和 Git 工作区为准，不依赖聊天记忆。任何业务流程变化都应同步更新上述四份文档。
