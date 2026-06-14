# AI 软著工厂 — 完整流程图

> 适用版本：当前代码（2026-06-12，含样例数据 + Demo 启动修复）。
> 阅读路径：架构概览 → 用户旅程 → 状态机 → 关键文件 → 并发安全。

---

## 0. 系统架构总览

```
┌──────────────────────────────────────────────────────────────────────┐
│                         用户浏览器 (Vue 3 SPA)                        │
│  HomePage        HistoryPage        PlanningReviewPage              │
│  表单+进度       历史任务列表        模块/页面/表的可视化编辑         │
└──────────────────┬───────────────────────────────────────────────────┘
                   │ fetch / axios (CORS allowed: 5173 ↔ 8000)
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   FastAPI :8000  (uvicorn)                           │
│  ┌─ main.py ──────────────────────────────────────────────────────┐ │
│  │ 19 个 HTTP 端点 (POST /api/jobs, /confirm, /demo/start, ...)   │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│  ┌─ workflow.py ───────────────────────────────────────────────────┐ │
│  │ STEPS[11] + tasks[10] 串行调度                                  │ │
│  │ start_online_demo / stop_online_demo / _launch_demo             │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│  ┌─ planner.py ───────────┐  ┌─ project_generator.py ──────────────┐│
│  │ LLM/template 双模式   │  │ Spring Boot + Vue 3 模板生成          ││
│  │ 读行业知识库           │  │ 含 5 表×15 条种子数据                 ││
│  └────────────────────────┘  └──────────────────────────────────────┘│
│  ┌─ enhancer.py ──────────┐  ┌─ compliance.py ──────────────────────┐│
│  │ AI 代码增强（白名单） │  │ 8 项 100 分制软著合规检查            ││
│  └────────────────────────┘  └──────────────────────────────────────┘│
│  ┌─ industry_knowledge ───┐  ┌─ settings.py ────────────────────────┐│
│  │ 4 行业模块/字段白名单 │  │ .env 读写 + Planner 公共/私有视图     ││
│  └────────────────────────┘  └──────────────────────────────────────┘│
└──────────────────┬───────────────────────────────────────────────────┘
                   │ 状态文件 + 多进程/线程后台
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│   outputs/{job_id}/   ←  ── 所有产物落盘到以 job_id 命名的子目录     │
│   ├─ status.json         (总指挥台: status/progress/current_step)    │
│   ├─ planning.json       (单一可信源: modules/fields/tables)        │
│   ├─ demo_runtime.json   (Demo 进程登记: pid/port/stage)            │
│   ├─ generated_project/  (Spring Boot + Vue 3 完整可运行项目)        │
│   ├─ screenshots/        (Playwright 截的 PNG)                     │
│   ├─ docs/               (.docx 软著材料)                           │
│   ├─ logs/               (backend.log / frontend.log / demo_build)  │
│   ├─ enhancement.json    run_validation.json  code_stats.json       │
│   ├─ compliance_report.json                                         │
│   └─ copyright_package.zip  ← 最终交付                              │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 1. 三大用户旅程

### 旅程 A — 提交表单到规划确认（人参与，每步等几十秒）

```
┌─────────────────────────────────────────────────────────────────┐
│ [A1] HomePage.vue: 填写表单 + 勾选行业模块                       │
│      form: software_name / industry_type / clarification_answers │
│            planner_mode / codegen_mode / document_template ...   │
│      提交按钮 ── POST /api/jobs ──┐                             │
└────────────────────────────────────┼────────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ [A2] main.py::submit_job (202 立即返回)                         │
│      ├─ create_job() 写 outputs/{job_id}/status.json            │
│      │   status="generating", progress=0, current_step=规划生成 │
│      │   steps[11项] 全 pending                                  │
│      └─ Process(generate_planning_draft).start()  ★ 异步        │
└──────────────────────────────────┬──────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ [A3] generate_planning_draft (后台进程)                         │
│      ├─ _step("planning", running)                              │
│      ├─ generate_planning() → build_planning()                  │
│      │   ├─ mode=template: 硬编码行业模板                       │
│      │   └─ mode=auto/llm:   POST {BASE_URL}/chat/completions   │
│      │      (失败 → fallback to template, 写 fallback_reason)   │
│      ├─ 写 outputs/{job_id}/planning.json                       │
│      │   含 software_name / modules[] / database_tables[]       │
│      │      / api_list[] / screenshots[] / document_outline[]   │
│      ├─ _step("planning", completed), progress=10               │
│      └─ _update status.json: status="draft_planning"            │
│              current_step="等待确认软件规划"                     │
└──────────────────────────────────┬──────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ [A4] HomePage 1.5s 轮询 GET /api/jobs/{jobId}                   │
│      status==="draft_planning" → router.push(/planning-review)  │
└──────────────────────────────────┬──────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ [A5] PlanningReviewPage.vue: 可视化编辑                         │
│      · 修改模块名 / 描述 / pages / fields                       │
│      · 新增/删除模块 (>=3 强制)                                 │
│      · 新增/删除表                                              │
│      三个按钮:                                                  │
│      ├─ 重新生成规划 → POST /api/planning/regenerate            │
│      │   (复位 steps, 重 spawn Process(generate_planning_draft))│
│      ├─ 保存规划   → PUT /api/planning/{jobId} (写盘)           │
│      └─ 确认并开始生成                                          │
│          ├─ PUT /api/planning/{jobId} (隐式保存)                │
│          └─ POST /api/jobs/{jobId}/confirm (202 立即返回)       │
│              ├─ 校验 planning.json 存在                         │
│              ├─ _update status.json: status="confirmed"         │
│              └─ Process(run_job).start()  ★ 异步 10 步流水线   │
└─────────────────────────────────────────────────────────────────┘
```

### 旅程 B — 主流水线 10 步（run_job 串行，约 3-10 分钟）

```
Process(run_job, job_id)
  │
  ▼
[step 1] project ─ generate_java_project
  │ 读 planning.json
  │ 写 generated_project/
  │   ├─ backend/  (pom.xml, src/main/java/.../*.{java},
  │   │             src/main/resources/{application.yml,
  │   │             application-demo.yml, schema-demo.sql,
  │   │             data-demo.sql ← 75 条种子})
  │   ├─ frontend/ (package.json, src/{App.vue,main.js,router.js,
  │   │              views/*Page.vue, api/*.js, config/*.js})
  │   └─ sql/init.sql, README.md
  ├ 进度 ≈ 18%
  ▼
[step 2] enhance ─ enhance_project
  │ 备份 .enhancer_backup/{App.vue, style.css, README.md}
  │ 调 LLM (只允许改这 3 个白名单文件)
  │ 写 enhancement.json: actual_mode / model / changed_files
  │ auto 模式失败 → fallback to template (保留 .enhancer_backup)
  ├ 进度 ≈ 25%
  ▼
[step 3] run ─ run_generated_project
  │ 1) npm install (180s)
  │ 2) npm run build (120s)
  │ 3) 校验 Java 项目结构
  │ 4) mvn test (300s)
  │ 写 run_validation.json: frontend_build/backend_structure/maven_test
  │ 失败 & codegen=llm → restore_enhancement 回滚 + 重跑
  │                  → 仍失败则 raise 终止流水线
  ├ 进度 ≈ 40%
  ▼
[step 4] demo ─ start_online_demo → _launch_demo
  │ stop_online_demo (清理旧进程)
  │ _free_port() × 2 分配端口
  │ 复用策略: target/*.jar mtime >= .java mtime → 跳过 mvn package
  │ 否则 mvn package -DskipTests (300s, JAVA_HOME=JDK 17)
  │ 写 logs/demo_build.log
  │ Popen java -jar (Spring Boot, demo profile, UTF-8 init)
  │ Popen npm run dev (Vite, --port)
  │ _wait_port(backend, 90s) + _wait_port(frontend, 40s)
  │ 写 demo_runtime.json:
  │   status=running, stage=running,
  │   backend_pid/port, frontend_pid/port,
  │   demo_url, swagger_url, maven_version, expires_at
  │ 写 logs/backend.log + logs/frontend.log
  ├ 进度 ≈ 55%
  ▼
[step 5] screenshot ─ capture_screenshots
  │ 检查 demo 是否在跑 (否则自己临时启一次)
  │ Playwright + Edge headless, viewport 1440×900
  │ 截图: 01-login → 02-dashboard
  │       03..N 每个模块 1 张 (点 [data-module-key] 菜单)
  │       04,07,... 部分模块额外 -form (弹新增弹窗)
  │ 写 screenshots/*.png
  │ 临时启的 demo 在 finally 杀 PID
  ├ 进度 ≈ 65%
  ▼
[step 6] analyze ─ analyze_code
  │ rglob 收集 .java/.xml/.yml/.vue/.js/.ts/.html/.css/.sql
  │ 排除 node_modules / dist / target / venv / .git / __pycache__
  │ 写 code_stats.json: total_lines / frontend/backend/sql_lines
  ├ 进度 ≈ 70%
  ▼
[step 7] source ─ generate_source_document
  │ 拼接所有源码, 文件间用 // ===== {path} ===== 分隔
  │ 总行 > 3000 → 保留前 1500 + 后 1500 (硬上限 60 页×50 行)
  │ 写 docs/源代码材料.docx
  ├ 进度 ≈ 75%
  ▼
[step 8] docs ─ generate_documents
  │ 写 docs/设计说明书.docx (4 章: 概述/总体/功能/数据接口)
  │ 写 docs/用户操作手册.docx (含 screenshots 内嵌)
  │ 写 docs/软件著作权申请信息表.docx (含真实行数)
  │ document_template 决定字号/行距 (standard 10pt/1.5)
  ├ 进度 ≈ 82%
  ▼
[step 9] compliance ─ run_compliance_check
  │ 8 项检查 (每项 5-15 分, 满分 100):
  │   code_frontend_modules (15)
  │   code_backend_modules (15)
  │   screenshot_modules (15)
  │   design_modules (15)
  │   manual_modules (15)
  │   source_material (10)
  │   required_documents (10)
  │   software_name_consistency (5)
  │ 写 compliance_report.json: score/grade/passed/items/suggestions
  │ 写 docs/软著材料合规检查报告.docx
  │ _update status.json: compliance_score/grade/passed
  ├ 进度 ≈ 92%
  ▼
[step 10] package ─ build_package
  │ _zip_dir(generated_project) → generated_project.zip
  │ 写 README_软著材料说明.md (含真实行数)
  │ 打包 copyright_package.zip 根目录:
  │   generated_project.zip
  │   planning.json
  │   enhancement.json         (可选)
  │   code_stats.json
  │   compliance_report.json   (可选)
  │   README_软著材料说明.md
  │   docs/{设计说明书, 用户操作手册, 源代码材料,
  │         软件著作权申请信息表, 软著材料合规检查报告}.docx
  │   screenshots/*.png
  │ _update status.json: status="success", progress=100
  └ DONE
```

### 旅程 C — Demo 生命周期（可由用户随时触发）

```
┌──────────────────────────────────────────────────────────────────┐
│ [C1] 用户点 "启动 Demo" (HomePage 或 HistoryPage)                │
│      POST /api/jobs/{jobId}/demo/start                          │
│      ├─ 校验 job.status=="success"                              │
│      ├─ _DEMO_START_LOCK + _DEMO_STARTING set 防重入             │
│      └─ Thread(_start_demo_worker).start()  ★ 异步线程         │
└──────────────────────────────────┬───────────────────────────────┘
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│ [C2] _start_demo_worker (后台线程)                              │
│      ├─ get_job(job_id)                                         │
│      ├─ start_online_demo(job, job_dir/{job_id})                │
│      │   (流程同 journey-B step 4, 但可被用户主动重启)          │
│      └─ except 块:                                              │
│          ├─ 截断 error 500 字符                                 │
│          ├─ 保留 runtime 已有字段                               │
│          ├─ 写 status="failed", stage="failed", error=...       │
│          └─ _update status.json: run_status="failed"            │
│      finally: _DEMO_START_LOCK 释放, 从 set 移除                │
└──────────────────────────────────┬───────────────────────────────┘
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│ [C3] 启动成功 → 写 demo_runtime.json                             │
│      {                                                           │
│        status: "running",                                        │
│        stage:  "running",                                        │
│        stage_detail: "Demo 已就绪",                              │
│        backend_pid, frontend_pid,                                │
│        backend_port, frontend_port,                              │
│        demo_url, swagger_url,                                    │
│        maven_version,                                            │
│        started_at, expires_at (=started+1h),                     │
│      }                                                           │
│                                                                  │
│      写 status.json.run_status="running" + demo_url/swagger_url  │
└──────────────────────────────────┬───────────────────────────────┘
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│ [C4] 前端轮询 GET /api/jobs/{jobId}/demo (2s × 90 = 180s)       │
│      阶段文案映射:                                               │
│        queued/building → "正在构建 JAR…"                          │
│        starting        → "正在启动 Spring Boot 与 Vite"          │
│        running         → 绿色"运行中" + 查看 Demo / Swagger 按钮 │
│        failed          → 红色"启动失败" + error 行 + 日志按钮    │
│      GET /api/jobs/{jobId}/logs/{service} 拉后端/前端日志       │
└──────────────────────────────────┬───────────────────────────────┘
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│ [C5] 用户点 "关闭 Demo" 或 1 小时到期                            │
│      POST /api/jobs/{jobId}/demo/stop                            │
│      → stop_online_demo(job_id):                                 │
│        ├─ 读 demo_runtime.json                                   │
│        ├─ taskkill /PID /T /F 杀 backend_pid, frontend_pid      │
│        ├─ 写 demo_runtime.json: status="stopped", stopped_at    │
│        └─ _update status.json: run_status="stopped"              │
└──────────────────────────────────────────────────────────────────┘

【其他副作用】
demo_runtime() 读取时:
  - status==running 但 expires_at 到期 → 自动 stop_online_demo
  - status==running 但端口不通 → 写回 status=stopped, stop_reason=进程已退出
```

---

## 2. 状态机

### 2.1 `status.json.status`（主任务状态）

```
                    ┌─────────────────┐
   create_job ────► │   generating   │  ← 规划生成中 (Process)
                    └────────┬────────┘
                             │ planning.json 写完
                             ▼
                    ┌─────────────────┐
   重新生成规划 ──► │ draft_planning  │  ← 等待用户在 /planning-review 确认
                    └────────┬────────┘
                             │ POST /api/jobs/{id}/confirm
                             ▼
                    ┌─────────────────┐
   run_job 启动 ──►│   confirmed     │
                    └────────┬────────┘
                             │ run_job 10 步开始
                             ▼
                    ┌─────────────────┐
                    │   generating    │  ← 流水线中 (current_step 跟踪)
                    └────────┬────────┘
                             │ package step 写完
                             ▼
                    ┌─────────────────┐
                    │     success     │  ← 显示预览 + 下载按钮
                    └─────────────────┘
                             │
                  任一步抛异常 │
                             ▼
                    ┌─────────────────┐
                    │     failed      │  ← current_step 指明失败位置, error 详情
                    └─────────────────┘
```

### 2.2 `status.json.run_status`（Demo/验证状态）

```
                              ┌──────────┐
                  create_job ─►│ pending  │
                              └────┬─────┘
                                   │ step 3 run 完成
                                   ▼
                  ┌────────┬───────────────┬─────────┐
                  ▼        ▼               ▼         ▼
              verified  structure_verified  failed  (其他同 failed)
                  │        │
                  │  step 4 demo 启动      │
                  ▼        ▼
              ┌──────────┐
              │ starting │  ← _DEMO_STARTING set
              └────┬─────┘
                   ▼
              ┌──────────┐
              │ running  │  ← demo_runtime.status=running
              └────┬─────┘
                   │ user stop / 1h expire / 端口不通
                   ▼
              ┌──────────┐
              │ stopped  │  ← demo_runtime.status=stopped
              └──────────┘
                   │ user 点击 "重新启动 Demo"
                   ▼
                (回到 starting)
```

### 2.3 `demo_runtime.json.stage`（Demo 启动阶段）

```
queued (排队中…)
   │ _launch_demo 启动
   ▼
building (正在构建 JAR… 或 复用已构建 JAR)
   │ mvn package 完成 / 复用命中
   ▼
starting (正在启动 Spring Boot 与 Vite)
   │ Popen java -jar + Popen npm run dev
   ▼
running (Demo 已就绪)
   │
   ├─ 失败 → failed (错误信息截断 500 字符)
   └─ 用户/到期 → stopped
```

---

## 3. 关键文件输出（按 job 维度）

```
outputs/{job_id}/
├── status.json              # 总指挥台 — 11 步进度 + 元数据
├── planning.json            # 单一可信源 — 模块/页面/表
├── enhancement.json         # AI 增强结果 — 改了什么文件
├── run_validation.json      # 验证结果 — npm/mvn 测试通过?
├── demo_runtime.json        # Demo 进程登记 — pid/port/stage
├── code_stats.json          # 真实代码行数 — 软著申请信息表用
├── compliance_report.json   # 合规评分 — 100 分制
├── .enhancer_backup/        # 增强前白名单文件备份 (隐藏)
│
├── generated_project/       # ★ Spring Boot + Vue 3 完整可运行项目
│   ├── backend/
│   │   ├── pom.xml
│   │   ├── src/main/java/com/aicopyright/.../
│   │   │   ├── CopyrightApplication.java
│   │   │   ├── common/        (ApiResponse, PageQuery, GlobalExceptionHandler)
│   │   │   ├── config/        (MybatisPlusConfig, WebConfig)
│   │   │   └── module/{key}/  (entity/dto/vo/mapper/service/controller/metadata/*)
│   │   ├── src/main/resources/
│   │   │   ├── application.yml         (主配置, MySQL)
│   │   │   ├── application-demo.yml    (H2 demo, encoding: utf-8)
│   │   │   ├── schema-demo.sql         (DDL)
│   │   │   └── data-demo.sql           (75 条 INSERT — 5 表 × 15 条)
│   │   └── src/test/java/.../          (5 类 JUnit 5 合约测试)
│   ├── frontend/
│   │   ├── package.json
│   │   ├── vite.config.js, index.html
│   │   └── src/
│   │       ├── App.vue, main.js, router.js, style.css
│   │       ├── api/{request.js, {key}.js × 5}
│   │       ├── config/{key}.js × 5      (字段定义)
│   │       └── views/{DashboardPage.vue, {Pascal}Page.vue × 5}
│   ├── sql/init.sql                     (MySQL 全量 DDL + 75 条 INSERT)
│   └── README.md
│
├── screenshots/             # Playwright 截图
│   ├── 01-login.png
│   ├── 02-dashboard.png
│   ├── 03-{模块A}.png, 04-{模块A}-form.png
│   ├── 05-{模块B}.png
│   └── ... (N 个模块, 部分额外 -form 截图)
│
├── docs/                    # 5 个 .docx 软著材料
│   ├── 设计说明书.docx
│   ├── 用户操作手册.docx
│   ├── 源代码材料.docx                 (前/后 1500 行)
│   ├── 软件著作权申请信息表.docx
│   └── 软著材料合规检查报告.docx
│
├── logs/                    # 调试日志
│   ├── backend.log          (Spring Boot stdout/stderr)
│   ├── frontend.log         (Vite dev stdout/stderr)
│   └── demo_build.log       (mvn package 输出)
│
├── generated_project.zip    # 源码包 (过滤 target/node_modules/dist)
├── README_软著材料说明.md   # 材料包说明
└── copyright_package.zip    # ★ 最终交付包
```

---

## 4. 同步 vs 异步 后台任务

| # | HTTP 端点 | handler 同步部分 | 异步 spawn | 后台入口 |
|---|----------|----------------|----------|---------|
| 1 | `POST /api/jobs` | 写 status.json (pending→generating) | **`multiprocessing.Process`** | `generate_planning_draft` |
| 2 | `POST /api/planning/regenerate` | 复位 steps | **`multiprocessing.Process`** | `generate_planning_draft` |
| 3 | `POST /api/jobs/{id}/confirm` | 状态 → confirmed | **`multiprocessing.Process`** | `run_job` (10 步) |
| 4 | `POST /api/jobs/{id}/demo/start` | 加锁, 加 _DEMO_STARTING | **`threading.Thread`** | `_start_demo_worker` → `start_online_demo` |
| - | (内部) `mvn package` | — | `subprocess.run` 同步阻塞 (在 Process 内) | mvn cmd |
| - | (内部) `npm install/build` | — | `subprocess.run` 同步阻塞 | npm cmd |
| - | (内部) `java -jar` | — | `subprocess.Popen` 持久子进程 | Spring Boot |
| - | (内部) `npm run dev` | — | `subprocess.Popen` 持久子进程 | Vite |
| - | (内部) Playwright 截图 | — | 同步 (在 Process 内) | Edge headless |

**规则**：HTTP handler 内**永不**直接 `subprocess.run` 长任务；都是先 `Process`/`Thread` 异步化，再在子上下文里同步跑子进程。

---

## 5. 并发安全

| 锁 | 位置 | 保护对象 | 写冲突场景 |
|---|------|---------|----------|
| `_LOCK` (threading.Lock) | workflow.py | `status.json` 读写 | 多线程同时 `_update` (e.g. demo 启动 + run_job 状态) |
| `_DEMO_START_LOCK` + `_DEMO_STARTING: Set` | main.py:63-64 | demo 启动防重入 | 用户连点两次 "启动 Demo" |
| `SETTINGS_LOCK` (threading.Lock) | settings.py | `.env` 文件写 | 并发 PUT /api/settings/planner |
| `_json_write` 原子写 | workflow.py | 所有 .json 写盘 | 读端读到半截文件 |
| 复用 JAR 比较 mtime | workflow.py `_java_sources_mtime` / `_find_existing_jar` | 跳过 mvn package | 并发启 demo 都判断同一目标 JAR |

**原子写模式**：写 `*.json` → 先写 `*.json.{pid}.tmp` → `os.replace` 覆盖。读端永远读到完整文件。

---

## 6. LLM 调用清单（OpenAI 兼容协议）

| 调用点 | 触发步骤 | 输入 | 输出 | 失败行为 |
|--------|---------|------|------|---------|
| `planner._request_llm` | step: planning | software_name + industry_knowledge 白名单 | planning.json 结构 | fallback to template (auto) / raise (llm) |
| `enhancer._request_enhancement` | step: enhance | App.vue + style.css + README.md 原文 | JSON {summary, files: [{path, content}]} | 保留 template (auto) / raise (llm) |

环境变量：`AI_PLANNER_BASE_URL` / `AI_PLANNER_API_KEY` / `AI_PLANNER_MODEL` / `AI_CODEGEN_MODEL` / `*_TIMEOUT`。配置存于 `backend/.env`（已 `.gitignore`）。

---

## 7. 关键文件/行号速查

| 关注点 | 位置 |
|--------|------|
| HTTP 入口 | [main.py:131-421](c:/Users/whn/Documents/软著/backend/app/main.py#L131-L421) |
| STEPS/tasks 调度 | [workflow.py:33-45](c:/Users/whn/Documents/软著/backend/app/workflow.py#L33-L45) / [200-244](c:/Users/whn/Documents/软著/backend/app/workflow.py#L200-L244) |
| Planning 生成 | [planner.py:140-200](c:/Users/whn/Documents/软著/backend/app/planner.py#L140-L200) |
| 项目模板生成 | [project_generator.py:1522-1666](c:/Users/whn/Documents/软著/backend/app/project_generator.py#L1522-L1666) |
| 种子数据 | [project_generator.py:1080-1190](c:/Users/whn/Documents/软著/backend/app/project_generator.py#L1080-L1190) |
| Demo 启动/停止 | [workflow.py:600-770](c:/Users/whn/Documents/软著/backend/app/workflow.py#L600-L770) |
| mvn JAVA_HOME 修复 | [workflow.py:819-840](c:/Users/whn/Documents/软著/backend/app/workflow.py#L819-L840) |
| 截图 | [workflow.py:940-999](c:/Users/whn/Documents/软著/backend/app/workflow.py#L940-L999) |
| 合规检查 | [compliance.py:45-214](c:/Users/whn/Documents/软著/backend/app/compliance.py#L45-L214) |
| 打包 | [workflow.py:1266-1299](c:/Users/whn/Documents/软著/backend/app/workflow.py#L1266-L1299) |
| 前端路由 | [router.js](c:/Users/whn/Documents/软著/frontend/src/router.js) |
| 前端 HomePage | [HomePage.vue](c:/Users/whn/Documents/软著/frontend/src/pages/HomePage.vue) |
| 前端规划页 | [PlanningReviewPage.vue](c:/Users/whn/Documents/软著/frontend/src/pages/PlanningReviewPage.vue) |
| 前端历史页 | [HistoryPage.vue](c:/Users/whn/Documents/软著/frontend/src/pages/HistoryPage.vue) |
| 根文档 | [README.md](c:/Users/whn/Documents/软著/README.md) |
