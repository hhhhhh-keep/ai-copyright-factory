import unittest
from unittest.mock import patch

from app.workflow import STEPS, run_job


class WorkflowOrderTests(unittest.TestCase):
    def test_demo_starts_before_screenshot(self):
        keys = [key for key, _ in STEPS]
        self.assertLess(keys.index("run"), keys.index("demo"))
        self.assertLess(keys.index("demo"), keys.index("screenshot"))
        self.assertLess(keys.index("screenshot"), keys.index("package"))

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


if __name__ == "__main__":
    unittest.main()
