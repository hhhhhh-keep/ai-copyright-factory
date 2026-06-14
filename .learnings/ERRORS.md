# Errors

## [ERR-20260611-005] python38-built-in-generics

**Logged**: 2026-06-11T19:31:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: backend

### Summary
后端新增 `set[str]` 类型标注，但当前运行环境为 Python 3.8，导致应用导入失败。

### Error
`TypeError: 'type' object is not subscriptable`

### Context
- Python 3.8 不支持内置集合类型的 PEP 585 下标语法
- 项目依赖明确兼容 Python 3.8

### Suggested Fix
使用 `typing.Set[str]`，并在新增类型标注后执行真实 Uvicorn 导入验证。

### Metadata
- Reproducible: yes
- Related Files: backend/app/main.py

### Resolution
- **Resolved**: 2026-06-11T19:32:00+08:00
- **Notes**: 改用 `Set[str]`，异步 Demo API 验证通过。

---

## [ERR-20260611-004] spring-boot-run-chinese-path

**Logged**: 2026-06-11T18:16:00+08:00
**Priority**: high
**Status**: resolved
**Area**: backend

### Summary
IntelliJ 内置 Maven 在中文工作区使用 `spring-boot:run` 时，分叉 JVM 找不到已编译主类。

### Error
`ClassNotFoundException: com.aicopyright.copyright.CopyrightApplication`

### Context
- 同一项目 `mvn test` 编译成功且 79 项测试通过
- 失败仅发生在 Spring Boot Maven Plugin 的 run 目标
- 工作区路径包含中文字符

### Suggested Fix
在线 Demo 使用标准部署路径：`mvn package -DskipTests` 后执行 `java -jar`。

### Metadata
- Reproducible: yes
- Related Files: backend/app/workflow.py

### Resolution
- **Resolved**: 2026-06-11T18:17:00+08:00
- **Notes**: 改为可执行 JAR 启动，前端、健康接口、业务 API 和 Swagger 均返回 HTTP 200。

---

## [ERR-20260611-003] recursive-maven-search-timeout

**Logged**: 2026-06-11T18:04:00+08:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
从 C 盘和 D 盘根目录递归搜索 `mvn.cmd` 超时。

### Error
`command timed out after 121066 milliseconds`

### Context
- 超时前已发现 IntelliJ 2023.1 自带 Maven

### Suggested Fix
优先检查 PATH 和已知 IDE Maven 安装路径，避免全盘递归。

### Metadata
- Reproducible: yes
- Related Files: backend/app/workflow.py

### Resolution
- **Resolved**: 2026-06-11T18:05:00+08:00
- **Notes**: 流水线增加 IntelliJ Maven 已知路径探测。

---

## [ERR-20260611-002] workspace-tmp-permission

**Logged**: 2026-06-11T17:58:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
当前 Windows 权限拒绝在 `C:\tmp` 创建 Java 生成器验收目录。

### Error
`CreateDirectoryUnauthorizedAccessError`

### Context
- 验收样例原计划写入 `C:\tmp`
- 工作区目录可正常写入

### Suggested Fix
验收产物使用工作区内独立命名目录。

### Metadata
- Reproducible: yes
- Related Files: none

### Resolution
- **Resolved**: 2026-06-11T17:59:00+08:00
- **Notes**: 改用工作区 `backend/outputs/_java_*` 目录完成验收。

---

## [ERR-20260611-001] hardcoded-npm-path

**Logged**: 2026-06-11T00:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
临时启动前端服务时硬编码了错误的 Node.js 安装盘符。

### Error
`The system cannot find the file specified`

### Context
- 误用 `C:\Program Files\nodejs\npm.cmd`
- 当前环境实际路径由 `Get-Command npm.cmd` 解析为 `D:\Program Files\nodejs\npm.cmd`

### Suggested Fix
Windows 自动化中通过 `Get-Command npm.cmd` 动态解析可执行文件路径。

### Metadata
- Reproducible: yes
- Related Files: none
- See Also: ERR-20260610-002

### Resolution
- **Resolved**: 2026-06-11T00:00:00+08:00
- **Notes**: 改为使用当前环境解析出的 npm.cmd 路径，并完成前端 HTTP 200 验证。

---

## [ERR-20260610-012] npm-output-gbk

**Logged**: 2026-06-10T00:00:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: tests

### Summary
Windows Python 按 GBK 解码 npm 的 UTF-8 构建输出，导致读取线程异常。

### Error
`UnicodeDecodeError: 'gbk' codec can't decode byte ...`

### Context
- subprocess 使用 text=True 但未指定 encoding
- Vite/Rollup 输出包含 UTF-8 字符

### Suggested Fix
npm install/build 子进程显式使用 UTF-8，并对异常字节 replace。

### Metadata
- Reproducible: yes
- Related Files: backend/app/workflow.py

### Resolution
- **Resolved**: 2026-06-10T00:00:00+08:00
- **Notes**: 已设置 encoding=utf-8, errors=replace。

---

## [ERR-20260610-006] powershell-start-process-path-collision

**Logged**: 2026-06-10T22:20:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: config

### Summary
PowerShell `Start-Process` 因环境中同时存在 `Path` 与 `PATH` 而无法启动本地服务。

### Error
`已添加项。字典中的关键字:“Path”所添加的关键字:“PATH”`

### Context
- 后台启动 FastAPI 和 Vite
- Windows PowerShell 进程环境包含大小写重复键

### Suggested Fix
使用 `System.Diagnostics.ProcessStartInfo` 启动隐藏后台进程并重定向日志。

### Metadata
- Reproducible: yes
- Related Files: backend-server.log, frontend-server.log

### Resolution
- **Resolved**: 2026-06-10T22:20:00+08:00
- **Notes**: 改用 .NET 进程 API。

---

## [ERR-20260610-005] gh-address-comments-repository-resolution

**Logged**: 2026-06-10T22:10:00+08:00
**Priority**: medium
**Status**: pending
**Area**: config

### Summary
无法从当前工作区解析 GitHub PR，因为 Git CLI 不可用且目录不是 Git 仓库。

### Error
`git` 未被识别为命令；`.git/config` 和 `.git/HEAD` 均不存在。

### Context
- 尝试为 `gh-address-comments` 工作流解析当前分支关联的 PR
- 工作区：`C:\Users\whn\Documents\软著`

### Suggested Fix
提供明确的 GitHub PR URL 或 `owner/repo#PR编号`；若需本地修改同步到 PR，还需初始化/克隆对应仓库并安装 Git CLI。

### Metadata
- Reproducible: yes
- Related Files: none

---

## [ERR-20260610-011] generated-template-build-script

**Logged**: 2026-06-10T00:00:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: frontend

### Summary
Phase 3 增加前端构建验证后，生成项目模板缺少 build 脚本。

### Error
`npm error Missing script: "build"`

### Context
- Phase 1 模板只定义了 dev 脚本
- Phase 3 必须通过生产构建验证 AI 增强代码

### Suggested Fix
生成项目 package.json 增加 `build: vite build`。

### Metadata
- Reproducible: yes
- Related Files: backend/app/workflow.py

### Resolution
- **Resolved**: 2026-06-10T00:00:00+08:00
- **Notes**: 已补充生成模板 build 脚本。

---

## [ERR-20260610-010] vite-sandbox-cwd

**Logged**: 2026-06-10T00:00:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: frontend

### Summary
沙箱虚拟 cwd 与工作区真实路径不同，导致 Vite 生成非法入口相对路径。

### Error
`emitted chunks and assets ... received "../../../../../whn/Documents/软著/frontend/index.html"`

### Context
- Node process.cwd() 指向沙箱映射目录
- index.html realpath 指向实际工作区

### Suggested Fix
Vite 配置使用 import.meta.url 所在目录显式设置 root。

### Metadata
- Reproducible: yes
- Related Files: frontend/vite.config.js, backend/app/workflow.py

### Resolution
- **Resolved**: 2026-06-10T00:00:00+08:00
- **Notes**: 主前端和生成项目模板均显式配置 Vite root。

---

## [ERR-20260610-009] screenshot-module-name-locator

**Logged**: 2026-06-10T00:00:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: tests

### Summary
截图 Agent 使用模块显示名称定位按钮，重复名称会触发 strict mode violation。

### Error
`Locator.click: strict mode violation ... resolved to 3 elements`

### Context
- Phase 2 模型规划允许不同模块名称发生意外重复
- 模块 key 已由 Pydantic 校验为唯一

### Suggested Fix
菜单按钮输出 data-module-key，截图按唯一 key 定位。

### Metadata
- Reproducible: yes
- Related Files: backend/app/workflow.py

### Resolution
- **Resolved**: 2026-06-10T00:00:00+08:00
- **Notes**: 截图定位已切换为 data-module-key。

---

## [ERR-20260610-008] playwright-windows-thread

**Logged**: 2026-06-10T00:00:00+08:00
**Priority**: high
**Status**: resolved
**Area**: backend

### Summary
Windows Python 3.8 中从后台线程启动 Playwright 子进程会触发 NotImplementedError。

### Error
`Future exception was never retrieved ... NotImplementedError()`

### Context
- API 创建任务后使用 daemon Thread 执行流水线
- Playwright 同步 API 在截图阶段需要创建浏览器子进程
- 主线程直接执行流水线时不复现

### Suggested Fix
将任务执行单元改为 multiprocessing.Process，使 Playwright 在独立进程主线程运行。

### Metadata
- Reproducible: yes
- Related Files: backend/app/main.py, backend/app/workflow.py

### Resolution
- **Resolved**: 2026-06-10T00:00:00+08:00
- **Notes**: 已改为独立进程，并使用原子 JSON 状态写入。

---

## [ERR-20260610-007] fastapi-background-task-response

**Logged**: 2026-06-10T00:00:00+08:00
**Priority**: high
**Status**: resolved
**Area**: backend

### Summary
长时间生成流水线使用 FastAPI BackgroundTasks，导致创建任务响应持续等待。

### Error
`POST /api/jobs` 在 20 秒客户端超时内未返回。

### Context
- 流水线包含 npm install、截图和文档生成
- 前端因此一直显示“正在创建”

### Suggested Fix
创建任务后使用独立工作线程执行流水线，HTTP 接口立即返回 202。

### Metadata
- Reproducible: yes
- Related Files: backend/app/main.py

### Resolution
- **Resolved**: 2026-06-10T00:00:00+08:00
- **Notes**: 已改用 daemon Thread 执行 run_job。

---

## [ERR-20260610-001] git-command

**Logged**: 2026-06-10T00:00:00+08:00
**Priority**: low
**Status**: pending
**Area**: config

### Summary
当前 Windows 终端未配置可用的 git 命令。

### Error
`git : 无法将“git”项识别为 cmdlet、函数、脚本文件或可运行程序的名称。`

### Context
- 在空工作区检查仓库状态时执行 `git status --short`
- 不影响本地 MVP 实现和验证

### Suggested Fix
需要版本控制时安装 Git for Windows 并将其加入 PATH。

### Metadata
- Reproducible: yes
- Related Files: none

---

## [ERR-20260610-006] in-app-browser-localhost

**Logged**: 2026-06-10T00:00:00+08:00
**Priority**: low
**Status**: pending
**Area**: tests

### Summary
内置浏览器拒绝访问已确认返回 HTTP 200 的本地前端。

### Error
`net::ERR_BLOCKED_BY_CLIENT`

### Context
- `Invoke-WebRequest http://127.0.0.1:5173` 返回 200
- 内置浏览器访问 127.0.0.1 和 localhost 均被客户端拦截

### Suggested Fix
检查 Codex 内置浏览器的本地地址访问策略；当前使用项目内 Playwright + Edge 作为页面渲染验证后备。

### Metadata
- Reproducible: yes
- Related Files: frontend/src/App.vue

---

## [ERR-20260610-005] fastapi-testclient-httpx

**Logged**: 2026-06-10T00:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
FastAPI TestClient 需要未安装的可选依赖 httpx。

### Error
`The starlette.testclient module requires the httpx package to be installed.`

### Context
- 仅发生在验收脚本，不影响应用运行

### Suggested Fix
使用真实 Uvicorn 进程做 API 健康检查，避免扩充生产依赖。

### Metadata
- Reproducible: yes
- Related Files: backend/requirements.txt

### Resolution
- **Resolved**: 2026-06-10T00:00:00+08:00
- **Notes**: 验收改为实际 HTTP 请求。

---

## [ERR-20260610-003] vite-vue-plugin

**Logged**: 2026-06-10T00:00:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: frontend

### Summary
首次构建缺少 Vite Vue 插件配置。

### Error
`Failed to parse source for import analysis. Install @vitejs/plugin-vue to handle .vue files.`

### Context
- `@vitejs/plugin-vue` 已声明为依赖，但未创建 `vite.config.js`

### Suggested Fix
为主前端和生成项目模板添加 Vue 插件配置。

### Metadata
- Reproducible: yes
- Related Files: frontend/vite.config.js, backend/app/workflow.py

### Resolution
- **Resolved**: 2026-06-10T00:00:00+08:00
- **Notes**: 已添加 `plugins: [vue()]`。

---

## [ERR-20260610-004] playwright-python38

**Logged**: 2026-06-10T00:00:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: config

### Summary
Playwright 1.49.1 没有当前 Python 3.8 环境可安装的发行包。

### Error
`Could not find a version that satisfies the requirement playwright==1.49.1`

### Context
- 当前 Python 版本为 3.8.8

### Suggested Fix
锁定到支持 Python 3.8 的 Playwright 1.46.0。

### Metadata
- Reproducible: yes
- Related Files: backend/requirements.txt

### Resolution
- **Resolved**: 2026-06-10T00:00:00+08:00
- **Notes**: 已调整依赖版本。

---

## [ERR-20260610-002] powershell-npm-policy

**Logged**: 2026-06-10T00:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
PowerShell 执行策略阻止 npm.ps1。

### Error
`npm.ps1，因为在此系统上禁止运行脚本。`

### Context
- 执行 `npm --version` 时触发
- `npm.cmd` 可正常运行

### Suggested Fix
项目命令和自动化统一调用 `npm.cmd`。

### Metadata
- Reproducible: yes
- Related Files: backend/app/workflow.py, README.md

### Resolution
- **Resolved**: 2026-06-10T00:00:00+08:00
- **Notes**: Windows 环境自动选择 npm.cmd。

---
