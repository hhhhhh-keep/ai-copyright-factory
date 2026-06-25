"""ISSUE-024（P0-2）：从生成项目模板扫描"实际渲染的 CSS 选择器"。

背景
----
ISSUE-023 修复后，UI 子步骤白名单仍有"与生成器实际 class 失配"的盲区：
jobId=20260624095339-9d44c135 暴露 dashboard / responsive 步用了
``.kpi-grid`` / ``.dashboard-row`` 等生成器真实生成的 class，但白名单只列了
已废弃的 ``.metric-grid`` / ``.kpi-icon``。

本模块提供系统化的白名单来源：

- ``collect_real_selectors(project_root)`` 扫描生成项目的
  ``frontend/src/style.css`` 与 ``frontend/src/views/*.vue``，合并
  规则选择器与 ``class="..."`` 字面量。
- ``merge_with_hints(base_hints, real_selectors)`` 把运行时补充的 selectors
  合并入 hints（``base_hints`` 仍优先，以保留禁片保护）。
- ``audit_drift(...)`` 在 ``.learnings/`` 写漂移告警，便于 CI / 人工复审。

约束
----
- 仅扫描 ``generated_project/frontend/src/`` 下的文件；不扫 Vue 运行时注入的
  class（如 Element Plus BEM 派生），运行时 class 由 ``UI_STEP_SELECTOR_HINTS``
  中的 ``__*`` / ``--*`` 通配兜底。
- 漂移审计独立可选，``enhance_project`` 默认仅做合并，不强制要求生成器签名匹配。
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Optional, Set, Tuple


_VUE_CLASS_ATTR = re.compile(r"""class\s*=\s*["']([^"']+)["']""")
_CSS_RULE_HEADER = re.compile(r"([^{}]+)\{")


def collect_real_selectors(project_root: Path) -> Set[str]:
    """从生成项目模板收集真实使用的 CSS 选择器。

    扫描：
    - ``<root>/frontend/src/style.css`` 全部规则选择器（含 ``@media`` 嵌套）；
    - ``<root>/frontend/src/views/*.vue`` 内 ``class="..."`` 静态字面量；
    - ``<root>/frontend/src/App.vue``（壳层 class，可能被业务页引用）。

    剥离 CSS 注释与空白后做集合去重。返回小写、normalized 形式。
    """
    root = Path(project_root) / "frontend" / "src"
    if not root.exists():
        return set()

    selectors: Set[str] = set()

    style_css = root / "style.css"
    if style_css.exists():
        selectors.update(_extract_css_rule_selectors(style_css.read_text(encoding="utf-8", errors="ignore")))

    for vue_file in root.rglob("*.vue"):
        text = vue_file.read_text(encoding="utf-8", errors="ignore")
        for match in _VUE_CLASS_ATTR.finditer(text):
            for token in match.group(1).split():
                token = token.strip()
                if not token:
                    continue
                # 跳过动态绑定 :class="{ active: isActive }"
                if token.startswith(":") or token.startswith("v-"):
                    continue
                selectors.add(token.lower())

    return selectors


def _extract_css_rule_selectors(css_text: str) -> Iterable[str]:
    """从 CSS 文本提取全部规则选择器，跳过注释。"""
    no_comments = re.sub(r"/\*.*?\*/", "", css_text, flags=re.DOTALL)
    for match in _CSS_RULE_HEADER.finditer(no_comments):
        raw = match.group(1).strip()
        if not raw:
            continue
        for selector in raw.split(","):
            selector = selector.strip().lower()
            if selector:
                yield selector


def merge_with_hints(
    base_hints: Dict[str, Tuple[str, ...]],
    real_selectors: Set[str],
) -> Dict[str, Tuple[str, ...]]:
    """把运行时收集的真实 selectors 合并入 hints。

    合并规则：
    - 保留 ``base_hints`` 的全部原值（常数 + 禁片 + 通配仍由常量控制）；
    - 把不在 ``base_hints[step_key]`` 里的 selectors 按"通用基础选择器"启发式
      追加到对应步：
      - 包含 ``shell`` / ``login`` / ``hero`` / ``page-heading`` 等关键字 → ``shell`` 步；
      - 包含 ``kpi`` / ``dashboard`` / ``trend`` / ``donut`` / ``bar-svg`` 等关键字 → ``dashboard`` 步；
      - 包含 ``el-card`` / ``el-button`` / ``el-table`` / ``el-tag`` / ``el-form`` / ``el-dialog`` / ``el-input``
        / ``module-page`` / ``toolbar`` / ``filter-bar`` / ``status-pill`` → ``business`` 步；
      - 包含 ``shell-split`` / ``shell-main`` / ``shell-top`` / ``shell-aside`` 且包含 ``max-width``
        或媒体查询 → ``responsive`` 步；否则进 ``shell`` 步；
      - 其它未识别 selector 不进 hints（避免 LLM 误把运行时类当业务类）。
    """
    if not real_selectors:
        return base_hints

    buckets: Dict[str, list] = {key: list(values) for key, values in base_hints.items()}

    business_keywords = (
        "el-card", "el-button", "el-table", "el-tag", "el-form",
        "el-dialog", "el-input", "el-pagination", "el-checkbox",
        "el-radio", "el-select", "el-tooltip", "el-message",
        "el-popover", "el-dropdown", "el-menu", "el-upload", "el-tabs",
        "module-page", "toolbar", "filter-bar", "status-pill",
        "master-detail", "tree-detail", "kanban",
        "btn-primary", "btn-ghost", "btn-default", "btn-danger",
        "module-", "task-", "form-",
    )
    dashboard_keywords = (
        "kpi", "dashboard", "trend", "donut", "bar-svg", "donut-svg",
        "trend-svg", "metric-grid", "activity-panel", "status-panel",
        "m-", "pattern-", "stat-", "metric-",
    )
    shell_keywords = (
        "shell-top", "shell-aside", "shell-split", "shell-main",
        "login-page", "login-brand", "login-card", "hero", "page-heading",
        "context-panel", "el-header", "el-aside",
    )
    responsive_keywords = (
        "@media", "max-width", "min-width",
        "page-heading", "actions",
    )

    for selector in real_selectors:
        if any(selector in step_hint or selector.startswith(step_hint.rstrip("*"))
               for step_hint in base_hints.get("theme", ())):
            continue
        target = _classify_selector(
            selector, business_keywords, dashboard_keywords, shell_keywords, responsive_keywords
        )
        if target is None:
            continue
        if selector not in buckets[target]:
            buckets[target].append(selector)

    return {key: tuple(values) for key, values in buckets.items()}


def _classify_selector(
    selector: str,
    business_keywords: Tuple[str, ...],
    dashboard_keywords: Tuple[str, ...],
    shell_keywords: Tuple[str, ...],
    responsive_keywords: Tuple[str, ...],
) -> Optional[str]:
    """启发式分类 selector 到对应 UI 步。返回 None 表示不归入任何步。"""
    lowered = selector.lower()
    if lowered.startswith("@media") or any(kw in lowered for kw in responsive_keywords):
        return "responsive"
    if any(kw in lowered for kw in dashboard_keywords):
        return "dashboard"
    if any(kw in lowered for kw in business_keywords):
        return "business"
    if any(kw in lowered for kw in shell_keywords):
        return "shell"
    return None


def audit_drift(
    generators_root: Path,
    real_selectors: Set[str],
    learnings_root: Path,
    *,
    issue_id: str = "ISSUE-024",
) -> Optional[Path]:
    """在 ``.learnings/`` 写漂移审计报告。

    仅当 ``project_generator.py`` / 生成产物与 ``UI_STEP_SELECTOR_HINTS``
    存在差集时落盘；目录缺失则静默跳过。
    """
    if not learnings_root.exists():
        return None

    from app.enhancer import UI_STEP_SELECTOR_HINTS  # 局部导入避免循环

    base_union: Set[str] = set()
    for values in UI_STEP_SELECTOR_HINTS.values():
        base_union.update(values)
    base_union.update(["html", "*", "@media"])

    missing_in_hints = sorted(
        sel for sel in real_selectors
        if not any(sel.startswith(base.rstrip("*")) for base in base_union)
        and not any(_match_wildcard(sel, base) for base in base_union)
    )

    generator_path = generators_root / "project_generator.py"
    generator_hash = ""
    if generator_path.exists():
        generator_hash = hashlib.sha1(
            generator_path.read_bytes()
        ).hexdigest()[:12]

    today = datetime.now().strftime("%Y%m%d")
    target = learnings_root / f"ERRORS-{today}-selector-drift.md"
    header = (
        f"\n\n## {issue_id} 选择器漂移审计 · generator_sha1={generator_hash}\n\n"
        f"- 真实选择器数量：{len(real_selectors)}\n"
        f"- 未命中白名单基线的 selector（前 30 个）："
    )
    body = "\n".join(f"  - `{sel}`" for sel in missing_in_hints[:30]) or "  - （无）"
    if not missing_in_hints:
        return None
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    if not existing.endswith("\n"):
        existing += "\n"
    target.write_text(existing + header + "\n" + body + "\n", encoding="utf-8")
    return target


def _match_wildcard(selector: str, base: str) -> bool:
    """``base`` 末尾为 ``*`` 时做前缀匹配。"""
    if not base.endswith("*"):
        return False
    prefix = base[:-1]
    return bool(prefix) and selector.startswith(prefix)


__all__ = [
    "collect_real_selectors",
    "merge_with_hints",
    "audit_drift",
]
