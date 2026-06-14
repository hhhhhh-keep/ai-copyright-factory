# AI软著工厂 V1.0

输入软件名称、行业和描述后，系统先检索公安、政法、工业或教育行业知识库，完成需求澄清与 Planning Review，再生成 Java 17、Spring Boot 3、MyBatis Plus、MySQL、Vue 3 和 Element Plus 项目，以及截图、代码统计、DOCX 文档和最终 ZIP。

当前 P0 能力：

- 四行业结构化知识库与需求澄清。
- `planning.json` 锁定及知识库一致性约束。
- 每模块生成 Entity、DTO、VO、Mapper、Service、ServiceImpl、Controller、Vue 页面、API 文件和 SQL 表。
- 自动执行前端生产构建和 Maven 测试。
- 使用 H2 Demo 配置启动真实 Spring Boot 在线演示，生产配置保持 MySQL。
- 提供 Demo、Swagger、运行日志、启动、停止和一小时超时回收接口。
- 流水线顺序为运行验证、启动 Demo、复用 Demo 自动截图、生成文档、材料打包。
- 首页和历史任务页均可查看或重新启动 Demo，并可查看 Swagger、前后端日志和下载材料。

Phase 3 在模板项目生成后增加受约束的 AI Code Enhancer：

- 只允许修改 `frontend/src/App.vue`、`frontend/src/style.css` 和生成项目 `README.md`；Java 后端由确定性生成器负责。
- 模型必须返回结构化 JSON 和完整文件内容。
- 修改前自动备份原文件。
- 构建或语法验证失败时，`auto` 模式自动回滚到固定模板。
- `llm` 模式验证失败会终止任务，便于排查模型输出。

Phase 4 增加软著合规能力：

- 代码模块、API、截图、设计说明书和用户手册一致性检查。
- 自动将真实源码行数填入软件著作权申请信息表。
- 生成标准版、正式版或紧凑版文档。
- 生成 `compliance_report.json` 和《软著材料合规检查报告》。
- 按 100 分制输出模拟评分、评级、关键问题及整改建议。
- 最终材料增加《软件著作权申请信息表》。

## 软件规划确认

创建任务后不会立即生成项目。新流程为：

```text
输入软件信息
→ 生成 planning.json
→ 打开 /planning-review/{jobId}
→ 可视化修改模块、页面和数据库表
→ 保存并确认规划
→ 生成项目、截图和软著材料
```

任务状态：

- `draft_planning`：规划草稿可修改。
- `confirmed`：规划已锁定。
- `generating`：正在生成项目和材料。
- `success`：生成成功。
- `failed`：生成失败。

确认规划后，`planning.json` 将被锁定。Project Generator、Screenshot Agent、Doc Generator、Source Material Generator 和 Package Builder 均只读取该文件。

## Planner 配置

启动前后端后，可在首页点击“模型设置”，填写：

- API Base URL
- API Key
- 模型名称
- 请求超时
- 默认 Planner 模式

配置保存在：

```text
C:\Users\whn\Documents\软著\backend\.env
```

前端读取配置时不会返回 API Key 明文，只显示是否已配置及末四位。该文件已加入 `.gitignore`。

也可以手动复制配置文件并填写 OpenAI-compatible API：

```powershell
Copy-Item "C:\Users\whn\Documents\软著\backend\.env.example" "C:\Users\whn\Documents\软著\backend\.env"
```

```env
AI_PLANNER_MODE=auto
AI_PLANNER_BASE_URL=https://api.openai.com/v1
AI_PLANNER_API_KEY=你的密钥
AI_PLANNER_MODEL=你实际可用的模型名
AI_PLANNER_TIMEOUT=60
AI_CODEGEN_MODEL=代码增强模型名，留空则复用 Planner 模型
AI_CODEGEN_TIMEOUT=90
```

- `auto`：优先 LLM，失败自动回退模板。
- `llm`：强制 LLM，调用或 JSON 校验失败则任务失败。
- `template`：只使用 Phase 1 固定模板。

任务页面还可选择代码生成模式：

- `auto`：调用 AI Code Enhancer，构建失败自动回滚模板。
- `llm`：强制使用增强代码，失败时终止任务。
- `template`：不调用代码增强模型。

## 启动后端

```powershell
cd “C:\Users\whn\Documents\软著\backend”
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m uvicorn app.main:app --reload
```

## 启动前端

```powershell
cd “C:\Users\whn\Documents\软著\frontend”
npm.cmd install
npm.cmd run dev
```

浏览器访问 `http://127.0.0.1:5173`，使用默认的”智慧停车管理系统”输入即可验收。

最终文件生成到：

```text
C:\Users\whn\Documents\软著\outputs\{job_id}\copyright_package.zip
```

## 故障排查：Demo 一直停在”启动中”

启动 Demo 会经历 3 个阶段，前端会依次显示：

- `正在构建 JAR…`（首次约 1-3 分钟，二次启动秒级）
- `正在启动 Spring Boot…`（约 15 秒）
- `运行中`（绿色徽标，可点击”查看 Demo”）

若 UI 一直显示”启动中…”或变红色”启动失败”：

1. **检查 8000 端口是否被旧 uvicorn 占用**：

   ```powershell
   Get-NetTCPConnection -LocalPort 8000 -State Listen
   # 若有占用，先结束：
   Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
   ```

   旧 uvicorn 进程不会自动加载新代码，必须杀掉重启。

2. **查看 Maven 完整日志**：

   ```text
   outputs\{job_id}\logs\demo_build.log
   ```

   常见错误：
   - `PluginContainerException / Number of foreign imports: 1`：系统 PATH 上的 Maven 与项目不兼容。`workflow.py` 的 `_maven_command` 已经优先使用 IntelliJ 自带 mvn.cmd，确认本机已安装 IntelliJ IDEA 2023.1 / 2024.1 / 2025.1 之一即可。
   - `JAVA_HOME not set` / `java not found`：未安装 JDK 17 或未加入 PATH。

3. **清理残留 Java / Node 进程**：

   ```powershell
   Get-Process java, node -ErrorAction SilentlyContinue | Where-Object { (Get-CimInstance Win32_Process -Filter “ProcessId=$($_.Id)”).CommandLine -like '*软著*' } | Stop-Process -Force
   ```

4. **强制重新构建（跳过 JAR 复用）**：

   ```powershell
   Remove-Item “outputs\{job_id}\generated_project\backend\target” -Recurse -Force
   ```

5. **JDK 与 Maven 要求**：
   - JDK 17（`java -version` 应为 17.x）
   - Maven 3.9+（任意位置，IntelliJ 自带版本亦可）
