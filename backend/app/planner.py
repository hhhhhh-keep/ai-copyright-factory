"""软件规划器。

ISSUE-007 实施后，Planner 完全由 LLM 驱动：

- 只读取软件名称、类型、描述和行业名称；行业仅作为普通上下文，不再约束模块范围。
- 不再读取 `industry_knowledge/`，不再做行业一致性校验。
- 不再有 `auto/llm/template` 模式与模板回退。
- 首次 JSON 解析或 Pydantic 校验失败时，自动将错误摘要和原响应发回模型请求修复一次。
- 二次仍失败或 API 调用失败时，抛出原始错误，调用方将任务置为 `failed`，由用户重试。
- `propose_revision()` 同步改为 LLM-only，使用相同的 JSON 容错和一次自动修复。
"""

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, model_validator


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


PagePattern = Literal[
    "table_crud",
    "master_detail",
    "tree_detail",
    "workflow_timeline",
    "kanban",
    "dashboard",
]
ShellPattern = Literal["sidebar_admin", "top_workspace", "split_console"]


class PlannerValidationError(ValueError):
    """规划两次校验失败时携带 LLM 原始响应，供 workflow 落盘诊断。"""

    def __init__(
        self,
        message: str,
        *,
        first_text: str = "",
        second_text: str = "",
        first_error: str = "",
        second_error: str = "",
    ) -> None:
        super().__init__(message)
        self.first_text = first_text
        self.second_text = second_text
        self.first_error = first_error
        self.second_error = second_error


class UIPlan(BaseModel):
    shell: ShellPattern = "sidebar_admin"
    home_pattern: Literal["metric_dashboard", "task_dashboard", "analysis_dashboard"] = (
        "metric_dashboard"
    )
    navigation: Literal["side", "top", "split"] = "side"
    density: Literal["compact", "standard", "comfortable"] = "standard"


class ModulePlan(BaseModel):
    key: str = Field(min_length=2, max_length=40, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=2, max_length=30)
    description: str = Field(default="", max_length=300)
    pages: List[str] = Field(min_length=1, max_length=8)
    fields: List[str] = Field(min_length=2, max_length=20)
    page_pattern: PagePattern = "table_crud"
    detail_pattern: PagePattern = "master_detail"
    edit_pattern: Literal["dialog", "drawer", "form_wizard"] = "dialog"

    @field_validator("pages", "fields")
    @classmethod
    def unique_text_items(cls, value: List[str]) -> List[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        return list(dict.fromkeys(cleaned))


class Planning(BaseModel):
    software_name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=5, max_length=1000)
    software_type: str = Field(min_length=2, max_length=50)
    industry_type: str = Field(default="", max_length=40)
    industry_name: str = Field(default="", max_length=30)
    target_users: str = Field(default="系统业务管理人员", min_length=2, max_length=200)
    ui_plan: UIPlan = Field(default_factory=UIPlan)
    modules: List[ModulePlan] = Field(min_length=3, max_length=8)
    database_tables: List[str] = Field(min_length=1, max_length=12)
    api_list: List[str] = Field(min_length=1, max_length=30)
    screenshots: List[str] = Field(min_length=3, max_length=20)
    document_outline: List[str] = Field(min_length=3, max_length=12)

    @field_validator("database_tables")
    @classmethod
    def valid_database_tables(cls, value: List[str]) -> List[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("数据库表名称不能重复")
        for item in cleaned:
            if not re.fullmatch(r"[a-z][a-z0-9_]{1,39}", item):
                raise ValueError(f"数据库表名称不合法: {item}")
        return cleaned

    @field_validator("modules")
    @classmethod
    def unique_module_keys(cls, value: List[ModulePlan]) -> List[ModulePlan]:
        keys = [item.key for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("模块 key 必须唯一")
        return value

    @model_validator(mode="after")
    def tables_match_modules(self) -> "Planning":
        if len(self.database_tables) != len(self.modules):
            raise ValueError("每个功能模块必须对应一个数据库表")
        return self


class PlannerResult(BaseModel):
    planning: Planning
    model: Optional[str] = None


class RevisionResult(BaseModel):
    planning: Planning
    summary: str
    model: Optional[str] = None


# ---------- 行业基础映射（仅 key -> 显示名，不含知识库） ----------

INDUSTRY_DISPLAY_NAMES = {
    "public_security": "公安",
    "justice": "政法",
    "industry": "工业",
    "education": "教育",
}


def industry_name_for(key: str) -> str:
    """根据行业内部编码返回显示名。找不到时返回空串。"""
    if not key:
        return ""
    return INDUSTRY_DISPLAY_NAMES.get(key, "")


# ---------- Schema example and messages ----------


def _schema_example() -> Dict[str, Any]:
    return {
        "software_name": "示例管理系统",
        "description": "系统用途和业务范围说明",
        "software_type": "管理系统",
        "target_users": "业务管理人员",
        "ui_plan": {
            "shell": "top_workspace",
            "home_pattern": "task_dashboard",
            "navigation": "top",
            "density": "standard",
        },
        "modules": [
            {
                "key": "items",
                "name": "信息管理",
                "description": "维护核心业务信息",
                "pages": ["信息列表", "信息新增"],
                "fields": ["名称", "分类", "状态", "更新时间"],
                "page_pattern": "master_detail",
                "detail_pattern": "workflow_timeline",
                "edit_pattern": "drawer",
            },
            {
                "key": "records",
                "name": "记录管理",
                "description": "查询和管理业务操作记录",
                "pages": ["记录列表", "记录详情"],
                "fields": ["记录编号", "操作人", "操作时间", "结果"],
                "page_pattern": "workflow_timeline",
                "detail_pattern": "master_detail",
                "edit_pattern": "form_wizard",
            },
            {
                "key": "reports",
                "name": "统计分析",
                "description": "展示核心业务指标和趋势",
                "pages": ["数据概览", "趋势统计"],
                "fields": ["统计日期", "业务数量", "完成率", "同比变化"],
                "page_pattern": "dashboard",
                "detail_pattern": "master_detail",
                "edit_pattern": "dialog",
            },
        ],
        "database_tables": ["items", "records", "reports"],
        "api_list": ["GET /api/items", "POST /api/items", "GET /api/reports"],
        "screenshots": ["登录页", "首页", "信息管理", "统计分析"],
        "document_outline": ["项目概述", "总体设计", "功能设计", "数据设计"],
    }


def _industry_hint_text(job: Dict[str, Any]) -> str:
    """根据 job 中的行业信息生成"行业参考"提示文本。

    优先使用 job['industry_name']，否则用行业内部编码查 INDUSTRY_DISPLAY_NAMES。
    最终传给模型的始终是显示名（如"公安"），不是内部编码（如"public_security"）。
    """
    code = job.get("industry_type") or ""
    name = job.get("industry_name") or industry_name_for(code) or ""
    if not name:
        return ""
    return f"行业参考：{name}（仅作为业务背景，不限制模块范围）\n"


def _initial_messages(job: Dict[str, Any]) -> List[Dict[str, str]]:
    system = (
        "你是软件产品规划器。直接根据用户提供的软件名称、软件类型和软件描述，"
        "输出一个结构化的软件规划 JSON 对象。\n"
        "- 行业字段仅作为普通参考信息，禁止把行业关键词当作模块白名单。\n"
        "- modules 数量为 3 到 8；每个模块 key 使用小写英文 snake_case 且唯一。\n"
        "- database_tables 必须与 modules 数量相同、顺序一致；每个模块对应一个 snake_case 数据库表名。\n"
        "- 每个模块包含 1 到 8 个 pages；fields 建议 6 到 12 个，最多 20 个。\n"
        "- 每个模块必须提供 description；必须提供 target_users。\n"
        "- screenshots 只能引用登录页、首页或 modules 中存在的模块。\n"
        "- 必须生成 ui_plan；每个模块必须选择 page_pattern、detail_pattern 和 edit_pattern。\n"
        "- 同一规划至少使用两种 page_pattern，不能把全部模块都生成为 table_crud。\n"
        "- 只输出一个合法 JSON 对象，不要 Markdown 围栏、不要解释、不要尾随说明。"
    )
    industry_hint = _industry_hint_text(job)
    user = (
        "请为以下软件生成结构化规划。\n"
        f"软件名称：{job['software_name']}\n"
        f"软件描述：{job.get('description') or '未提供，请根据软件名称做最小合理规划'}\n"
        f"软件类型：{job.get('software_type') or '管理系统'}\n"
        f"{industry_hint}"
        "输出 JSON 结构参考：\n"
        + json.dumps(_schema_example(), ensure_ascii=False)
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _repair_messages(
    job: Dict[str, Any],
    original_text: str,
    error_text: str,
) -> List[Dict[str, str]]:
    system = (
        "你之前的输出无法被解析或不符合目标 JSON schema。"
        "请重新输出一个严格符合目标 schema 的合法 JSON 对象。"
        "特别注意：database_tables 必须与 modules 数量相同、顺序一致，"
        "每个模块对应一个合法且不重复的 snake_case 数据库表名。"
        "只输出 JSON 本身，不要 Markdown 围栏、不要解释、不要尾随说明。"
    )
    industry_hint = _industry_hint_text(job)
    user = (
        f"软件名称：{job['software_name']}\n"
        f"软件描述：{job.get('description') or '未提供'}\n"
        f"软件类型：{job.get('software_type') or '管理系统'}\n"
        f"{industry_hint}\n"
        "你之前的原始输出：\n"
        f"{original_text}\n\n"
        "解析/校验错误摘要：\n"
        f"{error_text}\n\n"
        "目标 JSON 结构参考：\n"
        + json.dumps(_schema_example(), ensure_ascii=False)
        + "\n\n请重新输出符合 schema 的 JSON 对象。"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _revision_messages(
    job: Dict[str, Any],
    current: Dict[str, Any],
    instruction: str,
) -> List[Dict[str, str]]:
    system = (
        "你是软件规划修改助手。根据当前规划和用户意见，输出 JSON："
        "summary 为修改摘要，planning 为修改后的完整规划。"
        "只输出 JSON 本身，不要 Markdown 围栏、不要解释。"
        "行业字段仅作为业务背景，禁止把行业当作模块白名单。"
        "不得输出源码。"
    )
    industry_hint = _industry_hint_text(job)
    user = json.dumps(
        {
            "instruction": instruction,
            "current_planning": current,
            "industry_hint": industry_hint.strip(),
            "schema": _schema_example(),
        },
        ensure_ascii=False,
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# ---------- 用户输入字段强制恢复 ----------


def _restore_user_input_fields(planning: Planning, job: Dict[str, Any]) -> Planning:
    """强制恢复用户输入的任务基本信息，避免 LLM 篡改。

    覆盖字段：software_name、description（若用户提供）、software_type（若用户提供）、
    industry_type、industry_name（按内部编码查显示名）。
    propose_revision 入口不调用本函数，因为它代表用户主动的"重命名/换行业"操作。
    """
    planning.software_name = job["software_name"]
    description = job.get("description")
    if description is not None and description.strip():
        planning.description = description
    software_type = job.get("software_type")
    if software_type is not None and software_type.strip():
        planning.software_type = software_type
    industry_code = job.get("industry_type") or ""
    if industry_code:
        planning.industry_type = industry_code
        planning.industry_name = industry_name_for(industry_code)
    elif job.get("industry_name"):
        planning.industry_name = job["industry_name"]
    return planning


# ---------- 结构规范化 ----------


def _safe_table_name(name: str) -> str:
    table = re.sub(r"[^a-z0-9_]+", "_", (name or "").strip().lower())
    table = re.sub(r"_+", "_", table).strip("_")
    if not table or not re.match(r"^[a-z]", table):
        table = f"t_{table}" if table else "module_table"
    table = table[:40].rstrip("_")
    if len(table) < 2:
        table = f"{table}_table"
    return table


def _unique_table_name(base: str, used: Set[str]) -> str:
    table = _safe_table_name(base)
    if table not in used:
        used.add(table)
        return table
    suffix = 2
    while True:
        suffix_text = f"_{suffix}"
        candidate = f"{table[:40 - len(suffix_text)]}{suffix_text}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        suffix += 1


def _normalize_database_tables(raw: Dict[str, Any]) -> Dict[str, Any]:
    """按 modules 规范化 database_tables，降低 LLM 少表/多表导致的失败率。

    规则：
    - 模块缺表时，按模块 key 补齐。
    - 表多于模块时，按模块数量截断。
    - 表名非法或重复时，规范化为合法且唯一的 snake_case。
    - 表顺序始终与 modules 顺序一致。
    """
    if not isinstance(raw, dict):
        return raw
    modules = raw.get("modules")
    if not isinstance(modules, list) or not modules:
        return raw
    source_tables = raw.get("database_tables")
    if not isinstance(source_tables, list):
        source_tables = []

    normalized: List[str] = []
    used: Set[str] = set()
    for index, module in enumerate(modules):
        module_key = ""
        if isinstance(module, dict):
            module_key = str(module.get("key") or "")
        candidate = ""
        if index < len(source_tables):
            candidate = str(source_tables[index] or "")
        if not candidate.strip():
            candidate = module_key or f"module_{index + 1}"
        normalized.append(_unique_table_name(candidate, used))

    raw["database_tables"] = normalized
    return raw


# ---------- JSON 容错 ----------


def _strip_code_fence(text: str) -> str:
    content = text.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content, count=1)
        content = re.sub(r"\s*```\s*$", "", content, count=1)
    return content.strip()


def _first_json_object(text: str) -> str:
    """从包含前后说明或多个对象的文本中提取首个完整 JSON 对象。

    规则：
    1. 先去掉代码围栏。
    2. 找出所有顶层 `{` 起点，对每个起点匹配对应的 `}`，得到候选子串。
    3. 逐个 `json.loads` 验证，验证通过的第一个就是返回结果。
    4. 字符串字面量内的引号和括号不被算作边界。
    """
    stripped = _strip_code_fence(text)
    if stripped.startswith("{") and stripped.endswith("}"):
        # 快速路径：去除空白后看起来就是单对象，先做一次 JSON 校验
        try:
            json.loads(stripped)
            return stripped
        except json.JSONDecodeError:
            pass  # 走到下面的候选匹配

    # 收集所有顶层 `{` 起点（不在字符串内的 `{`）
    in_string = False
    escape = False
    candidates: List[int] = []
    for index, char in enumerate(stripped):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            candidates.append(index)
        elif char == "}":
            # 顶级 `}` 不是起点；忽略即可
            continue

    # 对每个起点，从起点开始寻找与之配对的 `}` 并尝试解析
    for start in candidates:
        in_string = False
        escape = False
        depth = 0
        for index in range(start, len(stripped)):
            char = stripped[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidate = stripped[start : index + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        # 该起点不是合法 JSON，跳到下一个起点
                        break
        # 配对失败或解析失败，继续下一个起点

    raise ValueError("模型响应中没有合法 JSON 对象")


def _extract_json(text: str) -> Dict[str, Any]:
    content = _first_json_object(text)
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 解析失败: {exc.msg}（位置 {exc.lineno}:{exc.colno}）") from exc
    if not isinstance(value, dict):
        raise ValueError("模型响应必须是 JSON 对象")
    return value


# ---------- LLM 调用 ----------


def _planner_endpoint() -> Tuple[str, str, str, int]:
    base_url = os.getenv("AI_PLANNER_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    api_key = os.getenv("AI_PLANNER_API_KEY", "").strip()
    model = os.getenv("AI_PLANNER_MODEL", "").strip()
    timeout = int(os.getenv("AI_PLANNER_TIMEOUT", "60"))
    if not api_key:
        raise RuntimeError("未配置 AI_PLANNER_API_KEY")
    if not model:
        raise RuntimeError("未配置 AI_PLANNER_MODEL")
    return f"{base_url}/chat/completions", api_key, model, timeout


def _post_chat_completion(messages: List[Dict[str, str]], temperature: float) -> str:
    url, api_key, model, timeout = _planner_endpoint()
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        url,
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
        raise RuntimeError(f"Planner API 返回 HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Planner API 连接失败: {exc.reason}") from exc
    try:
        return response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Planner API 响应缺少 choices[0].message.content") from exc


def _parse_and_validate(text: str) -> Planning:
    raw = _extract_json(text)
    raw = _normalize_database_tables(raw)
    return Planning.model_validate(raw)


# ---------- 单次规划 + 一次自动修复 ----------


def _generate_with_repair(
    job: Dict[str, Any],
    messages_for: Any,
    postprocess: Any,
    temperature: float,
) -> Tuple[Planning, str]:
    """统一封装：先按 messages_for(job) 调用一次，失败自动修复一次。

    `messages_for`: 可调用对象，接收一个 (job, payload) 元组返回消息列表。
    `postprocess`: 接收 (planning, payload) 并返回最终结果对象（用于 revision/initial 不同返回类型）。
    `temperature`: 浮点温度。

    抛出原始错误时把任务交给调用方处理。
    """
    initial_messages = messages_for(job)
    model_name = os.getenv("AI_PLANNER_MODEL", "").strip() or None
    try:
        first_text = _post_chat_completion(initial_messages, temperature)
    except Exception:
        # API 调用失败不进入修复路径，直接抛出
        raise
    try:
        planning = _parse_and_validate(first_text)
        return postprocess(planning, first_text), model_name
    except Exception as first_exc:
        first_error = f"{type(first_exc).__name__}: {first_exc}"
        # 修复阶段：把错误摘要、原响应和目标 schema 一起发给模型
        repair_messages = _repair_messages(job, first_text, first_error)
        second_text = _post_chat_completion(repair_messages, temperature)
        try:
            planning = _parse_and_validate(second_text)
            return postprocess(planning, second_text), model_name
        except Exception as second_exc:
            second_error = f"{type(second_exc).__name__}: {second_exc}"
            raise PlannerValidationError(
                second_error,
                first_text=first_text,
                second_text=second_text,
                first_error=first_error,
                second_error=second_error,
            ) from second_exc


def _build_planning_result(planning: Planning, _text: str) -> Planning:
    return planning


def build_planning(job: Dict[str, Any]) -> PlannerResult:
    """仅走 LLM 路径；失败抛错，调用方负责把任务置为 failed。

    无论 LLM 返回什么，最终都会用用户的原始输入（software_name / description /
    software_type / industry_type / industry_name）覆盖 planning 中对应字段，
    防止模型篡改任务基本信息。`propose_revision` 不走此覆盖，因为它代表用户
    主动的"重命名/换行业"操作。
    """
    planning, model_name = _generate_with_repair(
        job=job,
        messages_for=_initial_messages,
        postprocess=_build_planning_result,
        temperature=0.2,
    )
    planning = _restore_user_input_fields(planning, job)
    return PlannerResult(planning=planning, model=model_name)


# ---------- 返工：LLM-only + 一次自动修复 ----------


def _build_revision_payload(planning: Planning, text: str) -> Dict[str, Any]:
    try:
        payload = _extract_json(text)
    except Exception:
        # 修复路径下 second_text 也可能不是 JSON；统一转交
        raise
    if not isinstance(payload, dict) or "planning" not in payload:
        raise ValueError("返工响应必须包含 planning 字段")
    return payload


def propose_revision(
    job: Dict[str, Any],
    current: Dict[str, Any],
    instruction: str,
) -> RevisionResult:
    """对话式返工：仅 LLM，失败抛错，不回退到规则改写。"""
    initial_messages = _revision_messages(job, current, instruction)
    model_name = os.getenv("AI_PLANNER_MODEL", "").strip() or None
    try:
        first_text = _post_chat_completion(initial_messages, 0.1)
    except Exception:
        raise
    try:
        payload = _extract_json(first_text)
        if not isinstance(payload, dict) or "planning" not in payload:
            raise ValueError("返工响应必须包含 planning 字段")
        planning = Planning.model_validate(payload["planning"])
        return RevisionResult(
            planning=planning,
            summary=str(payload.get("summary") or instruction),
            model=model_name,
        )
    except Exception as first_exc:
        first_error = f"{type(first_exc).__name__}: {first_exc}"
        # 修复提示里把当前规划和用户意见一起带上
        repair_system = (
            "你之前的返工输出无法被解析或不符合目标 JSON schema。"
            "请重新输出一个严格符合 schema 的 JSON 对象，"
            "其中 planning 字段为修改后的完整规划，summary 字段为修改摘要。"
            "只输出 JSON 本身，不要 Markdown 围栏、不要解释。"
        )
        repair_user = json.dumps(
            {
                "instruction": instruction,
                "current_planning": current,
                "previous_output": first_text,
                "error": first_error,
                "schema": _schema_example(),
            },
            ensure_ascii=False,
        )
        second_text = _post_chat_completion(
            [
                {"role": "system", "content": repair_system},
                {"role": "user", "content": repair_user},
            ],
            0.1,
        )
        payload = _extract_json(second_text)
        if not isinstance(payload, dict) or "planning" not in payload:
            raise ValueError("返工修复响应必须包含 planning 字段")
        planning = Planning.model_validate(payload["planning"])
        return RevisionResult(
            planning=planning,
            summary=str(payload.get("summary") or instruction),
            model=model_name,
        )
