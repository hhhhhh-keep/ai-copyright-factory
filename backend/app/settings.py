import os
import threading
from pathlib import Path
from typing import Dict, Optional

from dotenv import dotenv_values
from pydantic import BaseModel, Field, HttpUrl


ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
SETTINGS_LOCK = threading.Lock()
SETTING_KEYS = (
    "AI_PLANNER_BASE_URL",
    "AI_PLANNER_API_KEY",
    "AI_PLANNER_MODEL",
    "AI_PLANNER_TIMEOUT",
    "AI_CODEGEN_MODEL",
    "AI_CODEGEN_TIMEOUT",
    "AI_DOCUMENT_MODEL",
    "AI_DOCUMENT_TIMEOUT",
)


class PlannerSettingsUpdate(BaseModel):
    base_url: HttpUrl
    api_key: Optional[str] = Field(default=None, max_length=500)
    model: str = Field(default="", max_length=100)
    timeout: int = Field(default=180, ge=5, le=300)
    codegen_model: str = Field(default="", max_length=100)
    codegen_timeout: int = Field(default=240, ge=10, le=600)
    document_model: str = Field(default="", max_length=100)
    document_timeout: int = Field(default=90, ge=10, le=300)
    clear_api_key: bool = False


def _current_values() -> Dict[str, str]:
    file_values = {
        key: value or ""
        for key, value in dotenv_values(ENV_PATH).items()
        if key in SETTING_KEYS
    }
    return {
        key: os.getenv(key, file_values.get(key, ""))
        for key in SETTING_KEYS
    }


def public_planner_settings() -> Dict[str, object]:
    values = _current_values()
    api_key = values["AI_PLANNER_API_KEY"].strip()
    return {
        "base_url": values["AI_PLANNER_BASE_URL"] or "https://api.openai.com/v1",
        "model": values["AI_PLANNER_MODEL"],
        "timeout": int(values["AI_PLANNER_TIMEOUT"] or "180"),
        "codegen_model": values["AI_CODEGEN_MODEL"],
        "codegen_timeout": int(values["AI_CODEGEN_TIMEOUT"] or "240"),
        "document_model": values["AI_DOCUMENT_MODEL"],
        "document_timeout": int(values["AI_DOCUMENT_TIMEOUT"] or "90"),
        "api_key_configured": bool(api_key),
        "api_key_hint": f"***{api_key[-4:]}" if len(api_key) >= 4 else ("***" if api_key else ""),
    }


def save_planner_settings(payload: PlannerSettingsUpdate) -> Dict[str, object]:
    with SETTINGS_LOCK:
        existing = {
            key: value or ""
            for key, value in dotenv_values(ENV_PATH).items()
        }
        api_key = existing.get("AI_PLANNER_API_KEY", "")
        if payload.clear_api_key:
            api_key = ""
        elif payload.api_key and payload.api_key.strip():
            api_key = payload.api_key.strip()

        updates = {
            "AI_PLANNER_BASE_URL": str(payload.base_url).rstrip("/"),
            "AI_PLANNER_API_KEY": api_key,
            "AI_PLANNER_MODEL": payload.model.strip(),
            "AI_PLANNER_TIMEOUT": str(payload.timeout),
            "AI_CODEGEN_MODEL": payload.codegen_model.strip(),
            "AI_CODEGEN_TIMEOUT": str(payload.codegen_timeout),
            "AI_DOCUMENT_MODEL": payload.document_model.strip(),
            "AI_DOCUMENT_TIMEOUT": str(payload.document_timeout),
        }
        existing.update(updates)
        lines = [
            f"{key}={_quote_env_value(str(value))}"
            for key, value in existing.items()
            if key
        ]
        temporary = ENV_PATH.with_suffix(".env.tmp")
        temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.replace(str(temporary), str(ENV_PATH))
        for key, value in updates.items():
            os.environ[key] = value
    return public_planner_settings()


def _quote_env_value(value: str) -> str:
    if not value or any(char.isspace() for char in value) or any(char in value for char in '#"'):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value
