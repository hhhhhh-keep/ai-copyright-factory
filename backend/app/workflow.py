import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from datetime import datetime, timedelta
from multiprocessing import Process
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

from .compliance import build_compliance_report
from .enhancer import enhance_project, restore_enhancement
from .planner import PlannerValidationError, build_planning
from .project_generator import generate_java_project


BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = BASE_DIR / "outputs"
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
_LOCK = threading.Lock()

# ISSUE-008 L1 状态与超时阈值：超过这个时间且进程不存在/锁文件陈旧
# 的任务会被启动扫描标记为 interrupted。
INTERRUPTED_STATUS = "interrupted"
EXECUTING_STATUSES = {
    "generating",
    "regenerating_project",
    "generating_materials",
    "confirmed",
    "awaiting_demo_review",
}
# 不同状态下"updated_at" 超过这个秒数即视为陈旧
INTERRUPT_AGE_SECONDS = {
    "confirmed": 600,  # 10 分钟，规划已确认但项目目录还没建
    "generating": 1800,  # 30 分钟，生成项目阶段
    "regenerating_project": 1800,
    "generating_materials": 3600,  # 60 分钟，材料阶段
}
# awaiting_demo_review 不自动标 interrupted（可能用户长时间不操作）

STEPS = [
    ("planning", "生成软件规划"),
    ("project", "生成可运行项目"),
    ("enhance", "AI 增强项目代码"),
    ("run", "运行项目并验证"),
    ("demo", "启动在线 Demo"),
    ("screenshot", "自动截图"),
    ("analyze", "统计真实代码行数"),
    ("source", "生成源码材料"),
    ("docs", "生成设计说明书和用户手册"),
    ("compliance", "执行软著合规检查"),
    ("package", "打包软著材料"),
]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _json_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(temporary), str(path))


def _json_read(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _set_demo_stage(job_id: str, **changes: Any) -> None:
    """更新 demo_runtime.json 的 stage / error / 进度等字段。

    不修改 status="running" 的运行态；status 仍由 start_online_demo 收尾时统一写。
    """
    path = OUTPUT_ROOT / job_id / "demo_runtime.json"
    with _LOCK:
        if not path.exists():
            runtime = {
                "status": "starting",
                "stage": "queued",
                "started_at": _now(),
                "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(
                    timespec="seconds"
                ),
            }
        else:
            runtime = _json_read(path)
        runtime.update(changes)
        runtime["updated_at"] = _now()
        _json_write(path, runtime)


def _status_path(job_id: str) -> Path:
    return OUTPUT_ROOT / job_id / "status.json"


# ----------------- ISSUE-008 L1：worker 锁与中断检测 -----------------


def _worker_lock_path(job_id: str) -> Path:
    return OUTPUT_ROOT / job_id / "worker.lock"


def _pid_alive(pid: Optional[int]) -> bool:
    """检查 PID 是否仍存在。Windows 上 os.kill(pid, 0) 抛 OSError 即死亡。"""
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _acquire_worker_lock(job_id: str, task_name: str) -> Dict[str, Any]:
    """把当前 Worker 写入 outputs/{job_id}/worker.lock。

    返回 lock 字典（含 pid、started_at、task）。如果 lock 已存在且 PID 仍存活，
    抛 RuntimeError，让调用方拒绝重复启动。
    """
    job_dir = OUTPUT_ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    lock_path = _worker_lock_path(job_id)
    if lock_path.exists():
        try:
            existing = _json_read(lock_path)
        except (OSError, ValueError):
            existing = {}
        existing_pid = existing.get("pid")
        if _pid_alive(existing_pid):
            raise RuntimeError(
                f"任务 {job_id} 已有活跃 Worker (PID {existing_pid})，拒绝重复启动"
            )
    lock = {
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "task": task_name,
        "started_at": _now(),
    }
    _json_write(lock_path, lock)
    return lock


def _release_worker_lock(job_id: str) -> None:
    """删除 worker.lock。"""
    lock_path = _worker_lock_path(job_id)
    if lock_path.exists():
        try:
            lock_path.unlink()
        except OSError:
            pass


def _is_job_orphaned(status: Dict[str, Any]) -> bool:
    """根据 lock 文件和 updated_at 判断任务是否需要标 interrupted。"""
    job_id = status.get("job_id")
    if not job_id:
        return False
    if status.get("status") not in EXECUTING_STATUSES:
        return False
    # success / failed / interrupted / draft_planning 直接跳过
    if status.get("status") in {"success", "failed", INTERRUPTED_STATUS, "draft_planning"}:
        return False
    # awaiting_demo_review：长时间没动可能用户没操作，但应给机会先看 UI
    # 暂时保守：awaiting_demo_review 不自动 interrupted（用户可手动恢复）
    if status.get("status") == "awaiting_demo_review":
        return False
    # 优先级 1：worker.lock 是否存在
    # - 活锁：Worker 仍在跑，即使 updated_at 旧也不能算孤儿（避免长任务被误杀）
    # - 死锁：Worker 已退出，视为孤儿
    # - 坏锁：lock JSON 解析失败，视为孤儿
    lock_path = _worker_lock_path(job_id)
    if lock_path.exists():
        try:
            lock = _json_read(lock_path)
        except (OSError, ValueError):
            return True
        if not _pid_alive(lock.get("pid")):
            return True
        return False
    # 优先级 2：无锁 + updated_at 超时 → 视为孤儿
    # （任务曾经启动过 worker，但 worker 没写 lock 就崩溃了，靠 updated_at 兜底）
    updated_at = status.get("updated_at")
    if updated_at:
        try:
            last = datetime.fromisoformat(updated_at)
            age = (datetime.now() - last).total_seconds()
            threshold = INTERRUPT_AGE_SECONDS.get(status["status"], 1800)
            if age >= threshold:
                return True
        except ValueError:
            pass
    return False


def scan_for_interrupted_jobs() -> List[str]:
    """扫描 outputs/*/status.json，对疑似失联的任务标记 interrupted。

    返回被标记的 job_id 列表。服务启动时调用一次。
    """
    marked: List[str] = []
    if not OUTPUT_ROOT.exists():
        return marked
    for status_path in OUTPUT_ROOT.glob("*/status.json"):
        try:
            status = _json_read(status_path)
        except (OSError, ValueError):
            continue
        job_id = status.get("job_id")
        if not job_id:
            continue
        if not _is_job_orphaned(status):
            continue
        try:
            # 标记前先停掉任何残留 Demo
            try:
                stop_online_demo(job_id)
            except Exception:
                pass
            steps = status.get("steps", [])
            for item in steps:
                if item.get("status") == "running":
                    item["status"] = "failed"
            _update(
                job_id,
                status=INTERRUPTED_STATUS,
                steps=steps,
                current_step="后台进程中断，等待用户恢复",
                failed_stage=status.get("status"),
                interrupted_at=_now(),
                interrupted_reason=(
                    "updated_at 超过阈值或 worker 锁进程已退出，"
                    "请在历史任务页点击'恢复任务'继续。"
                ),
                error=None,
            )
            _release_worker_lock(job_id)
            marked.append(job_id)
        except Exception:
            # 单个任务标记失败不影响其它任务
            continue
    return marked


def _has_active_worker_lock(job_id: str) -> bool:
    """只读检查：lock 文件存在且 PID 仍存活。

    与 `_acquire_worker_lock` 不同，这里不抢锁，只用于 resume 前防双跑。
    """
    lock_path = _worker_lock_path(job_id)
    if not lock_path.exists():
        return False
    try:
        lock = _json_read(lock_path)
    except (OSError, ValueError):
        return False
    return _pid_alive(lock.get("pid"))


def resume_job(job_id: str) -> Dict[str, Any]:
    """根据任务当前阶段选择恢复点，启动新 Worker。

    恢复策略（与 ISSUE-008 文档表一致）：
    - confirmed：项目目录不存在 → 从 project 开始
    - project/enhance：清掉 generated_project/ 后从 project 开始
    - run：从 run 重新执行
    - demo：清掉残留进程后从 demo 重新启动
    - generating_materials：清掉 screenshots/ docs/ copyright_package.zip 等，从 materials 整体重做
    - 其余状态（含 success / draft_planning / failed / awaiting_demo_review）：
      抛 ValueError，由 main.py 转为 409
    - 防双跑：若 lock 文件中 PID 仍存活则拒绝，避免重复点击启动两个生成进程。

    返回 dict：被恢复任务的最新 status。
    """
    status = get_job(job_id)
    if not status:
        raise LookupError("任务不存在")
    current = status.get("status")
    if current == "success":
        raise ValueError("任务已完成，无需恢复")
    if current == "draft_planning":
        raise ValueError("规划未确认，无需恢复")
    if current == "awaiting_demo_review":
        raise ValueError("任务正在等待用户审查 Demo，无需恢复")
    if current != INTERRUPTED_STATUS:
        raise ValueError(f"当前状态 {current} 不可恢复，请先中断或失败后重试")

    # 防双跑：先释放陈旧 lock（PID 已死），再检查是否还有活锁
    lock_path = _worker_lock_path(job_id)
    if lock_path.exists():
        try:
            existing = _json_read(lock_path)
        except (OSError, ValueError):
            existing = {}
        if not _pid_alive(existing.get("pid")):
            _release_worker_lock(job_id)
    if _has_active_worker_lock(job_id):
        raise RuntimeError("已有活跃 Worker 在执行该任务，请稍候再试")

    job_dir = OUTPUT_ROOT / job_id
    # 清理可能残留的运行中 step
    steps = status.get("steps", [])
    for item in steps:
        if item["key"] == "planning":
            item["status"] = "completed"
        elif item["status"] == "running":
            item["status"] = "failed"

    # 根据中断前的状态选择恢复点
    prev_status = status.get("failed_stage") or current
    target = "project"  # 默认从 project 开始
    if prev_status in {"generating_materials", "materials"}:
        # 材料阶段：内部 target 落到第一个材料步骤 screenshot，
        # 避免 STEPS 中没有"materials"导致从 planning 全部重置
        target = "screenshot"
        for name in (
            "screenshots",
            "docs",
            "logs",
            "copyright_package.zip",
            "generated_project.zip",
        ):
            path = job_dir / name
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
    elif prev_status == "confirmed":
        target = "project"
    elif prev_status in {"project", "enhance"}:
        target = "project"
        gen_dir = job_dir / "generated_project"
        if gen_dir.exists():
            shutil.rmtree(gen_dir)
    elif prev_status == "run":
        target = "run"
    elif prev_status == "demo":
        target = "demo"
        try:
            stop_online_demo(job_id)
        except Exception:
            pass

    # 解析 target 在 STEPS 中的位置；若 target 不在 STEPS，target=project 时回退到 1 (project)
    # materials 已在前面改写为 screenshot（STEPS 中存在），不会再走这里。
    target_idx = next(
        (i for i, s in enumerate(STEPS) if s[0] == target),
        1 if target in {"project", "enhance"} else 0,
    )

    # 重置 target 之后（含）所有 step 状态为 pending
    for i, (key, _name) in enumerate(STEPS):
        if i >= target_idx:
            for item in steps:
                if item["key"] == key:
                    item["status"] = "pending"

    resume_count = int(status.get("resume_count", 0)) + 1
    # 选择目标状态与 Worker：材料阶段直接进入 generating_materials，避免短暂写 regenerating_project
    if target == "screenshot" or target == "materials":
        new_status = "generating_materials"
        target_fn = continue_material_generation
    else:
        new_status = "generating"
        target_fn = run_job
    _update(
        job_id,
        status=new_status,
        current_step=f"恢复任务，从 {target} 重新开始",
        steps=steps,
        error=None,
        failed_stage=None,
        interrupted_at=None,
        interrupted_reason=None,
        recovery_from_step=target,
        resume_count=resume_count,
        resumed_at=_now(),
    )

    Process(
        target=target_fn,
        args=(job_id,),
        name=f"resume-{target}-{job_id}",
        daemon=True,
    ).start()
    return get_job(job_id)


def create_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    job_id = datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
    job_dir = OUTPUT_ROOT / job_id
    job_dir.mkdir(parents=True)
    status = {
        "job_id": job_id,
        "software_name": payload["software_name"].strip(),
        "description": payload.get("description", "").strip(),
        "software_type": payload.get("software_type", "管理系统").strip(),
        "industry_type": payload["industry_type"],
        "clarification_answers": payload.get("clarification_answers", {}),
        "planner_model": None,
        "codegen_mode": payload.get("codegen_mode", "auto"),
        "codegen_actual_mode": None,
        "codegen_model": None,
        "codegen_summary": None,
        "codegen_changed_files": [],
        "codegen_fallback_reason": None,
        "document_template": payload.get("document_template", "standard"),
        "version": payload.get("version", "V1.0"),
        "applicant_name": payload.get("applicant_name", "待填写"),
        "completion_date": payload.get("completion_date")
        or datetime.now().strftime("%Y-%m-%d"),
        "publication_status": payload.get("publication_status", "未发表"),
        "compliance_score": None,
        "compliance_grade": None,
        "compliance_passed": None,
        "demo_url": None,
        "swagger_url": None,
        "run_status": "pending",
        "run_validation": None,
        "status": "generating",
        "progress": 0,
        "current_step": "生成软件规划",
        "steps": [{"key": key, "name": name, "status": "pending"} for key, name in STEPS],
        "failed_stage": None,
        "error": None,
        # ISSUE-008 L1：执行信息
        "worker_pid": None,
        "worker_started_at": None,
        "worker_heartbeat_at": None,
        "interrupted_at": None,
        "interrupted_reason": None,
        "resume_count": 0,
        "recovery_from_step": None,
        "resumed_at": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    _json_write(_status_path(job_id), status)
    return status


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    path = _status_path(job_id)
    if not path.exists():
        return None
    return _json_read(path)


def _update(job_id: str, **changes: Any) -> Dict[str, Any]:
    with _LOCK:
        status = _json_read(_status_path(job_id))
        status.update(changes)
        status["updated_at"] = _now()
        _json_write(_status_path(job_id), status)
        return status


def _step(job_id: str, key: str, state: str) -> None:
    status = get_job(job_id)
    if not status:
        return
    for item in status["steps"]:
        if item["key"] == key:
            item["status"] = state
    completed = len([item for item in status["steps"] if item["status"] == "completed"])
    current = next((name for step_key, name in STEPS if step_key == key), key)
    _update(
        job_id,
        steps=status["steps"],
        current_step=current,
        progress=int(completed / len(STEPS) * 100),
    )


def generate_planning_draft(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return
    job_dir = OUTPUT_ROOT / job_id
    try:
        _acquire_worker_lock(job_id, "generate_planning_draft")
    except RuntimeError:
        # 已有活跃 Worker，跳过启动
        return
    try:
        _update(
            job_id,
            status="generating",
            current_step="生成软件规划",
            error=None,
            failed_stage=None,
            worker_pid=os.getpid(),
            worker_started_at=_now(),
            worker_heartbeat_at=_now(),
        )
        _step(job_id, "planning", "running")
        generate_planning(job, job_dir)
        _step(job_id, "planning", "completed")
        _update(
            job_id,
            status="draft_planning",
            progress=10,
            current_step="等待确认软件规划",
            failed_stage=None,
        )
    except Exception as exc:
        _write_planner_diagnostics(job_dir, exc)
        status = get_job(job_id)
        if status:
            for item in status["steps"]:
                if item["status"] == "running":
                    item["status"] = "failed"
            _update(
                job_id,
                status="failed",
                steps=status["steps"],
                current_step="规划生成失败",
                failed_stage="planning",
                error=f"{type(exc).__name__}: {exc}",
            )
    finally:
        _release_worker_lock(job_id)


def run_job(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return
    job_dir = OUTPUT_ROOT / job_id
    if not (job_dir / "planning.json").exists():
        _update(
            job_id,
            status="failed",
            current_step="生成失败",
            failed_stage="project",
            error="planning.json 不存在，禁止开始项目生成",
        )
        return
    try:
        _acquire_worker_lock(job_id, "run_job")
    except RuntimeError:
        return
    try:
        _update(
            job_id,
            status="generating",
            current_step="开始生成",
            error=None,
            failed_stage=None,
            worker_pid=os.getpid(),
            worker_started_at=_now(),
            worker_heartbeat_at=_now(),
        )
        tasks = [
            ("project", lambda: generate_project(job_dir)),
            ("enhance", lambda: enhance_generated_project(job, job_dir)),
            ("run", lambda: validate_generated_project(job, job_dir)),
            ("demo", lambda: start_online_demo(job, job_dir)),
        ]
        for key, action in tasks:
            _step(job_id, key, "running")
            action()
            _step(job_id, key, "completed")
        _update(
            job_id,
            status="awaiting_demo_review",
            progress=int(5 / len(STEPS) * 100),
            current_step="等待用户审查在线 Demo",
            review_round=int(job.get("review_round", 0)) + 1,
        )
    except Exception as exc:
        status = get_job(job_id)
        if status:
            for item in status["steps"]:
                if item["status"] == "running":
                    item["status"] = "failed"
            _update(
                job_id,
                status="failed",
                steps=status["steps"],
                current_step="生成失败",
                failed_stage="project",
                error=f"{type(exc).__name__}: {exc}",
            )
    finally:
        _release_worker_lock(job_id)


def continue_material_generation(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return
    job_dir = OUTPUT_ROOT / job_id
    try:
        _acquire_worker_lock(job_id, "continue_material_generation")
    except RuntimeError:
        return
    try:
        _update(
            job_id,
            status="generating_materials",
            current_step="Demo 审查通过，开始生成软著材料",
            error=None,
            failed_stage=None,
            worker_pid=os.getpid(),
            worker_started_at=_now(),
            worker_heartbeat_at=_now(),
        )
        tasks = [
            ("screenshot", lambda: capture_screenshots(job_dir)),
            ("analyze", lambda: analyze_code(job_dir)),
            ("source", lambda: generate_source_document(job_dir)),
            ("docs", lambda: generate_documents(job, job_dir)),
            ("compliance", lambda: run_compliance_check(job, job_dir)),
            ("package", lambda: build_package(job_dir)),
        ]
        for key, action in tasks:
            _step(job_id, key, "running")
            action()
            _step(job_id, key, "completed")
        _update(job_id, status="success", progress=100, current_step="生成完成")
    except Exception as exc:
        status = get_job(job_id)
        if status:
            for item in status["steps"]:
                if item["status"] == "running":
                    item["status"] = "failed"
            _update(
                job_id,
                status="failed",
                steps=status["steps"],
                current_step="材料生成失败",
                failed_stage="materials",
                error=f"{type(exc).__name__}: {exc}",
            )
    finally:
        _release_worker_lock(job_id)


def save_planning_version(
    job_id: str,
    planning: Dict[str, Any],
    instruction: str = "",
    summary: str = "",
) -> int:
    versions_dir = OUTPUT_ROOT / job_id / "planning_versions"
    versions_dir.mkdir(parents=True, exist_ok=True)
    version = len(list(versions_dir.glob("v*.json"))) + 1
    _json_write(
        versions_dir / f"v{version}.json",
        {
            "version": version,
            "created_at": _now(),
            "instruction": instruction,
            "summary": summary,
            "planning": planning,
        },
    )
    return version


def reset_job_for_revision(job_id: str) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise ValueError("任务不存在")
    stop_online_demo(job_id)
    job_dir = OUTPUT_ROOT / job_id
    for name in (
        "generated_project",
        ".enhancer_backup",
        "screenshots",
        "docs",
        "logs",
        "copyright_package.zip",
        "generated_project.zip",
        "enhancement.json",
        "run_validation.json",
        "code_stats.json",
        "compliance_report.json",
        "demo_runtime.json",
    ):
        path = job_dir / name
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    for item in job["steps"]:
        if item["key"] != "planning":
            item["status"] = "pending"
    return _update(
        job_id,
        status="regenerating_project",
        progress=10,
        current_step="按修改后的规划重新生成项目",
        steps=job["steps"],
        run_status="pending",
        demo_url=None,
        swagger_url=None,
        error=None,
    )


def generate_planning(job: Dict[str, Any], job_dir: Path) -> None:
    result = build_planning(job)
    planning = result.planning.model_dump()
    planning["planner"] = {
        "model": result.model,
    }
    _json_write(job_dir / "planning.json", planning)
    _update(
        job["job_id"],
        planner_model=result.model,
    )


def _write_planner_diagnostics(job_dir: Path, exc: Exception) -> None:
    if not isinstance(exc, PlannerValidationError):
        return
    diagnostics_dir = job_dir / "planner_diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    (diagnostics_dir / "planner_raw_initial.txt").write_text(
        exc.first_text or "",
        encoding="utf-8",
    )
    (diagnostics_dir / "planner_raw_repair.txt").write_text(
        exc.second_text or "",
        encoding="utf-8",
    )
    _json_write(
        diagnostics_dir / "planner_diagnostics.json",
        {
            "created_at": _now(),
            "error": str(exc),
            "first_error": exc.first_error,
            "second_error": exc.second_error,
            "initial_response_file": "planner_raw_initial.txt",
            "repair_response_file": "planner_raw_repair.txt",
        },
    )


def enhance_generated_project(job: Dict[str, Any], job_dir: Path) -> None:
    planning = _json_read(job_dir / "planning.json")
    result = enhance_project(
        job,
        planning,
        job_dir / "generated_project",
        job_dir / ".enhancer_backup",
    )
    _json_write(job_dir / "enhancement.json", result.model_dump())
    _update(
        job["job_id"],
        codegen_actual_mode=result.actual_mode,
        codegen_model=result.model,
        codegen_summary=result.summary,
        codegen_changed_files=result.changed_files,
        codegen_fallback_reason=result.fallback_reason,
    )


def validate_generated_project(job: Dict[str, Any], job_dir: Path) -> None:
    try:
        run_generated_project(job_dir)
        validation = _json_read(job_dir / "run_validation.json")
        _update(
            job["job_id"],
            run_status=(
                "verified"
                if validation["maven_test"] == "passed"
                else "structure_verified"
            ),
            run_validation=validation,
            demo_url="http://127.0.0.1:9002",
            swagger_url="http://127.0.0.1:9001/swagger-ui/index.html",
        )
    except Exception as exc:
        status = get_job(job["job_id"]) or {}
        if (
            job.get("codegen_mode") == "auto"
            and status.get("codegen_actual_mode") == "llm"
        ):
            restored = restore_enhancement(
                job_dir / "generated_project",
                job_dir / ".enhancer_backup",
            )
            reason = f"{type(exc).__name__}: {str(exc)[:600]}"
            _update(
                job["job_id"],
                codegen_actual_mode="template",
                codegen_fallback_reason=(
                    f"增强代码验证失败，已回滚 {len(restored)} 个文件: "
                    f"{reason}"
                ),
            )
            enhancement = _json_read(job_dir / "enhancement.json")
            enhancement["actual_mode"] = "template"
            enhancement["fallback_reason"] = (
                f"验证失败并回滚: {reason}"
            )
            _json_write(job_dir / "enhancement.json", enhancement)
            run_generated_project(job_dir)
            validation = _json_read(job_dir / "run_validation.json")
            _update(
                job["job_id"],
                run_status=(
                    "verified"
                    if validation["maven_test"] == "passed"
                    else "structure_verified"
                ),
                run_validation=validation,
                demo_url="http://127.0.0.1:9002",
                swagger_url="http://127.0.0.1:9001/swagger-ui/index.html",
            )
            return
        raise


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def generate_project(job_dir: Path) -> None:
    generate_java_project(job_dir)
    return
    planning = _json_read(job_dir / "planning.json")
    root = job_dir / "generated_project"
    frontend = root / "frontend"
    backend = root / "backend"
    name = planning["software_name"]
    modules = planning["modules"]
    _write(
        frontend / "package.json",
        """{
  "name": "copyright-demo-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {"dev": "vite --host 127.0.0.1", "build": "vite build"},
  "dependencies": {"@vitejs/plugin-vue": "^5.2.1", "vite": "^6.0.5", "vue": "^3.5.13"},
  "devDependencies": {}
}""",
    )
    _write(
        frontend / "vite.config.js",
        """import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  root: dirname(fileURLToPath(import.meta.url)),
  plugins: [vue()]
})
""",
    )
    _write(
        frontend / "index.html",
        '<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>'
        + name
        + '</title></head><body><div id="app"></div><script type="module" src="/src/main.js"></script></body></html>',
    )
    _write(
        frontend / "src/main.js",
        """import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
createApp(App).mount('#app')
""",
    )
    module_json = json.dumps(modules, ensure_ascii=False)
    mock_rows = {
        module["key"]: [
            [f"{field}示例一" for field in module["fields"]],
            [f"{field}示例二" for field in module["fields"]],
        ]
        for module in modules
    }
    mock_rows_json = json.dumps(mock_rows, ensure_ascii=False)
    app_vue = """<script setup>
import { computed, ref } from 'vue'
const softwareName = %s
const modules = %s
const active = ref('dashboard')
const loggedIn = ref(false)
const showModal = ref(false)
const rows = %s
const current = computed(() => modules.find(m => m.key === active.value))
</script>
<template>
  <div v-if="!loggedIn" class="login-page">
    <div class="login-brand"><h1>{{softwareName}}</h1><p>业务运营管理平台</p></div>
    <div class="login-card"><h2>欢迎登录</h2><p>请输入管理员账号进入系统</p><label>用户名</label><input value="admin"><label>密码</label><input type="password" value="123456"><button @click="loggedIn=true">登录系统</button><small>演示账号：admin / 123456</small></div>
  </div>
  <div v-else class="shell">
    <aside><h2>{{ softwareName }}</h2><div class="brand-sub">智慧运营中心</div>
      <button :class="{on:active==='dashboard'}" @click="active='dashboard'">运营首页</button>
      <button v-for="m in modules" :key="m.key" :data-module-key="m.key" :class="{on:active===m.key}" @click="active=m.key">{{m.name}}</button>
    </aside>
    <main>
      <header><div><b>{{ active==='dashboard'?'运营首页':current.name }}</b><span>数据更新时间：2026-06-10 10:30</span></div><div class="user">管理员</div></header>
      <section v-if="active==='dashboard'">
        <div class="hero"><div><p>系统运行概览</p><h1>{{softwareName}}运行正常</h1><small>当前已启用 {{modules.length}} 个业务模块</small></div><div class="rate">{{modules.length}}<small>业务模块</small></div></div>
        <div class="cards"><article v-for="(module,index) in modules.slice(0,4)"><span>{{module.name}}</span><b>{{128 + index * 37}}</b><i>数据状态正常</i></article></div>
        <div class="panel"><h3>近七日业务趋势</h3><div class="chart"><i v-for="h in [48,60,52,72,66,84,76]" :style="{height:h+'%%'}"></i></div></div>
      </section>
      <section v-else>
        <div class="toolbar"><div><h2>{{current.name}}</h2><p>{{current.description || ('统一维护'+current.name+'相关业务数据')}}</p></div><button class="primary" @click="showModal=true">+ 新增记录</button></div>
        <div class="filters"><input placeholder="请输入关键字搜索"><button>查询</button><button>重置</button></div>
        <div class="panel table"><table><thead><tr><th>序号</th><th v-for="f in current.fields">{{f}}</th><th>操作</th></tr></thead><tbody><tr v-for="(row,i) in rows[active]"><td>{{i+1}}</td><td v-for="cell in row">{{cell}}</td><td><a>编辑</a><a>详情</a></td></tr></tbody></table></div>
      </section>
    </main>
    <div v-if="showModal" class="modal-mask"><div class="modal"><h2>新增{{current.name}}记录</h2><p>请填写以下业务信息</p><label v-for="field in current.fields">{{field}}<input :placeholder="'请输入'+field"></label><div><button @click="showModal=false">取消</button><button class="primary" @click="showModal=false">保存</button></div></div></div>
  </div>
</template>
""" % (json.dumps(name, ensure_ascii=False), module_json, mock_rows_json)
    _write(frontend / "src/App.vue", app_vue)
    _write(
        frontend / "src/style.css",
        """*{box-sizing:border-box}body{margin:0;font-family:"Microsoft YaHei",Arial;color:#1f2d3d;background:#f3f6fb}.login-page{min-height:100vh;background:linear-gradient(120deg,#0d3268,#2186c9);display:flex;align-items:center;justify-content:center;gap:130px;color:white}.login-brand h1{font-size:38px;margin:0 0 10px}.login-brand p{opacity:.7;letter-spacing:4px}.login-card{width:380px;background:white;color:#24354b;padding:38px;border-radius:14px;box-shadow:0 22px 60px #06224655}.login-card h2{margin:0}.login-card p,.login-card small{color:#8b98a9}.login-card label,.modal label{display:block;font-size:13px;margin:18px 0 7px}.login-card input,.modal input{width:100%;padding:11px;border:1px solid #d6dfeb;border-radius:6px}.login-card button{width:100%;padding:12px;margin:22px 0 14px;border:0;border-radius:6px;background:#176bc1;color:white}.shell{display:flex;min-height:100vh}aside{width:230px;background:linear-gradient(180deg,#123b73,#0a2750);color:white;padding:25px 16px}aside h2{font-size:20px;margin:0 8px 4px}.brand-sub{font-size:12px;opacity:.6;margin:0 8px 28px}aside button{display:block;width:100%;border:0;background:transparent;color:#cbd8ea;text-align:left;padding:13px 16px;margin:4px 0;border-radius:7px;font-size:14px;cursor:pointer}aside button.on,aside button:hover{background:#1d579c;color:white}main{flex:1}header{height:68px;background:white;display:flex;justify-content:space-between;align-items:center;padding:0 30px;border-bottom:1px solid #e7ecf3}header b{font-size:18px}header span{font-size:12px;color:#8795a8;margin-left:20px}.user{background:#edf4ff;color:#2868b2;padding:8px 15px;border-radius:18px}section{padding:24px 30px}.hero{background:linear-gradient(120deg,#1769c2,#25a2d8);color:white;border-radius:12px;padding:28px 35px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 10px 24px #1d72b533}.hero p{margin:0}.hero h1{margin:8px 0;font-size:27px}.hero small{opacity:.8}.rate{font-size:36px;font-weight:bold;text-align:center}.rate small{display:block;font-size:13px;font-weight:normal}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin:20px 0}.cards article,.panel{background:white;border-radius:10px;padding:22px;box-shadow:0 3px 12px #193b6010}.cards span{display:block;color:#7f8da0}.cards b{display:block;font-size:28px;margin:12px 0}.cards i{font-style:normal;color:#3d9b72;font-size:12px}.panel h3{margin:0}.chart{height:210px;display:flex;align-items:flex-end;gap:34px;padding:30px 45px 0;border-bottom:1px solid #dfe6ef}.chart i{flex:1;background:linear-gradient(#51a6e8,#1970c4);border-radius:5px 5px 0 0}.toolbar{display:flex;justify-content:space-between;align-items:center}.toolbar h2{margin:0}.toolbar p{color:#8795a8}.primary{background:#176bc1!important;color:white;border:0!important}.toolbar button,.filters button{padding:10px 18px;border:1px solid #d7e0eb;border-radius:5px;background:white}.filters{background:white;padding:18px;margin:16px 0;border-radius:8px}.filters input{width:280px;padding:10px;border:1px solid #d7e0eb;border-radius:5px;margin-right:10px}.table{padding:0;overflow:hidden}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:16px;border-bottom:1px solid #edf0f4}th{background:#f8fafc;color:#657489}td a{color:#176bc1;margin-right:14px;font-size:13px}.modal-mask{position:fixed;inset:0;background:#10243d88;display:grid;place-items:center}.modal{width:480px;background:white;border-radius:12px;padding:28px;box-shadow:0 20px 60px #10243d55}.modal h2{margin:0}.modal p{color:#8290a2}.modal>div{text-align:right;margin-top:22px}.modal>div button{padding:10px 22px;margin-left:10px;border:1px solid #d8e0ea;background:white;border-radius:6px}""",
    )
    _write(
        backend / "requirements.txt",
        "fastapi==0.115.6\nuvicorn[standard]==0.32.1",
    )
    route_definitions = []
    schema_statements = []
    database_tables = planning["database_tables"]
    for index, module in enumerate(modules):
        key = module["key"]
        table_name = database_tables[index % len(database_tables)]
        route_definitions.append(
            f'''
@app.get("/api/{key}")
def list_{key}():
    return rows("{table_name}")

@app.post("/api/{key}")
def create_{key}(payload: dict):
    return {{"id": 3, **payload}}
'''
        )
    for index, table_name in enumerate(database_tables):
        module = modules[index % len(modules)]
        columns = ", ".join(
            f"field_{field_index} TEXT"
            for field_index, _ in enumerate(module["fields"], start=1)
        )
        schema_statements.append(
            f"CREATE TABLE IF NOT EXISTS {table_name} (id INTEGER PRIMARY KEY, {columns});"
        )
        for row_index in range(1, 3):
            values = [
                f"{field}示例{'一' if row_index == 1 else '二'}"
                for field in module["fields"]
            ]
            sql_values = ", ".join(
                "'" + value.replace("'", "''") + "'" for value in values
            )
            schema_statements.append(
                f"INSERT INTO {table_name} VALUES ({row_index}, {sql_values});"
            )
    routes_code = "\n".join(route_definitions)
    schema_sql = "\n".join(schema_statements)
    _write(
        backend / "main.py",
        """import sqlite3
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title=%s)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DB = Path(__file__).with_name("app.db")

def rows(table):
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute("select * from " + table)]

@app.get("/api/health")
def health(): return {"status": "ok"}

@app.get("/api/dashboard")
def dashboard():
    return {"module_count": %s, "status": "running", "today_records": 328, "completion_rate": 78.6}

%s
""" % (json.dumps(name, ensure_ascii=False), len(modules), routes_code),
    )
    _write(backend / "schema.sql", schema_sql)
    with __import__("sqlite3").connect(backend / "app.db") as conn:
        conn.executescript((backend / "schema.sql").read_text(encoding="utf-8"))
    _write(
        root / "README.md",
        f"""# {name}

本项目由 AI软著工厂 Phase 3 生成，基础结构来自固定模板，并可经过受约束的 AI 代码增强。

## 后端
```powershell
cd "{(root / 'backend').resolve()}"
python -m pip install -r requirements.txt
python -m uvicorn main:app --port 9001
```

## 前端
```powershell
cd "{(root / 'frontend').resolve()}"
npm.cmd install
npm.cmd run dev -- --port 9002
```
""",
    )


def _wait_port(port: int, timeout: int = 30) -> None:
    started = time.time()
    while time.time() - started < timeout:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.4)
    raise RuntimeError(f"端口 {port} 启动超时")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _terminate_pid(pid: Optional[int]) -> None:
    if not pid:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                timeout=15,
            )
        else:
            os.kill(pid, 15)
    except (OSError, subprocess.SubprocessError):
        pass


def _port_open(port: Optional[int]) -> bool:
    if not port:
        return False
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", int(port))) == 0


def _java_sources_mtime(backend: Path) -> float:
    sources = list((backend / "src").rglob("*.java")) if (backend / "src").exists() else []
    pom = backend / "pom.xml"
    latest = pom.stat().st_mtime if pom.exists() else 0
    for path in sources:
        latest = max(latest, path.stat().st_mtime)
    return latest


def _find_existing_jar(backend: Path) -> Optional[Path]:
    target = backend / "target"
    if not target.exists():
        return None
    jars = sorted(
        (p for p in target.glob("*.jar") if not p.name.endswith(".original")),
        key=lambda p: p.stat().st_mtime,
    )
    return jars[-1] if jars else None


def _launch_demo(
    job_id: str,
    job_dir: Path,
    backend_port: int,
    frontend_port: int,
) -> Tuple[subprocess.Popen, subprocess.Popen, str]:
    project = job_dir / "generated_project"
    backend = project / "backend"
    frontend = project / "frontend"
    maven = _maven_command()
    if not maven:
        raise RuntimeError("未找到 Maven，无法启动 Spring Boot Demo")
    maven_version = _maven_version(maven)

    logs = job_dir / "logs"
    logs.mkdir(exist_ok=True)
    build_log_path = logs / "demo_build.log"

    # 复用已经构建的 JAR：源代码/POM 没更新就不重跑 mvn
    existing_jar = _find_existing_jar(backend)
    src_mtime = _java_sources_mtime(backend)
    if existing_jar and existing_jar.stat().st_mtime >= src_mtime:
        _set_demo_stage(
            job_id,
            stage="building",
            stage_detail="复用已构建的 JAR，跳过 mvn package",
            maven_version=maven_version,
            jar_reused=True,
        )
        jars = [existing_jar]
    else:
        _set_demo_stage(
            job_id,
            stage="building",
            stage_detail="正在执行 mvn package -DskipTests",
            maven_version=maven_version,
            jar_reused=False,
        )
        with open(build_log_path, "a", encoding="utf-8") as build_log:
            build_log.write(f"\n===== mvn package @ {_now()} =====\n")
            mvn_env = _maven_subprocess_env()
            package_result = subprocess.run(
                [maven, "package", "-DskipTests"],
                cwd=str(backend),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
                env=mvn_env,
            )
            build_log.write(package_result.stdout or "")
            if package_result.stderr:
                build_log.write("\n--- stderr ---\n")
                build_log.write(package_result.stderr)
            build_log.write(f"\nexit={package_result.returncode}\n")
        if package_result.returncode != 0:
            detail = (package_result.stderr or package_result.stdout)[-1500:]
            raise RuntimeError("Spring Boot JAR 构建失败: " + detail)
        jars = sorted(
            path
            for path in (backend / "target").glob("*.jar")
            if not path.name.endswith(".original")
        )
        if not jars:
            raise RuntimeError("Maven 构建完成但未找到可执行 JAR")

    _set_demo_stage(
        job_id,
        stage="starting",
        stage_detail="正在启动 Spring Boot 与 Vite",
    )
    backend_output = open(logs / "backend.log", "a", encoding="utf-8")
    frontend_output = open(logs / "frontend.log", "a", encoding="utf-8")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    backend_process = subprocess.Popen(
        [
            shutil.which("java") or "java",
            "-jar",
            str(jars[-1]),
            "--spring.profiles.active=demo",
            f"--server.port={backend_port}",
        ],
        cwd=str(backend),
        stdout=backend_output,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    frontend_env = os.environ.copy()
    frontend_env["VITE_BACKEND_TARGET"] = f"http://127.0.0.1:{backend_port}"
    frontend_process = subprocess.Popen(
        [_npm_command(), "run", "dev", "--", "--port", str(frontend_port)],
        cwd=str(frontend),
        stdout=frontend_output,
        stderr=subprocess.STDOUT,
        env=frontend_env,
        creationflags=creationflags,
    )
    backend_output.close()
    frontend_output.close()
    try:
        _wait_port(backend_port, 90)
        _wait_port(frontend_port, 40)
    except Exception:
        _terminate_pid(backend_process.pid)
        _terminate_pid(frontend_process.pid)
        raise
    return backend_process, frontend_process, maven_version


def stop_online_demo(job_id: str) -> Dict[str, Any]:
    runtime_path = OUTPUT_ROOT / job_id / "demo_runtime.json"
    if not runtime_path.exists():
        return {"status": "stopped", "stage": "stopped"}
    runtime = _json_read(runtime_path)
    if _port_open(runtime.get("backend_port")):
        _terminate_pid(runtime.get("backend_pid"))
    if _port_open(runtime.get("frontend_port")):
        _terminate_pid(runtime.get("frontend_pid"))
    runtime["status"] = "stopped"
    runtime["stage"] = "stopped"
    runtime["stopped_at"] = _now()
    _json_write(runtime_path, runtime)
    _update(job_id, run_status="stopped")
    return runtime


def start_online_demo(job: Dict[str, Any], job_dir: Path) -> Dict[str, Any]:
    stop_online_demo(job["job_id"])
    # 立刻写入 starting 状态，让前端轮询时能区分 "正在启动"
    # 与"已停止"，并展示当前 stage。
    initial_runtime = {
        "status": "starting",
        "stage": "queued",
        "stage_detail": "排队中…",
        "started_at": _now(),
        "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(
            timespec="seconds"
        ),
    }
    _json_write(job_dir / "demo_runtime.json", initial_runtime)
    _update(job["job_id"], run_status="starting")

    backend_port = _free_port()
    frontend_port = _free_port()
    backend_process, frontend_process, maven_version = _launch_demo(
        job["job_id"],
        job_dir,
        backend_port,
        frontend_port,
    )
    runtime = {
        "status": "running",
        "stage": "running",
        "stage_detail": "Demo 已就绪",
        "maven_version": maven_version,
        "backend_pid": backend_process.pid,
        "frontend_pid": frontend_process.pid,
        "backend_port": backend_port,
        "frontend_port": frontend_port,
        "demo_url": f"http://127.0.0.1:{frontend_port}",
        "swagger_url": f"http://127.0.0.1:{backend_port}/swagger-ui/index.html",
        "started_at": _now(),
        "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(timespec="seconds"),
    }
    _json_write(job_dir / "demo_runtime.json", runtime)
    _update(
        job["job_id"],
        run_status="running",
        demo_url=runtime["demo_url"],
        swagger_url=runtime["swagger_url"],
    )
    return runtime


def demo_runtime(job_id: str) -> Dict[str, Any]:
    path = OUTPUT_ROOT / job_id / "demo_runtime.json"
    if not path.exists():
        return {"status": "stopped"}
    runtime = _json_read(path)
    expires_at = runtime.get("expires_at")
    if runtime.get("status") == "running" and expires_at:
        if datetime.now() >= datetime.fromisoformat(expires_at):
            return stop_online_demo(job_id)
        if not (
            _port_open(runtime.get("backend_port"))
            and _port_open(runtime.get("frontend_port"))
        ):
            runtime["status"] = "stopped"
            runtime["stopped_at"] = _now()
            runtime["stop_reason"] = "Demo 进程已退出"
            _json_write(path, runtime)
            _update(job_id, run_status="stopped")
    return runtime


def _npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def _maven_command() -> Optional[str]:
    """选择 Maven 可执行文件。

    优先使用 IntelliJ 自带 mvn.cmd（与生成项目兼容性好、避免 PluginContainerException），
    其次才回退到系统 PATH 中的 mvn。
    """
    if os.name == "nt":
        candidates = [
            Path(r"C:\Program Files\JetBrains\IntelliJ IDEA 2025.1\plugins\maven\lib\maven3\bin\mvn.cmd"),
            Path(r"C:\Program Files\JetBrains\IntelliJ IDEA 2024.1\plugins\maven\lib\maven3\bin\mvn.cmd"),
            Path(r"C:\Program Files\JetBrains\IntelliJ IDEA 2023.1\plugins\maven\lib\maven3\bin\mvn.cmd"),
        ]
        found = next((path for path in candidates if path.exists()), None)
        if found:
            return str(found)
    command = shutil.which("mvn.cmd" if os.name == "nt" else "mvn")
    return command


def _maven_subprocess_env() -> Dict[str, str]:
    """构造调用 mvn 时的环境变量。

    IntelliJ 自带 mvn.cmd 内部默认走 Java 8 启动器，但生成项目依赖 mybatis-spring-3.0.3+
    已经是 Java 17 字节码（version 61.0）。Java 8 无法读取 61.0 类文件，编译会报
    "类文件具有的版本 61.0, 应为 52.0"。

    解决：自动探测本机 JDK 17（系统安装/IntelliJ 自带 JBR），并把 JAVA_HOME 指向它，
    这样 mvn 会用 Java 17 跑 javac 编译，避免版本不匹配。
    """
    env = os.environ.copy()
    if os.name != "nt":
        return env
    candidates = [
        Path(r"D:\Program Files\Java\jdk-17"),
        Path(r"C:\Program Files\Java\jdk-17"),
        Path(r"D:\Program Files\JetBrains\IntelliJ IDEA 2023.1\jbr"),
        Path(r"C:\Program Files\JetBrains\IntelliJ IDEA 2023.1\jbr"),
    ]
    java17 = next((p for p in candidates if (p / "bin" / "java.exe").exists()), None)
    if java17:
        env["JAVA_HOME"] = str(java17)
        env["PATH"] = f"{java17}\\bin;{env.get('PATH', '')}"
    return env


def _maven_version(maven: str) -> str:
    try:
        result = subprocess.run(
            [maven, "-v"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired) as exc:
        return f"{maven} (version unknown: {type(exc).__name__})"
    text = (result.stdout or result.stderr or "").strip()
    return text.splitlines()[0] if text else maven


def run_generated_project(job_dir: Path) -> None:
    project = job_dir / "generated_project"
    frontend = project / "frontend"
    backend = project / "backend"
    validation = {
        "frontend_build": "pending",
        "backend_structure": "pending",
        "maven_test": "unavailable",
        "maven_reason": None,
    }
    install = subprocess.run(
        [_npm_command(), "install", "--no-audit", "--no-fund"],
        cwd=str(frontend),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    if install.returncode != 0:
        raise RuntimeError("前端依赖安装失败: " + install.stderr[-500:])
    build = subprocess.run(
        [_npm_command(), "run", "build"],
        cwd=str(frontend),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if build.returncode != 0:
        detail = (build.stderr or build.stdout)[-1000:]
        raise RuntimeError("前端构建失败: " + detail)
    validation["frontend_build"] = "passed"

    required = [
        backend / "pom.xml",
        backend / "src/main/resources/application.yml",
        project / "sql/init.sql",
    ]
    java_files = list((backend / "src/main/java").rglob("*.java"))
    if any(not path.exists() for path in required) or not java_files:
        raise RuntimeError("Java 项目结构不完整")
    validation["backend_structure"] = "passed"

    maven = _maven_command()
    wrapper = backend / ("mvnw.cmd" if os.name == "nt" else "mvnw")
    command = [maven, "test"] if maven else ([str(wrapper), "test"] if wrapper.exists() else None)
    if command:
        result = subprocess.run(
            command,
            cwd=str(backend),
            env=_maven_subprocess_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout)[-1500:]
            raise RuntimeError("Maven 测试失败: " + detail)
        validation["maven_test"] = "passed"
    else:
        validation["maven_reason"] = "当前主机未安装 Maven，且生成项目中没有可用 Maven Wrapper"
    _json_write(job_dir / "run_validation.json", validation)


def _edge_path() -> Optional[str]:
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    return str(next((path for path in candidates if path.exists()), "")) or None


def _safe_filename(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "-", value).strip(" .") or "page"


def capture_screenshots(job_dir: Path) -> None:
    from playwright.sync_api import sync_playwright

    planning = _json_read(job_dir / "planning.json")
    screenshot_modules = planning["modules"]
    screenshot_dir = job_dir / "screenshots"
    screenshot_dir.mkdir(exist_ok=True)
    runtime_path = job_dir / "demo_runtime.json"
    runtime = _json_read(runtime_path) if runtime_path.exists() else {}
    borrowed_demo = (
        runtime.get("status") == "running"
        and _port_open(runtime.get("backend_port"))
        and _port_open(runtime.get("frontend_port"))
    )
    backend_process = None
    frontend_process = None
    if borrowed_demo:
        frontend_port = int(runtime["frontend_port"])
    else:
        backend_port = _free_port()
        frontend_port = _free_port()
        job_id = job_dir.name
        backend_process, frontend_process, _ = _launch_demo(
            job_id,
            job_dir,
            backend_port,
            frontend_port,
        )
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, executable_path=_edge_path())
            page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
            page.goto(f"http://127.0.0.1:{frontend_port}", wait_until="networkidle")
            page.screenshot(path=str(screenshot_dir / "01-login.png"), full_page=True)
            page.locator(".login-card button").click()
            page.screenshot(path=str(screenshot_dir / "02-dashboard.png"), full_page=True)
            index = 3
            for module in screenshot_modules:
                label = module["name"]
                page.locator(f'[data-module-key="{module["key"]}"]').click()
                page.wait_for_timeout(250)
                safe_label = _safe_filename(label)
                page.screenshot(
                    path=str(screenshot_dir / f"{index:02d}-{safe_label}.png"),
                    full_page=True,
                )
                index += 1
                if index == 4:
                    page.locator('[data-action="create"]').click()
                    page.screenshot(
                        path=str(screenshot_dir / f"{index:02d}-{safe_label}-form.png"),
                        full_page=True,
                    )
                    page.locator(".el-dialog__footer button").first.click()
                    index += 1
            browser.close()
    finally:
        if not borrowed_demo:
            _terminate_pid(backend_process.pid if backend_process else None)
            _terminate_pid(frontend_process.pid if frontend_process else None)


CODE_EXTENSIONS = {".java", ".xml", ".yml", ".yaml", ".vue", ".js", ".ts", ".html", ".css", ".sql"}
EXCLUDED = {"node_modules", "dist", "venv", ".git", "__pycache__"}


def _source_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in CODE_EXTENSIONS:
            if not any(part in EXCLUDED for part in path.parts):
                yield path


def analyze_code(job_dir: Path) -> None:
    root = job_dir / "generated_project"
    stats = {"total_lines": 0, "frontend_lines": 0, "backend_lines": 0, "sql_lines": 0, "files": []}
    for path in _source_files(root):
        lines = len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
        relative = path.relative_to(root).as_posix()
        stats["total_lines"] += lines
        if relative.startswith("frontend/"):
            stats["frontend_lines"] += lines
        if relative.startswith("backend/"):
            stats["backend_lines"] += lines
        if path.suffix == ".sql":
            stats["sql_lines"] += lines
        stats["files"].append({"path": relative, "lines": lines})
    _json_write(job_dir / "code_stats.json", stats)


def _set_cell_text_font(run: Any, font_name: str, size: int) -> None:
    run.font.name = font_name
    run.font.size = Pt(size)
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font_name)


def _add_page_number(paragraph: Any) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    run._r.append(field)


def _setup_doc(document: Document, title: str) -> None:
    section = document.sections[0]
    section.top_margin = Cm(1.8)
    section.bottom_margin = Cm(1.8)
    section.left_margin = Cm(2)
    section.right_margin = Cm(2)
    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_cell_text_font(header.add_run(title), "宋体", 9)
    _add_page_number(section.footer.paragraphs[0])


def _apply_document_template(document: Document, template: str) -> None:
    style = document.styles["Normal"]
    if template == "compact":
        style.font.size = Pt(9)
        style.paragraph_format.line_spacing = 1.15
    elif template == "formal":
        style.font.size = Pt(11)
        style.paragraph_format.line_spacing = 1.75
    else:
        style.font.size = Pt(10)
        style.paragraph_format.line_spacing = 1.5


def generate_source_document(job_dir: Path) -> None:
    planning = _json_read(job_dir / "planning.json")
    root = job_dir / "generated_project"
    code_lines: List[Tuple[str, str]] = []
    for path in _source_files(root):
        relative = path.relative_to(root).as_posix()
        code_lines.append((relative, f"// ===== {relative} ====="))
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            code_lines.append((relative, line))
    max_lines = 60 * 50
    if len(code_lines) > max_lines:
        code_lines = code_lines[:1500] + code_lines[-1500:]
    document = Document()
    _setup_doc(document, planning["software_name"] + " 源代码材料")
    style = document.styles["Normal"]
    style.paragraph_format.space_after = Pt(0)
    style.paragraph_format.line_spacing = 1
    for _, line in code_lines:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(0)
        _set_cell_text_font(paragraph.add_run(line or " "), "Courier New", 7)
    docs = job_dir / "docs"
    docs.mkdir(exist_ok=True)
    document.save(docs / "源代码材料.docx")


def _title(document: Document, text: str, subtitle: str) -> None:
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(120)
    _set_cell_text_font(paragraph.add_run(text), "黑体", 24)
    sub = document.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_cell_text_font(sub.add_run(subtitle), "宋体", 14)
    document.add_page_break()


def _heading(document: Document, text: str, level: int = 1) -> None:
    paragraph = document.add_heading(text, level=level)
    for run in paragraph.runs:
        _set_cell_text_font(run, "黑体", 16 if level == 1 else 13)


def _body(document: Document, text: str) -> None:
    paragraph = document.add_paragraph(text)
    paragraph.paragraph_format.first_line_indent = Cm(0.74)
    paragraph.paragraph_format.line_spacing = 1.5
    for run in paragraph.runs:
        _set_cell_text_font(run, "宋体", 10)


def _add_info_table(document: Document, rows: List[Tuple[str, str]]) -> None:
    table = document.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for label, value in rows:
        cells = table.add_row().cells
        cells[0].text = label
        cells[1].text = value
        for index, cell in enumerate(cells):
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    _set_cell_text_font(run, "黑体" if index == 0 else "宋体", 10)


def generate_documents(job: Dict[str, Any], job_dir: Path) -> None:
    planning = _json_read(job_dir / "planning.json")
    stats = _json_read(job_dir / "code_stats.json")
    name = planning["software_name"]
    docs_dir = job_dir / "docs"
    screenshots = sorted((job_dir / "screenshots").glob("*.png"))
    document_template = job.get("document_template", "standard")

    design = Document()
    _setup_doc(design, name + " 设计说明书")
    _apply_document_template(design, document_template)
    _title(design, name, "软件设计说明书")
    _heading(design, "1 项目概述")
    _body(design, planning["description"])
    _body(design, f"本系统采用前后端分离架构，包含 {len(planning['modules'])} 个业务模块，实际源码共 {stats['total_lines']} 行。")
    _heading(design, "2 总体设计")
    _body(design, "前端采用 Vue 3、Element Plus 与 Vite，后端采用 Java 17、Spring Boot 3 和 MyBatis Plus，生产数据使用 MySQL 存储。系统通过 REST API 完成页面与业务数据交互。")
    _heading(design, "3 功能设计")
    for index, module in enumerate(planning["modules"], start=1):
        _heading(design, f"3.{index} {module['name']}", 2)
        _body(design, f"{module.get('description') or module['name']}。包含页面：{'、'.join(module['pages'])}。主要数据字段：{'、'.join(module['fields'])}。")
    _heading(design, "4 数据与接口设计")
    _body(design, "数据库表包括：" + "、".join(planning["database_tables"]) + "。")
    for api in planning["api_list"]:
        _body(design, api)
    design.save(docs_dir / "设计说明书.docx")

    manual = Document()
    _setup_doc(manual, name + " 用户操作手册")
    _apply_document_template(manual, document_template)
    _title(manual, name, "用户操作手册")
    _heading(manual, "1 系统简介")
    _body(manual, planning["description"])
    _body(manual, "目标用户：" + planning.get("target_users", "系统业务管理人员") + "。")
    _heading(manual, "2 运行环境")
    _body(manual, "使用现代浏览器访问系统。开发环境后端地址为 http://127.0.0.1:9001，前端地址为 http://127.0.0.1:9002。")
    _heading(manual, "3 功能操作")
    for index, module in enumerate(planning["modules"], start=1):
        _heading(manual, f"3.{index} {module['name']}", 2)
        _body(manual, f"在左侧菜单选择“{module['name']}”，可进入{'、'.join(module['pages'])}等页面，查看或维护{'、'.join(module['fields'])}。")
        matching = next((shot for shot in screenshots if module["name"] in shot.name), None)
        if matching:
            manual.add_picture(str(matching), width=Cm(15.5))
            manual.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    manual.save(docs_dir / "用户操作手册.docx")

    application = Document()
    _setup_doc(application, name + " 软件著作权申请信息表")
    _apply_document_template(application, document_template)
    _title(application, name, "软件著作权申请信息表")
    _heading(application, "1 软件基本信息")
    _add_info_table(
        application,
        [
            ("软件全称", name),
            ("软件简称", name.replace("系统", "")[:20]),
            ("版本号", job.get("version", "V1.0")),
            ("软件分类", planning["software_type"]),
            ("开发完成日期", job.get("completion_date", "")),
            ("发表状态", job.get("publication_status", "未发表")),
            ("著作权人", job.get("applicant_name", "待填写")),
            ("开发方式", "独立开发"),
            ("源程序量", f"{stats['total_lines']} 行"),
        ],
    )
    _heading(application, "2 软件功能与技术特点")
    _body(application, planning["description"])
    _body(
        application,
        "主要功能模块包括：" + "、".join(module["name"] for module in planning["modules"]) + "。",
    )
    _body(
        application,
        "技术架构采用 Vue 3、Element Plus、Java 17、Spring Boot 3、MyBatis Plus 与 MySQL，实现前后端分离和业务数据持久化。",
    )
    _heading(application, "3 提交前确认")
    _body(application, "本表由系统根据 planning.json 和真实源码统计自动生成。著作权人、版本号、开发完成日期等申请主体信息应在正式提交前人工复核。")
    application.save(docs_dir / "软件著作权申请信息表.docx")


def run_compliance_check(job: Dict[str, Any], job_dir: Path) -> None:
    report = build_compliance_report(job_dir)
    _json_write(job_dir / "compliance_report.json", report)

    document = Document()
    planning = _json_read(job_dir / "planning.json")
    _setup_doc(document, planning["software_name"] + " 合规检查报告")
    _apply_document_template(document, job.get("document_template", "standard"))
    _title(document, planning["software_name"], "软著材料合规检查报告")
    _heading(document, "1 模拟评分")
    _body(
        document,
        f"综合得分：{report['score']}/{report['max_score']}，评级：{report['grade']}，"
        f"检查结论：{'通过' if report['passed'] else '需整改'}。",
    )
    _heading(document, "2 检查明细")
    table = document.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    headers = ["检查项", "结果", "得分", "说明"]
    for cell, value in zip(table.rows[0].cells, headers):
        cell.text = value
    for item in report["items"]:
        cells = table.add_row().cells
        cells[0].text = item["name"]
        cells[1].text = "通过" if item["passed"] else "不通过"
        cells[2].text = f"{item['points']}/{item['max_points']}"
        cells[3].text = item["detail"]
    _heading(document, "3 整改建议")
    if report["suggestions"]:
        for index, suggestion in enumerate(report["suggestions"], start=1):
            _body(document, f"{index}. {suggestion}")
    else:
        _body(document, "未发现需要整改的关键问题。正式提交前仍应人工核对申请主体、版本号和日期。")
    document.save(job_dir / "docs" / "软著材料合规检查报告.docx")
    _update(
        job["job_id"],
        compliance_score=report["score"],
        compliance_grade=report["grade"],
        compliance_passed=report["passed"],
    )


def _zip_dir(source: Path, target: Path, base: Optional[Path] = None) -> None:
    base = base or source
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file() and not any(
                part in {"node_modules", "target", "dist", "__pycache__"}
                for part in path.parts
            ):
                archive.write(path, path.relative_to(base))


def build_package(job_dir: Path) -> None:
    generated_zip = job_dir / "generated_project.zip"
    _zip_dir(job_dir / "generated_project", generated_zip, job_dir / "generated_project")
    readme = job_dir / "README_软著材料说明.md"
    planning = _json_read(job_dir / "planning.json")
    stats = _json_read(job_dir / "code_stats.json")
    _write(
        readme,
        f"""# {planning['software_name']} 软著材料说明

- 生成时间：{_now()}
- 真实源码总行数：{stats['total_lines']}
- 前端代码行数：{stats['frontend_lines']}
- 后端代码行数：{stats['backend_lines']}
- SQL 代码行数：{stats['sql_lines']}

材料由任务规划、固定模板和可选 AI 代码增强自动生成，文档功能范围与 planning.json 保持一致。
代码增强详情见 enhancement.json。
""",
    )
    package = job_dir / "copyright_package.zip"
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(generated_zip, generated_zip.name)
        archive.write(job_dir / "planning.json", "planning.json")
        if (job_dir / "enhancement.json").exists():
            archive.write(job_dir / "enhancement.json", "enhancement.json")
        archive.write(job_dir / "code_stats.json", "code_stats.json")
        if (job_dir / "compliance_report.json").exists():
            archive.write(job_dir / "compliance_report.json", "compliance_report.json")
        archive.write(readme, readme.name)
        for path in sorted((job_dir / "docs").glob("*.docx")):
            archive.write(path, path.name)
        for path in sorted((job_dir / "screenshots").glob("*.png")):
            archive.write(path, f"screenshots/{path.name}")
