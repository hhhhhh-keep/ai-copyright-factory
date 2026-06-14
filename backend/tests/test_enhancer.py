import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

from app.enhancer import enhance_project, restore_enhancement


class EnhancerHandler(BaseHTTPRequestHandler):
    response_content = {}

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            self.response_content, ensure_ascii=False
                        )
                    }
                }
            ]
        }
        body = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class EnhancerTests(unittest.TestCase):
    def _project(self, root: Path):
        files = {
            "frontend/src/App.vue": "<template><h1>Template</h1></template>",
            "frontend/src/style.css": "body{color:#000}",
            "README.md": "# Template",
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def test_template_mode_does_not_change_files(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            self._project(project)
            result = enhance_project(
                {"codegen_mode": "template"},
                {"software_name": "Test"},
                project,
                Path(directory) / "backup",
            )
            self.assertEqual(result.actual_mode, "template")
            self.assertIn("Template", (project / "README.md").read_text())

    def test_llm_mode_applies_only_allowed_files_and_can_restore(self):
        EnhancerHandler.response_content = {
            "summary": "Improve title",
            "files": [
                {
                    "path": "frontend/src/App.vue",
                    "content": "<template><h1>Enhanced</h1></template>",
                }
            ],
        }
        server = HTTPServer(("127.0.0.1", 0), EnhancerHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                backup = Path(directory) / "backup"
                self._project(project)
                env = {
                    "AI_PLANNER_BASE_URL": f"http://127.0.0.1:{server.server_port}/v1",
                    "AI_PLANNER_API_KEY": "test-key",
                    "AI_CODEGEN_MODEL": "test-codegen",
                }
                with patch.dict(os.environ, env, clear=False):
                    result = enhance_project(
                        {"codegen_mode": "llm"},
                        {"software_name": "Test"},
                        project,
                        backup,
                    )
                self.assertEqual(result.actual_mode, "llm")
                self.assertIn("Enhanced", (project / "frontend/src/App.vue").read_text())
                restore_enhancement(project, backup)
                self.assertIn("Template", (project / "frontend/src/App.vue").read_text())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
