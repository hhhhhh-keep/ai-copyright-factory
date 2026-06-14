import json
import os
import shutil
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, field_validator


ALLOWED_FILES = {
    "frontend/src/App.vue",
    "frontend/src/style.css",
    "README.md",
}
MAX_FILE_CHARS = 120_000
MAX_TOTAL_CHARS = 300_000


class EnhancedFile(BaseModel):
    path: str
    content: str = Field(min_length=1, max_length=MAX_FILE_CHARS)

    @field_validator("path")
    @classmethod
    def allowed_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/").strip("/")
        if normalized not in ALLOWED_FILES:
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
    actual_mode: Literal["template", "llm"]
    model: Optional[str] = None
    summary: Optional[str] = None
    changed_files: List[str] = Field(default_factory=list)
    fallback_reason: Optional[str] = None


def _extract_json(text: str) -> Dict[str, Any]:
    content = text.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1]
        content = content.rsplit("```", 1)[0]
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("代码增强响应中没有 JSON 对象")
        value = json.loads(content[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("代码增强响应必须是 JSON 对象")
    return value


def _project_context(project_root: Path) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for relative in sorted(ALLOWED_FILES):
        path = project_root / relative
        if path.exists():
            result[relative] = path.read_text(encoding="utf-8")
    return result


def _request_enhancement(
    planning: Dict[str, Any], project_root: Path
) -> Tuple[EnhancementResponse, str]:
    base_url = os.getenv("AI_PLANNER_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    api_key = os.getenv("AI_PLANNER_API_KEY", "").strip()
    model = (
        os.getenv("AI_CODEGEN_MODEL", "").strip()
        or os.getenv("AI_PLANNER_MODEL", "").strip()
    )
    timeout = int(os.getenv("AI_CODEGEN_TIMEOUT", os.getenv("AI_PLANNER_TIMEOUT", "90")))
    if not api_key:
        raise RuntimeError("未配置 AI_PLANNER_API_KEY")
    if not model:
        raise RuntimeError("未配置 AI_CODEGEN_MODEL 或 AI_PLANNER_MODEL")

    system = (
        "你是受约束的软件代码增强器。只输出合法 JSON，不要 Markdown 或解释。"
        "你只能返回允许修改的文件，不能创建其他文件，不能修改依赖，不能调用外部服务。"
        "保持项目可运行，前端使用 Vue 3 script setup 和 Element Plus，"
        "后端 Java 代码由固定生成器负责，不允许修改。"
        "增强目标：让界面、文案、示例数据和 API 更贴合 planning.json，"
        "但不能新增 planning.json 中不存在的业务模块。"
        '输出结构为 {"summary":"说明","files":[{"path":"允许路径","content":"完整文件内容"}]}。'
    )
    user_payload = {
        "planning": planning,
        "allowed_files": sorted(ALLOWED_FILES),
        "current_files": _project_context(project_root),
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False),
            },
        ],
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

    try:
        content = response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("代码增强 API 响应缺少 choices[0].message.content") from exc
    return EnhancementResponse.model_validate(_extract_json(content)), model


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


def enhance_project(
    job: Dict[str, Any], planning: Dict[str, Any], project_root: Path, backup_root: Path
) -> EnhancementResult:
    requested_mode = (job.get("codegen_mode") or "auto").strip().lower()
    if requested_mode not in {"template", "auto", "llm"}:
        raise RuntimeError("codegen_mode 必须是 template、auto 或 llm")
    if requested_mode == "template":
        return EnhancementResult(
            requested_mode="template",
            actual_mode="template",
            summary="使用固定项目模板",
        )
    try:
        response, model = _request_enhancement(planning, project_root)
        _backup_files(project_root, backup_root, response.files)
        for item in response.files:
            target = project_root / item.path
            target.write_text(item.content, encoding="utf-8")
        return EnhancementResult(
            requested_mode=requested_mode,
            actual_mode="llm",
            model=model,
            summary=response.summary,
            changed_files=[item.path for item in response.files],
        )
    except Exception as exc:
        if requested_mode == "llm":
            raise
        return EnhancementResult(
            requested_mode="auto",
            actual_mode="template",
            summary="代码增强失败，保留固定模板",
            fallback_reason=f"{type(exc).__name__}: {exc}",
        )
