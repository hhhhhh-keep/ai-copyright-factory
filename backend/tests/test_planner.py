import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

from app.planner import Planning, build_planning, propose_revision


VALID_PLANNING = {
    "software_name": "教学管理系统",
    "description": "用于学生、教师和课程信息管理",
    "software_type": "管理系统",
    "industry_type": "education",
    "industry_name": "教育",
    "modules": [
        {
            "key": "students",
            "name": "学生管理",
            "description": "维护学生基本信息、班级和学籍状态",
            "pages": ["学生列表", "学生登记"],
            "fields": ["学号", "学生姓名", "班级", "学籍状态"],
        },
        {
            "key": "teachers",
            "name": "教师管理",
            "description": "维护教师档案、所属部门和任课信息",
            "pages": ["教师列表", "教师登记"],
            "fields": ["教师编号", "教师姓名", "所属部门", "在职状态"],
        },
        {
            "key": "courses",
            "name": "课程管理",
            "description": "维护课程信息、授课教师和开课计划",
            "pages": ["课程列表", "课程维护"],
            "fields": ["课程编号", "课程名称", "授课教师", "课程状态"],
        },
    ],
    "database_tables": [
        "education_students",
        "education_teachers",
        "education_courses"
    ],
    "api_list": [
        "GET /api/students",
        "POST /api/students",
        "GET /api/teachers",
    ],
    "screenshots": ["登录页", "首页", "学生管理", "教师管理", "课程管理"],
    "document_outline": ["项目概述", "总体设计", "功能设计", "数据设计"],
}


class MockPlannerHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers["Content-Length"])
        json.loads(self.rfile.read(length).decode("utf-8"))
        response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(VALID_PLANNING, ensure_ascii=False)
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


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.job = {
            "software_name": "教学管理系统",
            "description": "用于学生、教师和课程信息管理",
            "software_type": "管理系统",
            "industry_type": "education",
            "clarification_answers": {
                "students": True,
                "teachers": True,
                "courses": True,
                "exams": False,
                "scores": False,
                "analysis": False,
            },
        }

    def test_template_mode(self):
        result = build_planning({**self.job, "planner_mode": "template"})
        self.assertEqual(result.actual_mode, "template")
        self.assertIsInstance(result.planning, Planning)

    def test_auto_mode_falls_back_without_key(self):
        with patch.dict(os.environ, {"AI_PLANNER_API_KEY": ""}, clear=False):
            result = build_planning({**self.job, "planner_mode": "auto"})
        self.assertEqual(result.actual_mode, "template")
        self.assertIn("AI_PLANNER_API_KEY", result.fallback_reason)

    def test_llm_mode_accepts_valid_structured_json(self):
        server = HTTPServer(("127.0.0.1", 0), MockPlannerHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            env = {
                "AI_PLANNER_BASE_URL": f"http://127.0.0.1:{server.server_port}/v1",
                "AI_PLANNER_API_KEY": "test-key",
                "AI_PLANNER_MODEL": "test-model",
            }
            with patch.dict(os.environ, env, clear=False):
                result = build_planning({**self.job, "planner_mode": "llm"})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.assertEqual(result.actual_mode, "llm")
        self.assertEqual(result.model, "test-model")
        self.assertEqual(result.planning.modules[0].key, "students")

    def test_llm_mode_accepts_industry_aligned_custom_module(self):
        custom = {**VALID_PLANNING, "modules": [*VALID_PLANNING["modules"]]}
        custom["modules"][0] = {
            **custom["modules"][0],
            "key": "classroom_patrol",
            "name": "课堂巡课",
            "description": "面向教师和课程开展课堂教学巡查",
        }
        custom["database_tables"] = [
            "education_classroom_patrol",
            "education_teachers",
            "education_courses",
        ]
        with patch("app.planner._extract_json", return_value=custom):
            with patch("app.planner.urllib.request.urlopen") as request:
                response = request.return_value.__enter__.return_value
                response.read.return_value = json.dumps(
                    {"choices": [{"message": {"content": "{}"}}]}
                ).encode("utf-8")
                with patch.dict(
                    os.environ,
                    {
                        "AI_PLANNER_API_KEY": "test-key",
                        "AI_PLANNER_MODEL": "test-model",
                    },
                    clear=False,
                ):
                    result = build_planning({**self.job, "planner_mode": "llm"})
        self.assertEqual(result.planning.modules[0].key, "classroom_patrol")

    def test_template_mode_generates_ui_plan_and_multiple_page_patterns(self):
        result = build_planning({**self.job, "planner_mode": "template"})
        self.assertIn(
            result.planning.ui_plan.shell,
            {"sidebar_admin", "top_workspace", "split_console"},
        )
        self.assertGreaterEqual(
            len({module.page_pattern for module in result.planning.modules}),
            2,
        )

    def test_revision_rules_can_add_module_and_change_shell(self):
        current = build_planning(
            {**self.job, "planner_mode": "template"}
        ).planning.model_dump()
        with patch.dict(
            os.environ,
            {"AI_PLANNER_API_KEY": "", "AI_PLANNER_MODEL": ""},
            clear=False,
        ):
            result = propose_revision(
                self.job,
                current,
                "增加课堂巡课模块，整体改为顶部导航",
            )
        self.assertEqual(result.actual_mode, "rules")
        self.assertEqual(result.planning.ui_plan.shell, "top_workspace")
        self.assertIn("课堂巡课", [item.name for item in result.planning.modules])


if __name__ == "__main__":
    unittest.main()
