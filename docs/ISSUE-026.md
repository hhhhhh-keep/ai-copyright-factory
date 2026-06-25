# ISSUE-026：workflow.py logger NameError + daemon SSL read timeout + CSS 空响应

- 状态：`已修正，Codex 代码复审通过`
- 优先级：`P0`
- 首次记录：2026-06-24
- 关联：ISSUE-023（worker 状态机告警 + retry + actual_mode 修复，**埋了 3 个新雷**）；ISSUE-024/025（白名单补全）

## 用户目标

- "软著材料打包"阶段不再抛 `NameError: name 'logger' is not defined`。
- daemon Worker 下 LLM API SSL read 挂死能在 12s wall-clock 窗口内被强制中断，而不是等到 1006s 后才抛出。
- LLM 多次重试后仍返回"无 CSS 规则"的响应时，UI 子步骤标 `skipped` 而非 `failed`，不影响任务。

## 失败现场

jobId=`20260624160110-58039b6d`（涉案车辆管理系统，`codegen_mode=auto`）+ 用户从 `awaiting_demo_review` 进入"打包软著材料"阶段时崩溃：

| # | 子步骤 | status | 错误 |
|---|---|---|---|
| 1 | theme | completed | - |
| 2 | shell | completed | - |
| 3 | business | **failed** | `RuntimeError: Code enhancer API read timed out`（1006s = 16 分钟） |
| 4 | dashboard | completed | - |
| 5 | responsive | **failed** | `ValueError: UI 子步骤 responsive 未包含可校验的 CSS 选择器`（LLM 返回 `@media{...}{/* 注释 */}`） |

随后用户点"打包软著材料" → 触发 `workflow.continue_material_generation` → 末尾 `logger.warning(...)` 调用抛 `NameError: name 'logger' is not defined`，**直接阻断软著材料打包流程**。

## 根因分析（3 类独立 bug）

### 根因 A `workflow.py` logger NameError

ISSUE-023 P1-3 在 `backend/app/workflow.py` 的 `continue_material_generation` 末尾新增 `logger.warning(...)` 调用，但**未在模块顶部 `import logging` 也未定义 `logger = logging.getLogger(__name__)`**。该函数在用户点"打包软著材料"时调用，导致 `NameError` 直接阻断流水线。

### 根因 B daemon Worker 下 SSL read timeout 无法强制中断

`_call_chat_completion_with_deadline` 在 daemon Worker 走 urllib 直读：
- `urllib.request.urlopen(timeout=N)` **只覆盖 TCP connect 阶段**，不覆盖 SSL read；
- jobId=`20260624160110-58039b6d` 的 business 步在 SSL read 阶段挂死 1006s（16 分钟），即使 `max_attempts=3` + 退避仍超时；
- `multiprocessing.Process` 路径在 daemon Worker 下被禁用（`AssertionError: daemonic processes are not allowed to have children`），所以 daemon 下没有硬超时兜底。

### 根因 C LLM 多次返回空 CSS 时整步 failed 阻断任务

`_request_ui_step` 在 `_validate_ui_block` 抛 `ValueError: 未包含可校验的 CSS 选择器`（CSS 内容纯注释或 `@media{}` 空体）时，调用方 `_enhance_ui_steps` 标 `failed` 并重试 `max_attempts=2` 次仍失败，最终阻断任务。

ISSUE-026 实施初期埋了 2 个新 bug：
- `attempts` 变量在 `_request_ui_step` 内未定义（NameError）；
- skipped 分支 `break` 后未设 `success=True`，下方 `if not success:` 覆盖为 failed。

## 修复方案（Claude 实施 2026-06-24）

### P0-1 workflow.py logger NameError

- `backend/app/workflow.py` 顶部新增 `import logging` 与 `logger = logging.getLogger(__name__)`。

### P0-2 daemon Worker 下 SSL read timeout（subprocess 硬截止）

- 第一版 `ThreadPoolExecutor + future.result(timeout)` 能让调用方返回，但无法杀死卡在 SSL read 的 Python 线程，长期运行会积累后台线程；Codex 复审未通过。
- 当前实现改为：daemon Worker 下用独立 Python subprocess 执行 HTTP 请求，主进程通过 `subprocess.run(..., timeout=AI_CODEGEN_TIMEOUT+10)` 做硬截止。
- 子进程 timeout 后由 `subprocess` 杀掉，不在工厂 worker 进程里留下不可回收线程。
- 非 daemon 远端调用仍走原 `multiprocessing` 硬超时；本地 `127.0.0.1/localhost` 调用直接走 `_chat_completion_request`，避免测试和本地模型调用大量 spawn 进程。

### P0-3 LLM 空 CSS 响应 → skipped 而非 failed

- `backend/app/enhancer.py` `UIStepResponse.block` 改为 `Optional[UIStepBlock] = None`，加 `skip_reason` 字段；
- `_request_ui_step` 在 `_validate_ui_block` 之前检查 `_css_rule_selectors(block.content)`：
  - 空 selectors → 返回 `UIStepResponse(block=None, skip_reason="LLM 返回内容不含任何 CSS 规则...")`，不抛错；
- `_enhance_ui_steps` 调用方识别 `response.block is None` → 标 `status="skipped"`、记 `summary=skip_reason`，**`success=True`**（避免下方 `if not success:` 覆盖）。

### P1 测试覆盖

`backend/tests/test_enhancer.py` 新增/调整后共 **35/35 全过**：
- `test_workflow_logger_imported` — 验证 `from app.workflow import logger` 不抛 NameError；
- `test_daemon_worker_uses_transport_timeout_without_child_process` — daemon 模式走 subprocess，不创建 `multiprocessing` 子进程，不调用当前进程内 `_chat_completion_request`；
- `test_daemon_subprocess_error_is_reported` — 子进程返回 provider 错误时准确抛出；
- `test_daemon_worker_read_timeout_bounded` — mock `subprocess.TimeoutExpired`，daemon 模式下立即转 `RuntimeError("daemon worker")`；
- `test_empty_css_response_is_skipped` — 4 步返回纯注释，验证 `status="skipped"` + summary 含"不含任何 CSS 规则"。

### P2 文档同步

- `AGENTS.md` 顶部说明 + 已完成升级加 ISSUE-026 条目；
- `README.md` 顶部"实现状态说明"加 ISSUE-026 增量；
- `docs/FLOW.md` enhance 阶段描述 + 状态机说明加 ISSUE-026 3 项；
- `docs/ISSUE-020.md` 追加"运行时回归修正（2026-06-24 第三次，ISSUE-026 关联）"小节；
- `docs/ISSUE-026.md`（本文件）+ `docs/ISSUES.md` 末尾追加章节。

## 验证

```bash
cd "C:\Users\whn\Documents\软著\backend"
python -m unittest discover -s tests
```

预期：focused enhancer 测试 35 项通过；全量测试以当前机器资源为准，若遇到外部中断需单独重跑失败模块。

端到端流程验证（daemon Worker 模拟 + 5 步 UI 增强 + 1 步空响应）：

- `from app.workflow import logger` 不抛 NameError ✓
- `enhance_project` 在 daemon 模拟下完整跑完，5 步状态：`4 completed + 1 skipped` ✓
- `actual_mode=llm`、`changed_files=['frontend/src/style.css']`（skipped 不阻断任务）✓

## Codex 复审核验（2026-06-25）

- 发现第一版 `ThreadPoolExecutor.shutdown(wait=False)` 不能回收后台线程：小实验显示主调用返回后 Python 进程仍不会退出，直到阻塞线程结束。
- 已改为 subprocess 硬截止，并补充 daemon 成功、错误和 timeout 三类测试。
- 验证：`python -m unittest tests.test_enhancer -v`，35 项通过。

## 剩余风险

- daemon 分支会为每个远端 LLM 请求启动一个 Python 子进程，稳定性优先于性能；如后续并发量上升，可再改为常驻受控 worker 池。
- LLM 空响应是"提示词工程"问题，本 ISSUE 仅做"任务不被阻断"兜底，未强制重试要求返回 ≥1 个 CSS 规则。
- `success=True` 在 skipped 分支的修复是**必要修补**，未来 `_enhance_ui_steps` 重构时要保留。

## 落地触发条件

按用户硬性约束"问题收集期不修业务代码，等用户'统一修改'命令"——本次由用户在 ISSUE-025 落地后报告 "打包软著材料显示 NameError: name 'logger' is not defined，并且 jobId=... 的 AI 增强代码还是报错"，触发"立即修"指令。
