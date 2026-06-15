from pathlib import Path
from multiprocessing import Process
import re
import shutil
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional, Set

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .settings import (
    PlannerSettingsUpdate,
    public_planner_settings,
    save_planner_settings,
)
from .planner import Planning, propose_revision
from .industry_knowledge import clarification_for, list_industries
from .workflow import (
    OUTPUT_ROOT,
    _json_read,
    _json_write,
    _update,
    create_job,
    continue_material_generation,
    demo_runtime,
    generate_planning_draft,
    get_job,
    run_job,
    reset_job_for_revision,
    save_planning_version,
    start_online_demo,
    stop_online_demo,
)


class JobRequest(BaseModel):
    software_name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=1000)
    software_type: str = Field(default="管理系统", max_length=50)
    industry_type: Literal[
        "public_security", "justice", "industry", "education"
    ]
    planner_mode: Literal["auto", "template", "llm"] = "auto"
    codegen_mode: Literal["auto", "template", "llm"] = "auto"
    document_template: Literal["standard", "compact", "formal"] = "standard"
    version: str = Field(default="V1.0", min_length=1, max_length=30)
    applicant_name: str = Field(default="待填写", min_length=1, max_length=100)
    completion_date: str = Field(default="", max_length=20)
    publication_status: Literal["未发表", "已发表"] = "未发表"


class RegeneratePlanningRequest(BaseModel):
    job_id: str = Field(min_length=5, max_length=100)


class ClarificationRequest(BaseModel):
    software_name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=1000)
    industry_type: Optional[
        Literal["public_security", "justice", "industry", "education"]
    ] = None


class RevisionRequest(BaseModel):
    instruction: str = Field(min_length=2, max_length=2000)


_DEMO_START_LOCK = threading.Lock()
_DEMO_STARTING: Set[str] = set()


def _start_demo_worker(job_id: str) -> None:
    try:
        job = get_job(job_id)
        if not job:
            return
        start_online_demo(job, OUTPUT_ROOT / job_id)
    except Exception as exc:
        # 截断错误到 500 字符，避免 demo_runtime.json 过大
        error_text = f"{type(exc).__name__}: {exc}"
        if len(error_text) > 500:
            error_text = error_text[:500] + "…"
        runtime_path = OUTPUT_ROOT / job_id / "demo_runtime.json"
        if runtime_path.exists():
            runtime = _json_read(runtime_path)
        else:
            runtime = {
                "started_at": datetime.now().isoformat(timespec="seconds"),
                "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(timespec="seconds"),
            }
        runtime["status"] = "failed"
        runtime["stage"] = "failed"
        runtime["error"] = error_text
        _json_write(runtime_path, runtime)
        _update(job_id, run_status="failed")
    finally:
        with _DEMO_START_LOCK:
            _DEMO_STARTING.discard(job_id)


def planning_response(job_id: str) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    path = OUTPUT_ROOT / job_id / "planning.json"
    if not path.exists():
        raise HTTPException(status_code=409, detail="规划尚未生成")
    planning = Planning.model_validate(_json_read(path)).model_dump()
    page_count = 2 + sum(len(module["pages"]) for module in planning["modules"])
    table_count = len(planning["database_tables"])
    screenshot_count = 3 + len(planning["modules"])
    return {
        "job_id": job_id,
        "status": job["status"],
        "locked": job["status"] != "draft_planning",
        "planning": planning,
        "estimates": {
            "page_count": page_count,
            "table_count": table_count,
            "code_lines": page_count * 180 + table_count * 80 + len(planning["modules"]) * 250,
            "screenshot_count": screenshot_count,
        },
    }


app = FastAPI(title="AI软著工厂", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/industries")
def industries() -> Dict[str, Any]:
    return {"items": list_industries()}


@app.post("/api/clarifications")
def clarifications(payload: ClarificationRequest) -> Dict[str, Any]:
    try:
        return clarification_for(
            payload.software_name,
            payload.description,
            payload.industry_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/settings/planner")
def get_planner_settings() -> Dict[str, object]:
    return public_planner_settings()


@app.put("/api/settings/planner")
def update_planner_settings(payload: PlannerSettingsUpdate) -> Dict[str, object]:
    return save_planner_settings(payload)


@app.post("/api/jobs", status_code=202)
def submit_job(payload: JobRequest) -> Dict[str, Any]:
    job = create_job(payload.model_dump())
    Process(
        target=generate_planning_draft,
        args=(job["job_id"],),
        name=f"planning-job-{job['job_id']}",
        daemon=True,
    ).start()
    return job


@app.get("/api/planning/{job_id}")
def get_planning(job_id: str) -> Dict[str, Any]:
    return planning_response(job_id)


@app.put("/api/planning/{job_id}")
def update_planning(job_id: str, payload: Planning) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job["status"] != "draft_planning":
        raise HTTPException(status_code=409, detail="规划已锁定，禁止修改")
    planning = payload.model_dump()
    existing_path = OUTPUT_ROOT / job_id / "planning.json"
    existing = _json_read(existing_path)
    planning["planner"] = existing.get("planner", {})
    planning["screenshots"] = ["登录页", "首页"] + [
        module["name"] for module in planning["modules"]
    ]
    planning["api_list"] = [
        route
        for module in planning["modules"]
        for route in (f"GET /api/{module['key']}", f"POST /api/{module['key']}")
    ]
    _json_write(existing_path, planning)
    _update(
        job_id,
        software_name=planning["software_name"],
        description=planning["description"],
        software_type=planning["software_type"],
        current_step="软件规划已保存，等待确认",
    )
    return planning_response(job_id)


@app.post("/api/planning/regenerate", status_code=202)
def regenerate_planning(payload: RegeneratePlanningRequest) -> Dict[str, Any]:
    job = get_job(payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job["status"] != "draft_planning":
        raise HTTPException(status_code=409, detail="仅草稿规划允许重新生成")
    steps = job["steps"]
    for item in steps:
        item["status"] = "pending"
    _update(
        payload.job_id,
        status="generating",
        progress=0,
        current_step="重新生成软件规划",
        steps=steps,
        error=None,
    )
    Process(
        target=generate_planning_draft,
        args=(payload.job_id,),
        name=f"planning-regenerate-{payload.job_id}",
        daemon=True,
    ).start()
    return get_job(payload.job_id)


@app.post("/api/jobs/{job_id}/confirm", status_code=202)
def confirm_job(job_id: str) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job["status"] != "draft_planning":
        raise HTTPException(status_code=409, detail="当前任务不能确认规划")
    if not (OUTPUT_ROOT / job_id / "planning.json").exists():
        raise HTTPException(status_code=409, detail="planning.json 不存在")
    planning = _json_read(OUTPUT_ROOT / job_id / "planning.json")
    versions_dir = OUTPUT_ROOT / job_id / "planning_versions"
    if not versions_dir.exists() or not list(versions_dir.glob("v*.json")):
        save_planning_version(job_id, planning, summary="首次确认规划")
    confirmed = _update(
        job_id,
        status="confirmed",
        current_step="规划已确认，准备生成项目",
        error=None,
    )
    Process(
        target=run_job,
        args=(job_id,),
        name=f"copyright-job-{job_id}",
        daemon=True,
    ).start()
    return confirmed


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    runtime = demo_runtime(job_id)
    if runtime.get("status") == "running":
        job["demo_url"] = runtime["demo_url"]
        job["swagger_url"] = runtime["swagger_url"]
        job["run_status"] = "running"
    job["demo_stage"] = runtime.get("stage")
    job["demo_error"] = runtime.get("error", "")
    return job


@app.get("/api/history/jobs")
def job_history(limit: int = 100) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for path in OUTPUT_ROOT.glob("*/status.json"):
        try:
            job = _json_read(path)
        except (OSError, ValueError):
            continue
        runtime = demo_runtime(job["job_id"])
        items.append(
            {
                "job_id": job["job_id"],
                "software_name": job.get("software_name", ""),
                "industry_type": job.get("industry_type", ""),
                "status": job.get("status", "unknown"),
                "progress": job.get("progress", 0),
                "current_step": job.get("current_step", ""),
                "run_status": runtime.get("status", job.get("run_status", "stopped")),
                "demo_url": runtime.get("demo_url"),
                "swagger_url": runtime.get("swagger_url"),
                "compliance_score": job.get("compliance_score"),
                "created_at": job.get("created_at"),
                "updated_at": job.get("updated_at"),
                "has_package": (path.parent / "copyright_package.zip").exists(),
                "has_planning": (path.parent / "planning.json").exists(),
            }
        )
    items.sort(
        key=lambda item: item.get("created_at") or item["job_id"],
        reverse=True,
    )
    return {"items": items[: max(1, min(limit, 500))], "total": len(items)}


@app.get("/api/jobs/{job_id}/demo")
def get_demo(job_id: str) -> Dict[str, Any]:
    if not get_job(job_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    runtime = demo_runtime(job_id)
    with _DEMO_START_LOCK:
        if job_id in _DEMO_STARTING and runtime.get("status") in ("stopped", None):
            runtime = {
                **runtime,
                "status": "starting",
                "stage": "queued",
                "stage_detail": "排队中…",
            }
    return runtime


@app.post("/api/jobs/{job_id}/demo/start")
def start_demo(job_id: str) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job["status"] not in {"success", "awaiting_demo_review"}:
        raise HTTPException(status_code=409, detail="任务尚未生成完成")
    current = demo_runtime(job_id)
    if current.get("status") == "running":
        return current
    with _DEMO_START_LOCK:
        if job_id in _DEMO_STARTING:
            return {"status": "starting"}
        _DEMO_STARTING.add(job_id)
    threading.Thread(
        target=_start_demo_worker,
        args=(job_id,),
        name=f"demo-start-{job_id}",
        daemon=True,
    ).start()
    return {"status": "starting"}


@app.post("/api/jobs/{job_id}/demo/stop")
def stop_demo(job_id: str) -> Dict[str, Any]:
    if not get_job(job_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    return stop_online_demo(job_id)


@app.post("/api/jobs/{job_id}/review/approve", status_code=202)
def approve_demo_review(job_id: str) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job["status"] != "awaiting_demo_review":
        raise HTTPException(status_code=409, detail="当前任务不在 Demo 审查阶段")
    updated = _update(
        job_id,
        status="generating_materials",
        current_step="Demo 审查通过，准备生成软著材料",
        review_approved_at=datetime.now().isoformat(timespec="seconds"),
    )
    Process(
        target=continue_material_generation,
        args=(job_id,),
        name=f"materials-job-{job_id}",
        daemon=True,
    ).start()
    return updated


@app.post("/api/jobs/{job_id}/revision/propose")
def revision_propose(job_id: str, payload: RevisionRequest) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job["status"] not in {"awaiting_demo_review", "revision_review"}:
        raise HTTPException(status_code=409, detail="当前任务不能提出返工意见")
    planning_path = OUTPUT_ROOT / job_id / "planning.json"
    result = propose_revision(job, _json_read(planning_path), payload.instruction)
    proposal = {
        "instruction": payload.instruction,
        "summary": result.summary,
        "actual_mode": result.actual_mode,
        "model": result.model,
        "fallback_reason": result.fallback_reason,
        "planning": result.planning.model_dump(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    proposals_dir = OUTPUT_ROOT / job_id / "revision_proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    proposal_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
    proposal["proposal_id"] = proposal_id
    _json_write(proposals_dir / f"{proposal_id}.json", proposal)
    _json_write(OUTPUT_ROOT / job_id / "revision_proposal.json", proposal)
    _update(
        job_id,
        status="revision_review",
        current_step="等待确认规划修改",
        revision_summary=result.summary,
    )
    return proposal


@app.post("/api/jobs/{job_id}/revision/confirm", status_code=202)
def revision_confirm(job_id: str) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job["status"] != "revision_review":
        raise HTTPException(status_code=409, detail="当前没有待确认的规划修改")
    proposal_path = OUTPUT_ROOT / job_id / "revision_proposal.json"
    if not proposal_path.exists():
        raise HTTPException(status_code=409, detail="规划修改建议不存在")
    proposal = _json_read(proposal_path)
    planning = proposal["planning"]
    _json_write(OUTPUT_ROOT / job_id / "planning.json", planning)
    version = save_planning_version(
        job_id,
        planning,
        instruction=proposal["instruction"],
        summary=proposal["summary"],
    )
    reset_job_for_revision(job_id)
    _update(job_id, planning_version=version)
    Process(
        target=run_job,
        args=(job_id,),
        name=f"revision-job-{job_id}-v{version}",
        daemon=True,
    ).start()
    return get_job(job_id)


@app.post("/api/jobs/{job_id}/revision/cancel")
def revision_cancel(job_id: str) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job["status"] != "revision_review":
        raise HTTPException(status_code=409, detail="当前没有待确认的规划修改")
    return _update(
        job_id,
        status="awaiting_demo_review",
        current_step="等待用户审查在线 Demo",
        revision_summary=None,
    )


@app.get("/api/jobs/{job_id}/revisions")
def revision_history(job_id: str) -> Dict[str, Any]:
    if not get_job(job_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    versions = []
    for path in sorted((OUTPUT_ROOT / job_id / "planning_versions").glob("v*.json")):
        try:
            data = _json_read(path)
        except (OSError, ValueError):
            continue
        versions.append(
            {
                "version": data.get("version"),
                "created_at": data.get("created_at"),
                "instruction": data.get("instruction", ""),
                "summary": data.get("summary", ""),
            }
        )
    return {"items": versions}


@app.post("/api/jobs/{job_id}/revisions/{version}/restore", status_code=202)
def restore_revision(job_id: str, version: int) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job["status"] not in {"awaiting_demo_review", "revision_review", "failed"}:
        raise HTTPException(status_code=409, detail="当前任务不能回退规划")
    path = OUTPUT_ROOT / job_id / "planning_versions" / f"v{version}.json"
    if version < 1 or not path.exists():
        raise HTTPException(status_code=404, detail="规划版本不存在")
    restored = _json_read(path)["planning"]
    _json_write(OUTPUT_ROOT / job_id / "planning.json", restored)
    new_version = save_planning_version(
        job_id,
        restored,
        instruction=f"回退到规划 v{version}",
        summary=f"从规划 v{version} 恢复并重新生成",
    )
    reset_job_for_revision(job_id)
    _update(job_id, planning_version=new_version)
    Process(
        target=run_job,
        args=(job_id,),
        name=f"restore-job-{job_id}-v{version}",
        daemon=True,
    ).start()
    return get_job(job_id)


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str) -> Dict[str, Any]:
    if not re.fullmatch(r"\d{14}-[a-f0-9]{8}", job_id):
        raise HTTPException(status_code=400, detail="任务编号不合法")
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job["status"] in {
        "generating",
        "confirmed",
        "regenerating_project",
        "generating_materials",
    }:
        raise HTTPException(status_code=409, detail="任务正在执行，暂不能删除")
    stop_online_demo(job_id)
    with _DEMO_START_LOCK:
        _DEMO_STARTING.discard(job_id)
    target = (OUTPUT_ROOT / job_id).resolve()
    root = OUTPUT_ROOT.resolve()
    if target.parent != root:
        raise HTTPException(status_code=400, detail="任务路径不合法")
    shutil.rmtree(target)
    return {"deleted": True, "job_id": job_id}


@app.get("/api/jobs/{job_id}/logs/{service}")
def demo_logs(job_id: str, service: Literal["backend", "frontend"]) -> Dict[str, str]:
    if not get_job(job_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    path = OUTPUT_ROOT / job_id / "logs" / f"{service}.log"
    if not path.exists():
        return {"service": service, "content": ""}
    content = path.read_text(encoding="utf-8", errors="replace")
    return {"service": service, "content": content[-20000:]}


@app.get("/api/jobs/{job_id}/preview")
def job_preview(job_id: str) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    job_dir = OUTPUT_ROOT / job_id
    screenshots: List[str] = []
    documents: List[str] = []
    if (job_dir / "screenshots").exists():
        screenshots = [
            f"/api/jobs/{job_id}/files/screenshots/{path.name}"
            for path in sorted((job_dir / "screenshots").glob("*.png"))
        ]
    if (job_dir / "docs").exists():
        documents = [path.name for path in sorted((job_dir / "docs").glob("*.docx"))]
    compliance = None
    compliance_path = job_dir / "compliance_report.json"
    if compliance_path.exists():
        import json

        compliance = json.loads(compliance_path.read_text(encoding="utf-8"))
    return {
        "job": job,
        "screenshots": screenshots,
        "documents": documents,
        "compliance": compliance,
        "demo": demo_runtime(job_id),
    }


@app.get("/api/jobs/{job_id}/files/screenshots/{filename}")
def screenshot_file(job_id: str, filename: str) -> FileResponse:
    path = (OUTPUT_ROOT / job_id / "screenshots" / Path(filename).name).resolve()
    expected = (OUTPUT_ROOT / job_id / "screenshots").resolve()
    if expected not in path.parents or not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path)


@app.get("/api/jobs/{job_id}/download")
def download(job_id: str) -> FileResponse:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    package = OUTPUT_ROOT / job_id / "copyright_package.zip"
    if not package.exists():
        raise HTTPException(status_code=409, detail="材料包尚未生成")
    return FileResponse(
        package,
        media_type="application/zip",
        filename=f"{job['software_name']}_软著材料包.zip",
    )
