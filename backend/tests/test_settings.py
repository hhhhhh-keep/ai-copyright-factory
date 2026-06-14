import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import settings
from app.settings import PlannerSettingsUpdate


class PlannerSettingsTests(unittest.TestCase):
    def test_save_and_read_masks_api_key(self):
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            with patch.object(settings, "ENV_PATH", env_path):
                with patch.dict(os.environ, {}, clear=True):
                    result = settings.save_planner_settings(
                        PlannerSettingsUpdate(
                            mode="llm",
                            base_url="https://example.com/v1",
                            api_key="secret-key-1234",
                            model="example-model",
                            timeout=45,
                        )
                    )
                    public = settings.public_planner_settings()

            text = env_path.read_text(encoding="utf-8")
            self.assertIn("AI_PLANNER_API_KEY=secret-key-1234", text)
            self.assertNotIn("secret-key-1234", str(result))
            self.assertNotIn("secret-key-1234", str(public))
            self.assertEqual(public["api_key_hint"], "***1234")
            self.assertTrue(public["api_key_configured"])

    def test_blank_key_preserves_existing_key(self):
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text("AI_PLANNER_API_KEY=existing-key\n", encoding="utf-8")
            with patch.object(settings, "ENV_PATH", env_path):
                with patch.dict(os.environ, {}, clear=True):
                    settings.save_planner_settings(
                        PlannerSettingsUpdate(
                            mode="auto",
                            base_url="https://example.com/v1",
                            api_key="",
                            model="example-model",
                            timeout=60,
                        )
                    )
            self.assertIn(
                "AI_PLANNER_API_KEY=existing-key",
                env_path.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()

