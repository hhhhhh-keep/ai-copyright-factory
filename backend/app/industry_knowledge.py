import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional


KNOWLEDGE_ROOT = Path(__file__).resolve().parents[2] / "industry_knowledge"
KNOWLEDGE_FILES = (
    "public_security.json",
    "justice.json",
    "industry.json",
    "education.json",
)


@lru_cache(maxsize=1)
def load_industries() -> Dict[str, Dict[str, Any]]:
    industries: Dict[str, Dict[str, Any]] = {}
    for filename in KNOWLEDGE_FILES:
        path = KNOWLEDGE_ROOT / filename
        data = json.loads(path.read_text(encoding="utf-8"))
        industries[data["key"]] = data
    return industries


def list_industries() -> List[Dict[str, Any]]:
    return [
        {
            "key": item["key"],
            "name": item["name"],
            "typical_projects": item["typical_projects"],
        }
        for item in load_industries().values()
    ]


def detect_industry(
    software_name: str,
    description: str = "",
    explicit_key: Optional[str] = None,
) -> Dict[str, Any]:
    industries = load_industries()
    if explicit_key:
        if explicit_key not in industries:
            raise ValueError(f"不支持的行业类型: {explicit_key}")
        return industries[explicit_key]

    text = f"{software_name} {description}".lower()
    ranked = []
    for industry in industries.values():
        score = sum(text.count(alias.lower()) for alias in industry["aliases"])
        ranked.append((score, industry["key"], industry))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    if not ranked or ranked[0][0] == 0:
        raise ValueError("无法识别行业，请明确选择公安、政法、工业或教育")
    return ranked[0][2]


def clarification_for(
    software_name: str,
    description: str = "",
    industry_key: Optional[str] = None,
) -> Dict[str, Any]:
    industry = detect_industry(software_name, description, industry_key)
    return {
        "industry": {
            "key": industry["key"],
            "name": industry["name"],
            "terms": industry["terms"],
            "typical_projects": industry["typical_projects"],
        },
        "questions": [
            {
                "module_key": module["key"],
                "module_name": module["name"],
                "question": module["question"],
                "default": module["default"],
            }
            for module in industry["modules"]
        ],
    }


def selected_modules(industry: Dict[str, Any], answers: Dict[str, bool]) -> List[Dict[str, Any]]:
    modules = [
        module
        for module in industry["modules"]
        if answers.get(module["key"], module["default"])
    ]
    if len(modules) < 3:
        raise ValueError("至少需要选择 3 个行业模块")
    return modules


def planning_context(job: Dict[str, Any]) -> Dict[str, Any]:
    industry = detect_industry(
        job["software_name"],
        job.get("description", ""),
        job.get("industry_type"),
    )
    answers = job.get("clarification_answers") or {}
    modules = selected_modules(industry, answers)
    return {
        "industry": industry,
        "modules": modules,
        "allowed_module_keys": [module["key"] for module in modules],
    }
