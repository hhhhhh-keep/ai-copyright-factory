"""受证据约束的软著材料文案生成。

LLM 只负责润色模块简介、前置条件、步骤和注意事项；DOCX 结构、截图、事实字段
及最终排版仍由固定生成器控制。未配置模型或校验失败时始终使用确定性回退文案。
"""

import json
import os
import re
import urllib.request
from typing import Any, Dict, List, Tuple


SYSTEM_PROMPT = """你是计算机软件著作权材料的技术文档工程师。
仅依据提供的事实包，编写专业、简洁、可验证的中文模块说明。不得新增或推测任何
页面、字段、按钮、接口、角色、算法、性能指标、硬件环境或合规结论。没有事实时
必须省略，不得补造。只输出严格 JSON，不要 Markdown。
每个模块必须保留原 key，overview 为 80-160 字，preconditions 为 1-3 条，steps
为 4-6 条（每条仅含 action、expected_result），notes 为 0-3 条。"""


def _fallback(module: Dict[str, Any], actions: List[str]) -> Dict[str, Any]:
    fields = "、".join(module.get("fields", [])) or "业务字段"
    name = module["name"]
    description = str(module.get("description") or name).rstrip("。；; ")
    pages = "、".join(module.get("pages", [])) or f"{name}功能页"
    action_text = "、".join(actions) or "查询、登记、维护"
    return {
        "overview": (
            f"{description}。该模块以{pages}为业务入口，围绕{fields}等信息开展查询、"
            f"登记、编辑和业务办理。操作人员可在页面中按条件定位记录，核对字段信息后执行"
            f"{action_text}等已开放操作；提交成功后，系统将反馈处理结果并同步刷新页面数据。"
        ),
        "preconditions": [f"已进入{name}功能菜单", "具备相应的业务数据维护权限"],
        "steps": [
            {"action": f"从系统菜单进入{name}，确认页面已加载完成", "expected_result": f"显示{name}功能页及可用的查询、维护操作区域"},
            {"action": "按实际业务需要填写查询条件并执行查询", "expected_result": "列表仅显示符合条件的业务记录，便于继续核对或办理"},
            {"action": "选择新增或编辑入口，逐项填写或核对表单字段", "expected_result": f"可维护{fields}等与本次业务相关的信息"},
            {"action": "确认字段内容无误后提交保存，等待页面提示", "expected_result": "系统返回处理结果，列表或详情区域刷新为最新状态"},
        ],
        "notes": [f"可用操作：{'、'.join(actions)}。"] if actions else [],
    }


def _facts(planning: Dict[str, Any], actions_by_key: Dict[str, List[str]]) -> Dict[str, Any]:
    return {
        "software_name": planning["software_name"],
        "software_type": planning.get("software_type", ""),
        "target_users": planning.get("target_users", ""),
        "modules": [
            {
                "key": item["key"], "name": item["name"], "description": item.get("description", ""),
                "pages": item.get("pages", []), "fields": item.get("fields", []),
                "actions": actions_by_key.get(item["key"], []),
            }
            for item in planning["modules"]
        ],
    }


def _call(messages: List[Dict[str, str]]) -> str:
    base_url = os.getenv("AI_PLANNER_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    api_key = os.getenv("AI_PLANNER_API_KEY", "").strip()
    model = os.getenv("AI_DOCUMENT_MODEL", "").strip()
    if not api_key or not model:
        raise RuntimeError("AI_DOCUMENT_MODEL is not configured")
    payload = json.dumps({"model": model, "temperature": 0.1, "messages": messages}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/chat/completions", data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}, method="POST",
    )
    timeout = int(os.getenv("AI_DOCUMENT_TIMEOUT", "90"))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def _validate(raw: Any, planning: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    if not isinstance(raw, dict) or not isinstance(raw.get("modules"), list):
        raise ValueError("modules missing")
    expected = {item["key"] for item in planning["modules"]}
    output: Dict[str, Dict[str, Any]] = {}
    for item in raw["modules"]:
        if not isinstance(item, dict) or item.get("key") not in expected or item["key"] in output:
            raise ValueError("unknown or duplicate module key")
        overview = str(item.get("overview", "")).strip()
        steps = item.get("steps", [])
        if not 40 <= len(overview) <= 240 or not isinstance(steps, list) or not 4 <= len(steps) <= 6:
            raise ValueError("invalid overview or steps")
        clean_steps = []
        for step in steps:
            if not isinstance(step, dict):
                raise ValueError("invalid step")
            action = str(step.get("action", "")).strip()
            result = str(step.get("expected_result", "")).strip()
            if not action or not result or len(action) > 80 or len(result) > 100:
                raise ValueError("invalid step text")
            clean_steps.append({"action": action, "expected_result": result})
        output[item["key"]] = {
            "overview": overview,
            "preconditions": [str(value).strip() for value in item.get("preconditions", []) if str(value).strip()][:3],
            "steps": clean_steps,
            "notes": [str(value).strip() for value in item.get("notes", []) if str(value).strip()][:3],
        }
    if set(output) != expected:
        raise ValueError("module coverage mismatch")
    return output


def build_document_narratives(planning: Dict[str, Any], actions_by_key: Dict[str, List[str]]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    fallback = {item["key"]: _fallback(item, actions_by_key.get(item["key"], [])) for item in planning["modules"]}
    facts = _facts(planning, actions_by_key)
    try:
        text = _call([{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": json.dumps(facts, ensure_ascii=False)}])
        content = re.sub(r"^```json\s*|\s*```$", "", text.strip())
        return _validate(json.loads(content), planning), {"mode": "llm", "validated": True}
    except Exception as exc:
        return fallback, {"mode": "template", "validated": False, "fallback_reason": type(exc).__name__}
