import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

from .industry_knowledge import planning_context


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


class ModulePlan(BaseModel):
    key: str = Field(min_length=2, max_length=40, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=2, max_length=30)
    description: str = Field(default="", max_length=300)
    pages: List[str] = Field(min_length=1, max_length=8)
    fields: List[str] = Field(min_length=2, max_length=12)

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


class PlannerResult(BaseModel):
    planning: Planning
    requested_mode: Literal["template", "llm", "auto"]
    actual_mode: Literal["template", "llm"]
    model: Optional[str] = None
    fallback_reason: Optional[str] = None


def validate_planning_against_context(
    planning: Planning,
    context: Dict[str, Any],
    require_all_modules: bool = False,
) -> None:
    allowed_keys = set(context["allowed_module_keys"])
    actual_keys = {module.key for module in planning.modules}
    if not actual_keys.issubset(allowed_keys) or (
        require_all_modules and actual_keys != allowed_keys
    ):
        missing = ", ".join(sorted(allowed_keys - actual_keys))
        invalid = ", ".join(sorted(actual_keys - allowed_keys))
        details = []
        if missing:
            details.append(f"缺少已确认模块: {missing}")
        if invalid:
            details.append(f"包含未确认模块: {invalid}")
        raise ValueError("；".join(details))

    source_modules = {module["key"]: module for module in context["modules"]}
    allowed_tables = {
        module["table"]
        for module in context["modules"]
        if module["key"] in actual_keys
    }
    if set(planning.database_tables) != allowed_tables:
        raise ValueError("数据库表必须与当前行业模块一致")
    for module in planning.modules:
        source = source_modules[module.key]
        if not set(module.pages).issubset(set(source["pages"])):
            raise ValueError(f"模块 {module.key} 包含知识库之外的页面")
        if not set(module.fields).issubset(set(source["fields"])):
            raise ValueError(f"模块 {module.key} 包含知识库之外的字段")


def template_planning(job: Dict[str, Any]) -> Planning:
    context = planning_context(job)
    industry = context["industry"]
    modules = context["modules"]
    return Planning.model_validate(
        {
            "software_name": job["software_name"],
            "description": job["description"]
            or f"面向{industry['name']}行业的业务管理、过程跟踪和统计分析平台",
            "software_type": job["software_type"],
            "industry_type": industry["key"],
            "industry_name": industry["name"],
            "target_users": industry["target_users"],
            "modules": [
                {
                    key: value
                    for key, value in module.items()
                    if key in {"key", "name", "description", "pages", "fields"}
                }
                for module in modules
            ],
            "database_tables": [module["table"] for module in modules],
            "api_list": [
                route
                for module in modules
                for route in (
                    f"GET /api/{module['key']}",
                    f"POST /api/{module['key']}",
                    f"PUT /api/{module['key']}/{{id}}",
                    f"DELETE /api/{module['key']}/{{id}}",
                )
            ],
            "screenshots": ["登录页", "首页"] + [module["name"] for module in modules],
            "document_outline": [
                "系统概述",
                "总体架构",
                "功能设计",
                "数据库设计",
                "接口设计",
                "部署说明",
                "页面说明",
            ],
        }
    )


def _schema_example() -> Dict[str, Any]:
    return {
        "software_name": "示例管理系统",
        "description": "系统用途和业务范围说明",
        "software_type": "管理系统",
        "target_users": "业务管理人员",
        "modules": [
            {
                "key": "items",
                "name": "信息管理",
                "description": "维护核心业务信息",
                "pages": ["信息列表", "信息新增"],
                "fields": ["名称", "分类", "状态", "更新时间"],
            },
            {
                "key": "records",
                "name": "记录管理",
                "description": "查询和管理业务操作记录",
                "pages": ["记录列表", "记录详情"],
                "fields": ["记录编号", "操作人", "操作时间", "结果"],
            },
            {
                "key": "reports",
                "name": "统计分析",
                "description": "展示核心业务指标和趋势",
                "pages": ["数据概览", "趋势统计"],
                "fields": ["统计日期", "业务数量", "完成率", "同比变化"],
            },
        ],
        "database_tables": ["items", "records"],
        "api_list": ["GET /api/items", "POST /api/items", "GET /api/reports"],
        "screenshots": ["登录页", "首页", "信息管理", "统计分析"],
        "document_outline": ["项目概述", "总体设计", "功能设计", "数据设计"],
    }


def _messages(job: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, str]]:
    industry = context["industry"]
    modules = context["modules"]
    system = (
        "你是软件产品规划器。只输出一个合法 JSON 对象，不要 Markdown、解释或代码围栏。"
        "规划必须严格基于提供的行业知识库，不得增加知识库之外的模块、页面、字段或数据表。"
        "modules 数量为 3 到 8；每个模块 key 使用小写英文 snake_case 且唯一；"
        "每个模块包含 1 到 8 个 pages、2 到 12 个 fields。"
        "每个模块必须提供 description；必须提供 target_users。"
        "screenshots 只能引用登录页、首页或 modules 中存在的模块。"
    )
    user = (
        "请为以下软件生成结构化规划。\n"
        f"软件名称：{job['software_name']}\n"
        f"软件描述：{job.get('description') or '未提供，请根据软件名称做最小合理规划'}\n"
        f"软件类型：{job.get('software_type') or '管理系统'}\n"
        f"行业：{industry['name']}（{industry['key']}）\n"
        "允许使用的行业知识库：\n"
        + json.dumps(
            {
                "terms": industry["terms"],
                "target_users": industry["target_users"],
                "modules": modules,
            },
            ensure_ascii=False,
        )
        + "\n"
        "输出 JSON 结构参考：\n"
        + json.dumps(_schema_example(), ensure_ascii=False)
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _extract_json(text: str) -> Dict[str, Any]:
    content = text.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("模型响应中没有 JSON 对象")
        value = json.loads(content[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("模型响应必须是 JSON 对象")
    return value


def _request_llm(job: Dict[str, Any]) -> Tuple[Planning, str]:
    context = planning_context(job)
    base_url = os.getenv("AI_PLANNER_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    api_key = os.getenv("AI_PLANNER_API_KEY", "").strip()
    model = os.getenv("AI_PLANNER_MODEL", "").strip()
    timeout = int(os.getenv("AI_PLANNER_TIMEOUT", "60"))
    if not api_key:
        raise RuntimeError("未配置 AI_PLANNER_API_KEY")
    if not model:
        raise RuntimeError("未配置 AI_PLANNER_MODEL")

    payload = {
        "model": model,
        "messages": _messages(job, context),
        "temperature": 0.2,
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
        raise RuntimeError(f"Planner API 返回 HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Planner API 连接失败: {exc.reason}") from exc

    try:
        content = response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Planner API 响应缺少 choices[0].message.content") from exc
    planning = Planning.model_validate(_extract_json(content))
    planning.software_name = job["software_name"]
    planning.description = job.get("description") or planning.description
    planning.software_type = job.get("software_type") or planning.software_type
    planning.industry_type = context["industry"]["key"]
    planning.industry_name = context["industry"]["name"]
    validate_planning_against_context(planning, context, require_all_modules=True)
    return planning, model


def build_planning(job: Dict[str, Any]) -> PlannerResult:
    requested_mode = (
        job.get("planner_requested_mode")
        or job.get("planner_mode")
        or os.getenv("AI_PLANNER_MODE", "auto")
    ).strip().lower()
    if requested_mode not in {"template", "llm", "auto"}:
        raise RuntimeError("AI_PLANNER_MODE 必须是 template、llm 或 auto")

    if requested_mode == "template":
        return PlannerResult(
            planning=template_planning(job),
            requested_mode="template",
            actual_mode="template",
        )

    try:
        planning, model = _request_llm(job)
        return PlannerResult(
            planning=planning,
            requested_mode=requested_mode,
            actual_mode="llm",
            model=model,
        )
    except Exception as exc:
        if requested_mode == "llm":
            raise
        return PlannerResult(
            planning=template_planning(job),
            requested_mode="auto",
            actual_mode="template",
            fallback_reason=f"{type(exc).__name__}: {exc}",
        )
