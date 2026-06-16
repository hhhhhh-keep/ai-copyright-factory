"""ISSUE-008 L1：worker 锁、interrupted 状态扫描、resume 接口的测试。"""

import json
import multiprocessing
import os
import shutil
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.workflow import (
    INTERRUPT_AGE_SECONDS,
    INTERRUPTED_STATUS,
    OUTPUT_ROOT,
    _acquire_worker_lock,
    _is_job_orphaned,
    _json_read,
    _json_write,
    _now,
    _pid_alive,
    _release_worker_lock,
    _worker_lock_path,
    create_job,
    resume_job,
    scan_for_interrupted_jobs,
)


class WorkerLockTests(unittest.TestCase):
    """worker.lock 文件读写与 PID 活性检查。"""

    def setUp(self):
        self.tmp = OUTPUT_ROOT / "_test_lock"
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pid_alive_for_self(self):
        self.assertTrue(_pid_alive(os.getpid()))

    def test_pid_alive_for_zero(self):
        self.assertFalse(_pid_alive(0))

    def test_pid_alive_for_none(self):
        self.assertFalse(_pid_alive(None))

    def test_pid_alive_for_dead_pid(self):
        # 用一个不太可能存在的 PID
        self.assertFalse(_pid_alive(999999))

    def test_acquire_writes_lock_file(self):
        with patch("app.workflow.OUTPUT_ROOT", self.tmp):
            lock = _acquire_worker_lock("job-1", "run_job")
            self.assertEqual(lock["pid"], os.getpid())
            self.assertEqual(lock["task"], "run_job")
            self.assertIn("started_at", lock)
            # 文件落盘（仍在 patch 块内，路径解析使用 patched OUTPUT_ROOT）
            self.assertTrue(_worker_lock_path("job-1").exists())

    def test_acquire_rejects_when_locked_by_alive_process(self):
        with patch("app.workflow.OUTPUT_ROOT", self.tmp):
            _acquire_worker_lock("job-2", "run_job")
            # 同一 job_id 再获取应该抛错（因为当前进程的 PID 仍活跃）
            with self.assertRaises(RuntimeError):
                _acquire_worker_lock("job-2", "run_job")

    def test_acquire_overrides_dead_lock(self):
        with patch("app.workflow.OUTPUT_ROOT", self.tmp):
            _acquire_worker_lock("job-3", "run_job")
            # 把 lock 写成一个已死的 PID
            dead = {"pid": 999999, "task": "x", "started_at": _now()}
            _json_write(_worker_lock_path("job-3"), dead)
            # 再次获取应该成功（旧的 dead PID 被覆盖）
            lock = _acquire_worker_lock("job-3", "run_job")
            self.assertEqual(lock["pid"], os.getpid())

    def test_release_removes_file(self):
        with patch("app.workflow.OUTPUT_ROOT", self.tmp):
            _acquire_worker_lock("job-4", "run_job")
            self.assertTrue(_worker_lock_path("job-4").exists())
            _release_worker_lock("job-4")
            self.assertFalse(_worker_lock_path("job-4").exists())


class IsJobOrphanedTests(unittest.TestCase):
    """_is_job_orphaned 判定逻辑。"""

    def setUp(self):
        self.tmp = OUTPUT_ROOT / "_test_orphan"
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_status(self, job_id, **overrides):
        base = {
            "job_id": job_id,
            "status": "generating",
            "updated_at": _now(),
            "steps": [],
        }
        base.update(overrides)
        return base

    def test_success_not_orphaned(self):
        self.assertFalse(
            _is_job_orphaned(self._make_status("j1", status="success"))
        )

    def test_failed_not_orphaned(self):
        self.assertFalse(
            _is_job_orphaned(self._make_status("j1", status="failed"))
        )

    def test_draft_planning_not_orphaned(self):
        self.assertFalse(
            _is_job_orphaned(self._make_status("j1", status="draft_planning"))
        )

    def test_awaiting_demo_review_not_orphaned(self):
        # 长时间不动也不自动标 interrupted（用户可能离开浏览器）
        self.assertFalse(
            _is_job_orphaned(
                self._make_status("j1", status="awaiting_demo_review")
            )
        )

    def test_interrupted_already_not_re_marked(self):
        self.assertFalse(
            _is_job_orphaned(
                self._make_status("j1", status=INTERRUPTED_STATUS)
            )
        )

    def test_recent_generating_not_orphaned(self):
        with patch("app.workflow.OUTPUT_ROOT", self.tmp):
            self.assertFalse(
                _is_job_orphaned(self._make_status("j1", status="generating"))
            )

    def test_old_confirmed_is_orphaned(self):
        # confirmed 状态 10 分钟前的 updated_at → 视为中断
        old = (datetime.now() - timedelta(seconds=INTERRUPT_AGE_SECONDS["confirmed"] + 60)).isoformat(timespec="seconds")
        self.assertTrue(
            _is_job_orphaned(
                self._make_status("j1", status="confirmed", updated_at=old)
            )
        )

    def test_old_generating_with_dead_lock_is_orphaned(self):
        # 写入一个已死 PID 的 lock，再标记为 generating + 旧 updated_at
        with patch("app.workflow.OUTPUT_ROOT", self.tmp):
            job_dir = self.tmp / "j2"
            job_dir.mkdir(parents=True, exist_ok=True)
            lock = {"pid": 999999, "task": "run_job", "started_at": _now()}
            _json_write(job_dir / "worker.lock", lock)
            old = (datetime.now() - timedelta(seconds=4000)).isoformat(timespec="seconds")
            self.assertTrue(
                _is_job_orphaned(
                    self._make_status("j2", status="generating", updated_at=old)
                )
            )

    def test_active_lock_with_old_updated_at_is_not_orphaned(self):
        """复审 Bug 1：活锁 + 旧 updated_at 不应被标为中断。

        旧实现按 updated_at 优先判定，会把长任务误杀。修复后活锁优先。
        """
        with patch("app.workflow.OUTPUT_ROOT", self.tmp):
            job_dir = self.tmp / "j3"
            job_dir.mkdir(parents=True, exist_ok=True)
            # 当前进程 PID 写入 lock（活锁）
            live_lock = {
                "pid": os.getpid(),
                "ppid": os.getppid(),
                "task": "run_job",
                "started_at": _now(),
            }
            _json_write(job_dir / "worker.lock", live_lock)
            # updated_at 设到 1 小时前（远大于 INTERRUPT_AGE_SECONDS["generating"]=1800）
            old = (
                datetime.now() - timedelta(seconds=INTERRUPT_AGE_SECONDS["generating"] + 3600)
            ).isoformat(timespec="seconds")
            self.assertFalse(
                _is_job_orphaned(
                    self._make_status("j3", status="generating", updated_at=old)
                )
            )

    def test_dead_lock_with_recent_updated_at_is_orphaned(self):
        """复审 Bug 1 补强：死锁即使 updated_at 新鲜也应被视为中断。"""
        with patch("app.workflow.OUTPUT_ROOT", self.tmp):
            job_dir = self.tmp / "j4"
            job_dir.mkdir(parents=True, exist_ok=True)
            # 写入已死 PID 的 lock
            dead_lock = {"pid": 999999, "task": "run_job", "started_at": _now()}
            _json_write(job_dir / "worker.lock", dead_lock)
            # updated_at 是现在（理论上应"不超时"），但 PID 死也算孤儿
            self.assertTrue(
                _is_job_orphaned(
                    self._make_status("j4", status="generating", updated_at=_now())
                )
            )

    def test_corrupt_lock_is_orphaned(self):
        """复审 Bug 1 补强：lock 文件存在但 JSON 损坏时视为孤儿。"""
        with patch("app.workflow.OUTPUT_ROOT", self.tmp):
            job_dir = self.tmp / "j5"
            job_dir.mkdir(parents=True, exist_ok=True)
            # 写一个无效 JSON
            (job_dir / "worker.lock").write_text("{not valid json", encoding="utf-8")
            self.assertTrue(
                _is_job_orphaned(self._make_status("j5", status="generating"))
            )


class ScanForInterruptedJobsTests(unittest.TestCase):
    """scan_for_interrupted_jobs 端到端。"""

    def setUp(self):
        self.tmp = OUTPUT_ROOT / "_test_scan"
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_marks_only_orphans(self):
        # 准备 3 个任务：1 个 confirmed 陈旧（应被标记），1 个 generating 新鲜（不标记），1 个 success（不标记）
        for i, (st, age_sec) in enumerate(
            [
                ("confirmed", INTERRUPT_AGE_SECONDS["confirmed"] + 60),
                ("generating", 10),  # 新鲜
                ("success", 0),
            ]
        ):
            jid = f"job-{i}"
            d = self.tmp / jid
            d.mkdir(parents=True, exist_ok=True)
            old = (
                (datetime.now() - timedelta(seconds=age_sec)).isoformat(
                    timespec="seconds"
                )
                if age_sec
                else _now()
            )
            status = {
                "job_id": jid,
                "status": st,
                "updated_at": old,
                "steps": [
                    {"key": "planning", "name": "p", "status": "completed"},
                    {"key": "project", "name": "pr", "status": "running"},
                ],
                "failed_stage": None,
                "error": None,
            }
            _json_write(d / "status.json", status)

        with patch("app.workflow.OUTPUT_ROOT", self.tmp), patch(
            "app.workflow.stop_online_demo", return_value=None
        ):
            marked = scan_for_interrupted_jobs()
        self.assertEqual(marked, ["job-0"])
        # job-0 应被标 interrupted
        job0 = _json_read(self.tmp / "job-0" / "status.json")
        self.assertEqual(job0["status"], INTERRUPTED_STATUS)
        self.assertIn("interrupted_at", job0)
        self.assertIn("interrupted_reason", job0)
        # job-1 / job-2 保持原样
        self.assertEqual(
            _json_read(self.tmp / "job-1" / "status.json")["status"],
            "generating",
        )
        self.assertEqual(
            _json_read(self.tmp / "job-2" / "status.json")["status"],
            "success",
        )

    def test_marks_with_dead_lock(self):
        d = self.tmp / "job-x"
        d.mkdir(parents=True, exist_ok=True)
        # lock 写一个已死 PID
        _json_write(
            d / "worker.lock",
            {"pid": 999999, "task": "run_job", "started_at": _now()},
        )
        status = {
            "job_id": "job-x",
            "status": "generating",
            "updated_at": _now(),
            "steps": [{"key": "project", "name": "pr", "status": "running"}],
            "failed_stage": None,
            "error": None,
        }
        _json_write(d / "status.json", status)
        with patch("app.workflow.OUTPUT_ROOT", self.tmp), patch(
            "app.workflow.stop_online_demo", return_value=None
        ):
            marked = scan_for_interrupted_jobs()
        self.assertEqual(marked, ["job-x"])
        # lock 应被释放
        self.assertFalse((d / "worker.lock").exists())


class ResumeEndpointTests(unittest.TestCase):
    """POST /api/jobs/{id}/resume 端到端。"""

    def setUp(self):
        self.tmp = OUTPUT_ROOT / "_test_resume"
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)
        self.client = TestClient(app)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _create_interrupted(self, job_id, prev_status="confirmed"):
        d = self.tmp / job_id
        d.mkdir(parents=True, exist_ok=True)
        # 完整 11 步状态：planning 已完成，前 5 步 (含 demo) 已完成表示项目已运行过
        # screenshot 及之后还未开始，便于验证 materials 恢复不会重置前面
        all_step_keys = [
            "planning", "project", "enhance", "run", "demo",
            "screenshot", "analyze", "source", "docs", "compliance", "package",
        ]
        steps = []
        for key in all_step_keys:
            if key == "planning":
                steps.append({"key": key, "name": key, "status": "completed"})
            elif key in ("project", "enhance", "run", "demo"):
                # 中断在 materials 阶段时这些都已完成；中断在 confirmed/project 时仍是 pending
                if prev_status in ("generating_materials", "materials"):
                    steps.append({"key": key, "name": key, "status": "completed"})
                else:
                    steps.append({"key": key, "name": key, "status": "pending"})
            else:
                # screenshot/analyze/source/docs/compliance/package 全部 pending
                steps.append({"key": key, "name": key, "status": "pending"})
        status = {
            "job_id": job_id,
            "software_name": "测试软件",
            "description": "测试",
            "software_type": "管理系统",
            "industry_type": "education",
            "status": INTERRUPTED_STATUS,
            "progress": 10,
            "current_step": "后台进程中断",
            "steps": steps,
            "failed_stage": prev_status,
            "error": None,
            "interrupted_at": _now(),
            "interrupted_reason": "测试",
            "resume_count": 0,
            "created_at": _now(),
            "updated_at": _now(),
        }
        _json_write(d / "status.json", status)
        # 项目目录可能存在也可能不存在
        if prev_status != "confirmed":
            (d / "generated_project").mkdir(exist_ok=True)

    def test_resume_unknown_returns_404(self):
        with patch("app.workflow.OUTPUT_ROOT", self.tmp), patch(
            "app.workflow.Process"
        ) as mock_process:
            response = self.client.post(
                "/api/jobs/20990101000000-zzzzzzzz/resume"
            )
            self.assertEqual(response.status_code, 404)
            mock_process.assert_not_called()

    def test_resume_success_status_returns_409(self):
        with patch("app.workflow.OUTPUT_ROOT", self.tmp), patch(
            "app.workflow.Process"
        ) as mock_process:
            d = self.tmp / "job-success"
            d.mkdir(parents=True, exist_ok=True)
            _json_write(
                d / "status.json",
                {"job_id": "job-success", "status": "success", "steps": []},
            )
            response = self.client.post("/api/jobs/job-success/resume")
            self.assertEqual(response.status_code, 409)
            mock_process.assert_not_called()

    def test_resume_draft_planning_returns_409(self):
        with patch("app.workflow.OUTPUT_ROOT", self.tmp), patch(
            "app.workflow.Process"
        ) as mock_process:
            d = self.tmp / "job-draft"
            d.mkdir(parents=True, exist_ok=True)
            _json_write(
                d / "status.json",
                {"job_id": "job-draft", "status": "draft_planning", "steps": []},
            )
            response = self.client.post("/api/jobs/job-draft/resume")
            self.assertEqual(response.status_code, 409)
            mock_process.assert_not_called()

    def test_resume_interrupted_confirmed_starts_process(self):
        self._create_interrupted("job-resume-1", prev_status="confirmed")
        # confirmed 阶段项目目录可能不存在，run_job 会因为缺 planning.json 早退；
        # 这里我们 mock run_job 让它不做任何事，重点看 resume_job 行为。
        with patch("app.workflow.OUTPUT_ROOT", self.tmp), patch(
            "app.workflow.Process"
        ) as mock_process, patch(
            "app.workflow.run_job"
        ) as mock_run:
            response = self.client.post("/api/jobs/job-resume-1/resume")
            self.assertEqual(response.status_code, 202)
            body = response.json()
            self.assertEqual(body["status"], "generating")
            self.assertEqual(body["recovery_from_step"], "project")
            self.assertEqual(body["resume_count"], 1)
            # Process 被启动，target 指向 run_job
            mock_process.assert_called_once()
            kwargs = mock_process.call_args.kwargs
            self.assertEqual(kwargs["target"], mock_run)

    def test_resume_interrupted_materials_clears_artifacts(self):
        self._create_interrupted("job-resume-2", prev_status="generating_materials")
        # 模拟已有材料产物
        d = self.tmp / "job-resume-2"
        (d / "screenshots").mkdir(exist_ok=True)
        (d / "copyright_package.zip").write_text("stale", encoding="utf-8")
        (d / "docs").mkdir(exist_ok=True)
        (d / "logs").mkdir(exist_ok=True)
        with patch("app.workflow.OUTPUT_ROOT", self.tmp), patch(
            "app.workflow.Process"
        ) as mock_process, patch(
            "app.workflow.continue_material_generation", lambda jid: None
        ):
            response = self.client.post("/api/jobs/job-resume-2/resume")
            self.assertEqual(response.status_code, 202)
            body = response.json()
            # 修复：内部 target 落到 screenshot（STEPS 中没有 "materials"），
            # 避免从 planning 全部重置
            self.assertEqual(body["recovery_from_step"], "screenshot")
            # 修复：状态直接进入 generating_materials，不再短暂写 regenerating_project
            self.assertEqual(body["status"], "generating_materials")
            self.assertEqual(body["resume_count"], 1)
            # 旧材料产物已清理
            self.assertFalse((d / "screenshots").exists())
            self.assertFalse((d / "copyright_package.zip").exists())
            self.assertFalse((d / "docs").exists())
            self.assertFalse((d / "logs").exists())
            mock_process.assert_called_once()
            # 关键：仅重置 screenshot 及之后步骤；planning/project/enhance/run/demo
            # 在 materials 阶段中断时本来就已完成，恢复后应保持 completed，
            # 不应被错误地"重置回 pending"（会留下空的结果目录不一致）
            step_states = {
                item["key"]: item["status"] for item in body["steps"]
            }
            for preserved in ("planning", "project", "enhance", "run", "demo"):
                self.assertEqual(
                    step_states[preserved],
                    "completed",
                    f"{preserved} step should remain completed during materials resume, got {step_states[preserved]}",
                )
            # screenshot 及之后全部 pending
            for pending in (
                "screenshot",
                "analyze",
                "source",
                "docs",
                "compliance",
                "package",
            ):
                self.assertEqual(
                    step_states[pending],
                    "pending",
                    f"{pending} step should be pending, got {step_states[pending]}",
                )

    def test_resume_rejected_by_active_lock(self):
        """Worker 锁冲突时不允许 resume（避免双跑）。"""
        self._create_interrupted("job-resume-3", prev_status="confirmed")
        with patch("app.workflow.OUTPUT_ROOT", self.tmp), patch(
            "app.workflow.Process"
        ) as mock_process:
            # 在 patch 块内写一个当前进程 PID 的 lock，模拟 Worker 还在跑
            _acquire_worker_lock("job-resume-3", "run_job")
            try:
                response = self.client.post(
                    "/api/jobs/job-resume-3/resume"
                )
                # 锁冲突时 resume_job 走 except 分支返回 RuntimeError，被 main.py 转 409
                self.assertEqual(response.status_code, 409)
                mock_process.assert_not_called()
            finally:
                _release_worker_lock("job-resume-3")

    def test_resume_clears_interrupted_metadata(self):
        self._create_interrupted("job-resume-4", prev_status="confirmed")
        with patch("app.workflow.OUTPUT_ROOT", self.tmp), patch(
            "app.workflow.Process"
        ), patch("app.workflow.run_job", lambda jid: None):
            self.client.post("/api/jobs/job-resume-4/resume")
        doc = _json_read(self.tmp / "job-resume-4" / "status.json")
        self.assertIsNone(doc.get("interrupted_at"))
        self.assertIsNone(doc.get("interrupted_reason"))
        self.assertIsNone(doc.get("error"))
        self.assertEqual(doc["recovery_from_step"], "project")
        self.assertEqual(doc["resume_count"], 1)
        self.assertIn("resumed_at", doc)


class StatusSchemaTests(unittest.TestCase):
    """create_job 初始化全部 L1 新字段。"""

    def setUp(self):
        self.tmp = OUTPUT_ROOT / "_test_schema"
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_create_job_writes_l1_fields(self):
        with patch("app.workflow.OUTPUT_ROOT", self.tmp):
            job = create_job(
                {
                    "software_name": "测试软件",
                    "description": "测试",
                    "software_type": "管理系统",
                    "industry_type": "education",
                }
            )
        doc = _json_read(self.tmp / job["job_id"] / "status.json")
        for field in (
            "worker_pid",
            "worker_started_at",
            "worker_heartbeat_at",
            "interrupted_at",
            "interrupted_reason",
            "recovery_from_step",
            "resumed_at",
        ):
            self.assertIn(field, doc, f"missing field: {field}")
        self.assertIsNone(doc["worker_pid"])
        self.assertIsNone(doc["interrupted_at"])
        self.assertEqual(doc["resume_count"], 0)


if __name__ == "__main__":
    unittest.main()
