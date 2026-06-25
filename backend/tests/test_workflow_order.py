import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from app.planner import PlannerValidationError
from app.enhancer import EnhancementResult
from app.workflow import (
    STEPS,
    _write_planner_diagnostics,
    enhance_generated_project,
    get_job,
    run_generated_project,
    run_job,
)


class WorkflowOrderTests(unittest.TestCase):
    @patch("app.workflow._update")
    @patch("app.workflow.enhance_project")
    def test_readme_progress_event_updates_readme_node(self, enhance_project, update):
        def emit_readme_event(*args, **kwargs):
            callback = kwargs["progress_callback"]
            callback({"file": "README.md", "status": "running"})
            callback({"file": "README.md", "status": "completed", "summary": "done"})
            return EnhancementResult(
                requested_mode="auto",
                actual_mode="llm",
                summary="done",
            )

        enhance_project.side_effect = emit_readme_event
        with TemporaryDirectory() as tmp:
            job_dir = Path(tmp)
            (job_dir / "planning.json").write_text("{}", encoding="utf-8")
            enhance_generated_project(
                {"job_id": "20260623150000-readme01", "codegen_mode": "auto"},
                job_dir,
            )

        step_updates = [
            call.kwargs["codegen_enhance_steps"]
            for call in update.call_args_list
            if "codegen_enhance_steps" in call.kwargs
        ]
        self.assertTrue(
            any(
                next(item for item in steps if item["key"] == "readme")["status"] == "completed"
                for steps in step_updates
            )
        )

    def test_demo_starts_before_screenshot(self):
        keys = [key for key, _ in STEPS]
        self.assertLess(keys.index("run"), keys.index("demo"))
        self.assertLess(keys.index("demo"), keys.index("screenshot"))
        self.assertLess(keys.index("screenshot"), keys.index("package"))

    def test_planner_validation_error_writes_diagnostics(self):
        with TemporaryDirectory() as tmp:
            job_dir = Path(tmp)
            error = PlannerValidationError(
                "second failed",
                first_text='{"bad": 1}',
                second_text='{"still_bad": 1}',
                first_error="first failed",
                second_error="second failed",
            )

            _write_planner_diagnostics(job_dir, error)

            diagnostics = job_dir / "planner_diagnostics"
            self.assertEqual(
                (diagnostics / "planner_raw_initial.txt").read_text(
                    encoding="utf-8"
                ),
                '{"bad": 1}',
            )
            self.assertEqual(
                (diagnostics / "planner_raw_repair.txt").read_text(
                    encoding="utf-8"
                ),
                '{"still_bad": 1}',
            )
            payload = json.loads(
                (diagnostics / "planner_diagnostics.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload["first_error"], "first failed")
            self.assertEqual(payload["second_error"], "second failed")

    def test_get_job_reads_status_with_utf8_bom(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            job_id = "20260618100000-bomtest1"
            job_dir = root / job_id
            job_dir.mkdir()
            (job_dir / "status.json").write_text(
                json.dumps({"job_id": job_id, "status": "awaiting_demo_review"}),
                encoding="utf-8-sig",
            )
            with patch("app.workflow.OUTPUT_ROOT", root):
                job = get_job(job_id)
            self.assertEqual(job["job_id"], job_id)
            self.assertEqual(job["status"], "awaiting_demo_review")

    @patch("app.workflow._update")
    @patch("app.workflow._step")
    @patch("app.workflow.start_online_demo")
    @patch("app.workflow.validate_generated_project")
    @patch("app.workflow.enhance_generated_project")
    @patch("app.workflow.generate_project")
    @patch("app.workflow.get_job")
    def test_project_pipeline_pauses_for_demo_review(
        self,
        get_job,
        generate_project,
        enhance_project,
        validate_project,
        start_demo,
        step,
        update,
    ):
        get_job.return_value = {
            "job_id": "20260615120000-abcdef12",
            "review_round": 0,
            "steps": [],
        }
        with patch("app.workflow.Path.exists", return_value=True):
            run_job("20260615120000-abcdef12")
        status_updates = [
            call.kwargs.get("status") for call in update.call_args_list
        ]
        self.assertIn("awaiting_demo_review", status_updates)
        start_demo.assert_called_once()

    @patch("app.workflow._json_write")
    @patch("app.workflow._maven_subprocess_env")
    @patch("app.workflow._maven_command", return_value="mvn.cmd")
    @patch("app.workflow.subprocess.run")
    def test_maven_validation_uses_java17_environment(
        self,
        run,
        _maven_command,
        maven_env,
        _json_write,
    ):
        run.return_value = SimpleNamespace(returncode=0, stdout="", stderr="")
        expected_env = {"JAVA_HOME": r"D:\Program Files\Java\jdk-17"}
        maven_env.return_value = expected_env

        with TemporaryDirectory() as tmp:
            job_dir = Path(tmp)
            frontend = job_dir / "generated_project" / "frontend"
            backend = job_dir / "generated_project" / "backend"
            (backend / "src/main/java/example").mkdir(parents=True)
            (backend / "src/main/resources").mkdir(parents=True)
            (job_dir / "generated_project" / "sql").mkdir(parents=True)
            frontend.mkdir(parents=True)
            (backend / "pom.xml").write_text("<project/>", encoding="utf-8")
            (backend / "src/main/resources/application.yml").write_text(
                "spring: {}", encoding="utf-8"
            )
            (backend / "src/main/java/example/App.java").write_text(
                "class App {}", encoding="utf-8"
            )
            (job_dir / "generated_project" / "sql/init.sql").write_text(
                "", encoding="utf-8"
            )

            run_generated_project(job_dir)

        maven_call = run.call_args_list[2]
        self.assertEqual(maven_call.args[0], ["mvn.cmd", "test"])
        self.assertIs(maven_call.kwargs["env"], expected_env)


if __name__ == "__main__":
    unittest.main()
