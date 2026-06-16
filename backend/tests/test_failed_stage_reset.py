"""验证 workflow.run_job / continue_material_generation 启动时清空 failed_stage。

ISSUE-007 复审 P1-b 要求：重新运行、重新规划或成功后必须清除上次失败留下的
failed_stage，否则任务状态会出现"运行中但仍标记为失败阶段"的不一致。
"""

import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from app.workflow import (
    OUTPUT_ROOT,
    _json_read,
    _json_write,
    _now,
    continue_material_generation,
    create_job,
    run_job,
)


def _set_failed_stage(root: Path, job_id: str, stage: str) -> None:
    path = root / job_id / "status.json"
    doc = _json_read(path)
    doc["failed_stage"] = stage
    doc["error"] = f"history: {stage}"
    _json_write(path, doc)


def _create_job(root: Path) -> str:
    job = create_job(
        {
            "software_name": "测试软件",
            "description": "测试",
            "software_type": "管理系统",
            "industry_type": "education",
        }
    )
    # 必须先有 planning.json，run_job 才不会因为缺文件直接 early-return
    (root / job["job_id"]).mkdir(parents=True, exist_ok=True)
    _json_write(root / job["job_id"] / "planning.json", {"dummy": True})
    return job["job_id"]


class RunJobFailureStageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = OUTPUT_ROOT / "_test_run_job_failed_stage"
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_job_clears_failed_stage_at_start(self):
        """run_job 启动时把上一次的 failed_stage 清空。"""
        with patch("app.workflow.OUTPUT_ROOT", self.tmp):
            job_id = _create_job(self.tmp)
            _set_failed_stage(self.tmp, job_id, "project")
            # mock 掉所有子步骤，避免真实跑 Spring Boot
            with patch(
                "app.workflow.generate_project", return_value=None
            ), patch(
                "app.workflow.enhance_generated_project", return_value=None
            ), patch(
                "app.workflow.validate_generated_project", return_value=None
            ), patch(
                "app.workflow.start_online_demo", return_value=None
            ):
                run_job(job_id)
        doc = _json_read(self.tmp / job_id / "status.json")
        # 启动后必须没有遗留 failed_stage
        self.assertIsNone(doc["failed_stage"])
        # 进入 awaiting_demo_review 是成功路径
        self.assertEqual(doc["status"], "awaiting_demo_review")


class ContinueMaterialFailureStageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = OUTPUT_ROOT / "_test_continue_material_failed_stage"
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_continue_material_clears_failed_stage_at_start(self):
        """continue_material_generation 启动时把上一次的 failed_stage 清空。"""
        with patch("app.workflow.OUTPUT_ROOT", self.tmp):
            job_id = _create_job(self.tmp)
            # 模拟上次失败（罕见但可能出现：materials 流程重试）
            _set_failed_stage(self.tmp, job_id, "materials")
            with patch(
                "app.workflow.capture_screenshots", return_value=None
            ), patch(
                "app.workflow.analyze_code", return_value=None
            ), patch(
                "app.workflow.generate_source_document", return_value=None
            ), patch(
                "app.workflow.generate_documents", return_value=None
            ), patch(
                "app.workflow.run_compliance_check", return_value=None
            ), patch(
                "app.workflow.build_package", return_value=None
            ):
                continue_material_generation(job_id)
        doc = _json_read(self.tmp / job_id / "status.json")
        self.assertIsNone(doc["failed_stage"])
        # 材料流水线成功
        self.assertEqual(doc["status"], "success")


if __name__ == "__main__":
    unittest.main()
