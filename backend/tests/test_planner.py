"""Planner 单元测试（ISSUE-007 实施后）。

覆盖：
- 正常 LLM JSON 响应。
- JSON 容错：代码围栏、前后说明文字、尾随文本。
- 一次自动修复：首次 JSON 解析失败，修复一次成功。
- 一次自动修复：首次 Pydantic 校验失败，修复一次成功。
- 两次失败：首次和修复都失败，错误向上抛。
- 返工：LLM 成功、LLM 修复成功、LLM 两次失败。
- 行业仅作为提示信息，不参与校验。
"""

import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List
from unittest.mock import patch

from app import planner
from app.planner import (
    Planning,
    PlannerResult,
    build_planning,
    propose_revision,
    _extract_json,
    _first_json_object,
)


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
        "education_courses",
    ],
    "api_list": [
        "GET /api/students",
        "POST /api/students",
        "GET /api/teachers",
    ],
    "screenshots": ["登录页", "首页", "学生管理", "教师管理", "课程管理"],
    "document_outline": ["项目概述", "总体设计", "功能设计", "数据设计"],
}


def _wrap_planning_response(planning: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "choices": [
            {"message": {"content": json.dumps(planning, ensure_ascii=False)}}
        ]
    }


class _ScriptedHandler(BaseHTTPRequestHandler):
    """按顺序返回脚本化响应的测试用 HTTP handler。

    通过类属性 `responses` 注入文本列表，每次 POST 消费一个。
    """

    responses: List[str] = []
    requests_received: List[Dict[str, Any]] = []

    def do_POST(self):  # noqa: N802 (BaseHTTPRequestHandler API)
        length = int(self.headers["Content-Length"])
        body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw": body}
        _ScriptedHandler.requests_received.append(payload)
        if not _ScriptedHandler.responses:
            self.send_response(500)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        content = _ScriptedHandler.responses.pop(0)
        response = {
            "choices": [{"message": {"content": content}}]
        }
        encoded = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):  # noqa: A002
        return


def _start_server(responses: List[str]) -> HTTPServer:
    _ScriptedHandler.responses = list(responses)
    _ScriptedHandler.requests_received = []
    server = HTTPServer(("127.0.0.1", 0), _ScriptedHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _stop_server(server: HTTPServer) -> None:
    server.shutdown()
    server.server_close()


def _patched_env(server: HTTPServer) -> Any:
    return patch.dict(
        os.environ,
        {
            "AI_PLANNER_BASE_URL": f"http://127.0.0.1:{server.server_port}/v1",
            "AI_PLANNER_API_KEY": "test-key",
            "AI_PLANNER_MODEL": "test-model",
        },
        clear=False,
    )


def _base_job() -> Dict[str, Any]:
    return {
        "software_name": "教学管理系统",
        "description": "用于学生、教师和课程信息管理",
        "software_type": "管理系统",
        "industry_type": "education",
        "industry_name": "教育",
    }


class ExtractJsonTests(unittest.TestCase):
    """_extract_json / _first_json_object 容错测试。"""

    def test_plain_object(self):
        text = json.dumps(VALID_PLANNING, ensure_ascii=False)
        self.assertEqual(_extract_json(text)["software_name"], "教学管理系统")

    def test_code_fence(self):
        text = "```json\n" + json.dumps(VALID_PLANNING, ensure_ascii=False) + "\n```"
        self.assertEqual(_extract_json(text)["software_name"], "教学管理系统")

    def test_code_fence_without_language(self):
        text = "```\n" + json.dumps(VALID_PLANNING, ensure_ascii=False) + "\n```"
        self.assertEqual(_extract_json(text)["software_name"], "教学管理系统")

    def test_leading_text(self):
        text = (
            "下面是规划：\n"
            + json.dumps(VALID_PLANNING, ensure_ascii=False)
        )
        self.assertEqual(_extract_json(text)["software_name"], "教学管理系统")

    def test_trailing_text(self):
        text = (
            json.dumps(VALID_PLANNING, ensure_ascii=False)
            + "\n以上即为规划内容。"
        )
        self.assertEqual(_extract_json(text)["software_name"], "教学管理系统")

    def test_leading_and_trailing_text(self):
        text = (
            "规划说明：\n"
            + json.dumps(VALID_PLANNING, ensure_ascii=False)
            + "\n请审查。"
        )
        self.assertEqual(_extract_json(text)["software_name"], "教学管理系统")

    def test_nested_braces_inside_strings(self):
        text = (
            "noise { not json }\n"
            + json.dumps(VALID_PLANNING, ensure_ascii=False)
        )
        self.assertEqual(_extract_json(text)["software_name"], "教学管理系统")

    def test_no_object_raises(self):
        with self.assertRaises(ValueError):
            _extract_json("这是说明文字，没有 JSON。")

    def test_invalid_json_raises(self):
        with self.assertRaises(ValueError):
            _extract_json("{ not valid json }")

    def test_multiple_objects_takes_first(self):
        first = json.dumps({"a": 1}, ensure_ascii=False)
        second = json.dumps(VALID_PLANNING, ensure_ascii=False)
        # 第一个对象不合法时，会继续往后找
        text = "prefix {bad " + second + " suffix"
        result = _extract_json(text)
        self.assertEqual(result["software_name"], "教学管理系统")


class PlanningSchemaTests(unittest.TestCase):
    def test_module_with_thirteen_fields_is_valid(self):
        planning = json.loads(json.dumps(VALID_PLANNING, ensure_ascii=False))
        planning["modules"][0]["fields"] = [
            "人员编号",
            "姓名",
            "性别",
            "出生日期",
            "证件号码",
            "所属监区",
            "监室编号",
            "入所日期",
            "案件编号",
            "人员状态",
            "紧急联系人",
            "联系电话",
            "更新时间",
        ]

        validated = Planning.model_validate(planning)

        self.assertEqual(len(validated.modules[0].fields), 13)


class BuildPlanningTests(unittest.TestCase):
    def test_missing_api_key_raises(self):
        with patch.dict(os.environ, {"AI_PLANNER_API_KEY": ""}, clear=False):
            with self.assertRaises(RuntimeError):
                build_planning(_base_job())

    def test_missing_model_raises(self):
        with patch.dict(
            os.environ,
            {"AI_PLANNER_API_KEY": "test-key", "AI_PLANNER_MODEL": ""},
            clear=False,
        ):
            with self.assertRaises(RuntimeError):
                build_planning(_base_job())

    def test_llm_success(self):
        server = _start_server([json.dumps(VALID_PLANNING, ensure_ascii=False)])
        try:
            with _patched_env(server):
                result = build_planning(_base_job())
        finally:
            _stop_server(server)
        self.assertEqual(result.model, "test-model")
        self.assertEqual(result.planning.modules[0].key, "students")
        self.assertEqual(len(_ScriptedHandler.requests_received), 1)

    def test_user_input_fields_override_llm_response(self):
        """P0：build_planning 必须用用户输入强制覆盖 LLM 返回的同名字段。"""
        llm_payload = {
            **VALID_PLANNING,
            "software_name": "被模型改名的软件",
            "description": "模型自己编的描述",
            "software_type": "被篡改类型",
            "industry_type": "education",
            "industry_name": "教育",
        }
        server = _start_server([json.dumps(llm_payload, ensure_ascii=False)])
        try:
            with _patched_env(server):
                result = build_planning(_base_job())
        finally:
            _stop_server(server)
        self.assertEqual(result.planning.software_name, "教学管理系统")
        self.assertEqual(
            result.planning.description, "用于学生、教师和课程信息管理"
        )
        self.assertEqual(result.planning.software_type, "管理系统")
        self.assertEqual(result.planning.industry_type, "education")
        self.assertEqual(result.planning.industry_name, "教育")

    def test_user_input_industry_code_is_converted_to_display_name(self):
        """P1-a：仅提供 industry_type 时，模型应收到显示名而不是内部编码。"""
        job = {
            "software_name": "监所管理系统",
            "description": "用于监所人员档案",
            "software_type": "管理系统",
            "industry_type": "public_security",
            # 注意：故意不传 industry_name
        }
        server = _start_server([json.dumps(VALID_PLANNING, ensure_ascii=False)])
        try:
            with _patched_env(server):
                build_planning(job)
        finally:
            _stop_server(server)
        # 检查发给 LLM 的请求体里行业提示是"公安"而不是"public_security"
        request_body = _ScriptedHandler.requests_received[0]
        user_message = request_body["messages"][-1]["content"]
        self.assertIn("公安", user_message)
        self.assertNotIn("public_security", user_message)
        # 同时检查 planning 里的 industry_name 也用显示名
        result = build_planning.__wrapped__ if hasattr(build_planning, "__wrapped__") else None
        # 再跑一次确认返回结果的 industry_name
        server2 = _start_server([json.dumps(VALID_PLANNING, ensure_ascii=False)])
        try:
            with _patched_env(server2):
                result2 = build_planning(job)
        finally:
            _stop_server(server2)
        self.assertEqual(result2.planning.industry_name, "公安")

    def test_unknown_industry_code_leaves_industry_name_empty(self):
        """未知行业编码不应抛错，industry_name 留空即可。"""
        job = {
            "software_name": "测试",
            "description": "测试描述",
            "software_type": "管理系统",
            "industry_type": "unknown_code_xyz",
        }
        server = _start_server([json.dumps(VALID_PLANNING, ensure_ascii=False)])
        try:
            with _patched_env(server):
                result = build_planning(job)
        finally:
            _stop_server(server)
        self.assertEqual(result.planning.industry_type, "unknown_code_xyz")
        self.assertEqual(result.planning.industry_name, "")

    def test_industry_is_only_hint_not_constraint(self):
        """行业被传给 LLM，但 Planner 不做行业白名单校验。"""
        job = {
            "software_name": "监所管理系统",
            "description": "用于在押人员档案、监室和勤务管理",
            "software_type": "管理系统",
            "industry_type": "public_security",
            "industry_name": "公安",
        }
        # 模型给出与行业关键词完全无关的模块（不会被拦截）
        custom_planning = {**VALID_PLANNING}
        custom_planning["modules"] = [
            {
                "key": "detainee_archives",
                "name": "在押人员档案",
                "description": "在押人员基本信息与变动",
                "pages": ["档案列表", "档案详情"],
                "fields": ["编号", "姓名", "入所时间", "状态"],
            },
            {
                "key": "cell_management",
                "name": "监室管理",
                "description": "监室分配和巡检",
                "pages": ["监室列表", "分配记录"],
                "fields": ["监室号", "容量", "当前人数", "负责人"],
            },
            {
                "key": "duty_arrangement",
                "name": "勤务安排",
                "description": "民警值班和交接班",
                "pages": ["值班表", "交接记录"],
                "fields": ["班次", "值班人", "交接时间", "备注"],
            },
        ]
        custom_planning["database_tables"] = [
            "detainee_archives",
            "cell_management",
            "duty_arrangement",
        ]
        custom_planning["software_name"] = "监所管理系统"
        custom_planning["industry_type"] = "public_security"
        custom_planning["industry_name"] = "公安"

        server = _start_server([json.dumps(custom_planning, ensure_ascii=False)])
        try:
            with _patched_env(server):
                result = build_planning(job)
        finally:
            _stop_server(server)
        self.assertEqual(
            [m.key for m in result.planning.modules],
            ["detainee_archives", "cell_management", "duty_arrangement"],
        )

    def test_first_response_with_fence_is_extracted(self):
        text = "```json\n" + json.dumps(VALID_PLANNING, ensure_ascii=False) + "\n```"
        server = _start_server([text])
        try:
            with _patched_env(server):
                result = build_planning(_base_job())
        finally:
            _stop_server(server)
        self.assertEqual(result.planning.modules[0].key, "students")

    def test_first_response_with_trailing_text_is_extracted(self):
        text = (
            json.dumps(VALID_PLANNING, ensure_ascii=False)
            + "\n请基于以上规划生成项目。"
        )
        server = _start_server([text])
        try:
            with _patched_env(server):
                result = build_planning(_base_job())
        finally:
            _stop_server(server)
        self.assertEqual(result.planning.modules[0].key, "students")

    def test_first_response_invalid_json_repairs_on_second_try(self):
        bad = "不是 JSON，只是说明：\n规划很复杂"
        server = _start_server(
            [bad, json.dumps(VALID_PLANNING, ensure_ascii=False)]
        )
        try:
            with _patched_env(server):
                result = build_planning(_base_job())
        finally:
            _stop_server(server)
        self.assertEqual(result.planning.modules[0].key, "students")
        # 第一次响应 + 修复一次 = 2 次请求
        self.assertEqual(len(_ScriptedHandler.requests_received), 2)
        # 第二次请求应该包含错误信息
        repair_request = _ScriptedHandler.requests_received[1]
        self.assertIn("ValueError", json.dumps(repair_request, ensure_ascii=False))

    def test_first_response_schema_violation_repairs_on_second_try(self):
        # modules 缺一不可；少于 3 个会被 Pydantic 拒绝
        invalid = {
            **VALID_PLANNING,
            "modules": VALID_PLANNING["modules"][:1],  # 只有 1 个模块
        }
        server = _start_server(
            [json.dumps(invalid, ensure_ascii=False),
             json.dumps(VALID_PLANNING, ensure_ascii=False)]
        )
        try:
            with _patched_env(server):
                result = build_planning(_base_job())
        finally:
            _stop_server(server)
        self.assertEqual(len(result.planning.modules), 3)
        self.assertEqual(len(_ScriptedHandler.requests_received), 2)

    def test_two_failures_raise(self):
        bad = "完全无效的响应，没有 JSON。"
        server = _start_server([bad, bad])
        try:
            with _patched_env(server):
                with self.assertRaises(ValueError):
                    build_planning(_base_job())
        finally:
            _stop_server(server)
        # 两次调用 = 1 次首请求 + 1 次修复
        self.assertEqual(len(_ScriptedHandler.requests_received), 2)

    def test_api_call_failure_does_not_enter_repair(self):
        # 服务器返回 500，应该直接抛错而不进入修复
        _ScriptedHandler.responses = []
        server = _start_server([])
        try:
            with _patched_env(server):
                with self.assertRaises(RuntimeError):
                    build_planning(_base_job())
        finally:
            _stop_server(server)
        # 失败时只调了一次，没有修复调用
        self.assertEqual(len(_ScriptedHandler.requests_received), 1)


class ProposeRevisionTests(unittest.TestCase):
    def _current_planning(self) -> Dict[str, Any]:
        return json.loads(json.dumps(VALID_PLANNING, ensure_ascii=False))

    def test_revision_success(self):
        new_planning = {**VALID_PLANNING}
        new_planning["ui_plan"] = {
            "shell": "top_workspace",
            "home_pattern": "task_dashboard",
            "navigation": "top",
            "density": "standard",
        }
        text = json.dumps(
            {"summary": "改为顶部导航", "planning": new_planning},
            ensure_ascii=False,
        )
        server = _start_server([text])
        try:
            with _patched_env(server):
                result = propose_revision(
                    _base_job(), self._current_planning(), "改为顶部导航"
                )
        finally:
            _stop_server(server)
        self.assertEqual(result.planning.ui_plan.shell, "top_workspace")
        self.assertEqual(result.summary, "改为顶部导航")

    def test_revision_repairs_invalid_json(self):
        new_planning = {**VALID_PLANNING}
        new_planning["ui_plan"] = {
            "shell": "split_console",
            "home_pattern": "task_dashboard",
            "navigation": "split",
            "density": "standard",
        }
        server = _start_server(
            [
                "不是 JSON",
                json.dumps(
                    {"summary": "改为分栏", "planning": new_planning},
                    ensure_ascii=False,
                ),
            ]
        )
        try:
            with _patched_env(server):
                result = propose_revision(
                    _base_job(), self._current_planning(), "改为分栏控制台"
                )
        finally:
            _stop_server(server)
        self.assertEqual(result.planning.ui_plan.shell, "split_console")
        self.assertEqual(len(_ScriptedHandler.requests_received), 2)

    def test_revision_raises_after_two_failures(self):
        server = _start_server(["无效响应", "也无效"])
        try:
            with _patched_env(server):
                with self.assertRaises(ValueError):
                    propose_revision(
                        _base_job(), self._current_planning(), "无效指令"
                    )
        finally:
            _stop_server(server)
        self.assertEqual(len(_ScriptedHandler.requests_received), 2)

    def test_revision_does_not_use_rule_fallback(self):
        """当 LLM 失败两次时，propose_revision 必须抛错，绝不回退到规则改写。"""
        # 关键检验：返回值不能是 _rule_based_revision 路径产生的
        # 旧版在没有 LLM 时会返回 actual_mode == "rules"；新版无此字段
        result_planning = {**VALID_PLANNING}
        # 模拟 LLM 完全失败
        server = _start_server(["bad1", "bad2"])
        try:
            with _patched_env(server):
                with self.assertRaises(Exception):
                    propose_revision(
                        _base_job(), self._current_planning(), "删除勤务模块"
                    )
        finally:
            _stop_server(server)


class IndustryKnowledgeIndependenceTests(unittest.TestCase):
    """验证 Planner 不再依赖 industry_knowledge 模块。"""

    def test_planner_does_not_import_industry_context(self):
        # 直接 inspect 源代码（去掉文档字符串和注释）
        import inspect
        import re
        source = inspect.getsource(planner)
        # 去掉三引号字符串和单行注释
        no_docstring = re.sub(r'"""[\s\S]*?"""', "", source)
        no_docstring = re.sub(r"'''[\s\S]*?'''", "", no_docstring)
        no_docstring = re.sub(r"#.*", "", no_docstring)
        self.assertNotIn("planning_context", no_docstring)
        self.assertNotIn("from .industry_knowledge", no_docstring)
        self.assertNotIn("import industry_knowledge", no_docstring)
        self.assertNotIn("template_planning", no_docstring)
        self.assertNotIn("validate_planning_against_context", no_docstring)
        self.assertNotIn("_validate_llm_industry_alignment", no_docstring)
        self.assertNotIn("_rule_based_revision", no_docstring)
        self.assertNotIn("_module_ui", no_docstring)
        self.assertNotIn("_ui_plan_for", no_docstring)

    def test_planner_result_has_no_mode_field(self):
        # PlannerResult 现在只有 planning + model
        fields = (
            PlannerResult.model_fields.keys()
            if hasattr(PlannerResult, "model_fields")
            else []
        )
        self.assertNotIn("actual_mode", fields)
        self.assertNotIn("requested_mode", fields)
        self.assertNotIn("fallback_reason", fields)


if __name__ == "__main__":
    unittest.main()
