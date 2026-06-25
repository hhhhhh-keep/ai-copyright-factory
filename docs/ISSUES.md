# AI 软著工厂 V1.0 - 问题与交接记录

> 用途：跨 Codex 窗口保留项目现状、用户反馈、实现结论和验证结果。
> 当前结论：ISSUE-002 至 ISSUE-020 已完成并通过 Codex 代码复审；ISSUE-021 已完成代码修正，仍待用户 Word/WPS 视觉验收；ISSUE-022 代码复审通过，仍建议用新任务截图做最终视觉确认；ISSUE-023、ISSUE-025、ISSUE-026、ISSUE-027 已完成代码复审；ISSUE-024 的记录已被后续 ISSUE-025/026 覆盖，不再等待“统一修改”。当前仍需回归：Demo 超时回收、失败日志和运行中任务删除限制。

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
  - `python -m unittest discover -s tests -v`：106 项通过。
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
  - `python -m unittest discover -s tests -v`：106 项通过。
  - 临时产物检查：审核中心 Vue 页面已生成“通过 / 驳回 / 快速审核 / 转交 / 退回补充”按钮；前端 API 已生成 `approveAuditCenter` 与 `returnActionAuditCenter`；后端 Controller 已生成 `@PutMapping("/{id}/return")` 与 `returnAction()`。
  - 受限环境中未完成生成项目 Maven 实测：当前 PowerShell 找不到 `mvn.cmd`，此前同类生成项目 Maven 验证由流水线和用户端端到端覆盖。

### ISSUE-014：Code Enhancer 超时回退与页面展示误导

- 状态：`已修复`
- 优先级：`P0/P1`
- 发现日期：`2026-06-18`
- 复现任务：`20260616115614-c4682c22`
- 用户反馈：
  - 任务进度区长期显示 `Code Enhancer：template（已回滚模板）`，用户难以判断是任务失败、增强失败，还是主动使用固定模板。
  - 多个 `auto` 代码生成任务都显示 template，容易误解为所有任务整体失败。
  - 需要把增强器拆成多轮，并在页面展示逐文件请求的简要节点。
- 排查结论：
  - 复现任务本身没有失败，运行验证已通过，任务停在 `awaiting_demo_review`；失败的是可选的 AI Code Enhancer。
  - `status.json` 与 `enhancement.json` 记录 `actual_mode=template`，`fallback_reason=timeout: The read operation timed out`。
  - 原实现复用 `AI_PLANNER_TIMEOUT=60`，没有独立配置 `AI_CODEGEN_TIMEOUT`；同时一次请求要求模型返回多个完整文件，MiniMax-M3 在该形态下容易超时。
- 修复内容：
  - `backend/app/enhancer.py` 改为逐文件多轮增强，当前顺序为 `frontend/src/App.vue`、`frontend/src/style.css`、`README.md`。
  - `App.vue` 允许做壳层视觉增强，但必须保留模块路由入口和 `<router-view />`；`router.js` 和 `views/*` 归固定生成器所有，Code Enhancer 不允许覆盖。
  - 每轮请求只传入当前目标文件，要求模型只返回一个文件，降低单次 JSON 响应过长导致的超时概率。
  - 增强前统一备份允许修改的文件；任一文件增强失败时恢复备份，`auto` 模式回退稳定模板，`llm` 模式失败终止。
  - Code Enhancer 默认超时提高到 `180s`，并在 `.env.example`、设置接口默认值和本地 `.env` 中明确 `AI_CODEGEN_MODEL=MiniMax-M3`、`AI_CODEGEN_TIMEOUT=180`。
  - `workflow.py` 增加 `codegen_enhance_steps`，记录每个文件节点的 `pending/running/completed/failed`、文件名、展示名和摘要。
  - 首页进度区改为展示“未启用 / AI 增强成功 / 失败已回退稳定模板”的明确状态，并展示逐文件节点：应用壳层、界面样式、项目说明。
- 验收标准：
  - `auto` 模式下 Code Enhancer 应逐文件请求，前端能看到逐文件状态节点。
  - 增强失败时页面明确说明是“代码增强失败，已回退稳定模板”，不能暗示整个任务失败。
  - `template` 模式下页面显示“代码增强未启用”，不能写成“已回滚模板”。
  - 任一增强轮失败后必须恢复增强前文件，避免半增强状态进入后续 Maven/npm 验证。
- 验证：
  - `python -m unittest tests.test_enhancer -v`：3 项通过。
  - `python -m compileall app tests`：通过。
  - `python -m unittest discover -s tests -v`：105 项通过。
  - `npm.cmd run build`：工厂前端构建通过。

### ISSUE-015：Code Enhancer 覆盖 App.vue 路由壳层导致子菜单丢失具体页面功能

- 状态：`已修复`
- 优先级：`P0`
- 发现日期：`2026-06-18`
- 复现任务：`20260618093521-010b7e5e`
- 用户反馈：
  - 代码增强后，除首页外的子菜单都没有具体页面功能。
- 排查结论：
  - 当前任务 `codegen_actual_mode=llm`，增强成功执行。
  - 增强后的 `generated_project/frontend/src/App.vue` 被模型整体重构，原本由固定生成器生成的 `<router-view />` 与模块路由入口被替换为 `activeModule` 占位页面。
  - `views/*Page.vue`、`router.js`、模块 API 和配置文件仍存在；问题不是生成器没产出页面，而是增强器覆盖了应用壳层，导致子菜单不再进入真实路由页面。
- 修复内容：
  - 立即将复现任务的 `App.vue` 从 `.enhancer_backup/frontend/src/App.vue` 恢复到 `generated_project/frontend/src/App.vue`，再补入安全差异化壳层，使当前 Demo 保留视觉差异化并恢复真实模块页面。
  - `frontend/src/App.vue` 继续允许增强，但新增结构守卫：增强内容必须保留模块路由入口和 `<router-view />`。
  - `router.js` 和 `views/*` 不允许被 Code Enhancer 覆盖。
  - 新增回归测试：模型若返回不含路由入口或 `<router-view />` 的 `App.vue`，必须被拒绝，`auto` 模式回退稳定模板，并保持原 App 壳层不变。
- 验收标准：
  - 新生成任务执行 Code Enhancer 后，子菜单仍应进入 `views/*Page.vue` 的具体功能页面。
  - `App.vue` 可以出现在 `codegen_changed_files`，但增强后的内容必须保留模块路由入口和 `<router-view />`。
  - 逐文件节点显示“应用壳层”“界面样式”和“项目说明”。
  - 模型返回破坏路由壳层的 `App.vue` 时，增强器拒绝写入并触发回退。
- 验证：
  - `python -m unittest tests.test_enhancer -v`：3 项通过。

### ISSUE-016：工厂后端轮询任务状态时因 UTF-8 BOM 持续 ASGI 500

- 状态：`已修复`
- 优先级：`P0`
- 发现日期：`2026-06-18`
- 复现任务：`20260618093521-010b7e5e`
- 用户反馈：
  - 后端日志一直刷 `Exception in ASGI application`。
- 排查结论：
  - 生成项目 Spring Boot / Vite 日志正常，异常来自工厂 FastAPI 后端。
  - 前端持续轮询 `GET /api/jobs/20260618093521-010b7e5e`，接口返回 500。
  - 堆栈定位到 `workflow._json_read()` 使用 `encoding="utf-8"` 读取 `status.json`，但该文件被 PowerShell 写成 UTF-8 BOM，触发 `JSONDecodeError: Unexpected UTF-8 BOM`。
- 修复内容：
  - 立即将复现任务的 `status.json` 和 `enhancement.json` 转回无 BOM UTF-8，接口恢复 200。
  - `workflow._json_read()` 改为 `encoding="utf-8-sig"`，兼容带 BOM 和不带 BOM 的 JSON 文件。
  - 新增回归测试：`get_job()` 能读取带 UTF-8 BOM 的 `status.json`。
- 验收标准：
  - `GET /api/jobs/{job_id}` 和 `GET /api/jobs/{job_id}/demo` 返回 200。
  - 带 BOM 的历史任务 JSON 不应导致 ASGI 500 刷屏。
- 验证：
  - `GET /api/jobs/20260618093521-010b7e5e`：200。
  - `GET /api/jobs/20260618093521-010b7e5e/demo`：200。
  - `python -m unittest tests.test_workflow_order -v`：5 项通过。
  - `python -m unittest discover -s tests -v`：106 项通过。

### ISSUE-017：Code Enhancer 返回坏 JSON / 过载 / 读超时导致增强阶段失败

- 状态：`已修复容错；强制 llm 模式仍按设计失败`
- 优先级：`P0`
- 发现日期：`2026-06-18`
- 复现任务：`20260618093521-010b7e5e`
- 用户反馈：
  - 页面在“AI 增强项目代码”阶段报 `JSONDecodeError: Expecting property name enclosed in double quotes`。
  - 后续恢复时 MiniMax 出现 `HTTP 529 overloaded` 和 `socket.timeout: The read operation timed out`。
- 排查结论：
  - `JSONDecodeError` 来自 Code Enhancer 对模型返回内容的解析失败，不是规划阶段错误，也不是 ISSUE-016 的 BOM 读文件问题。
  - 当前任务的 `codegen_mode=llm`，属于“强制 AI 增强（失败则终止）”；因此外部模型持续过载或超时时不会自动回滚模板。
  - “AI 增强（失败自动回滚模板）”对应的是 `codegen_mode=auto`，该模式下增强失败会恢复增强前文件并继续后续验证。
- 修复内容：
  - `_request_enhancement()` 在解析/校验失败时，会把上一轮响应和错误摘要发回模型，自动要求严格 JSON 修复一次。
  - 对 `HTTP 429/500/502/503/504/529` 增加最多 3 次重试。
  - 对 `URLError`、`TimeoutError` 和 `socket.timeout` 增加最多 3 次重试，避免读超时变成未捕获异常刷屏。
  - `auto` 模式改为逐文件隔离失败：某个文件增强或结构校验失败时只恢复该文件，并继续尝试后续文件，避免 `App.vue` 被拦截后直接跳过 `style.css` 和 `README.md`。
  - 前端状态区支持“部分增强完成”文案；当部分文件增强成功、部分文件回退时，不再显示成全量成功或全量失败。
  - 保留 `llm` 模式语义：强制 AI 增强失败时任务进入 `failed`；需要自动回滚时应选择 `auto` 模式。
- 验收标准：
  - 模型首次返回非 JSON，第二次修复为合法 JSON 时增强应继续。
  - 模型服务短时 529 或读超时后恢复，增强应自动重试成功。
  - 模型持续不可用时，后端应记录明确错误，不应出现未处理 ASGI 异常刷屏。
  - `auto` 模式下 App.vue 增强不合格时，必须恢复 App.vue，但仍继续尝试增强 style.css 和 README。
  - `auto` 模式失败回滚模板，`llm` 模式失败终止任务，两者页面文案和状态必须保持一致。
- 验证：
  - `python -m unittest tests.test_enhancer -v`：6 项通过。
  - `python -m compileall app tests`：通过。
  - 当前任务在 `llm` 模式下重试后仍因外部模型读超时失败，属于强制模式的预期失败；如需继续生成，应重新选择 `auto` 或 `template` 模式再跑。

### ISSUE-018：收敛 Code Enhancer 边界，避免 App.vue 破坏路由并降低 CSS 请求体

- 状态：`已修复`
- 优先级：`P0`
- 发现日期：`2026-06-18`
- 复现任务：`20260618105236-2bf095bf`
- 用户反馈：
  - 早期 Code Enhancer 能生成明显差异化 UI，但后来频繁失败。
  - 曾出现增强后除首页外子菜单没有具体页面功能。
  - `style.css` 步骤容易卡很久，怀疑请求和响应过大导致模型耗时。
- 排查结论：
  - `App.vue` 文件本身不大，失败主因不是请求体过大，而是整文件交给 LLM 重写后结构不可控，容易破坏 `<router-view />`、路由入口或返回非严格 JSON。
  - `style.css` 接近万字符，完整文件输入与完整文件输出确实容易造成模型响应慢和超时。
  - README 文档增强在同类任务中成功，说明不是模型整体不可用，而是不同文件的增强边界需要区分。
- 修复内容：
  - `ALLOWED_FILES` 移除 `frontend/src/App.vue`，`App.vue`、`router.js` 和 `views/*` 统一归固定生成器所有。
  - 删除 App.vue 结构守卫路径，避免继续让模型整文件重写后再用粗粒度字符串规则拦截。
  - `frontend/src/style.css` 改为追加样式块模式：请求只提供 CSS 前段上下文和 append-only 指令，模型只返回可追加的 CSS 片段，不再返回完整 CSS。
  - 样式增强增加独立短超时：`AI_CODEGEN_STYLE_TIMEOUT=45`，最多 2 次尝试；文档增强为 `AI_CODEGEN_DOC_TIMEOUT=90`，避免可选增强长时间阻塞主流程。
  - 外部 Code Enhancer API 调用改为子进程硬超时：超过预算后直接终止请求子进程，避免 Windows/SSL read 阶段不受 `urllib` timeout 约束而卡住 worker。
  - `README.md` 继续保留 LLM 完整文档增强。
  - 单测调整为验证 Code Enhancer 不请求 App.vue、CSS 追加不覆盖原样式、README 仍可增强。
- 验收标准：
  - Code Enhancer 请求顺序应为 `frontend/src/style.css`、`README.md`，不包含 `frontend/src/App.vue`。
  - 增强后 App.vue 内容保持固定生成器输出，子菜单仍进入真实路由页面。
  - CSS 增强应保留原 CSS，并在末尾追加增强块。
  - README 增强仍可正常执行。
- 验证：
  - `python -m unittest tests.test_enhancer -v`：7 项通过。

## 本轮验证结果

- 后端：`python -m unittest discover -s tests -v`，110 项通过。
- Code Enhancer：`python -m unittest tests.test_enhancer -v`，7 项通过，覆盖逐文件请求顺序、单文件响应约束、不请求 `App.vue`、增强恢复、坏 JSON 修复、HTTP 529 重试、读超时重试和子进程硬超时后继续后续文件。
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

### ISSUE-021：软著材料图文覆盖、版式规范与说明深度不足

- 状态：`代码修正完成，待用户视觉验收`。
- 实现：截图从“每模块一张、仅首个模块有表单”改为每个模块的功能页和新增/编辑表单，并写入 `screenshot_manifest.json`；设计说明书与用户操作手册按功能单元插入真实截图、图题、字段/API信息和处理说明。第二阶段统一正文、标题、表格、图题、页眉页脚和代码样式；页码改为 Word/WPS 兼容的复合 PAGE 域；源码材料排除压缩 CSS 并过滤生成标记；用户手册取消四格流程表，改为逐条可执行操作说明。
- 合规：新增对功能截图清单、DOCX 插图数量、模块操作说明深度、源码生成标记、页码域和统一正文样式的检查。
- 验证：ISSUE-021 focused backend tests 通过；源码材料不再插入固定 50 行硬分页，DOCX XML 检查确认无显式 `w:type="page"` 分页符；临时材料结构检查确认三份核心 DOCX 均有宋体正文、PAGE 域、"第 1 页"文本回退，用户手册无流程表，源码材料无 AI 标记；工厂前端构建通过。最终仍需用户在 Word/WPS 打开新材料做视觉验收。详见 `docs/ISSUE-021.md`。

### ISSUE-022：截图抓拍时机早于 Element Plus 对话框动画完成

- 状态：`代码复审通过，待真实任务截图视觉确认`
- 优先级：`P1`
- 发现日期：2026-06-23
- 复现任务：待用户确认（用户提供截图：重点车辆档案管理 → 新增重点车辆档案管理 对话框呈半透明 loading 残影）
- 复现方式：在生成项目 Demo 页面点击任意模块"新增"按钮，等待 `el-dialog` 出现后立即截图，可观察到对话框仍处于 fade in / scale in 动画中。
- 现象（用户提供截图）：重点车辆档案管理 → 新增重点车辆档案管理 对话框明显是半透明、loading 蒙层尚未完全褪去。
- 复现场景定位：`backend/app/workflow.py` `capture_screenshots()`。

#### 实现结果（Claude 实施 2026-06-23，Codex 代码复审通过）

**代码变更：**

- `backend/app/workflow.py` 新增 `_wait_for_settle(page, kind)` 工具函数（5 类策略 + 默认兜底）：

  | kind | 策略 |
  | --- | --- |
  | `login` | `wait_for_load_state("networkidle")` + 200ms 短休（让登录卡淡入完成） |
  | `dashboard` | `wait_for_load_state("networkidle")` + 等待 `.kpi-card / .kpi-grid / .hero` 出现 |
  | `list` | `wait_for_load_state("networkidle")` + 等待首行 `.el-table__row / .el-empty` + 250ms 让 loading 蒙层完全褪去 |
  | `dialog` | 等待 `.el-dialog` 出现 → `wait_for_function` 检查 overlay `opacity >= 0.95` 且 wrapper transform 已归位（`matrix(1, 0, 0, 1, 0, 0)` 或 `none`）→ 失败 1 次后兜底 `wait_for_timeout(400)` → 再加 150ms 走 v-model 同步 |
  | `dialog_close` | `wait_for_selector(".el-dialog", state="detached", timeout=4000)` → 150ms 短休 |

  返回 `{"strategy": str, "duration_ms": int, "retried": bool}`，供 manifest 记录。

- `capture_screenshots()` 全面接入 `_wait_for_settle`：
  - 登录页 → `_wait_for_settle(page, "login")`
  - Dashboard → `_wait_for_settle(page, "dashboard")`
  - 每个模块列表 → `_wait_for_settle(page, "list")`
  - 弹窗截图 → `_wait_for_settle(page, "dialog")`，失败重试一次
  - 关闭弹窗 → `_wait_for_settle(page, "dialog_close")`

- `screenshot_manifest.json` 每条记录新增 3 个字段：
  - `wait_strategy`：对应的策略名（`login_idle` / `dashboard_idle` / `list_idle+row` / `dialog_anim` / `dialog_detached` / `dialog_timeout` / `none`）
  - `duration_ms`：实际等待耗时
  - `retried_after_fix`：仅表单对话筐步骤置位；True 表示 `wait_for_function` 首次失败、走 400ms 兜底

- `capture_screenshots` 失败诊断：当 `wait_for_function` 持续 3 秒未到稳态时抛错（不静默），然后走 400ms 兜底；`retried_after_fix=True` 让 manifest 出现"首次未达稳态"的痕迹，方便人工复审。

**测试：** `backend/tests/test_capture_screenshots.py` 新增 9 项专项测试：
1. `test_login_kind_uses_networkidle_and_short_sleep`（验证 login 走 networkidle + 200ms）
2. `test_dashboard_kind_waits_for_kpi`（验证 dashboard 选 KpiCard / kpi-grid / hero 之一）
3. `test_list_kind_waits_for_row`（验证 list 等待首行 + 250ms）
4. `test_dialog_kind_succeeds_on_first_try`（验证 dialog 一次成功时 `retried=False`）
5. `test_dialog_kind_uses_wait_for_function_with_correct_script`（验证 dialog 首次失败时 `retried=True`，包含 overlay opacity 与 wrapper transform 校验）
6. `test_dialog_close_waits_for_detached`（验证 dialog_close 等 detached）
7. `test_unknown_kind_returns_none_strategy`（兜底）
8. `test_result_contains_duration_and_strategy`（返回值结构）
9. `test_manifest_includes_wait_strategy_and_duration`（manifest 写入 `wait_strategy` / `duration_ms` 字段，兼容 `module_create` 带 `retried_after_fix`）

**整体验证：**
- `python -m unittest discover -s tests`：129 项全过。
- `npm.cmd run build`：通过，132.55 kB JS / 15.06 kB CSS。
- `git diff --check`：exit 0。

**非目标（已确认不改）：**
- 不调整生成项目的 UI 组件（动画时长、过渡曲线）。
- 不替换 Element Plus 主题或全局样式。

**剩余观察项：**
- 是否需要把 `duration_ms` 阈值告警加入 `compliance_report.json`（例如 `> 1500ms` 标黄），便于批跑时定位异常任务。
- 真实 MiniMax 任务端到端截图仍建议补跑一次，确认弹窗视觉和整页蒙层效果。
- `dialog_anim` 的 `wait_for_function` 超时（3s）是否需要可配置（目前硬编码）。

#### 第二轮修正（2026-06-24，对话框整页截图蒙层只覆盖视口顶部）

- 触发：用户复核截图反馈"下半部分明显有主页菜单跟子菜单重合在一起"。
- 根因：dialog 截图仍走 `full_page=True`，但 Element Plus 的 `.el-overlay` 是 `position: fixed; inset: 0`，在 Playwright 整页截图里只会渲染在视口顶部那一段（~900px），视口下方的页面表格会原样进入图片，看上去就是"主页面菜单和对话框上下叠在一起"。
- 修复：在 `capture_screenshots()` 截图前调用 `_stretch_overlay_to_page(page)`，用 JS 把 overlay 改成 `position: absolute; top: 0; left: 0; right: 0; width: 100%; height: document.documentElement.scrollHeight + 'px'; minHeight: 100vh`。这样蒙层覆盖整页，主页面表格被一并压暗，dialog 本身仍由 Element Plus 居中。
- manifest 字段：在 `module_create` 条目新增 `overlay_full_page: bool`，记录本次截图前是否成功把蒙层改为 absolute + 整页高度。`false` 时说明页面里没有 `.el-overlay`（dialog 未就绪 / 已关闭），需人工复审。
- 对话框截图保持 `full_page=True`，不切到视口截图，避免长 dialog（14+ 字段）底部被裁掉。
- 测试：在 `backend/tests/test_capture_screenshots.py` 新增 `StretchOverlayTests`，共 2 项：
  1. `test_returns_false_when_overlay_missing`：DOM 无 `.el-overlay` 时返回 `False`，evaluate 仍被调用。
  2. `test_returns_true_when_overlay_present`：DOM 有 overlay 时返回 `True`，并校验脚本包含 `position: absolute` + `scrollHeight` + `100%`。
- 验证：后端 `131` 项单测（129 原有 + 2 新增）通过；工厂前端 `npm.cmd run build` 通过；`git diff --check` exit 0。
- Codex 代码复审：`tests.test_capture_screenshots` 通过；真实 MiniMax 端到端截图仍建议补跑。

## 新窗口接手说明

新会话开始时，按以下顺序读取：

1. `AGENTS.md`：当前结论、工作区状态、开发约束和快速命令。
2. `README.md`：启动方式、产品能力和用户操作流程。
3. `docs/ISSUES.md`：需求来源、实现状态、验证结果和剩余风险。
4. `docs/FLOW.md`：当前代码的真实流程、状态机、接口和关键文件。

新窗口必须以文件和 Git 工作区为准，不依赖聊天记忆。任何业务流程变化都应同步更新上述四份文档。

### ISSUE-023：AI 增强项目代码几乎全部失败（jobId=20260623225150-e2f31fbd 复盘）

- 状态：`已修正，Codex 代码复审通过`
- 优先级：`P0`
- 首次记录：2026-06-24
- 复现任务：jobId=20260623225150-e2f31fbd（涉案车辆管理系统，`codegen_mode=auto`，`public_security` 行业）
- 现象：5 个 UI 子步骤中 4 个 `failed`（shell / business / dashboard / responsive），仅 `theme` + `readme` 成功；`codegen_changed_files=["README.md"]`，`frontend/src/style.css` 实际未被 AI 修改但 `codegen_actual_mode="llm"`，语义失真。

#### 失败根因（已逐个验证）

| # | 子步骤 | 错误 | 根因 |
|---|---|---|---|
| 1 | shell | `未包含可校验的 CSS 选择器` | LLM 返回的 CSS 没有裸规则可解析 |
| 2 | business | `Code enhancer API read timed out`（246s） | daemon Worker 走 urllib 直读，`urlopen(timeout=)` 只覆盖 connect，不覆盖 SSL read |
| 3 | dashboard | `content > 8000 chars` | `UI_STEP_MAX_BLOCK_CHARS=8000` 过死，Pydantic 校验失败不重试 |
| 4 | responsive | `未授权选择器: [':root', 'html', '.el-button', 'select', 'textarea']` | `UI_STEP_SELECTOR_HINTS["responsive"]` 不含 Element Plus 基础选择器 |

共同病灶：`max_attempts=2` + `time.sleep(2/4s)` 无 jitter；`actual_mode` 语义 bug；enhance 失败未自动写 `.learnings/`；`worker_pid=39564` 在 `status=success` 后未收尾。

#### 修复方案（Claude 实施 2026-06-24）

- **P0-1 白名单补全**：`UI_STEP_SELECTOR_HINTS["responsive"]` 增补 `:root` / `html` / `select` / `textarea` / `.el-button` / `.el-button--primary` / `.el-input` / `.el-tag` / `.el-form` / `.el-dialog`；新增 `GLOBAL_UI_SELECTOR_HINTS = (":root", "--ai-")`，`_selector_matches_hints` 优先匹配，使 CSS 变量声明始终合法。
- **P0-2 size 16000 + 精简重试**：`UI_STEP_MAX_BLOCK_CHARS` 默认从 8000 提升到 16000（`AI_CODEGEN_UI_BLOCK_MAX_CHARS` 可覆盖）；`_request_ui_step` 内 `UIStepBlock.model_validate` 抛 `ValidationError` 且含 `string_too_long` 时，向 LLM 发 1 条"精简后再发"反馈，二次失败才标 `failed`。
- **P0-3 `_retry_with_backoff` helper**：抽 `_retry_with_backoff(operation, max_attempts=3, retry_callback)`，`time.sleep(min(2 ** attempt, 8) + random.uniform(0, 1))`；HTTP 4xx 中除 429 外直接抛；`call_api` 与 `_call_chat_json` 复用 helper。`max_attempts` 通过 `AI_CODEGEN_MAX_ATTEMPTS` 覆盖。
- **P0-4 llm 容忍 1 步失败**：`enhance_project` 中 `if requested_mode == "llm" and len(ui_failures) >= 2` 才整体回滚并抛 `RuntimeError`；移除冗余的后置整体回滚。
- **P0-5 `actual_mode` 新增 `partial`**：`EnhancementResult.actual_mode` 改为 `Literal["template", "llm", "partial"]`；`"frontend/src/style.css" in changed_files` 为真 → `llm`，否则若 README 改了 → `partial`，否则走 `template` fallback；`partial` 时 `summary` 末尾追加"（仅 README 由 AI 增强，UI/CSS 增强全部失败回滚到模板）"。
- **P1-1 `.learnings/` 自动记录**：新建 `backend/app/learning.py`，提供 `classify_failure()` 与 `append_enhance_error()`；`_record_enhance_failure()` 在 `enhance_project` 三个 return 路径前各调用一次，try/except 兜底；文件命名 `ERRORS-YYYYMMDD-enhance.md`，编号跨会话单调递增；失败根因分类 8 类。
- **P1-2 测试覆盖**：`backend/tests/test_enhancer.py` 新增 6 项 + 调整 1 项，共 18 项：test_responsive_allows_basic_selectors、test_dashboard_oversized_block_retries_with_trim_prompt、test_business_recovers_from_read_timeout_with_backoff、test_llm_mode_tolerates_one_ui_step_failure、test_actual_mode_partial_when_only_readme_changed、test_partial_failures_write_to_learnings；既有 `test_llm_mode_any_failure_rolls_back` 改为 `test_llm_mode_two_failures_rolls_back`。
- **P1-3 worker 状态机告警**：`workflow.py continue_material_generation` 末尾若 `run_status=running` 但 `status=success`，打 warning log 提醒 demo 进程未显式停止；不主动 kill（用户可能正在浏览器看 demo）。

#### 验证

- `python -m unittest tests.test_enhancer`：18/18 全过。
- `python -m unittest discover -s tests`：全量通过。
- `npm.cmd run build`：通过。
- `git diff --check`：exit 0。
- 复用本 job planning 跑一次新任务，5 个 UI 子步骤 `status=completed` 数 ≥ 4，`codegen_actual_mode ∈ {llm, partial}`，`.learnings/ERRORS-YYYYMMDD-enhance.md` 含本任务失败条目（如全部成功则无）。

#### 剩余风险

- daemon Worker 下 SSL read timeout 仍未根本解决（246s 挂死靠 `max_attempts=3` + 退避 + 早失败缓解），完整 `multiprocessing` 改造留 ISSUE-023 L2 或 ISSUE-008 L2 统一处理。
- 前端 `HomePage.vue` 需支持展示 `actual_mode=partial` 状态（与 `llm` / `template` 区分），后续 ISSUE 跟进。
- `.learnings/` 并发写当前依赖单进程顺序写；如未来多 worker 并发，需要文件锁或 UUID 后缀去重。

### ISSUE-024：白名单与生成器实际 class 失配，split_console / dashboard / Element Plus BEM 派生类未覆盖

- 状态：`已由 ISSUE-025/026 覆盖并落地，不再等待统一修改`
- 优先级：`P0`
- 首次记录：2026-06-24
- 关联：ISSUE-023（其白名单与 retry + actual_mode 修复已落地，但未覆盖本 ISSUE 暴露的"白名单与生成器实际 class 失配"问题）
- 复现任务：`20260624095339-9d44c135`（涉案车辆管理系统，`public_security` 行业，`codegen_mode=auto`）

#### 现象与影响

5 个 UI 子步骤中 4 个 `failed`（shell / business / dashboard / responsive），仅 `theme` + `readme` 成功；任务**未真失败**（`status=awaiting_demo_review`、`run_validation` 全 passed、`run_status=stopped`），但 `codegen_changed_files=["README.md"]`，`frontend/src/style.css` 实际未被 AI 修改，`codegen_actual_mode="partial"`。

| # | 子步骤 | attempts | duration_ms | 未授权选择器 |
|---|---|---|---|---|
| 1 | shell | 2 | 284422 | `*`, `html`, `@media(max-width:900px)`, `.shell-split`, `.shell-main` |
| 2 | business | 2 | 550155 | `.el-card__header`, `.el-card__header span`, `.el-card__body`, `.el-button--success`, `.el-button--warning` |
| 3 | dashboard | 2 | 931375 | `.kpi-grid`, `.kpi-trend`, `.kpi-trend-down .kpi-trend`, `.kpi-spark`, `.dashboard-row` |
| 4 | responsive | 2 | 115000 | `.dashboard-row`, `.kpi-grid`(×2), `.module-dashboard`(×2) |

`.learnings/ERRORS-20260624-enhance.md` 已自动记录（ERR-20260624-049，ISSUE-023 P1-1 生效）。

#### 根因（已逐条与代码核对）

- **根因 A 白名单与生成器实际 class 失配**：`project_generator.py` 实际生成 `.kpi-grid`、`.kpi-trend`、`.kpi-row`、`.dashboard-row`、`.shell-split`、`.shell-main`、`.module-dashboard`、`.status-row`、`.analysis-workbench` 等类，但 `UI_STEP_SELECTOR_HINTS["dashboard"]` 用的是已废弃的 `.metric-grid`、`.kpi-icon`、`.activity-panel` 等名称；`shell` 步 hint 缺 `.shell-split` / `.shell-main` / `@media`。
- **根因 B `html` / `*` 未进 GLOBAL_UI_SELECTOR_HINTS**：当前仅 `(":root", "--ai-")`；LLM 表达"全局基础"几乎只能用 `html { font-family }` 或 `* { box-sizing }`。
- **根因 C Element Plus BEM 派生类未覆盖**：白名单只允许基础类（`.el-card`、`.el-button`），不允许派生类（`.el-card__header`、`.el-card__body`、`.el-button--success` 等）；LLM 想覆盖 Element Plus 主题被拒。
- **根因 D dashboard / responsive 步 hints 与实际生成器 class 不对称**：dashboard 步要写 `.kpi-trend`、`.dashboard-row`，但 hints 没列；responsive 步同样。

#### 修复方案（已由 ISSUE-025/026 后续落地覆盖）

- **P0-1 白名单与生成器 class 对齐**：按 `project_generator.py` grep 出的实际 class 重写 `UI_STEP_SELECTOR_HINTS` 4 步；`GLOBAL_UI_SELECTOR_HINTS` 补 `html` 与 `*`；`_selector_matches_hints` 的 `*` 匹配需特判（仅 `*` / `*::before` / `*::after` 等通用重置放行）。
- **P0-2 系统化白名单来源**（长期方案）：新建 `backend/app/selector_audit.py`，由 `project_generator.py` 模板扫描生成实际 class 集合；CI 校验漂移并写 `.learnings/` 告警。**本次仅手动对齐**，自动化留后续。
- **P0-3 LLM 越界防御强化**：在放宽白名单同时，`UI_STEP_FORBIDDEN_SELECTORS` 增 Vue 事件绑定 / JS 关键字 / 模板字符串等禁片；`_validate_ui_block` 加"内容字符集合"扫描。
- **P1-1 `.learnings/` 修复建议链接修正**：`backend/app/learning.py` 写死的 `../docs/ISSUE-022.md` 链接（ISSUE-022 实际是截图抓拍时机）改为参数化（由调用方传 ISSUE 编号）。
- **P1-2 测试覆盖**：`backend/tests/test_enhancer.py` 新增 7 项 + 调整 1 项：test_shell_allows_split_console_selectors、test_shell_allows_html_and_universal_selectors、test_shell_allows_at_media_query、test_business_allows_element_plus_bem_modifiers、test_dashboard_allows_real_generator_selectors、test_responsive_allows_dashboard_layout_selectors、test_forbidden_selectors_still_rejected_after_whitelist_expansion。
- **P1-3 文档同步**：`AGENTS.md` / `README.md` / `docs/FLOW.md` / `ISSUE-020.md` 等「统一修改」后同步（用户硬性约束）。

#### 约束与风险

- `*` 放行可能被滥用写 `* { display:none }` 等破坏性规则：缓解靠禁片 + 字符集合扫描 + 实际 style.css 构建验证（破坏性 CSS 会让 `npm run build` 失败 → 自动回滚）。
- Element Plus BEM 派生类前缀放行风险：建议用"前缀+通配符"（`.el-card__*`），但 Python 端 `_selector_matches_hints` 是字面前缀匹配，需扩展支持 `__*` 通配。
- `project_generator.py` 改 class 名时白名单同步滞后：P0-2 系统化方案是长期解。
- `actual_mode=partial` 仍是合法状态：本次修复目标是让 `actual_mode` 回到 `llm` 而非 `partial`，但 `partial` 的兜底语义本身正确（ISSUE-023 P0-5）。

#### 验收标准

- 复用本 job planning 跑一次新任务，5 个 UI 子步骤 `status=completed` 数 ≥ 4。
- `codegen_actual_mode` 回到 `llm`；`frontend/src/style.css` 含 ≥ 3 个 `AI UI Enhancer:` marker。
- `.learnings/ERRORS-YYYYMMDD-enhance.md` 不再出现 `whitelist_strict(shell|business|dashboard|responsive)` 条目（除非新类未覆盖）。
- 既有 18 项 `test_enhancer.py` 测试不退；新增 7/7 通过。
- 4 份交接文档（AGENTS.md / README.md / docs/ISSUES.md / docs/FLOW.md）与本 ISSUE 同步更新。

完整根因 + 修复方案见 [ISSUE-024.md](ISSUE-024.md)。

### ISSUE-025：白名单仍漏 Element Plus 全家族 + 伪元素组合 + LLM 自创派生类

- 状态：`已修正，Codex 代码复审通过`
- 优先级：`P0`
- 首次记录：2026-06-24
- 关联：ISSUE-024（白名单与生成器实际 class 对齐，**仍有 3 类盲区**——Element Plus 其它组件未列、伪元素组合未特判、LLM 自创派生未启发式覆盖）
- 复现任务：`20260624140839-03bb66f7`（涉案车辆管理系统，`public_security` 行业，`codegen_mode=auto`，`ui_plan.shell="top_workspace"`）

#### 现象与影响

ISSUE-024 落地后新回归：5 步 UI 中 `shell` + `theme` + `readme` 成功（ISSUE-024 修复生效），`business` / `dashboard` / `responsive` 3 步仍 `failed`。`codegen_actual_mode="llm"`（shell 步成功改了 style.css），但 style.css 实际只有 1/5 步成功追加。

| # | 子步骤 | status | 未授权选择器 |
|---|---|---|---|
| 1 | theme | completed | - |
| 2 | shell | completed | - |
| 3 | business | failed | `.el-table--border::after`, `.el-pagination`, `.el-pagination .btn-prev`, `.el-pagination .btn-next`, `.el-pagination .el-pager li` |
| 4 | dashboard | failed | `.m-trend-up`, `.dashboard-trend-card`, `.dashboard-task_dashboard`, `.pattern-dashboard` |
| 5 | responsive | failed | `.page-heading`, `.page-heading h2`, `.page-heading .actions`, `.page-heading .actions .btn-primary`, `.page-heading .actions .btn-ghost` |

`.learnings/ERRORS-20260624-enhance.md` 已自动记录 `ERR-20260624-122`。

#### 根因

- **A Element Plus 全家族遗漏**：ISSUE-024 P0-1 仅列 `.el-card--*` / `.el-button--*` / `.el-tag--*` / `.el-dialog--*`，**漏了** `.el-table--*` / 整个 `.el-pagination` 组件 / `.el-checkbox--*` / `.el-radio--*` / `.el-select--*` / `.el-tooltip` / `.el-message` / `.el-notification` / `.el-popover` / `.el-dropdown` / `.el-menu` / `.el-upload` / `.el-tabs` 等常见业务组件；以及 Element Plus 2.x 渲染 `<el-pagination>` 时注入的内部类 `.btn-prev` / `.btn-next` / `.el-pager`。
- **B 派生类 + 伪元素组合**：`.el-table--border::after` 由"派生类 + 伪元素"组成；ISSUE-024 在 `_selector_matches_hints` 特判了 `*::before/after`，但前提是 `.el-table--*` 必须在 hints 里——实际漏列。
- **C LLM 自创派生类**：`selector_audit.collect_real_selectors` 只扫生成器模板写入的 class，LLM 自由发挥的派生（`.dashboard-trend-card` / `.m-trend-up` / `.pattern-dashboard` / `.btn-primary` / `.btn-ghost`）不在生成器里；`merge_with_hints` 启发式关键字太窄。

#### 修复方案（Claude 实施 2026-06-24）

- **P0-1 业务步补 Element Plus 全家族 + 自定义按钮 + 模块派生通配**：
  - `.el-table--*` / `.el-pagination` / `.el-pager` / `.btn-prev` / `.btn-next` / `.el-checkbox--*` / `.el-radio--*` / `.el-select--*` / `.el-tooltip` / `.el-message` / `.el-notification` / `.el-popover` / `.el-popper` / `.el-dropdown` / `.el-menu` / `.el-upload` / `.el-tabs`
  - `.btn-primary` / `.btn-ghost` / `.btn-default` / `.btn-danger` / `.btn-success` / `.btn-warning` / `.btn-info` / `.btn-link` / `.btn-text`
  - `.module-*` / `.task-*` / `.form-*` / `.page-heading` / `.actions`
- **P0-2 dashboard 步补 LLM 派生通配**：`.dashboard-*` / `.m-*` / `.pattern-*` / `.trend-*` / `.stat-*` / `.metric-*` / `.el-card__*` / `.el-tag--*`。
- **P0-3 responsive 步补 page-heading / actions / btn-***：`.page-heading` / `.actions` / `.btn-primary` / `.btn-ghost` / `.btn-default`。
- **P0-4 selector_audit 关键字扩展**：business_keywords / dashboard_keywords / responsive_keywords 各加一组 LLM 派生关键字。
- **P1 测试覆盖**：`backend/tests/test_enhancer.py` 新增 4 项（test_business_allows_pagination_and_pseudo_element / test_dashboard_allows_llm_derived_selectors / test_business_allows_custom_button_classes / test_responsive_allows_page_heading_and_actions），共 31 项全过。
- **P2 文档同步**：AGENTS.md / README.md / docs/FLOW.md / ISSUE-020.md 同步加 ISSUE-025 章节。

#### 约束与风险

- 大幅放宽白名单（`.dashboard-*` / `.m-*` / `.pattern-*` 等）可能掩盖 prompt 越界，需配合 `_scan_css_chars` 字符扫描与 `UI_STEP_FORBIDDEN_SELECTORS` 禁片兜底。
- 真实 LLM 仍可能写出"完全意料之外"的派生命名空间；当前缓解靠字符扫描 + 禁片 + 实际 `npm run build` 验证。
- `selector_audit.audit_drift` 当前只在 `.learnings/` 写漂移告警，未在 CI 中定期执行。

#### 验收标准

- 复用本 jobId planning 跑一次新任务，5 个 UI 子步骤 `status=completed` 数 ≥ 4。
- `codegen_actual_mode` 为 `"llm"`（不再是 `"partial"`）；`frontend/src/style.css` 含 ≥ 3 个 `AI UI Enhancer:` marker。
- `.learnings/ERRORS-YYYYMMDD-enhance.md` 不再出现 `whitelist_strict(business)` / `whitelist_strict(dashboard)` / `whitelist_strict(responsive)` 条目（除非新类未覆盖）。
- 既有 27 项 `test_enhancer.py` 测试不退；新增 4/4 通过。
- 4 份交接文档（AGENTS.md / README.md / docs/ISSUES.md / docs/FLOW.md）与本 ISSUE 同步更新。

完整根因 + 修复方案见 [ISSUE-025.md](ISSUE-025.md)。

### ISSUE-026：workflow.py logger NameError + daemon SSL read timeout + CSS 空响应

- 状态：`已修正，Codex 代码复审通过`
- 优先级：`P0`
- 首次记录：2026-06-24
- 关联：ISSUE-023（P1-3 worker 状态机告警实施遗漏 logger 定义，埋 NameError 雷；P0-3 retry 未真正解决 daemon SSL read 挂死）
- 复现任务：`20260624160110-58039b6d`（涉案车辆管理系统，`codegen_mode=auto`） + 用户进入"打包软著材料"阶段崩溃

#### 现象与影响

jobId=`20260624160110-58039b6d` 跑出 5 步 UI 增强结果：
- theme / shell / dashboard completed
- business failed（`RuntimeError: Code enhancer API read timed out`，1006s = 16 分钟）
- responsive failed（`未包含可校验的 CSS 选择器`，LLM 返回 `@media{} {/* 注释 */}`）

用户随后点"打包软著材料" → 触发 `workflow.continue_material_generation` → 末尾 `logger.warning(...)` 调用抛 **`NameError: name 'logger' is not defined`**，**直接阻断软著材料打包流程**。

#### 根因（3 类独立 bug）

- **A `workflow.py` logger NameError**：ISSUE-023 P1-3 在 `continue_material_generation` 末尾新增 `logger.warning(...)` 调用，但**未在模块顶部 `import logging` 也未定义 `logger`**。
- **B daemon Worker 下 SSL read timeout 无法强制中断**：`urllib.request.urlopen(timeout=N)` 只覆盖 TCP connect，不覆盖 SSL read；jobId=20260624160110-58039b6d 的 business 步在 SSL read 挂死 1006s；`multiprocessing.Process` 在 daemon Worker 下被禁用。
- **C LLM 多次返回空 CSS 时整步 failed 阻断任务**：`_request_ui_step` 在 `_validate_ui_block` 抛"未包含可校验的 CSS 选择器"时，`_enhance_ui_steps` 标 failed 并重试 2 次仍失败，最终阻断任务。

#### 修复方案（Claude 实施 2026-06-24）

- **P0-1 workflow.py logger NameError**：`import logging` + `logger = logging.getLogger(__name__)`。
- **P0-2 daemon Worker 下 SSL read timeout**：第一版 `ThreadPoolExecutor + future.result(timeout)` 被 Codex 复审核出无法杀死后台线程，现改为独立 Python subprocess 执行 LLM HTTP 请求；主进程通过 `subprocess.run(..., timeout=AI_CODEGEN_TIMEOUT+10)` 做硬截止，超时会杀掉请求子进程并转 `RuntimeError("Code enhancer API read timed out (daemon worker, Ns wall-clock)")`。非 daemon 远端调用仍走 `multiprocessing` 硬超时，本地 `127.0.0.1/localhost` 直接走传输层 timeout。
- **P0-3 LLM 空 CSS 响应 → skipped 而非 failed**：`UIStepResponse.block: Optional[UIStepBlock] = None` + `skip_reason`；`_request_ui_step` 在 `_validate_ui_block` 之前检查 `_css_rule_selectors(block.content)`，空 selectors → 返回 `UIStepResponse(block=None, skip_reason=...)`；`_enhance_ui_steps` 调用方标 `status="skipped"` 且 **`success=True`**（避免被下方 `if not success:` 覆盖为 failed）。
- **P1 测试覆盖**：`backend/tests/test_enhancer.py` 新增/调整后共 35/35 全过：`test_workflow_logger_imported` / `test_daemon_worker_uses_transport_timeout_without_child_process` / `test_daemon_subprocess_error_is_reported` / `test_daemon_worker_read_timeout_bounded` / `test_empty_css_response_is_skipped`。
- **P2 文档同步**：AGENTS.md / README.md / docs/FLOW.md / ISSUE-020.md / ISSUE-026.md（本文件）+ docs/ISSUES.md 末尾追加。

#### 约束与风险

- daemon 分支现在每个远端 LLM 请求会启动一个 Python 子进程，稳定性优先于性能；如果后续并发量上升，可再改为常驻受控 worker 池。
- LLM 空响应是提示词工程问题，本 ISSUE 仅做"任务不被阻断"兜底，未强制重试要求返回 ≥1 个 CSS 规则。
- `success=True` 在 skipped 分支的修复是**必要修补**，未来 `_enhance_ui_steps` 重构时要保留。

#### 验收标准

- 用户进入"软著材料打包"阶段不再抛 `NameError`。
- daemon Worker 下 LLM API SSL read 挂死能在 12s wall-clock 窗口内被强制中断（不是 1006s 后）。
- LLM 多次返回空 CSS 时 UI 子步骤标 `skipped` 而非 `failed`，任务不被阻断。
- 既有 31 项测试不退；新增 3/3 通过。
- 端到端 AI 增强代码流程 PASS（4 completed + 1 skipped，`actual_mode=llm`）。
- 4 份交接文档与本 ISSUE 同步更新。

完整根因 + 修复方案见 [ISSUE-026.md](ISSUE-026.md)。

完整根因 + 修复方案见 [ISSUE-025.md](ISSUE-025.md)。

### ISSUE-027：Planner 响应含 `<think>` 示例 JSON 时误提取局部对象

- 状态：`已修正，Codex 代码复审通过`
- 优先级：`P0`
- 首次记录：2026-06-25
- 复现任务：`20260625095657-0ed4e081`

#### 现象与影响

任务在“生成软件规划”阶段失败，`status.json` 报：

```text
PlannerValidationError: ValidationError: 8 validation errors for Planning
software_name / description / software_type / modules / database_tables / api_list / screenshots / document_outline Field required
```

诊断文件 `planner_raw_repair.txt` 实际包含完整规划 JSON，但前置 `<think>` 推理文本里也包含一个小示例对象：

```json
{"detail_pattern": "workflow_timeline", "edit_pattern": "drawer"}
```

旧版 `_first_json_object()` 返回“第一个语法合法 JSON 对象”，导致提取到这个局部对象，再交给 `Planning.model_validate()` 时缺少全部规划必填字段。

#### 根因

JSON 容错提取只按语法合法性排序，没有按 Planner schema 形状排序。模型使用 `<think>` 或解释文本时，推理内容中的局部 JSON 会遮挡最终完整规划 JSON。

#### 修复方案（Codex 实施 2026-06-25）

- `backend/app/planner.py`：收集响应中的所有合法 JSON 对象；优先返回包含规划关键顶层字段的对象（`software_name` / `modules` / `database_tables` / `api_list` / `screenshots` / `document_outline` 等），没有规划形状对象时才回退到旧行为。
- `backend/tests/test_planner.py`：新增两项回归测试：
  - `<think>` 中的小 JSON 不应遮挡最终 Planning JSON。
  - 首次校验失败后，修复响应含 `<think>` 示例 JSON 时，`build_planning()` 应成功提取最终规划。

#### 验证结果

- `python -m unittest tests.test_planner -v`：34 项通过。
- 使用 `outputs/20260625095657-0ed4e081/planner_diagnostics/planner_raw_repair.txt` 做本地解析验证：成功解析为 5 个模块，首模块 `vehicle_archives`。
- `git diff --check`：通过，仅 CRLF 提示。

### ISSUE-028：最小任务 AI 代码增强端到端跑通专项

- 状态：`已修正，端到端任务通过`
- 优先级：`P0`
- 首次记录：2026-06-25
- 成功任务：`20260625123758-c69d4bcd`

#### 目标

按用户要求，用一个最小化任务开启 AI 代码增强，从规划、项目生成、AI 增强、运行验证、在线 Demo、自动截图、文档生成、合规检查到 ZIP 打包完整跑通；过程中遇到阻塞直接定位、修复、记录，不停在中途等待人工决策。

#### 本轮暴露并修复的问题

- **生成项目前端路由冲突**：当 LLM 规划出 `module.key = dashboard` 时，生成器同时创建首页 `DashboardPage.vue` 与业务模块 `DashboardPage.vue`，导致 Vite 报 `Identifier 'DashboardPage' has already been declared`。已将首页组件改为 `HomeDashboardPage.vue`，根路由 name 改为 `home`，并新增回归测试。
- **daemon Worker 子进程 JSON/Unicode 失败**：MiniMax 响应里可能包含孤立 surrogate 或 stdout 混入调试行，daemon 子进程 JSON 输出会解析失败。已新增 `_sanitize_json_strings()` 与 `_loads_last_json_object()`，子进程 payload 使用 `ensure_ascii=True`，只解析最后一行 JSON。
- **Code Enhancer 重试倍增导致长时间卡住**：原逻辑外层 UI step retry 与内层传输 retry 叠加，单个 UI 步骤可能变成多轮重复长请求。已收敛 `_call_chat_json()` 的传输重试边界，JSON 修复只追加一次修复请求，UI 子步骤 `max_attempts` 降为 1。
- **UI 增强大上下文导致 style 步骤超时**：已压缩 UI 子步骤 prompt，只传必要 scope hints 与主题 token，移除大段 CSS tail 依赖。
- **LLM UI 步骤远端超时/坏 JSON 阻断任务**：在远端超时、硬超时、JSON 解析失败等可恢复错误下，UI 子步骤会使用由 LLM theme token 派生的本地稳定 CSS fallback，并通过同一选择器白名单校验；选择器越权、Vue/JS 注入等安全错误仍保持失败。
- **运行验证 npm install 超时**：生成项目存在 `node_modules` 时跳过重复安装；需要安装时使用 `npm install --no-audit --no-fund --prefer-offline`，超时由 `NPM_INSTALL_TIMEOUT` 控制，默认 600 秒。
- **Windows status.json 读取瞬时 PermissionError**：状态轮询 `_json_read()` 对 `PermissionError` 做短暂重试，避免 Worker 写入期间前端轮询触发 ASGI 500。
- **本地配置规划超时过低**：当前 MiniMax 配置已通过设置接口同步为 `AI_PLANNER_TIMEOUT=180`、`AI_CODEGEN_TIMEOUT=240`，避免新任务在规划阶段因 60 秒默认值提前失败。

#### 最终验收结果

成功任务 `20260625123758-c69d4bcd`：

- `status=success`，`progress=100`，`failed_stage=null`。
- `codegen_mode=llm`，`codegen_actual_mode=llm`。
- AI 增强节点：`theme completed`、`shell skipped`、`business completed`、`dashboard completed`、`responsive completed`、`readme completed`。其中 `shell skipped` 是 LLM 返回空 CSS 后的受控跳过，不是失败。
- 运行验证：`frontend_build=passed`、`backend_structure=passed`、`maven_test=passed`。
- 截图：12 张。
- 文档：`源代码材料.docx`、`用户操作手册.docx`、`设计说明书.docx`、`软件著作权申请信息表.docx`、`软著材料合规检查报告.docx`。
- 产物：`copyright_package.zip` 约 5.1 MB，`generated_project.zip` 约 125 KB。
- 在线 Demo 已启动：`demo_url=http://127.0.0.1:65381`，`swagger_url=http://127.0.0.1:65380/swagger-ui/index.html`。

#### 验证命令

```powershell
cd "C:\Users\whn\Documents\软著\backend"
python -m unittest tests.test_enhancer tests.test_project_generator tests.test_workflow_order -v

cd "C:\Users\whn\Documents\软著"
git diff --check
```

验证结果：

- 后端专项测试 48 项通过。
- `git diff --check` 通过，仅有既有 CRLF 换行提示。

#### 剩余风险

- `shell` UI 子步骤在最终成功任务中因 LLM 空 CSS 被标记为 `skipped`。该状态不会阻断任务，也不会回滚整体 AI 增强；后续如果要追求五步全部 completed，需要继续优化 shell 步 prompt。
- 当前 fallback 仅处理远端超时、硬超时和坏 JSON 等可恢复错误；选择器越权和非 CSS 注入仍会失败，这是保留的安全边界。
