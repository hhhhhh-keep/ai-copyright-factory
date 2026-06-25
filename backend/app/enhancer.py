import hashlib
import json
import logging
import multiprocessing
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, field_validator
from pydantic import ValidationError

from app.learning import append_enhance_error

logger = logging.getLogger(__name__)


ALLOWED_FILES = (
    "frontend/src/style.css",
    "README.md",
)
ALLOWED_FILE_SET = set(ALLOWED_FILES)
MAX_FILE_CHARS = 120_000
MAX_TOTAL_CHARS = 300_000


_CHAT_COMPLETION_SUBPROCESS_SCRIPT = r"""
import json
import socket
import sys
import urllib.error
import urllib.request


def _clean(obj):
    if isinstance(obj, str):
        return obj.encode("utf-8", errors="replace").decode("utf-8")
    if isinstance(obj, list):
        return [_clean(item) for item in obj]
    if isinstance(obj, dict):
        return {str(_clean(key)): _clean(value) for key, value in obj.items()}
    return obj


def _emit(payload):
    print(json.dumps(_clean(payload), ensure_ascii=True), flush=True)


def main() -> int:
    params = _clean(json.loads(sys.stdin.read()))
    payload = {
        "model": params["model"],
        "messages": params["messages"],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        params["base_url"].rstrip("/") + "/chat/completions",
        data=json.dumps(_clean(payload), ensure_ascii=True).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + params["api_key"],
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=int(params["timeout"])) as response:
            response_data = json.loads(response.read().decode("utf-8"))
        content = response_data["choices"][0]["message"]["content"]
        _emit({"ok": True, "content": content})
        return 0
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        print(json.dumps({"ok": False, "error": f"代码增强 API 返回 HTTP {exc.code}: {detail}"}, ensure_ascii=False))
        return 1
    except urllib.error.URLError as exc:
        print(json.dumps({"ok": False, "error": f"代码增强 API 连接失败: {exc.reason}"}, ensure_ascii=False))
        return 1
    except (TimeoutError, socket.timeout):
        _emit({"ok": False, "error": "Code enhancer API read timed out"})
        return 1
    except Exception as exc:
        _emit({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
"""


# ----------------- ISSUE-020: 分阶段 UI 增强 -----------------

UI_ENHANCEMENT_STEPS: Tuple[Tuple[str, str], ...] = (
    ("theme", "界面风格方案"),
    ("shell", "应用壳层"),
    ("business", "业务页面组件"),
    ("dashboard", "驾驶舱与图表"),
    ("responsive", "响应式与收尾"),
)
UI_STEP_KEYS: Tuple[str, ...] = tuple(key for key, _ in UI_ENHANCEMENT_STEPS)
UI_STEP_NAMES: Dict[str, str] = dict(UI_ENHANCEMENT_STEPS)
# 每个 UI 子步骤允许写入 CSS 的最大字符数，超出则丢弃，避免模型返回整份 style.css。
# ISSUE-022：默认值从 8000 提升到 16000，驾驶舱/图表类步骤常因 KPI/图表样式聚合超过旧上限。
# 可通过环境变量 ``AI_CODEGEN_UI_BLOCK_MAX_CHARS`` 覆盖。
UI_STEP_MAX_BLOCK_CHARS = int(os.getenv("AI_CODEGEN_UI_BLOCK_MAX_CHARS", "16000"))
# CSS 追加块中允许出现的选择器集合（白名单）。模型可新增 :root 变量，但其他选择器
# 必须落在这些前缀之一，避免越界改写路由 / 组件壳层
# ISSUE-024（2026-06-24）：白名单与生成器实际 class 对齐。
# - shell 步补 .shell-split / .shell-main / @media（split_console 壳层 + 响应式断点）；
# - business 步补 .el-card__* / .el-button--* / .el-tag--* / .el-dialog__* 等 Element Plus BEM 派生；
# - dashboard 步把已废弃的 .metric-grid / .kpi-icon / .activity-panel 改为生成器实际 class：
#   .kpi-grid / .kpi-trend* / .kpi-row / .dashboard-row / .module-dashboard / .status-row；
# - responsive 步补 .kpi-grid / .dashboard-row / .module-dashboard / .status-row / .analysis-workbench；
# - 所有 4 步（除 theme 外）允许写 @media。
UI_STEP_SELECTOR_HINTS: Dict[str, Tuple[str, ...]] = {
    "theme": (
        ":root", "--ai-", "body", "html", ".login-page", ".hero",
        ".shell", ".el-header", ".el-aside", ".context-panel",
    ),
    "shell": (
        ".login-page", ".login-brand", ".login-card", ".hero",
        ".shell-top", ".shell-top>header", ".shell-top nav",
        ".shell-aside", ".shell-aside .menu", ".el-aside",
        ".shell-split", ".shell-main",  # ISSUE-024：split_console 壳层
        ".page-heading", "body", "header",
        "@media",                       # ISSUE-024：壳层响应式断点
    ),
    "business": (
        # Element Plus 全家族（ISSUE-025：补 .el-table--* / .el-pagination / .el-checkbox / .el-radio / .el-select / .el-tooltip / .el-message / .el-popover / .el-dropdown / .el-menu）。
        ".el-card", ".el-card__*",
        ".el-table", ".el-table__*", ".el-table--*",
        ".el-button", ".el-button--*",
        ".el-tag", ".el-tag--*",
        ".el-input", ".el-form",
        ".el-dialog", ".el-dialog__*",
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
        # 自定义按钮 + 派生（LLM 自由发挥常见模式）
        ".btn-primary", ".btn-ghost", ".btn-default", ".btn-danger",
        ".btn-success", ".btn-warning", ".btn-info",
        ".btn-link", ".btn-text",
        # 项目结构（project_generator.py 真值）
        ".modal",
        ".filter-bar", ".toolbar", ".status-pill", ".kpi-card",
        ".module-page", ".master-detail-preview", ".tree-detail-preview",
        ".kanban-preview",
        ".page-heading", ".actions",
        # LLM 派生启发式：业务步允许任何 .module-* / .task-* / .form-* 派生
        ".module-*", ".task-*", ".form-*",
        "@media",
    ),
    "dashboard": (
        # ISSUE-024：与 project_generator.py 实际生成 class 对齐。
        ".kpi-grid", ".kpi-row", ".kpi-card",
        ".kpi-trend", ".kpi-trend-up", ".kpi-trend-down", ".kpi-spark",
        ".dashboard-row", ".module-dashboard",
        ".trend-panel", ".trend-svg", ".bar-panel", ".bar-svg",
        ".donut-panel", ".donut-svg",
        ".status-row", ".analysis-workbench",
        ".dashboard",
        # ISSUE-025：LLM 自创派生类启发式
        ".dashboard-*", ".m-*", ".pattern-*",
        ".trend-*", ".stat-*", ".metric-*",
        # Element Plus 派生（dashboard 偶尔用 Element Plus 组件）
        ".el-card", ".el-card__*", ".el-tag", ".el-tag--*",
        "@media",
    ),
    "responsive": (
        "@media", "body", "html",
        ".shell-top", ".shell-aside", ".shell-split", ".shell-main",
        ".module-page", ".module-dashboard",
        ".kpi-grid", ".kpi-row", ".kpi-card", ".dashboard-row",
        ".status-row", ".analysis-workbench",
        ".toolbar", ".el-card", ".el-table",
        ".login-page", ".hero", ".dashboard",
        # ISSUE-025：page-heading / actions / 自定义按钮也是常见响应式目标
        ".page-heading", ".actions",
        ".btn-primary", ".btn-ghost", ".btn-default",
        "input", "button", "select", "textarea",
        ":focus", ":hover",
        # ISSUE-022：补 Element Plus 基础选择器；ISSUE-024 步内显式展开 BEM 派生。
        ".el-button", ".el-button--*", ".el-input", ".el-tag", ".el-tag--*",
        ".el-form", ".el-dialog", ".el-dialog__*",
    ),
}
# 全局允许的 CSS 选择器前缀（任何 UI 子步骤都可写入）。
# - :root 与 --ai-* 用于 CSS 变量声明，是行业风格令牌的事实承载方式；
# - html 用于整页基础样式（font-family、color 等）；
# - * 用于全局重置（box-sizing、margin 等），仅限裸 * 与 *::before / *::after 等通用重置；
# - ``.el-*`` 是 Element Plus 全家族通配：jobId=20260625083914-ecc71dd6 的
#   business 步暴露 ``.el-input__wrapper`` / ``.el-textarea__inner`` /
#   ``.el-input__wrapper:hover`` 等输入框内部类（BEM 派生 + 伪类），
#   之前 50+ 行基础类白名单仍不够稳，``UI_STEP_FORBIDDEN_SELECTORS``
#   守住 ``<router-view`` / ``v-on:click`` / ``import`` 等禁片；
# ISSUE-022：jobId=20260623225150-e2f31fbd 的 responsive 步因此前白名单缺失被拒；
# ISSUE-024：jobId=20260624095339-9d44c135 的 shell 步因 * / html 未在白名单内被拒；
# ISSUE-027：jobId=20260625083914-ecc71dd6 的 business 步因 .el-input__wrapper 等
#   Element Plus 输入框内部派生类被拒；统一改 ``.el-*`` 通配兜底。
GLOBAL_UI_SELECTOR_HINTS: Tuple[str, ...] = (
    ":root",
    "--ai-",
    "html",
    "*",
    ".el-*",
    ".login-page",
    ".login-brand",
    ".login-card",
    ".shell-top",
    ".shell-aside",
    ".shell-split",
    ".shell-main",
    ".context-panel",
    ".hero",
    ":focus-visible",
    "a:focus-visible",
    "::selection",
    "::-webkit-scrollbar",
)

# 保留被禁止的关键 class：路由壳层、模块页面入口、动态 API 调用等必须由固定生成器控制
# ISSUE-024：放宽白名单的同时必须守住越界，防止 LLM 把 JS / Vue / 模板字符串塞进 CSS。
UI_STEP_FORBIDDEN_SELECTORS: Tuple[str, ...] = (
    # 路由壳层（ISSUE-018 锁定）
    "<router-view", "<router-link",
    "@click=\"active", "v-if=\"!loggedIn",
    "import App from", "createApp(App)",
    # Vue 事件绑定 / 指令（P0-3 新增）
    "v-on:click", "v-bind:", "v-model=",
    # JS / TS 关键字（P0-3 新增）
    "import ", "export ", "require(", "function(", "const ", "let ", "var ",
    "=> {", "=>{", "async (", "await ",
    # 模板字符串 / 插值（P0-3 新增）
    "${", "`",  # 反引号 + 模板插值
)


def _chat_completion_request(
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    timeout: int,
) -> str:
    messages = _sanitize_json_strings(messages)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"代码增强 API 返回 HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"代码增强 API 连接失败: {exc.reason}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise RuntimeError("Code enhancer API read timed out") from exc

    try:
        return response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("代码增强 API 响应缺少 choices[0].message.content") from exc


def _chat_completion_worker(args: Tuple[str, str, str, List[Dict[str, str]], int], queue: Any) -> None:
    try:
        queue.put({"ok": True, "content": _chat_completion_request(*args)})
    except Exception as exc:
        queue.put({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def _sanitize_json_strings(value: Any) -> Any:
    """Replace lone surrogate characters before JSON is encoded for transport."""
    if isinstance(value, str):
        return value.encode("utf-8", errors="replace").decode("utf-8")
    if isinstance(value, list):
        return [_sanitize_json_strings(item) for item in value]
    if isinstance(value, dict):
        return {
            str(_sanitize_json_strings(key)): _sanitize_json_strings(item)
            for key, item in value.items()
        }
    return value


def _loads_last_json_object(text: str) -> Dict[str, Any]:
    last_error: Optional[json.JSONDecodeError] = None
    for line in reversed((text or "").splitlines()):
        candidate = line.strip()
        if not candidate:
            continue
        try:
            result = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if isinstance(result, dict):
            return result
    if last_error:
        raise last_error
    raise json.JSONDecodeError("empty subprocess output", text or "", 0)


# ISSUE-022：统一的 retry helper。
# - max_attempts 默认 3（原 2），给 LLM 抖动更多缓冲；
# - 指数退避 + jitter，避免多 worker 雪崩；
# - 对未列入 retryable_http_codes 的 HTTP code（如 400/403/404/408）直接抛，不浪费重试；
# - retry_callback(attempt_number, message) 用于向前端进度回调推送 retrying 事件。
_RETRYABLE_HTTP_CODES = frozenset({429, 500, 502, 503, 504, 529})


def _retry_with_backoff(
    operation: Callable[[], Any],
    *,
    max_attempts: int = 3,
    retry_callback: Optional[Callable[[int, str], None]] = None,
) -> Any:
    """对 operation 做指数退避 + jitter 重试。

    行为约定：
    - HTTP 4xx 中除 429 外直接抛（用户/路由错误重试无意义）；
    - HTTP 5xx / 429 / 连接/读超时一律重试到 max_attempts；
    - 非 RuntimeError（如 KeyError）不在本 helper 处理，调用方需自己捕获。
    """
    last_error: Optional[BaseException] = None
    for attempt in range(max_attempts):
        try:
            return operation()
        except RuntimeError as exc:
            last_error = exc
            message = str(exc)
            http_code: Optional[int] = None
            if "HTTP " in message:
                try:
                    http_code = int(message.split("HTTP ", 1)[1].split(":", 1)[0])
                except (ValueError, IndexError):
                    http_code = None
            # 非 retryable 的 HTTP code → 直接抛
            if http_code is not None and http_code not in _RETRYABLE_HTTP_CODES:
                raise
            if attempt == max_attempts - 1:
                raise
            if retry_callback:
                retry_callback(attempt + 1, f"{type(exc).__name__}: {exc}")
            # 指数退避（封顶 8s）+ jitter，避免 worker 同步重试雪崩。
            time.sleep(min(2 ** attempt, 8) + random.uniform(0, 1))
    raise last_error or RuntimeError("代码增强 API 请求失败")


def _is_local_base_url(base_url: str) -> bool:
    host = urllib.parse.urlparse(base_url).hostname or ""
    return host in {"127.0.0.1", "localhost", "::1"}


def _call_chat_completion_with_deadline(
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    timeout: int,
) -> str:
    # The factory runs jobs in daemon Processes. Python prohibits a daemon
    # process from creating another ``multiprocessing.Process``. A thread-pool
    # can return control to the caller, but it cannot actually kill a thread
    # blocked in SSL read, so repeated provider hangs leak worker threads.
    #
    # ISSUE-026：daemon Worker 下改用普通 Python subprocess 执行 HTTP 请求，
    # 由 ``subprocess.run(..., timeout=...)`` 做真正硬截止；超时后子进程会被
    # kill，不会在当前工厂进程里留下无法回收的 Python 线程。
    if multiprocessing.current_process().daemon:
        request_payload = {
            "base_url": base_url.rstrip("/"),
            "api_key": api_key,
            "model": model,
            "messages": _sanitize_json_strings(messages),
            "timeout": timeout,
        }
        try:
            completed = subprocess.run(
                [sys.executable, "-c", _CHAT_COMPLETION_SUBPROCESS_SCRIPT],
                input=json.dumps(request_payload, ensure_ascii=True),
                text=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout + 10,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Code enhancer API read timed out (daemon worker, "
                f"{timeout + 10}s wall-clock)"
            ) from exc
        output = (completed.stdout or "").strip()
        try:
            result = _loads_last_json_object(output)
        except json.JSONDecodeError as exc:
            detail = (completed.stderr or output or "empty subprocess output")[-500:]
            raise RuntimeError(f"代码增强 API 子进程响应无法解析: {detail}") from exc
        if completed.returncode != 0 or not result.get("ok"):
            raise RuntimeError(str(result.get("error") or "代码增强 API 子进程失败"))
        return str(result.get("content") or "")

    # Local mock/local LLM endpoints are used heavily by unit tests and do not
    # need a spawned hard-timeout process. Keeping these direct also avoids
    # test suites spending minutes on process startup for dozens of small calls.
    if _is_local_base_url(base_url) and os.getenv("AI_CODEGEN_FORCE_HARD_TIMEOUT") != "1":
        return _chat_completion_request(base_url, api_key, model, messages, timeout)

    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue(maxsize=1)
    args = (base_url, api_key, model, messages, timeout)
    process = ctx.Process(target=_chat_completion_worker, args=(args, queue))
    process.start()
    process.join(timeout + 5)
    if process.is_alive():
        process.terminate()
        process.join(3)
        if process.is_alive():
            process.kill()
            process.join(3)
        raise RuntimeError(f"Code enhancer API hard timeout after {timeout}s")
    if queue.empty():
        raise RuntimeError("代码增强 API 子进程未返回结果")
    result = queue.get()
    if result.get("ok"):
        return result["content"]
    raise RuntimeError(result.get("error") or "代码增强 API 请求失败")


class EnhancedFile(BaseModel):
    path: str
    content: str = Field(min_length=1, max_length=MAX_FILE_CHARS)

    @field_validator("path")
    @classmethod
    def allowed_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/").strip("/")
        if normalized not in ALLOWED_FILE_SET:
            raise ValueError(f"不允许修改文件: {normalized}")
        return normalized


class EnhancementResponse(BaseModel):
    summary: str = Field(default="", max_length=500)
    files: List[EnhancedFile] = Field(min_length=1, max_length=len(ALLOWED_FILES))

    @field_validator("files")
    @classmethod
    def unique_files(cls, value: List[EnhancedFile]) -> List[EnhancedFile]:
        paths = [item.path for item in value]
        if len(paths) != len(set(paths)):
            raise ValueError("返回文件路径不能重复")
        if sum(len(item.content) for item in value) > MAX_TOTAL_CHARS:
            raise ValueError("返回代码总长度超过限制")
        return value


class EnhancementResult(BaseModel):
    requested_mode: Literal["template", "auto", "llm"]
    # ISSUE-022：新增 ``partial`` 字面值。语义：AI 仅增强 README.md（或其它文档），
    # UI/CSS 子步骤全部失败回滚到模板。区分"完全 AI 增强(llm)"和"半增强(partial)"，
    # 避免 jobId=20260623225150-e2f31fbd 这类"actual_mode=llm 但实际只改了 README"的语义失真。
    actual_mode: Literal["template", "llm", "partial"]
    model: Optional[str] = None
    summary: Optional[str] = None
    changed_files: List[str] = Field(default_factory=list)
    fallback_reason: Optional[str] = None
    # ISSUE-020：分阶段 UI 增强产物
    ui_plan: Optional[Dict[str, Any]] = None
    ui_steps: Optional[List[Dict[str, Any]]] = None


def _extract_json(text: str) -> Dict[str, Any]:
    """从 LLM 响应中提取首个 JSON 对象。

    LLM 经常返回 ``\\`\\`\\`json ... \\`\\`\\``` 代码围栏、说明文字，或在合法 JSON
    之后追加额外内容；本函数按"代码围栏 -> 平衡大括号 -> 字符串字面量不计入"
    顺序提取首个完整 JSON 对象。
    """
    content = text.strip()
    # 去掉代码围栏
    if content.startswith("```"):
        content = content.split("\n", 1)[-1]
        content = content.rsplit("```", 1)[0]
    # 找第一个 '{' 并尝试平衡匹配
    start = content.find("{")
    if start < 0:
        raise ValueError("代码增强响应中没有 JSON 对象")
    in_string = False
    escape = False
    depth = 0
    end = -1
    for i in range(start, len(content)):
        ch = content[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end < 0:
        raise ValueError("代码增强响应中没有完整 JSON 对象")
    try:
        value = json.loads(content[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"代码增强 JSON 解析失败: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError("代码增强响应必须是 JSON 对象")
    return value


def _project_context(project_root: Path, target_file: str) -> Dict[str, str]:
    path = project_root / target_file
    if not path.exists():
        return {}
    content = path.read_text(encoding="utf-8")
    if target_file == "frontend/src/style.css":
        return {
            target_file: content[:6000],
            "style_mode": "append_only",
            "instruction": "只返回可追加到文件末尾的 CSS 增强块，不要返回完整 style.css。",
        }
    return {target_file: content}


def _pick_style_theme(planning: Dict[str, Any]) -> Dict[str, str]:
    seed = "|".join([
        str(planning.get("software_name") or ""),
        str(planning.get("industry_type") or planning.get("industry_name") or ""),
        str((planning.get("ui_plan") or {}).get("shell") or ""),
        ",".join(str(module.get("key") or module.get("name") or "") for module in planning.get("modules", [])),
    ])
    digest = hashlib.sha256(seed.encode("utf-8", errors="ignore")).hexdigest()
    palettes = [
        {"name": "deep-blue", "primary": "#1557b0", "accent": "#18a6d9", "dark": "#0b2447", "soft": "#eaf4ff"},
        {"name": "teal-command", "primary": "#087f8c", "accent": "#25c2a0", "dark": "#12343b", "soft": "#e7fbf7"},
        {"name": "indigo-violet", "primary": "#4f46e5", "accent": "#8b5cf6", "dark": "#211a4d", "soft": "#f0edff"},
        {"name": "steel-cyan", "primary": "#2563eb", "accent": "#06b6d4", "dark": "#0f2f4a", "soft": "#e6f7fb"},
        {"name": "graphite-gold", "primary": "#334155", "accent": "#d99a2b", "dark": "#172033", "soft": "#fff7e8"},
    ]
    textures = [
        "radial-gradient(circle at 18% 12%, rgba(255,255,255,.22), transparent 30%), linear-gradient(135deg, var(--ai-primary), var(--ai-accent))",
        "linear-gradient(120deg, rgba(255,255,255,.16) 0 1px, transparent 1px 18px), linear-gradient(135deg, var(--ai-dark), var(--ai-primary))",
        "radial-gradient(circle at 80% 16%, rgba(255,255,255,.2), transparent 28%), linear-gradient(115deg, var(--ai-primary), var(--ai-dark))",
    ]
    palette = palettes[int(digest[:2], 16) % len(palettes)].copy()
    palette["texture"] = textures[int(digest[2:4], 16) % len(textures)]
    palette["radius"] = ["10px", "14px", "18px"][int(digest[4:6], 16) % 3]
    return palette


def _build_style_enhancement(planning: Dict[str, Any]) -> EnhancementResponse:
    theme = _pick_style_theme(planning)
    module_count = len(planning.get("modules") or [])
    ui_plan = planning.get("ui_plan") or {}
    shell = str(ui_plan.get("shell") or "workspace")
    home_pattern = str(ui_plan.get("home_pattern") or "dashboard")
    content = f"""
:root {{
  --ai-primary: {theme["primary"]};
  --ai-accent: {theme["accent"]};
  --ai-dark: {theme["dark"]};
  --ai-soft: {theme["soft"]};
  --ai-radius: {theme["radius"]};
}}

body {{
  background:
    radial-gradient(circle at 8% 6%, color-mix(in srgb, var(--ai-accent) 14%, transparent), transparent 28%),
    linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%);
}}

.hero, .login-page {{
  background: {theme["texture"]};
  box-shadow: 0 18px 42px rgba(15, 45, 85, .18);
}}

.shell-top>header, .el-header, .context-panel, .page-heading, .el-card {{
  backdrop-filter: blur(10px);
  border-color: color-mix(in srgb, var(--ai-primary) 16%, #e5ebf2);
}}

.shell-top nav a.router-link-active,
.el-aside .el-menu-item.is-active,
.quick-grid a:hover {{
  background: linear-gradient(135deg, var(--ai-soft), rgba(255,255,255,.92));
  color: var(--ai-primary);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ai-primary) 18%, transparent);
}}

.metric-grid>*, .kpi-card, .module-dashboard article, .analysis-metrics article,
.master-detail-preview>div, .master-detail-preview aside, .tree-detail-preview>*,
.kanban-preview article, .trend-panel, .status-panel, .bar-panel, .activity-panel {{
  border-radius: var(--ai-radius);
  border: 1px solid color-mix(in srgb, var(--ai-primary) 14%, #dfe8f3);
  box-shadow: 0 10px 28px rgba(22, 54, 95, .08);
}}

.kpi-icon, .m-icon, .workflow-preview span, .flow-line i {{
  background: linear-gradient(160deg, var(--ai-primary), var(--ai-accent));
  color: #fff;
}}

.bars i, .trend-line, .bar-rect {{
  filter: drop-shadow(0 8px 14px color-mix(in srgb, var(--ai-primary) 22%, transparent));
}}

.module-page::before, .dashboard::before {{
  content: "{module_count} modules · {shell} · {home_pattern}";
  display: inline-flex;
  margin: 0 0 12px;
  padding: 5px 12px;
  border-radius: 999px;
  color: var(--ai-primary);
  background: var(--ai-soft);
  font-size: 12px;
  letter-spacing: .02em;
}}

.el-table tr:hover>td {{
  background: color-mix(in srgb, var(--ai-soft) 74%, #fff);
}}

.el-button--primary {{
  background: linear-gradient(135deg, var(--ai-primary), var(--ai-accent));
  border: 0;
}}
""".strip()
    return EnhancementResponse(
        summary=f"本地生成 {theme['name']} 风格 CSS 追加块，避免远程样式增强超时",
        files=[EnhancedFile(path="frontend/src/style.css", content=content)],
    )


def _request_enhancement(
    planning: Dict[str, Any],
    project_root: Path,
    target_file: str,
    previous_summaries: List[str],
) -> Tuple[EnhancementResponse, str]:
    if target_file == "frontend/src/style.css":
        return _build_style_enhancement(planning), "local-style-generator"

    base_url = os.getenv("AI_PLANNER_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    api_key = os.getenv("AI_PLANNER_API_KEY", "").strip()
    model = (
        os.getenv("AI_CODEGEN_MODEL", "").strip()
        or os.getenv("AI_PLANNER_MODEL", "").strip()
    )
    configured_timeout = int(os.getenv("AI_CODEGEN_TIMEOUT", "180"))
    timeout = min(configured_timeout, int(os.getenv("AI_CODEGEN_DOC_TIMEOUT", "90")))
    # ISSUE-022：retry 次数从 2 提到 3，配合 _retry_with_backoff 指数退避 + jitter。
    max_attempts = int(os.getenv("AI_CODEGEN_MAX_ATTEMPTS", "3"))
    if not api_key:
        raise RuntimeError("未配置 AI_PLANNER_API_KEY")
    if not model:
        raise RuntimeError("未配置 AI_CODEGEN_MODEL 或 AI_PLANNER_MODEL")

    if target_file == "frontend/src/style.css":
        system = (
            "你是受约束的软件界面样式增强器。只输出合法 JSON，不要 Markdown 或解释。"
            "你每次只能增强 target_file 指定的一个文件，不能返回其他文件，不能创建其他文件，不能修改依赖，不能调用外部服务。"
            "本轮 target_file 是 frontend/src/style.css，但你只能返回可追加到 CSS 文件末尾的增强样式块，不能返回完整 style.css。"
            "增强目标：增加行业化视觉、驾驶舱质感、卡片/表格/状态标签差异化样式，且必须兼容现有 class。"
            "不要覆盖路由、Vue 文件、API 或后端代码。"
            '输出结构为 {"summary":"说明","files":[{"path":"frontend/src/style.css","content":"CSS 追加块"}]}。'
        )
    else:
        system = (
            "你是受约束的软件文档增强器。只输出合法 JSON，不要 Markdown 或解释。"
            "你每次只能增强 target_file 指定的一个文件，不能返回其他文件，不能创建其他文件，不能修改依赖，不能调用外部服务。"
            "增强目标：让文案、示例数据和 API 描述更贴合 planning.json，"
            "但不能新增 planning.json 中不存在的业务模块。"
            '输出结构为 {"summary":"说明","files":[{"path":"target_file","content":"完整文件内容"}]}。'
        )
    user_payload = {
        "planning": planning,
        "allowed_files": list(ALLOWED_FILES),
        "target_file": target_file,
        "current_files": _project_context(project_root, target_file),
        "previous_summaries": previous_summaries,
    }
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": json.dumps(user_payload, ensure_ascii=False),
        },
    ]

    def call_api(current_messages: List[Dict[str, str]]) -> str:
        # ISSUE-022：复用 _retry_with_backoff，自动获得指数退避 + jitter。
        def _do_call() -> str:
            return _call_chat_completion_with_deadline(
                base_url,
                api_key,
                model,
                current_messages,
                timeout,
            )

        try:
            return _retry_with_backoff(
                _do_call,
                max_attempts=max_attempts,
            )
        except RuntimeError as exc:
            raise RuntimeError(f"{type(exc).__name__}: {exc}") from exc

    last_error: Optional[Exception] = None
    for attempt in range(2):
        content = call_api(messages)
        try:
            parsed = EnhancementResponse.model_validate(_extract_json(content))
            if len(parsed.files) != 1 or parsed.files[0].path != target_file:
                raise ValueError(f"代码增强本轮只能返回 {target_file}")
            return parsed, model
        except Exception as exc:
            last_error = exc
            if attempt == 1:
                break
            messages.extend([
                {"role": "assistant", "content": content[:4000]},
                {
                    "role": "user",
                    "content": (
                        "上一轮响应不是可解析的合法 JSON 或结构不符合要求。"
                        f"错误：{type(exc).__name__}: {exc}。"
                        "请只返回严格 JSON 对象，不要 Markdown，不要注释，不要单引号，"
                        f"files 中必须且只能包含 path 为 {target_file} 的完整文件内容。"
                    ),
                },
            ])
    raise last_error or RuntimeError("代码增强响应解析失败")


def _backup_files(project_root: Path, backup_root: Path, files: List[EnhancedFile]) -> None:
    if backup_root.exists():
        shutil.rmtree(backup_root)
    for item in files:
        source = project_root / item.path
        if not source.exists():
            raise ValueError(f"模板文件不存在: {item.path}")
        target = backup_root / item.path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _backup_allowed_files(project_root: Path, backup_root: Path) -> None:
    if backup_root.exists():
        shutil.rmtree(backup_root)
    for relative in ALLOWED_FILES:
        source = project_root / relative
        if not source.exists():
            raise ValueError(f"模板文件不存在: {relative}")
        target = backup_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _restore_one_file(project_root: Path, backup_root: Path, relative: str) -> None:
    source = backup_root / relative
    if not source.exists():
        return
    target = project_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _write_enhanced_file(project_root: Path, item: EnhancedFile) -> None:
    target = project_root / item.path
    if item.path == "frontend/src/style.css":
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        marker = "\n\n/* AI Code Enhancer: style append */\n"
        target.write_text(existing.rstrip() + marker + item.content.strip() + "\n", encoding="utf-8")
        return
    target.write_text(item.content, encoding="utf-8")


def restore_enhancement(project_root: Path, backup_root: Path) -> List[str]:
    restored: List[str] = []
    if not backup_root.exists():
        return restored
    for source in backup_root.rglob("*"):
        if source.is_file():
            relative = source.relative_to(backup_root)
            target = project_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            restored.append(relative.as_posix())
    return restored


# ----------------- ISSUE-020：ui_enhancement_plan 公共数据结构 -----------------

class UIStepBlock(BaseModel):
    """单个 UI 子步骤返回的 CSS 追加块。

    - ``selectors`` 列出本块改动的 class / 标签集合，便于审计和后续按步回退。
    - ``content`` 必须是可追加到 style.css 末尾的 CSS 片段，长度有上限。
    """

    summary: str = Field(default="", max_length=240)
    content: str = Field(min_length=1, max_length=UI_STEP_MAX_BLOCK_CHARS)
    selectors: List[str] = Field(default_factory=list, max_length=200)


class UIStepResponse(BaseModel):
    step: str
    # ISSUE-026：LLM 返回内容无 CSS 规则（纯注释 / 空 `@media{}`）时，``block``
    # 为 ``None``，调用方标 ``skipped`` 而非 ``failed``，避免反复重试拖垮任务。
    block: Optional[UIStepBlock] = None
    skip_reason: Optional[str] = None


class UIEnhancementPlan(BaseModel):
    """LLM 第一次返回的界面风格方案，仅含 JSON 风格令牌与设计说明。"""

    summary: str = Field(default="", max_length=240)
    tokens: Dict[str, str] = Field(default_factory=dict)
    notes: List[str] = Field(default_factory=list, max_length=20)


# ----------------- ISSUE-020：ui_enhancement_plan 流程 -----------------

def _stable_ui_seed(planning: Dict[str, Any]) -> str:
    """生成稳定的 UI 种子，用于在本地兜底时仍能产生风格令牌。

    与原 ``_pick_style_theme`` 相同的 hash 源，保证同一规划跨进程产生相同的风格令牌。
    """
    seed = "|".join([
        str(planning.get("software_name") or ""),
        str(planning.get("industry_type") or planning.get("industry_name") or ""),
        str((planning.get("ui_plan") or {}).get("shell") or ""),
        ",".join(str(module.get("key") or module.get("name") or "") for module in planning.get("modules", [])),
    ])
    return hashlib.sha256(seed.encode("utf-8", errors="ignore")).hexdigest()


def _local_ui_tokens(planning: Dict[str, Any]) -> Dict[str, str]:
    """本地兜底风格令牌，作为 LLM 不可用时的稳定回退。

    必须确保同一规划跨进程产生相同令牌，从而本任务中所有子步骤风格一致。
    """
    theme = _pick_style_theme(planning)
    return {
        "name": theme["name"],
        "primary": theme["primary"],
        "accent": theme["accent"],
        "dark": theme["dark"],
        "soft": theme["soft"],
        "radius": theme["radius"],
        "texture": theme["texture"],
    }


def _resolve_tokens(planning: Dict[str, Any], plan: Optional[UIEnhancementPlan]) -> Dict[str, str]:
    """合并 LLM 返回的令牌与本地兜底，确保每个子步骤都拿到完整令牌。"""
    base = _local_ui_tokens(planning)
    if plan and plan.tokens:
        for key, value in plan.tokens.items():
            if isinstance(value, str) and value.strip():
                base[key] = value.strip()
    return base


def _css_rule_selectors(content: str) -> List[str]:
    """Extract rule headers from a small append-only CSS block for validation."""
    without_comments = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    selectors: List[str] = []
    header: List[str] = []
    for character in without_comments:
        if character == "{":
            value = "".join(header).strip()
            header = []
            if not value:
                continue
            if value.startswith("@"):
                selectors.append(value)
            else:
                selectors.extend(
                    item.strip() for item in value.split(",") if item.strip()
                )
        elif character == "}":
            header = []
        else:
            header.append(character)
    return selectors


def _selector_matches_hints(selector: str, hints: Tuple[str, ...]) -> bool:
    """判断 ``selector`` 是否落在白名单（含全局 + 当前步 hints）内。

    ISSUE-024（2026-06-24）：
    - 裸 ``*`` 与 ``*::before`` / ``*::after`` 等全局重置选择器一律放行；
    - hint 末尾的 ``*`` 视为前缀通配（``X*`` 匹配 X 开头的所有选择器）；
    - ``__*`` / ``--*`` 等 BEM 派生通配命中 Element Plus 派生类（如 ``.el-card__header``、
      ``.el-button--success``）。

    ISSUE-027（2026-06-25）：
    - 复合 selector（``A B`` / ``A>B`` / ``A+B`` / ``A~B``）按 ``> + ~`` 拆分后，
      每部分分别走 hints；任一部分通过即通过（``A B`` 是后代，常见于 LLM 把
      ``.kpi-trend-down .kpi-trend`` 写成复合 selector）；
    - 伪类（``:hover`` / ``:focus``）与伪元素（``::before`` / ``::after``）从最右侧
      拆掉后再匹配 hints，让 ``.el-input__wrapper:hover`` 通过 ``.el-*`` 通配。
    """
    normalized = _normalize_css_selector(selector)
    # 1) 全局重置选择器特判
    if normalized == "*" or normalized.startswith("*::"):
        return True
    # 2) 复合 selector 拆分：``.A .B:hover`` → [``.a``, ``.b``]（拆掉伪类/伪元素后再拆组合符）
    parts = _split_compound_selector(normalized)
    # 3) 全局白名单
    for global_hint in GLOBAL_UI_SELECTOR_HINTS:
        for part in parts:
            if _hint_matches(part, global_hint):
                return True
    # 4) 步骤白名单
    for hint in hints:
        for part in parts:
            if _hint_matches(part, hint):
                return True
    return False


def _split_compound_selector(selector: str) -> List[str]:
    """把复合 selector 按组合符 ``> + ~`` 与空白拆成多部分，每部分单独验证。

    伪类 ``:hover`` / ``:focus`` 与伪元素 ``::before`` / ``::after`` 视为
    selector 的尾部修饰，从最右侧剥离后只把"基础 selector"送入 hint 匹配。
    """
    # 按组合符与空白切分，但保留 ``::after`` / ``::before`` / ``:hover`` 等
    parts: List[str] = []
    buf: List[str] = []
    i = 0
    while i < len(selector):
        ch = selector[i]
        if ch in " \t\n,>+~":
            if buf:
                parts.append("".join(buf))
                buf = []
        elif ch == ":" and i + 1 < len(selector) and selector[i + 1] == ":":
            # ``::before`` / ``::after`` 一并切掉（含 ``::``）
            if buf:
                parts.append("".join(buf))
                buf = []
            # 跳过整个 ``::xxx``（可能含 ``-``）
            i += 2
            while i < len(selector) and selector[i] not in " \t\n,>+~":
                i += 1
            continue
        elif ch == ":":
            # 单冒号伪类：`` :hover`` / ``:focus`` 等同样切掉
            if buf:
                parts.append("".join(buf))
                buf = []
            i += 1
            while i < len(selector) and selector[i] not in " \t\n,>+~":
                i += 1
            continue
        else:
            buf.append(ch)
        i += 1
    if buf:
        parts.append("".join(buf))
    # 若只剩一个部分（即未拆分），仍要返回原 selector 以兼容非复合 selector
    return parts if parts else [selector]


def _normalize_css_selector(value: str) -> str:
    normalized = " ".join(value.strip().lower().split())
    return re.sub(r"\s*([>+~])\s*", r"\1", normalized)


def _hint_matches(normalized_selector: str, hint: str) -> bool:
    """单条 hint 对 normalized selector 的匹配。

    - ``X*`` 后缀通配：``X*`` 匹配以 X 开头的所有 selector。
      - 裸 ``*`` 仅匹配 ``*`` / ``*::xxx``（由 ``_selector_matches_hints`` 特判）；
      - ``X__*`` 涵盖 BEM 派生（``X__header`` / ``X__body`` 等以 ``X__`` 开头的派生类）；
      - ``X--*`` 涵盖 Element Plus 修饰符（``X--primary`` / ``X--success`` 等以 ``X--`` 开头的修饰类）。
    - ``@media`` 特殊：所有 ``@media`` 开头的 selector 都放行。
    - 其它 hint 走字面前缀匹配（X 后面必须是分隔符 ``  .:#>[+~(``）。
    """
    allowed = _normalize_css_selector(hint)
    # 末尾 * 通配
    if allowed.endswith("*"):
        prefix = allowed[:-1]
        if not prefix:
            return False  # 裸 * 已由调用方特判处理
        # selector 以 prefix 开头即匹配（涵盖 prefix 自身 + 所有派生）。
        return normalized_selector.startswith(prefix)
    # @media 特判
    if allowed == "@media":
        return normalized_selector.startswith("@media")
    # 字面前缀匹配
    if normalized_selector == allowed:
        return True
    if normalized_selector.startswith(allowed) and len(normalized_selector) > len(allowed):
        if normalized_selector[len(allowed)] in " .:#>[+~(":
            return True
    return False


def _validate_ui_block(step_key: str, block: UIStepBlock) -> None:
    """校验单个子步骤返回的 CSS 片段，避免越界改写壳层或返回整文件。

    ISSUE-024（2026-06-24）：放宽白名单的同时，新增 ``_scan_css_chars`` 字符集合扫描
    兜底：剥离注释后，剩余内容只允许常见 CSS 字符、ASCII 字母数字、空白与 Unicode
    字符（含中文）。其它 ASCII 控制字符或乱码直接拒，防止 LLM 漏网写入 JS / 异常字节。
    """
    content = block.content.strip()
    if len(content) > UI_STEP_MAX_BLOCK_CHARS:
        raise ValueError(f"UI 子步骤 {step_key} 返回的 CSS 片段超过 {UI_STEP_MAX_BLOCK_CHARS} 字符")
    lowered = content.lower()
    for forbidden in UI_STEP_FORBIDDEN_SELECTORS:
        if forbidden.lower() in lowered:
            raise ValueError(f"UI 子步骤 {step_key} 返回内容包含禁止片段: {forbidden}")
    _scan_css_chars(step_key, content)
    hints = UI_STEP_SELECTOR_HINTS.get(step_key, ())
    actual_selectors = _css_rule_selectors(content)
    if not actual_selectors:
        raise ValueError(f"UI 子步骤 {step_key} 未包含可校验的 CSS 选择器")
    unauthorized = [
        selector for selector in actual_selectors
        if not _selector_matches_hints(selector, hints)
    ]
    if unauthorized:
        raise ValueError(
            f"UI 子步骤 {step_key} CSS 内容包含未授权选择器: {unauthorized[:5]}"
        )


# ISSUE-024（P0-3）：剥离注释后，剩余 CSS 字符的合法集合。
# 常见 CSS 标点 + 字符串/模板分隔符 + ASCII 字母数字 + 空白 + Unicode（中文）。
_ALLOWED_CSS_CHARS: frozenset = frozenset(
    "{}[]();,.:#%!+-=*/<>'\"`~|^&$@?\\_"
)


def _scan_css_chars(step_key: str, content: str) -> None:
    """剥离注释后扫描剩余字符，命中非 ASCII 控制字符或乱码即报错。

    设计：
    - 注释 ``/* ... */`` 内允许任意字符（含中文），剥离后扫描；
    - 字符串字面量 ``"..."`` / ``'...'`` 与反引号 `` ` `` 允许（禁片已另行处理 ``${``）；
    - 中日韩越等 Unicode 字符（ord > 127）允许；
    - 其它 ASCII 可见字符与 tab/换行/回车允许；
    - ASCII 控制字符（\\x00-\\x08, \\x0b-\\x0c, \\x0e-\\x1f）直接拒。
    """
    no_comments = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    for char in no_comments:
        if char.isalnum() or char.isspace():
            continue
        if char in _ALLOWED_CSS_CHARS:
            continue
        if ord(char) > 127:
            continue
        # ASCII 控制字符或意外字节
        raise ValueError(
            f"UI 子步骤 {step_key} CSS 包含非法字符: {char!r} (ord={ord(char)})"
        )


def _call_chat_json(
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    timeout: int,
    retry_callback: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, Any]:
    """Call Chat Completion and parse one JSON object.

    HTTP/read-timeout retries are handled only by ``_retry_with_backoff``.
    JSON repair is a separate single follow-up request. This avoids the old
    outer-loop x inner-loop retry multiplication that could keep one UI step
    blocked for many minutes.
    """
    max_attempts = int(os.getenv("AI_CODEGEN_MAX_ATTEMPTS", "3"))

    def _do_call(current_messages: List[Dict[str, str]]) -> str:
        return _call_chat_completion_with_deadline(
            base_url, api_key, model, current_messages, timeout
        )

    content = _retry_with_backoff(
        lambda: _do_call(messages),
        max_attempts=max_attempts,
        retry_callback=retry_callback,
    )
    try:
        return _extract_json(content)
    except ValueError as exc:
        if retry_callback:
            retry_callback(1, f"{type(exc).__name__}: {exc}")
        repair_messages = list(messages) + [
            {"role": "assistant", "content": content[:4000]},
            {
                "role": "user",
                "content": (
                    "上一轮响应不是可解析的合法 JSON。"
                    f"错误：{type(exc).__name__}: {exc}。"
                    "请只返回严格 JSON 对象，不要 Markdown，不要注释，不要单引号。"
                ),
            },
        ]
        repaired = _retry_with_backoff(
            lambda: _do_call(repair_messages),
            max_attempts=max_attempts,
            retry_callback=retry_callback,
        )
        return _extract_json(repaired)

def _request_ui_plan(
    planning: Dict[str, Any],
    timeout: int,
    model: Optional[str],
    api_key: Optional[str],
    base_url: str,
    retry_callback: Optional[Callable[[int, str], None]] = None,
) -> Tuple[Optional[UIEnhancementPlan], Optional[str]]:
    """请求 LLM 返回界面风格方案（仅 JSON 风格令牌）。

    返回 ``(plan, error_message)``：成功时 plan 非空；LLM 不可用或解析失败时
    返回 ``(None, error_message)``，调用方应回退到本地风格令牌。
    """
    if not api_key or not model:
        return None, "未配置 AI_PLANNER_API_KEY 或 AI_CODEGEN_MODEL"
    tokens_hint = _local_ui_tokens(planning)
    system = (
        "你是受约束的界面风格规划师。"
        "只输出合法 JSON，不要 Markdown 或解释。"
        "目标：基于软件名称、类型、行业和模块语义，给出一份可被下游 CSS 子步骤复用的风格方案。"
        "禁止返回任何 CSS、HTML、Vue、JS 或 SQL。"
        '输出结构为 {"summary":"一句中文设计说明","tokens":{...},"notes":[可选，<=6 条]}，'
        'tokens 至少包含 primary/accent/dark/soft/radius/texture/name 共 7 项，'
        'value 必须是字符串，颜色用 hex、半径用 px、纹理用 CSS 背景表达式。'
    )
    user_payload = {
        "step": "theme",
        "task": "界面风格方案设计",
        "planning_summary": {
            "software_name": planning.get("software_name"),
            "software_type": planning.get("software_type"),
            "industry": planning.get("industry_name") or planning.get("industry_type"),
            "ui_plan": planning.get("ui_plan"),
            "module_keys": [
                str(module.get("key") or module.get("name") or "")
                for module in planning.get("modules", [])
            ],
        },
        "tokens_hint": tokens_hint,
    }
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]
    try:
        payload = _call_chat_json(
            base_url, api_key, model, messages, timeout, retry_callback
        )
        plan = UIEnhancementPlan.model_validate(payload)
        return plan, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _fallback_ui_step_block(
    step_key: str,
    step_name: str,
    tokens: Dict[str, str],
    planning: Dict[str, Any],
) -> UIStepBlock:
    """Render a small CSS block from the LLM theme tokens when a UI substep times out."""
    primary = tokens.get("primary", "#2563eb")
    accent = tokens.get("accent", "#38bdf8")
    dark = tokens.get("dark", "#102033")
    soft = tokens.get("soft", "#eef6ff")
    radius = tokens.get("radius", "16px")
    texture = tokens.get("texture", f"linear-gradient(135deg,{primary},{accent})")
    name = tokens.get("name", "ai-theme")
    module_count = len(planning.get("modules") or [])
    blocks: Dict[str, Tuple[str, List[str]]] = {
        "shell": (
            f"""
.login-page{{background:{texture};}}
.login-brand h1{{letter-spacing:.04em;color:#fff;}}
.login-card{{border-radius:{radius};box-shadow:0 22px 55px rgba(15,23,42,.18);}}
.shell-top>header{{background:linear-gradient(135deg,{dark},{primary});color:#fff;}}
.shell-top nav a.router-link-active,.shell-aside .menu .is-active{{background:{soft};color:{primary};}}
.shell-main{{background:linear-gradient(180deg,{soft},#fff);}}
""".strip(),
            [".login-page", ".login-brand h1", ".login-card", ".shell-top>header", ".shell-top nav a.router-link-active", ".shell-aside .menu .is-active", ".shell-main"],
        ),
        "business": (
            f"""
.module-page{{border-radius:{radius};background:rgba(255,255,255,.96);}}
.page-heading{{border-left:4px solid {accent};padding-left:14px;}}
.toolbar{{background:{soft};border-radius:{radius};padding:12px;}}
.el-card,.filter-bar{{border-color:color-mix(in srgb,{primary} 18%,#e5e7eb);box-shadow:0 10px 24px rgba(15,23,42,.08);}}
.el-button--primary,.btn-primary{{background:linear-gradient(135deg,{primary},{accent});border:0;}}
.status-pill,.el-tag--success{{border-radius:999px;}}
.el-table tr:hover>td{{background:color-mix(in srgb,{soft} 75%,#fff);}}
""".strip(),
            [".module-page", ".page-heading", ".toolbar", ".el-card", ".filter-bar", ".el-button--primary", ".btn-primary", ".status-pill", ".el-tag--success", ".el-table tr:hover>td"],
        ),
        "dashboard": (
            f"""
.module-dashboard{{background:linear-gradient(180deg,#fff,{soft});border-radius:{radius};}}
.kpi-grid{{gap:18px;}}
.kpi-card{{border-top:3px solid {accent};box-shadow:0 14px 30px rgba(15,23,42,.1);}}
.kpi-value{{color:{primary};font-size:28px;font-weight:800;}}
.kpi-trend,.kpi-icon{{color:{accent};}}
.trend-panel,.donut-panel,.bar-panel{{border-radius:{radius};border:1px solid color-mix(in srgb,{primary} 16%,#e5e7eb);}}
.trend-svg,.donut-svg,.bar-svg{{filter:drop-shadow(0 8px 16px rgba(15,23,42,.12));}}
.dashboard-row{{align-items:stretch;}}
""".strip(),
            [".module-dashboard", ".kpi-grid", ".kpi-card", ".kpi-value", ".kpi-trend", ".kpi-icon", ".trend-panel", ".donut-panel", ".bar-panel", ".trend-svg", ".donut-svg", ".bar-svg", ".dashboard-row"],
        ),
        "responsive": (
            f"""
@media (max-width: 960px){{.shell-split{{grid-template-columns:1fr;}}.kpi-grid,.dashboard-row{{grid-template-columns:1fr;}}.toolbar{{gap:8px;}}}}
@media (max-width: 640px){{.page-heading{{padding-left:10px;}}.module-page{{border-radius:12px;}}.el-table{{font-size:12px;}}}}
:focus-visible{{outline:3px solid {accent};outline-offset:2px;}}
::selection{{background:{accent};color:#fff;}}
""".strip(),
            ["@media", ".shell-split", ".kpi-grid", ".dashboard-row", ".toolbar", ".page-heading", ".module-page", ".el-table", ":focus-visible", "::selection"],
        ),
    }
    content, selectors = blocks.get(
        step_key,
        (f".module-page{{border-radius:{radius};box-shadow:0 10px 24px rgba(15,23,42,.08);}}", [".module-page"]),
    )
    block = UIStepBlock(
        summary=f"{step_name}：LLM 子步骤超时，使用 {name} 主题令牌生成稳定 CSS（模块数 {module_count}）",
        content=content,
        selectors=selectors,
    )
    _validate_ui_block(step_key, block)
    return block


def _request_ui_step(
    step_key: str,
    step_name: str,
    planning: Dict[str, Any],
    tokens: Dict[str, str],
    project_root: Path,
    timeout: int,
    model: Optional[str],
    api_key: Optional[str],
    base_url: str,
    retry_callback: Optional[Callable[[int, str], None]] = None,
) -> UIStepResponse:
    """Request one UI CSS substep with a small prompt and timeout-safe fallback."""
    hints = UI_STEP_SELECTOR_HINTS.get(step_key, ())
    if not api_key or not model:
        raise RuntimeError(f"UI 子步骤 {step_key} 未配置 AI API Key 或模型")
    modules = [
        {
            "key": str(module.get("key") or ""),
            "name": str(module.get("name") or ""),
            "pattern": str(module.get("page_pattern") or ""),
        }
        for module in (planning.get("modules") or [])[:6]
    ]
    step_tasks = {
        "shell": "只增强登录页、顶部/侧边导航、主工作区外壳。",
        "business": "只增强模块页卡片、筛选条、表格、按钮、状态标签。",
        "dashboard": "只增强 KPI、趋势图、柱状图、环形图和驾驶舱面板。",
        "responsive": "只增强移动端断点、焦点态和基础可访问性。",
    }
    system = (
        "你是受约束的 CSS 子步骤增强器。只输出合法 JSON，不要 Markdown。"
        "只返回可追加到 frontend/src/style.css 末尾的 CSS 片段。"
        "禁止 JS、Vue、HTML、SQL、import、router、事件绑定。"
        "content 建议 6 到 14 条 CSS 规则，尽量少于 1600 字符。"
        '输出格式：{"summary":"中文摘要","content":"CSS","selectors":["..."]}。'
    )
    user_payload = {
        "step": step_key,
        "task": step_tasks.get(step_key, step_name),
        "allowed_selectors": list(hints)[:32],
        "tokens": {key: str(value) for key, value in list(tokens.items())[:12]},
        "software_name": planning.get("software_name"),
        "modules": modules,
    }
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]
    try:
        payload = _call_chat_json(
            base_url, api_key, model, messages, timeout, retry_callback
        )
        try:
            block = UIStepBlock.model_validate(payload)
        except ValidationError as exc:
            if "string_too_long" not in str(exc):
                raise
            if retry_callback:
                retry_callback(0, "content 超过限制，反馈模型精简")
            trim_messages = messages + [
                {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)[:3000]},
                {"role": "user", "content": "content 太长。请精简到 1200 字符以内，只保留核心 CSS。"},
            ]
            payload = _call_chat_json(
                base_url, api_key, model, trim_messages, timeout, retry_callback
            )
            block = UIStepBlock.model_validate(payload)
        if not _css_rule_selectors(block.content):
            return UIStepResponse(
                step=step_key,
                block=None,
                skip_reason="LLM 返回内容不含任何 CSS 规则，已跳过本步以避免任务阻塞",
            )
        _validate_ui_block(step_key, block)
        return UIStepResponse(step=step_key, block=block)
    except (RuntimeError, ValueError) as exc:
        message = str(exc)
        recoverable = (
            "read timed out" in message
            or "hard timeout" in message
            or "JSON" in message
            or "json" in message
        )
        if not recoverable:
            raise
        return UIStepResponse(
            step=step_key,
            block=_fallback_ui_step_block(step_key, step_name, tokens, planning),
        )

def _step_block_marker(step_key: str, summary: str) -> str:
    safe_summary = summary.strip().replace("*/", "* /")[:160] or UI_STEP_NAMES.get(step_key, step_key)
    return f"\n\n/* AI UI Enhancer: {step_key} · {safe_summary} */\n"


def _append_style_block(project_root: Path, step_key: str, block: UIStepBlock) -> None:
    """把单个 UI 子步骤的 CSS 追加块写入 style.css，失败时可单独回滚。"""
    target = project_root / "frontend" / "src" / "style.css"
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    marker = _step_block_marker(step_key, block.summary)
    target.write_text(
        existing.rstrip() + marker + block.content.strip() + "\n",
        encoding="utf-8",
    )


def _ui_step_timeout() -> int:
    configured = int(os.getenv("AI_CODEGEN_UI_TIMEOUT", "60"))
    doc_cap = int(os.getenv("AI_CODEGEN_DOC_TIMEOUT", "90"))
    # UI 子步骤应明显短于文档增强，避免单步卡住过久
    return max(15, min(configured, doc_cap))


def _ui_base_url() -> str:
    return os.getenv("AI_PLANNER_BASE_URL", "https://api.openai.com/v1").rstrip("/")


def _ui_credentials() -> Tuple[str, str, Optional[str]]:
    api_key = os.getenv("AI_PLANNER_API_KEY", "").strip()
    model = (
        os.getenv("AI_CODEGEN_MODEL", "").strip()
        or os.getenv("AI_PLANNER_MODEL", "").strip()
        or None
    )
    return _ui_base_url(), api_key, model


def _backup_one_file(project_root: Path, backup_root: Path, relative: str) -> None:
    source = project_root / relative
    if not source.exists():
        return
    target = backup_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _ensure_step_status(steps: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    for item in steps:
        if item.get("step") == key:
            return item
    raise KeyError(f"unknown step {key}")


def enhance_project(
    job: Dict[str, Any],
    planning: Dict[str, Any],
    project_root: Path,
    backup_root: Path,
    progress_callback: Optional[Callable[[Dict[str, str]], None]] = None,
) -> EnhancementResult:
    """执行受约束的 AI 代码增强。

    ISSUE-020：在 README 文档增强之外，将 ``frontend/src/style.css`` 拆成 5 个 UI 子步骤，
    每个子步骤是小请求、独立超时、独立重试、按步回退的 CSS 追加块。
    前端可看到 ``pending / running / retrying / completed / failed`` 的实时进度。

    ISSUE-024：先扫描生成项目实际渲染的 class（``selector_audit.collect_real_selectors``），
    与常量 hints 合并为运行时 hints；只在本函数内有效，try/finally 恢复。
    """
    from app.selector_audit import collect_real_selectors, merge_with_hints, audit_drift  # noqa: WPS433
    from app.learning import default_learnings_root  # noqa: WPS433

    requested_mode = (job.get("codegen_mode") or "auto").strip().lower()
    if requested_mode not in {"template", "auto", "llm"}:
        raise RuntimeError("codegen_mode 必须是 template、auto 或 llm")
    if requested_mode == "template":
        return EnhancementResult(
            requested_mode="template",
            actual_mode="template",
            summary="使用固定项目模板",
        )

    _backup_allowed_files(project_root, backup_root)

    # ISSUE-024：合并生成器实际 class 到运行时 hints；enhance 完成后恢复常量。
    real_selectors = collect_real_selectors(project_root)
    merged_hints = merge_with_hints(UI_STEP_SELECTOR_HINTS, real_selectors)
    snapshot = {key: tuple(values) for key, values in UI_STEP_SELECTOR_HINTS.items()}
    UI_STEP_SELECTOR_HINTS.clear()
    UI_STEP_SELECTOR_HINTS.update(merged_hints)
    try:
        # UI 增强先执行：用户可立即看到 5 个长耗时界面步骤的实时进度。
        # README 是独立文档步骤，不应阻塞 UI 节点从 pending 进入 running。
        ui_steps, ui_plan, ui_changed = _enhance_ui_steps(
            planning,
            project_root,
            backup_root,
            progress_callback,
        )

        ui_failures = [
            item for item in ui_steps if item.get("status") == "failed"
        ]
        # ISSUE-022：llm 模式容忍最多 1 个 UI 子步骤失败（≥4/5 步成功仍视为 llm 增强成功）。
        # 仅当 ≥2 步失败才触发整体回滚 + 抛错。
        if requested_mode == "llm" and len(ui_failures) >= 2:
            restore_enhancement(project_root, backup_root)
            failed_steps = ", ".join(
                f"{UI_STEP_NAMES.get(item['step'], item['step'])}: "
                f"{item.get('failure_reason') or 'failed'}"
                for item in ui_failures
            )
            _record_enhance_failure(
                job,
                requested_mode,
                ui_steps,
                "；".join(
                    f"{UI_STEP_NAMES.get(item['step'], item['step'])}："
                    f"{item.get('failure_reason') or 'failed'}"
                    for item in ui_failures
                )[:500],
                issue_id="ISSUE-024",
            )
            raise RuntimeError(f"llm 模式 UI 增强失败 ≥2 步，已回滚: {failed_steps}")

        # README 文档增强保持逐文件行为，在 UI 阶段结束后独立执行。
        readme_status = _enhance_readme(
            job,
            planning,
            project_root,
            backup_root,
            progress_callback,
        )

        changed_files: List[str] = list(ui_changed)
        if readme_status.get("changed"):
            changed_files.append("README.md")

        summaries: List[str] = []
        failures: List[str] = []
        model: Optional[str] = None

        for item in ui_steps:
            if item.get("summary"):
                summaries.append(
                    f"{UI_STEP_NAMES.get(item['step'], item['step'])}：{item['summary']}"
                )
            if item.get("status") == "failed":
                failures.append(
                    f"{UI_STEP_NAMES.get(item['step'], item['step'])}："
                    f"{item.get('failure_reason') or '失败'}"
                )

        if readme_status.get("summary"):
            summaries.append(f"README.md：{readme_status['summary']}")
        if readme_status.get("failure"):
            failures.append(f"README.md：{readme_status['failure']}")
        if readme_status.get("model"):
            model = readme_status["model"]
        if ui_plan and ui_plan.get("model"):
            model = ui_plan["model"]

        # ISSUE-022：实际 AI 是否真正增强了 style.css 是关键判定。
        # 若 UI 子步骤全失败但 README 改了，旧逻辑错误地标 actual_mode="llm"，
        # 现改为 "partial"，让前端/合规检查能区分"完全增强"与"半增强"。
        style_css_changed = "frontend/src/style.css" in changed_files
        readme_changed = "README.md" in changed_files
        fallback_reason = "；".join(failures)[:500] if failures else None
        if not changed_files:
            # 全部失败，恢复 style.css + README.md
            restore_enhancement(project_root, backup_root)
            _record_enhance_failure(
                job, requested_mode, ui_steps, fallback_reason,
                issue_id="ISSUE-024",
            )
            return EnhancementResult(
                requested_mode=requested_mode,
                actual_mode="template",
                summary="代码增强失败，保留固定模板",
                fallback_reason=fallback_reason,
                ui_plan=ui_plan,
                ui_steps=ui_steps,
            )

        # 判定 actual_mode：
        # - style.css 实际改了 → llm（无论 README 是否改）
        # - 仅 README 改了、style.css 未改 → partial
        actual_mode = "llm" if style_css_changed else "partial"
        summary_text = "；".join(summaries)[:500] or "分阶段 UI 增强完成"
        if actual_mode == "partial":
            summary_text = (
                summary_text
                + "（仅 README 由 AI 增强，UI/CSS 增强全部失败回滚到模板）"
            )[:500]

        _record_enhance_failure(
            job, requested_mode, ui_steps, fallback_reason,
            issue_id="ISSUE-024",
        )
        return EnhancementResult(
            requested_mode=requested_mode,
            actual_mode=actual_mode,
            model=model,
            summary=summary_text,
            changed_files=changed_files,
            fallback_reason=fallback_reason,
            ui_plan=ui_plan,
            ui_steps=ui_steps,
        )
    finally:
        # ISSUE-024：恢复常量 hints，避免污染后续任务或测试。
        UI_STEP_SELECTOR_HINTS.clear()
        UI_STEP_SELECTOR_HINTS.update(snapshot)
        # ISSUE-024：漂移审计（异步无副作用，失败仅 log warning）。
        try:
            audit_drift(
                generators_root=Path(__file__).resolve().parent,
                real_selectors=real_selectors,
                learnings_root=default_learnings_root(),
                issue_id="ISSUE-024",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("audit_drift failed: %s", exc)


def _enhance_readme(
    job: Dict[str, Any],
    planning: Dict[str, Any],
    project_root: Path,
    backup_root: Path,
    progress_callback: Optional[Callable[[Dict[str, str]], None]],
) -> Dict[str, Any]:
    """保留原有的 README.md 文档增强行为，独立 try/except 不影响 UI 子步骤。"""
    target = "README.md"
    status: Dict[str, Any] = {
        "changed": False,
        "summary": "",
        "failure": None,
        "model": None,
    }
    try:
        if progress_callback:
            progress_callback({
                "file": target,
                "step": "readme",
                "name": "项目说明",
                "status": "running",
            })
        response, model = _request_enhancement(
            planning,
            project_root,
            target,
            [],
        )
        _write_enhanced_file(project_root, response.files[0])
        status["changed"] = True
        status["summary"] = response.summary
        status["model"] = model
        if progress_callback:
            progress_callback({
                "file": target,
                "step": "readme",
                "name": "项目说明",
                "status": "completed",
                "summary": response.summary,
            })
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        status["failure"] = message
        _restore_one_file(project_root, backup_root, target)
        if progress_callback:
            progress_callback({
                "file": target,
                "step": "readme",
                "name": "项目说明",
                "status": "failed",
                "summary": message,
            })
    return status


def _emit_ui_step(
    progress_callback: Optional[Callable[[Dict[str, str]], None]],
    step: Dict[str, Any],
) -> None:
    if not progress_callback:
        return
    event: Dict[str, Any] = {
        "file": f"frontend/src/style.css::{step['step']}",
        "step": step["step"],
        "name": step.get("name") or UI_STEP_NAMES.get(step["step"], step["step"]),
        "status": step.get("status", "pending"),
    }
    for optional in ("summary", "attempts", "duration_ms", "failure_reason", "selectors"):
        if optional in step and step[optional] not in (None, ""):
            event[optional] = step[optional]
    progress_callback(event)


def _record_step(
    steps: List[Dict[str, Any]],
    step_key: str,
    **changes: Any,
) -> Dict[str, Any]:
    for item in steps:
        if item["step"] == step_key:
            item.update(changes)
            return item
    return {}


def _record_enhance_failure(
    job: Dict[str, Any],
    requested_mode: str,
    ui_steps: List[Dict[str, Any]],
    fallback_reason: Optional[str],
    *,
    issue_id: str = "ISSUE-023",
    issue_doc: Optional[str] = None,
) -> None:
    """ISSUE-022：把 enhance 阶段失败摘要写到 ``.learnings/``。

    ISSUE-024：``issue_id`` / ``issue_doc`` 由调用方传入相关 ISSUE 编号与文档路径。
    失败时只记录 warning，不影响主流程。
    """
    try:
        append_enhance_error(
            job_id=str(job.get("job_id") or "?"),
            requested_mode=requested_mode,
            ui_steps=ui_steps,
            fallback_reason=fallback_reason,
            issue_id=issue_id,
            issue_doc=issue_doc,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("append_enhance_error failed: %s", exc)


def _enhance_ui_steps(
    planning: Dict[str, Any],
    project_root: Path,
    backup_root: Path,
    progress_callback: Optional[Callable[[Dict[str, str]], None]],
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]], List[str]]:
    """分阶段执行 UI 增强，返回 (steps, ui_plan, changed_files)。

    每一步：
    - 独立调用 LLM（小请求 + 小响应）；
    - 独立超时与重试；
    - 写完后单独记录，失败只恢复该步骤；
    - 通过 ``progress_callback`` 推送 ``pending / running / retrying / completed / failed``。
    """
    steps: List[Dict[str, Any]] = [
        {
            "step": key,
            "name": name,
            "status": "pending",
            "summary": "",
            "attempts": 0,
            "duration_ms": 0,
            "failure_reason": None,
            "selectors": [],
        }
        for key, name in UI_ENHANCEMENT_STEPS
    ]

    base_url, api_key, model = _ui_credentials()
    timeout = _ui_step_timeout()

    for step in steps:
        _emit_ui_step(progress_callback, step)

    ui_plan_payload: Optional[Dict[str, Any]] = None
    tokens: Dict[str, str] = _local_ui_tokens(planning)

    def emit_request_retry(step_key: str, request_attempt: int, message: str) -> None:
        step = _record_step(
            steps,
            step_key,
            status="retrying",
            attempts=request_attempt,
            summary=message[:240],
        )
        _emit_ui_step(progress_callback, step)

    plan_start = time.monotonic()
    try:
        if progress_callback:
            progress_callback({
                "file": "frontend/src/style.css::theme",
                "step": "theme",
                "name": UI_STEP_NAMES["theme"],
                "status": "running",
            })
        plan, plan_error = _request_ui_plan(
            planning,
            timeout,
            model,
            api_key,
            base_url,
            retry_callback=lambda attempt, message: emit_request_retry(
                "theme", attempt, message
            ),
        )
        if plan is None:
            raise RuntimeError(plan_error or "界面风格方案请求失败")
        tokens = _resolve_tokens(planning, plan)
        ui_plan_payload = {
            "summary": plan.summary,
            "tokens": tokens,
            "notes": plan.notes,
            "model": model,
            "duration_ms": int((time.monotonic() - plan_start) * 1000),
            "fallback": False,
            "error": None,
        }
        _record_step(
            steps,
            "theme",
            status="completed",
            summary=plan.summary or "界面风格方案设计完成",
            duration_ms=ui_plan_payload["duration_ms"],
            attempts=1,
        )
        _emit_ui_step(progress_callback, steps[0])
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        ui_plan_payload = {
            "summary": "本地风格令牌兜底",
            "tokens": tokens,
            "notes": [],
            "model": None,
            "duration_ms": int((time.monotonic() - plan_start) * 1000),
            "fallback": True,
            "error": message,
        }
        _record_step(
            steps,
            "theme",
            status="failed",
            summary="本地风格令牌兜底",
            duration_ms=ui_plan_payload["duration_ms"],
            attempts=1,
            failure_reason=message,
        )
        _emit_ui_step(progress_callback, steps[0])
        # 风格方案失败不影响后续子步骤：本地令牌同样能让后续子步骤稳定

    # 备份原始 style.css（增强前的快照），用于最后回滚到完全没增强的状态
    _backup_one_file(project_root, backup_root, "frontend/src/style.css")
    backup_css = backup_root / "frontend" / "src" / "style.css"
    original_css = (
        backup_css.read_text(encoding="utf-8") if backup_css.exists() else ""
    )

    css_path = project_root / "frontend" / "src" / "style.css"
    changed_files: List[str] = []

    for index, step in enumerate(steps[1:], start=1):
        step_key = step["step"]
        step_name = step["name"]
        attempts = 0
        max_attempts = 1
        step_start = time.monotonic()
        # 每一步都从当前 style.css 读快照，失败回滚只撤销本步
        pre_step_snapshot = (
            css_path.read_text(encoding="utf-8") if css_path.exists() else ""
        )
        if progress_callback:
            _emit_ui_step(progress_callback, step)
        success = False
        last_error: Optional[str] = None
        while attempts < max_attempts:
            attempts += 1
            try:
                if progress_callback:
                    progress_callback({
                        "file": f"frontend/src/style.css::{step_key}",
                        "step": step_key,
                        "name": step_name,
                        "status": "running",
                        "attempts": attempts,
                    })
                response = _request_ui_step(
                    step_key,
                    step_name,
                    planning,
                    tokens,
                    project_root,
                    timeout,
                    model,
                    api_key,
                    base_url,
                    retry_callback=lambda request_attempt, message: emit_request_retry(
                        step_key, request_attempt, message
                    ),
                )
                # ISSUE-026：LLM 始终返回空 CSS 时，标 skipped 而非 failed。
                if response.block is None:
                    _record_step(
                        steps,
                        step_key,
                        status="skipped",
                        attempts=attempts,
                        duration_ms=int((time.monotonic() - step_start) * 1000),
                        summary=response.skip_reason or "LLM 返回内容无 CSS 规则",
                    )
                    _emit_ui_step(progress_callback, steps[index])
                    # 关键：skipped 也是"成功结束本步"，必须设 success=True，
                    # 否则下面 ``if not success:`` 会把 skipped 覆盖回 failed。
                    success = True
                    break
                _append_style_block(project_root, step_key, response.block)
                _record_step(
                    steps,
                    step_key,
                    status="completed",
                    summary=response.block.summary,
                    attempts=attempts,
                    duration_ms=int((time.monotonic() - step_start) * 1000),
                    selectors=list(response.block.selectors),
                )
                _emit_ui_step(progress_callback, steps[index])
                if "frontend/src/style.css" not in changed_files:
                    changed_files.append("frontend/src/style.css")
                success = True
                break
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                # 失败立即回滚到本步骤开始时的快照（只撤销本步，前序成功步骤保留）
                css_path.write_text(pre_step_snapshot, encoding="utf-8")
                if attempts < max_attempts:
                    retry_step = _record_step(
                        steps,
                        step_key,
                        status="retrying",
                        attempts=attempts,
                        summary=last_error,
                    )
                    _emit_ui_step(progress_callback, retry_step)
                    time.sleep(1.0)
                    continue
        if not success:
            _record_step(
                steps,
                step_key,
                status="failed",
                attempts=attempts,
                duration_ms=int((time.monotonic() - step_start) * 1000),
                failure_reason=last_error,
                summary=last_error or "UI 子步骤失败",
            )
            _emit_ui_step(progress_callback, steps[index])
            # 失败后必须保证 css 已回滚到本步骤开始前
            css_path.write_text(pre_step_snapshot, encoding="utf-8")

    # 全部完成后，如果 style.css 与 backup 完全一致则视为无变更
    if css_path.exists():
        try:
            current = css_path.read_text(encoding="utf-8")
        except OSError:
            current = ""
        if current.strip() == original_css.strip():
            changed_files = [item for item in changed_files if item != "frontend/src/style.css"]

    return steps, ui_plan_payload, changed_files
