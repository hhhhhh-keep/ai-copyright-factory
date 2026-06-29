# AI软著工厂安装说明

本文面向首次拉取代码的使用者，只说明本地安装、配置和启动。

## 1. 环境要求

Windows 10/11 或 Windows Server，提前安装并加入 `PATH`：

- Python 3.10+
- Node.js 18+
- JDK 17
- Maven 3.9+
- Git

检查命令：

```powershell
python --version
node --version
npm.cmd --version
java -version
mvn.cmd -version
git --version
```

## 2. 拉取代码

```powershell
git clone <repo-url>
cd 软著
```

## 3. 一键初始化并启动

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

脚本会自动：

- 检查必要命令是否存在。
- 首次复制 `backend\.env.example` 为 `backend\.env`。
- 安装后端 Python 依赖。
- 安装 Playwright Chromium。
- 安装前端 npm 依赖。
- 启动后端和前端两个 PowerShell 窗口。

首次运行后，请先配置模型，再创建任务。

## 4. 配置模型

编辑：

```text
backend\.env
```

至少填写：

```env
AI_PLANNER_BASE_URL=https://api.openai.com/v1
AI_PLANNER_API_KEY=你的密钥
AI_PLANNER_MODEL=你的模型名
AI_PLANNER_TIMEOUT=180

AI_CODEGEN_MODEL=
AI_CODEGEN_TIMEOUT=240
AI_CODEGEN_DOC_TIMEOUT=90
AI_DOCUMENT_MODEL=
AI_DOCUMENT_TIMEOUT=90
NPM_INSTALL_TIMEOUT=600
```

`AI_CODEGEN_MODEL` 为空时复用 `AI_PLANNER_MODEL`。

## 5. 再次启动

配置完成后，依赖已安装过可快速启动：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1 -SkipInstall
```

访问：

```text
http://127.0.0.1:5173
```

后端：

```text
http://127.0.0.1:8000
```

## 6. 手动启动

如果不用一键脚本：

```powershell
cd backend
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

新开窗口：

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

## 7. 常见问题

### 端口被占用

换端口启动：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1 -BackendPort 8010 -FrontendPort 5174
```

### PowerShell 禁止运行脚本

使用：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

### 生成任务超时

确认 `backend\.env` 中：

```env
AI_PLANNER_TIMEOUT=180
AI_CODEGEN_TIMEOUT=240
NPM_INSTALL_TIMEOUT=600
```

### 不要提交的文件

不要提交：

- `backend\.env`
- `outputs\`
- `node_modules\`
- `backend-server*.log`
- `frontend-server*.log`
