"""规划阶段失败任务重试与拒绝非规划阶段失败的测试。"""

import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.workflow import (
    OUTPUT_ROOT,
    _json_read,
    _json_write,
    _now,
    create_job,
)


def _create_job_with_status(status: str, failed_stage=None) -> str:
    """直接写 status.json 创建任意状态的任务。"""
    now = _now()
    job_id = datetime.now().strftime("%Y%m%d%H%M%S%f") + "-" + "abcdef01"
    job_dir = OUTPUT_ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    status_doc = {
        "job_id": job_id,
        "software_name": "测试软件",
        "description": "测试用",
        "software_type": "管理系统",
        "industry_type": "education",
        "clarification_answers": {},
        "planner_model": None,
        "codegen_mode": "auto",
        "codegen_actual_mode": None,
        "codegen_model": None,
        "codegen_summary": None,
        "codegen_changed_files": [],
        "codegen_fallback_reason": None,
        "document_template": "standard",
        "version": "V1.0",
        "applicant_name": "测试",
        "completion_date": "2026-06-15",
        "publication_status": "未发表",
        "compliance_score": None,
        "compliance_grade": None,
        "compliance_passed": None,
        "demo_url": None,
        "swagger_url": None,
        "run_status": "pending",
        "run_validation": None,
        "status": status,
        "progress": 0,
        "current_step": "测试",
        "steps": [
            {"key": "planning", "name": "生成软件规划", "status": "failed"},
            {"key": "project", "name": "生成可运行项目", "status": "pending"},
            {"key": "enhance", "name": "AI 增强项目代码", "status": "pending"},
            {"key": "run", "name": "运行项目并验证", "status": "pending"},
            {"key": "demo", "name": "启动在线 Demo", "status": "pending"},
            {"key": "screenshot", "name": "自动截图", "status": "pending"},
            {"key": "analyze", "name": "统计真实代码行数", "status": "pending"},
            {"key": "source", "name": "生成源码材料", "status": "pending"},
            {"key": "docs", "name": "生成设计说明书和用户手册", "status": "pending"},
            {"key": "compliance", "name": "执行软著合规检查", "status": "pending"},
            {"key": "package", "name": "打包软著材料", "status": "pending"},
        ],
        "failed_stage": failed_stage,
        "error": "ValueError: 模拟失败" if status == "failed" else None,
        "created_at": now,
        "updated_at": now,
    }
    _json_write(job_dir / "status.json", status_doc)
    return job_id


class RegeneratePlanningTests(unittest.TestCase):
    """验证 /api/planning/regenerate 的重试策略。"""

    def setUp(self):
        self.client = TestClient(app)
        self.created_jobs: list = []

    def tearDown(self):
        for job_id in self.created_jobs:
            job_dir = OUTPUT_ROOT / job_id
            if job_dir.exists():
                import shutil
                shutil.rmtree(job_dir, ignore_errors=True)

    def _create_with_status(self, status, failed_step_key=None, failed_stage=None):
        job_id = _create_job_with_status(status, failed_stage=failed_stage)
        if failed_step_key:
            # 写入特定的失败步骤
            path = OUTPUT_ROOT / job_id / "status.json"
            doc = _json_read(path)
            for item in doc["steps"]:
                if item["key"] == failed_step_key:
                    item["status"] = "failed"
                else:
                    item["status"] = "pending"
            _json_write(path, doc)
        self.created_jobs.append(job_id)
        return job_id

    def test_draft_planning_can_regenerate(self):
        job_id = self._create_with_status("draft_planning")
        with patch("app.main.Process") as mock_process:
            response = self.client.post(
                "/api/planning/regenerate", json={"job_id": job_id}
            )
            self.assertEqual(response.status_code, 202)
            body = response.json()
            self.assertEqual(body["status"], "generating")
            self.assertEqual(body["current_step"], "重新生成软件规划")
            # 后台 Process 被调用一次，参数指向 generate_planning_draft
            mock_process.assert_called_once()
        # 原 status.json 不再保留 planner_model
        doc = _json_read(OUTPUT_ROOT / job_id / "status.json")
        self.assertNotIn("planner_mode", doc)
        self.assertNotIn("planner_requested_mode", doc)
        self.assertNotIn("planner_fallback_reason", doc)

    def test_planning_failure_can_regenerate(self):
        job_id = self._create_with_status(
            "failed", failed_step_key="planning", failed_stage="planning"
        )
        with patch("app.main.Process") as mock_process:
            response = self.client.post(
                "/api/planning/regenerate", json={"job_id": job_id}
            )
            self.assertEqual(response.status_code, 202)
            body = response.json()
            self.assertEqual(body["status"], "generating")
            self.assertIsNone(body["failed_stage"])
            mock_process.assert_called_once()
        # planning step 复位
        doc = _json_read(OUTPUT_ROOT / job_id / "status.json")
        for item in doc["steps"]:
            if item["key"] == "planning":
                self.assertEqual(item["status"], "pending")
            else:
                self.assertEqual(item["status"], "pending")

    def test_project_failure_cannot_regenerate_planning(self):
        # 项目阶段失败的标志：failed_stage="project" 且 project step 失败
        job_id = self._create_with_status(
            "failed", failed_step_key="project", failed_stage="project"
        )
        with patch("app.main.Process") as mock_process:
            response = self.client.post(
                "/api/planning/regenerate", json={"job_id": job_id}
            )
            self.assertEqual(response.status_code, 409)
            self.assertIn("规划阶段失败", response.json()["detail"])
            # 失败路径不应启动 Process
            mock_process.assert_not_called()

    def test_materials_failure_cannot_regenerate_planning(self):
        job_id = self._create_with_status(
            "failed", failed_step_key="package", failed_stage="materials"
        )
        with patch("app.main.Process") as mock_process:
            response = self.client.post(
                "/api/planning/regenerate", json={"job_id": job_id}
            )
            self.assertEqual(response.status_code, 409)
            mock_process.assert_not_called()

    def test_confirmed_cannot_regenerate_planning(self):
        # 确认状态下不应允许规划重试（必须走 revision 流程）
        job_id = self._create_with_status("confirmed")
        # 把所有步骤都设为 pending
        path = OUTPUT_ROOT / job_id / "status.json"
        doc = _json_read(path)
        for item in doc["steps"]:
            item["status"] = "pending"
        _json_write(path, doc)
        with patch("app.main.Process") as mock_process:
            response = self.client.post(
                "/api/planning/regenerate", json={"job_id": job_id}
            )
            self.assertEqual(response.status_code, 409)
            mock_process.assert_not_called()

    def test_awaiting_demo_review_cannot_regenerate_planning(self):
        job_id = self._create_with_status("awaiting_demo_review")
        with patch("app.main.Process") as mock_process:
            response = self.client.post(
                "/api/planning/regenerate", json={"job_id": job_id}
            )
            self.assertEqual(response.status_code, 409)
            mock_process.assert_not_called()

    def test_unknown_job_returns_404(self):
        with patch("app.main.Process") as mock_process:
            response = self.client.post(
                "/api/planning/regenerate", json={"job_id": "99999999999999-zzzzzzzz"}
            )
            self.assertEqual(response.status_code, 404)
            mock_process.assert_not_called()

    def test_planning_failure_retry_cleans_stale_artifacts(self):
        # 写入一个旧的 planning.json 和 planning_versions/v1.json
        job_id = self._create_with_status(
            "failed", failed_step_key="planning", failed_stage="planning"
        )
        job_dir = OUTPUT_ROOT / job_id
        _json_write(job_dir / "planning.json", {"stale": True})
        versions_dir = job_dir / "planning_versions"
        versions_dir.mkdir(parents=True, exist_ok=True)
        _json_write(versions_dir / "v1.json", {"stale": True})

        with patch("app.main.Process"):
            response = self.client.post(
                "/api/planning/regenerate", json={"job_id": job_id}
            )
            self.assertEqual(response.status_code, 202)
            # 旧产物已清理
            self.assertFalse((job_dir / "planning.json").exists())
            self.assertFalse(versions_dir.exists())

    def test_failed_stage_clears_on_resubmit(self):
        """P1-b 验证：触发 202 后 status.json 里的 failed_stage 已被置 None。"""
        job_id = self._create_with_status(
            "failed", failed_step_key="planning", failed_stage="planning"
        )
        # 重试前磁盘上是 "planning"
        doc_before = _json_read(OUTPUT_ROOT / job_id / "status.json")
        self.assertEqual(doc_before["failed_stage"], "planning")
        with patch("app.main.Process"):
            response = self.client.post(
                "/api/planning/regenerate", json={"job_id": job_id}
            )
            self.assertEqual(response.status_code, 202)
        # 重试后落盘
        doc_after = _json_read(OUTPUT_ROOT / job_id / "status.json")
        self.assertIsNone(doc_after["failed_stage"])
        self.assertIsNone(doc_after["error"])


class JobCreatePlannerFieldsTests(unittest.TestCase):
    """create_job 不再写入 planner_mode / planner_requested_mode / planner_fallback_reason。"""

    def setUp(self):
        import shutil
        self.tmp = Path(OUTPUT_ROOT) / "_test_job_create_xyz"
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_create_job_does_not_write_legacy_planner_fields(self):
        with patch("app.workflow.OUTPUT_ROOT", self.tmp):
            job = create_job(
                {
                    "software_name": "测试软件",
                    "description": "测试",
                    "software_type": "管理系统",
                    "industry_type": "education",
                }
            )
        status_doc = _json_read(self.tmp / job["job_id"] / "status.json")
        self.assertNotIn("planner_mode", status_doc)
        self.assertNotIn("planner_requested_mode", status_doc)
        self.assertNotIn("planner_fallback_reason", status_doc)
        # planner_model 仍然保留（默认 None）
        self.assertIn("planner_model", status_doc)
        self.assertIsNone(status_doc["planner_model"])


class WorkflowFailureStageTests(unittest.TestCase):
    """验证 _update 在每个失败阶段写入对应的 failed_stage。"""

    def setUp(self):
        import shutil
        self.tmp = Path(OUTPUT_ROOT) / "_test_failure_stage"
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_planning_draft_failure_sets_planning_stage(self):
        from app.workflow import generate_planning_draft

        with patch("app.workflow.OUTPUT_ROOT", self.tmp):
            job = create_job(
                {
                    "software_name": "测试软件",
                    "description": "测试",
                    "software_type": "管理系统",
                    "industry_type": "education",
                }
            )
            with patch(
                "app.workflow.generate_planning",
                side_effect=RuntimeError("模拟规划失败"),
            ):
                generate_planning_draft(job["job_id"])
        status_doc = _json_read(self.tmp / job["job_id"] / "status.json")
        self.assertEqual(status_doc["status"], "failed")
        self.assertEqual(status_doc["failed_stage"], "planning")
        self.assertIn("RuntimeError", status_doc["error"])


if __name__ == "__main__":
    unittest.main()
