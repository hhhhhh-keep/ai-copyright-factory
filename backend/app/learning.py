"""ISSUE-022：enhance 阶段失败自动写入 ``.learnings/``。

约定
----
- 文件名 ``ERRORS-YYYYMMDD-enhance.md``，每个失败任务追加一个 ``### ERR-YYYYMMDD-NNN`` 条目。
- 失败根因分类：``empty_selectors`` / ``whitelist_strict`` / ``size_exceeded`` /
  ``daemon_ssl_read_timeout`` / ``missing_credentials`` / ``api_http_error`` / ``other`` / ``unknown``。
- ``.learnings/`` 目录缺失时静默跳过（避免创建意外目录污染仓库）。
- 编号从已存在文件的 ``ERR-YYYYMMDD-NNN`` 累计，跨会话保持单调。
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_FAILURE_CLASSIFICATIONS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"未包含可校验的 CSS 选择器"), "empty_selectors"),
    (re.compile(r"未授权选择器"), "whitelist_strict"),
    (re.compile(r"string_too_long"), "size_exceeded"),
    (re.compile(r"read timed out"), "daemon_ssl_read_timeout"),
    (re.compile(r"未配置 AI"), "missing_credentials"),
    (re.compile(r"HTTP \d+"), "api_http_error"),
]


def classify_failure(failure_reason: Optional[str]) -> str:
    """根据 failure_reason 文本前缀做根因分类。"""
    if not failure_reason:
        return "unknown"
    for pattern, label in _FAILURE_CLASSIFICATIONS:
        if pattern.search(failure_reason):
            return label
    return "other"


def default_learnings_root(backend_dir: Optional[Path] = None) -> Path:
    """``backend/app/learning.py`` → 仓库根 → ``.learnings/``。"""
    base = backend_dir or Path(__file__).resolve().parent
    return base.parent.parent / ".learnings"


def append_enhance_error(
    job_id: str,
    requested_mode: str,
    ui_steps: List[Dict[str, Any]],
    fallback_reason: Optional[str],
    learnings_root: Optional[Path] = None,
    *,
    issue_id: str = "ISSUE-023",
    issue_doc: Optional[str] = None,
) -> Optional[Path]:
    """若 ``ui_steps`` 中存在 failed 步，把摘要追加到 ``.learnings/ERRORS-YYYYMMDD-enhance.md``。

    ISSUE-024：``issue_id`` 与 ``issue_doc`` 由调用方传入相关 ISSUE 编号与文档路径，
    不再硬编码 ``../docs/ISSUE-022.md``（该 ISSUE 实际是截图抓拍时机）。

    返回写入的文件路径；无失败步或目录缺失则返回 ``None``。
    """
    failed_steps = [item for item in ui_steps if item.get("status") == "failed"]
    if not failed_steps:
        return None

    root = learnings_root if learnings_root is not None else default_learnings_root()
    if not root.exists():
        return None

    today = datetime.now().strftime("%Y%m%d")
    target = root / f"ERRORS-{today}-enhance.md"

    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    nums = [int(m) for m in re.findall(r"ERR-\d{8}-(\d{3})", existing)]
    next_num = (max(nums) + 1) if nums else 1

    err_id = f"ERR-{today}-{next_num:03d}"

    classifications: Dict[str, List[str]] = {}
    for item in failed_steps:
        reason = item.get("failure_reason") or ""
        cls = classify_failure(reason)
        classifications.setdefault(cls, []).append(str(item.get("step") or "?"))

    classification_line = "；".join(
        f"{cls}({', '.join(steps)})" for cls, steps in classifications.items()
    )

    issue_link = (
        f"[{issue_id}.md](../docs/{issue_doc or (issue_id.lower() + '.md')})"
    )
    snippet = (
        "\n"
        f"### {err_id} · jobId={job_id} · codegen_mode={requested_mode}\n"
        f"- 失败子步骤：{', '.join(item['step'] for item in failed_steps)}\n"
        f"- 根因分类：{classification_line}\n"
        f"- fallback_reason：{(fallback_reason or '(无)')[:240]}\n"
        f"- 修复建议：见 {issue_link}\n"
    )

    if existing and not existing.endswith("\n"):
        existing = existing + "\n"
    target.write_text(existing + snippet, encoding="utf-8")
    return target
