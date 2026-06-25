"""ISSUE-020: AI UI 增强分阶段协议测试。

协议要点：
- 5 个 UI 子步骤（ui_theme / ui_shell / ui_business / ui_dashboard / ui_responsive）
  + 1 个 README 文档增强，独立 try/except + 独立超时 + 独立重试 + 按步回滚。
- 风格方案（ui_theme）必须由 AI 返回，不允许本地哈希令牌伪装为 AI 成功。
- 单子步骤 CSS 块必须落在白名单选择器内；超长 / 越界 / 含 JS-Vue 片段会被拒绝。
- auto 模式：单子步骤失败只回滚该步骤，前序成功 CSS 保留，后续步骤继续。
- llm 模式：任一最终失败必须整体回滚。
"""

import json
import os
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.enhancer import (
    UI_ENHANCEMENT_STEPS,
    _call_chat_completion_with_deadline,
    _call_chat_json,
    _loads_last_json_object,
    _sanitize_json_strings,
    enhance_project,
    restore_enhancement,
)


# --------------------- Mock HTTP 服务 ---------------------

UI_DEFAULT_RESPONSES = {
    "theme": {
        "summary": "AI 风格方案：现代蓝灰，业务感强",
        "tokens": {
            "primary": "#0a3a8c",
            "accent": "#1f9bd6",
            "dark": "#081c3f",
            "soft": "#e9f3ff",
            "radius": "12px",
            "texture": "linear-gradient(135deg, var(--ai-primary), var(--ai-accent))",
            "name": "ai-blue-grey",
        },
        "notes": ["柔和阴影", "圆角 12px"],
    },
    "shell": {
        "summary": "应用壳层升级：登录页与导航",
        "content": ".login-page{background:linear-gradient(135deg, var(--ai-primary), var(--ai-dark));}\n.shell-top>header{backdrop-filter:blur(8px);}",
        "selectors": [".login-page", ".shell-top>header", ".hero", ":root"],
    },
    "business": {
        "summary": "业务页面升级：卡片与表格",
        "content": ".el-card{box-shadow:0 6px 18px rgba(20,60,110,.08);border-radius:var(--ai-radius);}\n.kpi-card{background:var(--ai-soft);}",
        "selectors": [".el-card", ".kpi-card", ".el-table"],
    },
    "dashboard": {
        "summary": "驾驶舱升级：KPI 与图表",
        # ISSUE-024：dashboard mock 用新白名单里的真实生成器 class（.kpi-grid / .kpi-trend）。
        "content": ".kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;}\n.kpi-trend{color:var(--ai-accent);font-weight:600;}\n.trend-svg{filter:drop-shadow(0 4px 8px rgba(0,0,0,.1));}",
        "selectors": [".kpi-grid", ".kpi-trend", ".trend-svg"],
    },
    "responsive": {
        "summary": "响应式与可访问性",
        "content": "@media (max-width:1000px){.shell-split{grid-template-columns:1fr;}}",
        "selectors": ["@media", ".shell-split", ".kpi-card"],
    },
}


class UIEnhancerHandler(BaseHTTPRequestHandler):
    """按 step 关键字派发 UI 响应，按 target_file 派发 README 响应。"""

    response_content: dict = {}
    fail_steps: dict = {}  # step_key -> {"fail_times": int, "http": int}
    call_records: list = []  # [(kind, key), ...]
    # ISSUE-022：dynamic_responses 支持按调用次序返回不同响应（key -> [r1, r2, ...]）。
    dynamic_responses: dict = {}

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        payload = json.loads(body.decode("utf-8"))
        user_payload = json.loads(payload["messages"][1]["content"])
        # 兼容两种入口
        if "step" in user_payload:
            kind = "ui"
            key = user_payload["step"]
        else:
            kind = "file"
            key = user_payload.get("target_file", "")
        self.call_records.append((kind, key))

        # 检查 fail 列表
        fail = self.fail_steps.get(key, {})
        already = self.call_records.count((kind, key))
        if already <= fail.get("fail_times", 0):
            http = fail.get("http", 529)
            payload_body = json.dumps({"error": "overloaded"}).encode("utf-8")
            self.send_response(http)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload_body)))
            self.end_headers()
            self.wfile.write(payload_body)
            return

        if kind == "ui":
            # ISSUE-022：dynamic_responses 优先，按调用次序弹出响应。
            queue = self.dynamic_responses.get(key)
            if queue:
                content = queue.pop(0)
                if not queue:
                    self.dynamic_responses.pop(key, None)
            else:
                content = self.response_content.get(key, UI_DEFAULT_RESPONSES.get(key, {
                    "summary": f"默认 {key}",
                    "content": f".{key}-x{{color:red;}}",
                    "selectors": [".x", ":root"],
                }))
        else:
            content = self.response_content.get(key, {
                "summary": f"增强 {key}",
                "files": [{"path": key, "content": f"Enhanced {key}"}],
            })

        if isinstance(content, dict) and content.get("_delay"):
            time.sleep(float(content["_delay"]))

        response = {
            "choices": [
                {"message": {"content": json.dumps(content, ensure_ascii=False)}}
            ]
        }
        encoded = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):  # noqa: A002
        return


def _start_mock_server() -> HTTPServer:
    UIEnhancerHandler.call_records = []
    UIEnhancerHandler.response_content = {}
    UIEnhancerHandler.fail_steps = {}
    UIEnhancerHandler.dynamic_responses = {}
    server = HTTPServer(("127.0.0.1", 0), UIEnhancerHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


# --------------------- 公共 helper ---------------------


def _setup_project(root: Path) -> None:
    (root / "frontend/src").mkdir(parents=True, exist_ok=True)
    (root / "frontend/src/App.vue").write_text(
        "<template><h1>Template</h1></template>", encoding="utf-8"
    )
    (root / "frontend/src/style.css").write_text("body{color:#000;}", encoding="utf-8")
    (root / "README.md").write_text("# Template", encoding="utf-8")


def _env_for(server: HTTPServer) -> dict:
    return {
        "AI_PLANNER_BASE_URL": f"http://127.0.0.1:{server.server_port}/v1",
        "AI_PLANNER_API_KEY": "test-key",
        "AI_CODEGEN_MODEL": "test-codegen",
    }


def _ui_keys() -> list:
    return [key for key, _ in UI_ENHANCEMENT_STEPS]


def _ui_css_keys() -> list:
    """4 个 UI CSS 子步骤的 key（theme 风格方案是单独请求）"""
    return [k for k in _ui_keys() if k != "theme"]


# --------------------- 测试用例 ---------------------


class EnhancerTests(unittest.TestCase):
    def test_daemon_worker_uses_transport_timeout_without_child_process(self):
        with patch(
            "app.enhancer.multiprocessing.current_process",
            return_value=SimpleNamespace(daemon=True),
        ), patch(
            "app.enhancer.subprocess.run",
            return_value=SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"ok": True, "content": '{"ok": true}'}),
                stderr="",
            ),
        ) as run, patch(
            "app.enhancer._chat_completion_request",
        ) as request, patch(
            "app.enhancer.multiprocessing.get_context"
        ) as context:
            result = _call_chat_completion_with_deadline(
                "https://example.invalid/v1",
                "test-key",
                "test-model",
                [{"role": "user", "content": "test"}],
                12,
            )

        self.assertEqual(result, '{"ok": true}')
        run.assert_called_once()
        request.assert_not_called()
        context.assert_not_called()

    def test_daemon_subprocess_error_is_reported(self):
        with patch(
            "app.enhancer.multiprocessing.current_process",
            return_value=SimpleNamespace(daemon=True),
        ), patch(
            "app.enhancer.subprocess.run",
            return_value=SimpleNamespace(
                returncode=1,
                stdout=json.dumps({"ok": False, "error": "provider down"}),
                stderr="",
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "provider down"):
                _call_chat_completion_with_deadline(
                    "https://example.invalid/v1",
                    "test-key",
                    "test-model",
                    [{"role": "user", "content": "test"}],
                    12,
                )

    def test_sanitize_json_strings_replaces_lone_surrogates(self):
        cleaned = _sanitize_json_strings(
            {"messages": [{"role": "user", "content": "bad \udc80 text"}]}
        )

        self.assertNotIn("\udc80", cleaned["messages"][0]["content"])
        json.dumps(cleaned, ensure_ascii=False).encode("utf-8")

    def test_daemon_subprocess_payload_is_ascii_safe(self):
        captured = {}

        def fake_run(*args, **kwargs):
            captured["input"] = kwargs["input"]
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"ok": True, "content": "{}"}),
                stderr="",
            )

        with patch(
            "app.enhancer.multiprocessing.current_process",
            return_value=SimpleNamespace(daemon=True),
        ), patch("app.enhancer.subprocess.run", side_effect=fake_run):
            result = _call_chat_completion_with_deadline(
                "https://example.invalid/v1",
                "test-key",
                "test-model",
                [{"role": "user", "content": "bad \udc80 text"}],
                12,
            )

        self.assertEqual(result, "{}")
        captured["input"].encode("utf-8")
        self.assertNotIn("\udc80", captured["input"])

    def test_loads_last_json_object_ignores_extra_stdout_lines(self):
        result = _loads_last_json_object(
            "debug line\n"
            + json.dumps({"ok": True, "content": "done"}, ensure_ascii=True)
            + "\n"
        )

        self.assertEqual(result["content"], "done")

    def test_call_chat_json_does_not_multiply_transport_retries(self):
        calls = {"count": 0}

        def fail_request(*args, **kwargs):
            calls["count"] += 1
            raise RuntimeError("Code enhancer API read timed out")

        with patch.dict(os.environ, {"AI_CODEGEN_MAX_ATTEMPTS": "3"}, clear=False), patch(
            "app.enhancer._call_chat_completion_with_deadline",
            side_effect=fail_request,
        ), patch("app.enhancer.time.sleep"):
            with self.assertRaisesRegex(RuntimeError, "read timed out"):
                _call_chat_json(
                    "https://example.invalid/v1",
                    "test-key",
                    "test-model",
                    [{"role": "user", "content": "{}"}],
                    1,
                )

        self.assertEqual(calls["count"], 3)

    def test_template_mode_does_not_change_files(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            _setup_project(project)
            result = enhance_project(
                {"codegen_mode": "template"},
                {"software_name": "Test"},
                project,
                Path(directory) / "backup",
            )
            self.assertEqual(result.actual_mode, "template")
            self.assertIn("Template", (project / "README.md").read_text())

    def test_auto_mode_six_step_protocol(self):
        """auto 模式：5 UI 子步骤 + README，按 UI_ENHANCEMENT_STEPS 顺序调用。"""
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                with patch.dict(os.environ, _env_for(server), clear=False):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试软件"},
                        project,
                        Path(directory) / "backup",
                    )
                self.assertEqual(result.actual_mode, "llm")
                # 5 个 UI 子步骤（theme → shell → business → dashboard → responsive）按顺序调用
                self.assertEqual(
                    [v for k, v in UIEnhancerHandler.call_records if k == "ui"],
                    _ui_keys(),
                    f"UI 步骤顺序错: {UIEnhancerHandler.call_records}",
                )
                # theme 走独立的 plan 请求，作为 ui 步发出
                self.assertEqual(
                    UIEnhancerHandler.call_records[-1],
                    ("file", "README.md"),
                    "README must execute after all UI stages",
                )
                self.assertTrue(
                    any(k == "ui" and v == "theme" for k, v in UIEnhancerHandler.call_records),
                    f"theme 计划请求未触发: {UIEnhancerHandler.call_records}",
                )
                # README 单独作为 file
                self.assertTrue(
                    any(k == "file" and v == "README.md" for k, v in UIEnhancerHandler.call_records)
                )
                # style.css 含 4 个追加步 marker（theme 是 plan 步，不写 style.css）
                css = (project / "frontend/src/style.css").read_text(encoding="utf-8")
                for key, _ in UI_ENHANCEMENT_STEPS[1:]:  # 跳过 theme
                    self.assertIn(f"AI UI Enhancer: {key}", css)
                # 业务类（App.vue）保持模板
                self.assertIn(
                    "Template", (project / "frontend/src/App.vue").read_text()
                )
                # README 增强
                self.assertIn("Enhanced README", (project / "README.md").read_text())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_invalid_ui_block_is_rejected(self):
        """非法 selector / 越界 / 含 JS 片段的 CSS 块应被拒绝且不写入。"""
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                # business 返回带 Vue 路由片段（被禁止）
                UIEnhancerHandler.response_content["business"] = {
                    "summary": "带 Vue 路由片段",
                    "content": ".kpi-card{color:red;}\n<router-view />\nimport App from './App.vue'",
                    "selectors": [".kpi-card"],
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试软件"},
                        project,
                        Path(directory) / "backup",
                    )
                self.assertEqual(result.actual_mode, "llm")
                # 5 步中 business 失败；前序 theme / shell 保留；
                # 后续 dashboard / responsive 继续
                failed = [
                    s for s in result.ui_steps or [] if s.get("status") == "failed"
                ]
                self.assertEqual(
                    [s["step"] for s in failed], ["business"],
                    f"应只有 business 失败: {result.ui_steps}",
                )
                css = (project / "frontend/src/style.css").read_text(encoding="utf-8")
                # 前序 shell marker 仍在
                self.assertIn("AI UI Enhancer: shell", css)
                # business marker 不在（失败回滚）
                self.assertNotIn("AI UI Enhancer: business", css)
                # 后续 dashboard marker 在
                self.assertIn("AI UI Enhancer: dashboard", css)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_actual_css_selectors_cannot_bypass_declared_selectors(self):
        """Declared selectors cannot allow extra selectors in the actual CSS."""
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                UIEnhancerHandler.response_content["business"] = {
                    "summary": "out-of-scope selector",
                    "content": ".el-card{color:red;} .unapproved-layout{display:none;}",
                    "selectors": [".el-card"],
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "test"},
                        project,
                        Path(directory) / "backup",
                    )
                business = next(
                    step for step in result.ui_steps if step["step"] == "business"
                )
                self.assertEqual(business["status"], "failed")
                self.assertIn("CSS", business["failure_reason"])
                css = (project / "frontend/src/style.css").read_text(encoding="utf-8")
                self.assertNotIn("unapproved-layout", css)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_llm_mode_two_failures_rolls_back(self):
        """ISSUE-022：llm 模式 ≥2 个 UI 子步骤最终失败 → 整体回滚 style.css 和 README。

        llm 模式现在容忍 1 步失败（旧版任一失败即整体回滚）；此测试模拟
        theme 与 dashboard 持续 529，确保两个独立步同时失败仍触发整体回滚。
        """
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                # theme 与 dashboard 持续失败（fail_times=99 > 任何重试上限）
                UIEnhancerHandler.fail_steps["theme"] = {
                    "fail_times": 99, "http": 529
                }
                UIEnhancerHandler.fail_steps["dashboard"] = {
                    "fail_times": 99, "http": 529
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    with self.assertRaises(RuntimeError):
                        enhance_project(
                            {"codegen_mode": "llm"},
                            {"software_name": "测试"},
                            project,
                            Path(directory) / "backup",
                        )
                # style.css 与 README 都应回到模板（仍在 with 块内，目录未删）
                css = (project / "frontend/src/style.css").read_text(encoding="utf-8")
                self.assertEqual(css.strip(), "body{color:#000;}")
                self.assertEqual(
                    (project / "README.md").read_text(encoding="utf-8"), "# Template"
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_transient_529_retries_then_succeeds(self):
        server, thread = _start_mock_server()
        try:
            seen = []
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                # dashboard 第一次 529，第二次正常
                UIEnhancerHandler.fail_steps["dashboard"] = {
                    "fail_times": 1, "http": 529
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                        progress_callback=lambda event: seen.append(event.copy()),
                    )
            self.assertEqual(result.actual_mode, "llm")
            failed = [
                s for s in result.ui_steps or [] if s.get("status") == "failed"
            ]
            self.assertEqual(failed, [], f"重试后不应该有 failed: {result.ui_steps}")
            # dashboard 调用了 2 次
            self.assertEqual(
                sum(1 for k, _ in UIEnhancerHandler.call_records if k == "ui" and _ == "dashboard"),
                2,
            )
            self.assertTrue(
                any(
                    event.get("step") == "dashboard"
                    and event.get("status") == "retrying"
                    for event in seen
                ),
                f"request retry must be visible: {seen}",
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_app_vue_router_views_never_appear(self):
        """绝对禁止 LLM 返回 App.vue / router.js / views/* 片段。"""
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                # 尝试在 shell 注入 Vue 路由
                UIEnhancerHandler.response_content["shell"] = {
                    "summary": "尝试改 App.vue",
                    "content": ".shell-top{color:red;}\n<router-view />\nimport App from './App.vue'",
                    "selectors": [".shell-top"],
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
                self.assertEqual(result.actual_mode, "llm")
                # shell 失败，因含 Vue 路由片段
                shell_step = next(
                    s for s in result.ui_steps if s["step"] == "shell"
                )
                self.assertEqual(shell_step["status"], "failed")
                self.assertIn("router-view", shell_step["failure_reason"])
                # App.vue 没被改
                self.assertIn(
                    "Template", (project / "frontend/src/App.vue").read_text()
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_invalid_selector_block_is_rejected_without_slow_payload(self):
        """旧 8000 字符上限已升级为 16000 + 精简重试。

        这里保留"非法 CSS 块不应写入"的基础回归，但不再用 9000 字符长串
        模拟超长，避免把测试时间消耗在无意义的选择器解析上。
        """
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                UIEnhancerHandler.response_content["business"] = {
                    "summary": "非法选择器",
                    "content": ".unapproved-layout{color:red;}",
                    "selectors": [".unapproved-layout"],
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
            self.assertEqual(result.actual_mode, "llm")
            failed = [
                s["step"] for s in result.ui_steps or [] if s.get("status") == "failed"
            ]
            self.assertIn("business", failed)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_progress_callback_receives_ui_keys(self):
        """progress_callback 必须按 step key 推进 running / completed。"""
        server, thread = _start_mock_server()
        try:
            seen = []
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):

                    def cb(event):
                        seen.append((event.get("step"), event.get("status")))

                    enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                        progress_callback=cb,
                    )
            # 每个 UI 步骤至少出现一次 running + completed
            for key, _ in UI_ENHANCEMENT_STEPS:
                self.assertIn((key, "completed"), seen, f"missing {key} completed")
                self.assertIn((key, "running"), seen, f"missing {key} running")
            # README 也出现
            self.assertIn(("readme", "running"), seen)
            self.assertIn(("readme", "completed"), seen)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_extract_json_handles_llm_explanations_after_object(self):
        """回归：ISSUE-020 现场任务 `20260623155910-f232b739` 触发
        `JSONDecodeError: Extra data: line 28 column 1 (char 903)`。

        LLM 经常在合法 JSON 后追加说明文字，旧实现用 ``rfind("}")`` 抓尾巴
        导致解析失败；现改用平衡大括号扫描，必须能完整提取首个 JSON 对象。
        """
        from app.enhancer import _extract_json

        # 场景 1：JSON 后跟一段说明
        sample_1 = (
            '{"summary": "现代蓝灰", "tokens": {"primary": "#0a3a8c"}}\n\n'
            "（以上是设计方案，按需求给出风格令牌）"
        )
        out_1 = _extract_json(sample_1)
        self.assertEqual(out_1["summary"], "现代蓝灰")
        self.assertEqual(out_1["tokens"]["primary"], "#0a3a8c")

        # 场景 2：JSON 之后又跟了完整 JSON
        sample_2 = (
            '{"summary": "first"}\n{"summary": "second"}'
        )
        out_2 = _extract_json(sample_2)
        self.assertEqual(out_2["summary"], "first")

        # 场景 3：带代码围栏 + 后续说明
        sample_3 = (
            "```json\n"
            '{"summary": "theme plan", "tokens": {"primary": "#fff"}}\n'
            "```\n"
            "已生成上述方案。"
        )
        out_3 = _extract_json(sample_3)
        self.assertEqual(out_3["summary"], "theme plan")

        # 场景 4：字符串字面量内含 '{' 和 '}' 不能误判
        sample_4 = (
            '{"summary": "value with { and } inside", "tokens": {"primary": "#000"}}'
        )
        out_4 = _extract_json(sample_4)
        self.assertIn("{ and }", out_4["summary"])
        self.assertEqual(out_4["tokens"]["primary"], "#000")

        # 场景 5：合法 JSON 后没有任何多余内容
        sample_5 = '{"summary": "clean"}'
        self.assertEqual(_extract_json(sample_5)["summary"], "clean")

        # 场景 6：完全没有 JSON
        with self.assertRaises(ValueError):
            _extract_json("没有任何 JSON 对象的纯文本")

        # 场景 7：{ 但不闭合
        with self.assertRaises(ValueError):
            _extract_json('{"unclosed": ')

    def test_llm_response_with_trailing_text_passes_through_ui_enhancement(self):
        """回归：LLM 返回 JSON + 解释文本时，UI 增强整体仍能成功，不应被解析失败阻断。"""
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                # 拦截 HTTP 响应，在 JSON 后追加说明文字
                def patched_do_POST(self):
                    # 调用原始 POST 拿到 content
                    body = self.rfile.read(int(self.headers["Content-Length"]))
                    payload = json.loads(body.decode("utf-8"))
                    user_payload = json.loads(payload["messages"][1]["content"])
                    if "step" in user_payload:
                        kind = "ui"
                        key = user_payload["step"]
                    else:
                        kind = "file"
                        key = user_payload.get("target_file", "")
                    self.call_records.append((kind, key))
                    content = UI_DEFAULT_RESPONSES.get(key, {
                        "summary": f"增强 {key}",
                        "files": [{"path": key, "content": f"Enhanced {key}"}],
                    })
                    # 把每个默认响应附上尾随说明
                    extra = "\n\n/* 上述为 AI 风格方案，下方继续增强 */"
                    body = json.dumps({
                        "choices": [{
                            "message": {"content": json.dumps(content, ensure_ascii=False) + extra}
                        }]
                    }, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                mock_patches = [
                    patch.object(UIEnhancerHandler, "do_POST", patched_do_POST),
                    patch.dict(os.environ, _env_for(server), clear=False),
                    patch("app.enhancer.time.sleep"),
                ]
                with mock_patches[0], mock_patches[1], mock_patches[2]:
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
            # 5 步应全部成功（trailing 文本被 _extract_json 剥掉）
            failed = [
                s for s in result.ui_steps or [] if s.get("status") == "failed"
            ]
            self.assertEqual(failed, [], f"trailing 文本导致增强失败: {result.ui_steps}")
            self.assertEqual(result.actual_mode, "llm")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


    # ----------------- ISSUE-022 新增回归测试 -----------------

    def test_responsive_allows_basic_selectors(self):
        """ISSUE-022：responsive 步必须接受 Element Plus 基础选择器。

        jobId=20260623225150-e2f31fbd 的 responsive 步曾因白名单缺失 :root /
        html / .el-button / select / textarea 导致整步 failed。
        ISSUE-024：再补 ``*`` 与 ``html`` 全局重置选择器，验证 responsive 步允许
        全局 ``* { box-sizing }`` 与 ``html, body { ... }`` 写入。
        """
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                # 让 responsive 返回包含 :root、html、*、.el-button、select、textarea 的 CSS
                UIEnhancerHandler.response_content["responsive"] = {
                    "summary": "包含基础选择器的响应式 CSS",
                    "content": (
                        "* { box-sizing: border-box; }\n"
                        ":root{--ai-spacing:18px;}\n"
                        "html,body{font-size:14px;}\n"
                        ".el-button{border-radius:8px;}\n"
                        "select,textarea{min-height:32px;}\n"
                        "@media (max-width:1000px){.shell-split{grid-template-columns:1fr;}}\n"
                    ),
                    "selectors": [":root", "html", "body", "*", ".el-button", "select", "textarea", ".shell-split"],
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
                responsive = next(
                    s for s in result.ui_steps if s["step"] == "responsive"
                )
                self.assertEqual(
                    responsive["status"], "completed",
                    f"responsive 步应通过白名单校验: {responsive}",
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_shell_allows_split_console_selectors(self):
        """ISSUE-024：shell 步必须接受 ``split_console`` 壳层特有的
        ``.shell-split`` / ``.shell-main`` / ``.shell-split .menu``。

        jobId=20260624095339-9d44c135 暴露 split_console 壳层下
        LLM 写 ``.shell-split`` / ``.shell-main`` 被旧白名单拒。
        """
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                UIEnhancerHandler.response_content["shell"] = {
                    "summary": "split_console 壳层升级",
                    "content": (
                        ".shell-split{display:grid;grid-template-columns:240px 1fr;}\n"
                        ".shell-main{padding:24px;background:var(--ai-soft);}\n"
                        ".shell-split .menu a{padding:10px 13px;}\n"
                    ),
                    "selectors": [".shell-split", ".shell-main", ".shell-split .menu"],
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
                shell = next(s for s in result.ui_steps if s["step"] == "shell")
                self.assertEqual(
                    shell["status"], "completed",
                    f"shell 步应允许 .shell-split / .shell-main: {shell}",
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_shell_allows_html_and_universal_selectors(self):
        """ISSUE-024：shell 步必须接受 ``html`` 与裸 ``*`` 全局重置选择器。

        jobId=20260624095339-9d44c135 暴露 LLM 写 ``html { ... }`` /
        ``* { box-sizing }`` 被拒；二者已并入 ``GLOBAL_UI_SELECTOR_HINTS``。
        """
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                UIEnhancerHandler.response_content["shell"] = {
                    "summary": "全局基础样式",
                    "content": (
                        "*{box-sizing:border-box;margin:0;}\n"
                        "html{font-family:'PingFang SC',sans-serif;}\n"
                        "*::before,*::after{box-sizing:inherit;}\n"
                    ),
                    "selectors": ["*", "html", "*::before", "*::after"],
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
                shell = next(s for s in result.ui_steps if s["step"] == "shell")
                self.assertEqual(
                    shell["status"], "completed",
                    f"shell 步应允许 html 与裸 *: {shell}",
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_shell_allows_at_media_query(self):
        """ISSUE-024：shell 步必须接受 ``@media`` 响应式断点。

        split_console / top_workspace 模板内嵌 ``@media(max-width:1000px)``；
        LLM 想覆盖壳层响应式行为时不能被拒。
        """
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                UIEnhancerHandler.response_content["shell"] = {
                    "summary": "壳层响应式断点",
                    "content": (
                        "@media (max-width:900px){.shell-top>header{grid-template-columns:1fr auto;}}\n"
                        ".shell-top{height:76px;padding:0 30px;}\n"
                    ),
                    "selectors": ["@media", ".shell-top", ".shell-top>header"],
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
                shell = next(s for s in result.ui_steps if s["step"] == "shell")
                self.assertEqual(
                    shell["status"], "completed",
                    f"shell 步应允许 @media: {shell}",
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_business_allows_element_plus_bem_modifiers(self):
        """ISSUE-024：business 步必须接受 Element Plus BEM 派生类。

        ``.el-card__header`` / ``.el-button--success`` 等由 Element Plus 渲染时
        自动注入；白名单用 ``.el-card__*`` / ``.el-button--*`` 通配覆盖。
        """
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                UIEnhancerHandler.response_content["business"] = {
                    "summary": "Element Plus 派生类定制",
                    "content": (
                        ".el-card__header{padding:12px 16px;background:var(--ai-soft);}\n"
                        ".el-card__body{padding:16px;}\n"
                        ".el-button--success{background:#22c55e;border-color:#22c55e;}\n"
                        ".el-button--warning{background:#f59e0b;border-color:#f59e0b;}\n"
                        ".el-tag--danger{background:#ef4444;color:#fff;}\n"
                        ".el-dialog__header{padding:16px 24px;}\n"
                    ),
                    "selectors": [
                        ".el-card__header", ".el-card__body",
                        ".el-button--success", ".el-button--warning",
                        ".el-tag--danger", ".el-dialog__header",
                    ],
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
                business = next(s for s in result.ui_steps if s["step"] == "business")
                self.assertEqual(
                    business["status"], "completed",
                    f"business 步应允许 Element Plus BEM 派生: {business}",
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_business_allows_safe_shell_selectors(self):
        """E2E regression: harmless shell CSS in business step should not burn retries."""
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                UIEnhancerHandler.response_content["business"] = {
                    "summary": "Safe shell polish in business step",
                    "content": (
                        ".login-card{box-shadow:0 18px 45px rgba(31,41,90,.16);}\n"
                        ".shell-main{background:#f8f7ff;}\n"
                    ),
                    "selectors": [".login-card", ".shell-main"],
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "Test"},
                        project,
                        Path(directory) / "backup",
                    )
                business = next(s for s in result.ui_steps if s["step"] == "business")
                self.assertEqual(business["status"], "completed", business)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_dashboard_allows_real_generator_selectors(self):
        """ISSUE-024：dashboard 步必须接受生成器实际渲染的 class。

        ``.kpi-grid`` / ``.kpi-trend`` / ``.dashboard-row`` / ``.module-dashboard``
        取代旧白名单里的 ``.metric-grid`` / ``.kpi-icon``。
        """
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                UIEnhancerHandler.response_content["dashboard"] = {
                    "summary": "实际生成器 class 适配",
                    "content": (
                        ".kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;}\n"
                        ".kpi-trend{color:var(--ai-accent);font-weight:600;}\n"
                        ".kpi-trend-down .kpi-trend{color:#dc2626;}\n"
                        ".kpi-spark{height:32px;}\n"
                        ".dashboard-row{display:grid;grid-template-columns:1fr 1fr;gap:18px;}\n"
                        ".module-dashboard{padding:24px;}\n"
                    ),
                    "selectors": [
                        ".kpi-grid", ".kpi-trend", ".kpi-trend-down .kpi-trend",
                        ".kpi-spark", ".dashboard-row", ".module-dashboard",
                    ],
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
                dashboard = next(s for s in result.ui_steps if s["step"] == "dashboard")
                self.assertEqual(
                    dashboard["status"], "completed",
                    f"dashboard 步应允许真实生成器 class: {dashboard}",
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_responsive_allows_dashboard_layout_selectors(self):
        """ISSUE-024：responsive 步必须接受 dashboard 布局 class。

        LLM 在小屏适配时通常会覆盖 ``.kpi-grid`` / ``.dashboard-row`` 等；
        旧白名单只列了 ``.metric-grid`` 等近似 class，导致小屏断点被拒。
        """
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                UIEnhancerHandler.response_content["responsive"] = {
                    "summary": "小屏布局响应式",
                    "content": (
                        "@media (max-width:1000px){\n"
                        ".kpi-grid{grid-template-columns:repeat(2,1fr);}\n"
                        ".dashboard-row{grid-template-columns:1fr;}\n"
                        ".module-dashboard{grid-template-columns:1fr 1fr;}\n"
                        ".status-row{grid-template-columns:1fr;}\n"
                        ".analysis-workbench{grid-template-columns:1fr;}\n"
                        "}\n"
                    ),
                    "selectors": [
                        "@media", ".kpi-grid", ".dashboard-row",
                        ".module-dashboard", ".status-row", ".analysis-workbench",
                    ],
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
                responsive = next(
                    s for s in result.ui_steps if s["step"] == "responsive"
                )
                self.assertEqual(
                    responsive["status"], "completed",
                    f"responsive 步应允许 dashboard 布局 class: {responsive}",
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_forbidden_selectors_still_rejected_after_whitelist_expansion(self):
        """ISSUE-024（P0-3）：放宽白名单同时，必须守住越界禁片。

        即使白名单含 ``.el-card__*`` / ``*`` 等通配，``<router-view`` /
        ``v-on:click`` / ``import `` / ``function(`` / ``=>`` 等仍被拒。
        """
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                # shell 步返回包含 v-on:click / import / function( 等越界片段
                UIEnhancerHandler.response_content["shell"] = {
                    "summary": "越界 shell",
                    "content": (
                        ".shell-top{color:red;}\n"
                        "/* @click=\"active\" 这里看起来像 Vue 事件 */\n"
                        "/* import App from './App.vue' */\n"
                    ),
                    "selectors": [".shell-top"],
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
                shell = next(s for s in result.ui_steps if s["step"] == "shell")
                self.assertEqual(
                    shell["status"], "failed",
                    f"shell 步应被禁片规则拒: {shell}",
                )
                self.assertIn("禁止片段", shell["failure_reason"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_selector_audit_collects_real_selectors(self):
        """ISSUE-024（P0-2）：``selector_audit.collect_real_selectors`` 必须从
        生成项目 ``frontend/src`` 收集真实 class，并合并入运行时 hints。
        """
        from app.selector_audit import collect_real_selectors, merge_with_hints

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            (project / "frontend/src").mkdir(parents=True, exist_ok=True)
            (project / "frontend/src/style.css").write_text(
                ".real-class{color:red;}\n.real-derived span{font-weight:600;}\n",
                encoding="utf-8",
            )
            (project / "frontend/src/views").mkdir(parents=True, exist_ok=True)
            (project / "frontend/src/views/Foo.vue").write_text(
                '<template><div class="vue-class another-class">x</div></template>',
                encoding="utf-8",
            )
            real = collect_real_selectors(project)
            self.assertIn(".real-class", real)
            # 规则选择器按 "," 拆分多 selector，所以 `.real-derived span` 整体保留。
            self.assertIn(".real-derived span", real)
            self.assertIn("vue-class", real)
            self.assertIn("another-class", real)
            # dashboard 步必须包含 .real-derived 启发式分类
            merged = merge_with_hints(
                {"theme": (), "shell": (), "business": (), "dashboard": (), "responsive": ()},
                real,
            )
            # .real-derived 含 dashboard 关键字（kpi/trend/dashboard 等），本测试不强求分类，
            # 只验证合并后 hints 是 dict 且 key 完整。
            self.assertEqual(
                set(merged.keys()), {"theme", "shell", "business", "dashboard", "responsive"},
            )

    def test_partial_failures_link_issue_024(self):
        """ISSUE-024（P1-1）：enhance 阶段部分失败时，``append_enhance_error``
        写入的修复建议链接必须指向 ``ISSUE-024.md`` 而非历史误指的 ``ISSUE-022.md``。
        """
        from unittest.mock import patch as _patch
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                # 让全部 5 个 UI 步返回越界片段，全部失败 → style.css 未改 → partial
                fail_response = {
                    "summary": "越界",
                    "content": ".shell-top{color:red;}\n/* v-on:click=\"x\" */\n",
                    "selectors": [".shell-top"],
                }
                # dashboard/business/responsive 用同一个越界模板也会因禁片失败
                for key in ("shell", "business", "dashboard", "responsive"):
                    UIEnhancerHandler.response_content[key] = dict(fail_response)
                # 让 theme 也越界，确保 5 步全部失败
                UIEnhancerHandler.response_content["theme"] = dict(fail_response)
                # 但禁片匹配的内容触发 _validate_ui_block 失败，
                # theme 步 _request_theme_step 校验失败也会被 catch。
                # README 改不变（默认会改 README）。
                learnings_dir = Path(directory) / "learnings"
                learnings_dir.mkdir()
                with _patch.dict(os.environ, _env_for(server), clear=False), _patch(
                    "app.enhancer.time.sleep"
                ), _patch(
                    "app.learning.default_learnings_root", return_value=learnings_dir,
                ):
                    result = enhance_project(
                        {"job_id": "job-issue024", "codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
                # style.css 未改 + README 可能改 → actual_mode ∈ {"partial", "template"}
                self.assertIn(result.actual_mode, {"partial", "template"})
                err_file = learnings_dir / f"ERRORS-{__import__('datetime').datetime.now().strftime('%Y%m%d')}-enhance.md"
                self.assertTrue(err_file.exists(), f".learnings 应有失败记录: {err_file}")
                content = err_file.read_text(encoding="utf-8")
                self.assertIn("ISSUE-024", content)
                self.assertNotIn("ISSUE-022.md", content)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_dashboard_oversized_block_retries_with_trim_prompt(self):
        """ISSUE-022：dashboard 步返回超长 CSS 时，反馈模型精简后应成功。

        第一次响应 17000 字符（超 16000 默认上限），触发 ValidationError +
        1 次精简反馈重试；第二次响应 5000 字符，验证 status=completed 且总调用 2 次。
        """
        server, thread = _start_mock_server()
        try:
            oversized = {
                "summary": "超长响应",
                "content": ".kpi-card{color:red;}\n" + "x" * 17000,
                "selectors": [".kpi-card"],
            }
            trimmed = {
                "summary": "精简后",
                "content": ".kpi-card{color:red;}\n.trend-svg path{stroke-width:2;}",
                "selectors": [".kpi-card", ".trend-svg"],
            }
            UIEnhancerHandler.dynamic_responses["dashboard"] = [oversized, trimmed]

            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
                dashboard = next(
                    s for s in result.ui_steps if s["step"] == "dashboard"
                )
                self.assertEqual(
                    dashboard["status"], "completed",
                    f"dashboard 精简重试应成功: {dashboard}",
                )
                dashboard_calls = sum(
                    1 for k, _ in UIEnhancerHandler.call_records
                    if k == "ui" and _ == "dashboard"
                )
                self.assertEqual(
                    dashboard_calls, 2,
                    f"dashboard 应被调用 2 次（首次超长 + 精简重试），实际 {dashboard_calls}",
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_business_recovers_from_read_timeout_with_backoff(self):
        """ISSUE-022：business 步首次 socket.timeout(经 _chat_completion_request
        转为 RuntimeError)后，_retry_with_backoff 通过指数退避 + jitter 退避后第二次成功。
        """
        from app import enhancer as _enhancer

        server, thread = _start_mock_server()
        try:
            call_count = {"n": 0}

            def fake_call(base_url, api_key, model, messages, timeout):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    # 模拟 _chat_completion_request 把 socket.timeout 转 RuntimeError
                    raise RuntimeError("Code enhancer API read timed out")
                return _enhancer._chat_completion_request(
                    base_url, api_key, model, messages, timeout,
                )

            sleep_values = []

            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)

                def fake_sleep(seconds):
                    sleep_values.append(seconds)

                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer._call_chat_completion_with_deadline",
                    side_effect=fake_call,
                ), patch("app.enhancer.time.sleep", side_effect=fake_sleep), patch(
                    "app.enhancer.random.uniform", return_value=0.5,
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )

                self.assertEqual(result.actual_mode, "llm")
                self.assertGreaterEqual(
                    call_count["n"], 2,
                    f"business 应至少被调用 2 次（首次超时 + 重试成功），实际 {call_count['n']}",
                )
                self.assertGreater(
                    len(sleep_values), 0,
                    "应有退避 sleep 调用",
                )
                # 首次 retry sleep 应在 [1, 3) 范围（2^0=1 + jitter 0.5）
                self.assertGreaterEqual(sleep_values[0], 1.0)
                self.assertLess(sleep_values[0], 3.0)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_llm_mode_tolerates_one_ui_step_failure(self):
        """ISSUE-022：llm 模式容忍 1 个 UI 步失败（≥4/5 成功即视为 llm 增强）。"""
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                # 让 business 持续 529，其他步正常
                UIEnhancerHandler.fail_steps["business"] = {
                    "fail_times": 99, "http": 529
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "llm"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
                # business 失败但其他 4 步成功 → actual_mode=llm，不抛错
                self.assertEqual(result.actual_mode, "llm")
                failed = [
                    s["step"] for s in result.ui_steps or [] if s.get("status") == "failed"
                ]
                self.assertEqual(failed, ["business"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_actual_mode_partial_when_only_readme_changed(self):
        """ISSUE-022：4 个 UI CSS 步全失败 + README 成功 → actual_mode=partial。"""
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                # 4 个 UI CSS 步全部持续失败
                for step_key in ("shell", "business", "dashboard", "responsive"):
                    UIEnhancerHandler.fail_steps[step_key] = {
                        "fail_times": 99, "http": 529
                    }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
                self.assertEqual(
                    result.actual_mode, "partial",
                    f"4 UI 步全失败 + README 成功应得 partial，实际 {result.actual_mode}",
                )
                self.assertIn("README.md", result.changed_files)
                self.assertNotIn("frontend/src/style.css", result.changed_files)
                self.assertIn("仅 README 由 AI 增强", result.summary or "")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_partial_failures_write_to_learnings(self):
        """ISSUE-022：enhance 阶段出现失败步时，append_enhance_error 被调用一次。"""
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                # 让 business 持续失败触发 failures 非空
                UIEnhancerHandler.fail_steps["business"] = {
                    "fail_times": 99, "http": 529
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ), patch(
                    "app.enhancer.append_enhance_error"
                ) as mock_append:
                    enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
                self.assertGreaterEqual(
                    mock_append.call_count, 1,
                    "enhance 失败时 append_enhance_error 应被调用至少 1 次",
                )
                # 验证调用参数含失败步标识
                call_args = mock_append.call_args
                self.assertIn("business", str(call_args))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_business_allows_pagination_and_pseudo_element(self):
        """ISSUE-025：business 步必须接受 Element Plus 全家族（`.el-pagination` /
        `.btn-prev` / `.btn-next`）与派生类 + 伪元素组合（`.el-table--border::after`）。

        jobId=20260624140839-03bb66f7 暴露 business 步真实 LLM 写出
        ``.el-table--border::after``（修饰符 + 伪元素）、``.el-pagination``
        （Element Plus 整个分页组件）、``.btn-prev`` / ``.btn-next``
        （Element Plus 2.x 内部按钮类）三类被拒。
        """
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                UIEnhancerHandler.response_content["business"] = {
                    "summary": "Element Plus 分页与表格派生",
                    "content": (
                        ".el-table--border::after{content:'';border:1px solid var(--ai-border);}\n"
                        ".el-pagination{padding:8px 0;display:flex;gap:6px;}\n"
                        ".el-pagination .btn-prev,\n"
                        ".el-pagination .btn-next{min-width:32px;height:32px;}\n"
                        ".el-pagination .el-pager li{color:var(--ai-textMuted);}\n"
                    ),
                    "selectors": [
                        ".el-table--border::after",
                        ".el-pagination",
                        ".el-pagination .btn-prev",
                        ".el-pagination .btn-next",
                        ".el-pagination .el-pager li",
                    ],
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
                business = next(s for s in result.ui_steps if s["step"] == "business")
                self.assertEqual(
                    business["status"], "completed",
                    f"business 步应允许 Element Plus 全家族 + 伪元素: {business}",
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_dashboard_allows_llm_derived_selectors(self):
        """ISSUE-025：dashboard 步必须接受 LLM 自创的"模块名 + 功能"派生类。

        jobId=20260624140839-03bb66f7 暴露 dashboard 步真实 LLM 写出
        ``.dashboard-trend-card`` / ``.m-trend-up`` / ``.pattern-dashboard`` 等
        生成器里没有的派生类。
        """
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                UIEnhancerHandler.response_content["dashboard"] = {
                    "summary": "LLM 自创 dashboard 派生",
                    "content": (
                        ".dashboard-trend-card{background:var(--ai-soft);padding:16px;border-radius:10px;}\n"
                        ".m-trend-up{color:var(--ai-success);font-weight:600;}\n"
                        ".pattern-dashboard{display:grid;grid-template-columns:repeat(3,1fr);}\n"
                        ".dashboard-task_dashboard{margin-top:12px;}\n"
                    ),
                    "selectors": [
                        ".dashboard-trend-card",
                        ".m-trend-up",
                        ".pattern-dashboard",
                        ".dashboard-task_dashboard",
                    ],
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
                dashboard = next(s for s in result.ui_steps if s["step"] == "dashboard")
                self.assertEqual(
                    dashboard["status"], "completed",
                    f"dashboard 步应允许 LLM 自创派生: {dashboard}",
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_business_allows_custom_button_classes(self):
        """ISSUE-025：business 步必须接受 LLM 自定义按钮类（``.btn-primary`` /
        ``.btn-ghost``）与 ``.module-*`` / ``.task-*`` / ``.form-*`` 派生。
        """
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                UIEnhancerHandler.response_content["business"] = {
                    "summary": "自定义按钮 + 模块派生",
                    "content": (
                        ".btn-primary{background:var(--ai-primary);color:#fff;border-radius:8px;}\n"
                        ".btn-ghost{background:transparent;color:var(--ai-primary);}\n"
                        ".module-vehicle-archives .task-list{padding:12px;}\n"
                        ".form-search-bar{display:flex;gap:8px;}\n"
                    ),
                    "selectors": [
                        ".btn-primary", ".btn-ghost",
                        ".module-vehicle-archives .task-list",
                        ".form-search-bar",
                    ],
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
                business = next(s for s in result.ui_steps if s["step"] == "business")
                self.assertEqual(
                    business["status"], "completed",
                    f"business 步应允许 .btn-* / .module-* / .form-*: {business}",
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_responsive_allows_page_heading_and_actions(self):
        """ISSUE-025：responsive 步必须接受 ``.page-heading`` / ``.actions`` /
        ``.btn-primary`` / ``.btn-ghost``。jobId=20260624140839-03bb66f7 暴露
        responsive 步真实 LLM 写 ``.page-heading .actions .btn-primary`` 复合选择器
        被拒。
        """
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                UIEnhancerHandler.response_content["responsive"] = {
                    "summary": "page-heading 与 actions 响应式",
                    "content": (
                        "@media (max-width:768px){\n"
                        ".page-heading{flex-direction:column;align-items:flex-start;}\n"
                        ".page-heading h2{font-size:18px;}\n"
                        ".page-heading .actions{margin-top:8px;width:100%;}\n"
                        ".page-heading .actions .btn-primary,\n"
                        ".page-heading .actions .btn-ghost{width:100%;}\n"
                        "}\n"
                    ),
                    "selectors": [
                        "@media",
                        ".page-heading", ".page-heading h2",
                        ".page-heading .actions",
                        ".page-heading .actions .btn-primary",
                        ".page-heading .actions .btn-ghost",
                    ],
                }
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
                responsive = next(
                    s for s in result.ui_steps if s["step"] == "responsive"
                )
                self.assertEqual(
                    responsive["status"], "completed",
                    f"responsive 步应允许 .page-heading / .actions / .btn-*: {responsive}",
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_workflow_logger_imported(self):
        """ISSUE-026：``backend/app/workflow.py`` 在 ``continue_material_generation``
        末尾调用 ``logger.warning``，ISSUE-023 P1-3 实施时遗漏了模块顶部
        ``import logging`` 与 ``logger = logging.getLogger(__name__)``，导致
        用户进入"软著材料打包"阶段时抛 ``NameError: name 'logger' is not defined``
        直接阻断任务。

        本测试仅验证模块级 ``logger`` 可被导入且名字正确，避免回归。
        """
        from app import workflow

        self.assertTrue(hasattr(workflow, "logger"))
        self.assertEqual(workflow.logger.name, "app.workflow")

    def test_daemon_worker_read_timeout_bounded(self):
        """ISSUE-026：daemon Worker 下 ``urllib.request.urlopen(timeout=)`` 只覆盖
        TCP connect，不覆盖 SSL read；jobId=20260624160110-58039b6d 的 business
        步 SSL read 挂死 1006s（16 分钟），原 ``max_attempts=3`` 仍救不回。

        修复：daemon Worker 走普通 Python subprocess，并由 ``subprocess.run`` 的
        timeout 杀掉卡在 SSL read 的子进程；不能用 ThreadPoolExecutor，因为线程无法
        被 Python 安全杀死。
        """
        from app.enhancer import _call_chat_completion_with_deadline

        with patch("app.enhancer.multiprocessing.current_process",
                   return_value=SimpleNamespace(daemon=True)), patch(
            "app.enhancer.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["python", "-c", "..."], 12),
        ):
            start = time.monotonic()
            with self.assertRaises(RuntimeError) as ctx:
                _call_chat_completion_with_deadline(
                    "https://example.invalid/v1",
                    "test-key",
                    "test-model",
                    [{"role": "user", "content": "test"}],
                    2,  # 2 秒请求 timeout，daemon 子进程硬截止窗口为 12s
                )
            elapsed = time.monotonic() - start
            self.assertIn("daemon worker", str(ctx.exception))
            self.assertLess(
                elapsed, 1,
                f"daemon read timeout 必须在 wall-clock 窗口内抛出，实际 {elapsed:.1f}s",
            )

    def test_empty_css_response_is_skipped(self):
        """ISSUE-026：LLM 在两次重试后仍返回空 CSS（纯注释，无任何裸规则），
        原行为让该步 ``failed`` 并阻断任务；现在应标 ``skipped``，不影响其他步。

        jobId=20260624160110-58039b6d 的 responsive 步两次都返回
        ``@media(max-width:1000px){/* 仅有适配说明 */}``，但 ``_css_rule_selectors``
        会把 ``@media`` 整体作为 selector，所以本测试用真正"无任何 selector"的
        响应（``/* 仅适配说明 */``）模拟更彻底的空响应。
        """
        server, thread = _start_mock_server()
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                _setup_project(project)
                # 5 步 UI 都返回纯注释，无任何裸 CSS 规则
                empty_response = {
                    "summary": "空响应",
                    "content": "/* 仅适配说明，无具体规则 */",
                    "selectors": [],
                }
                for key in ("shell", "business", "dashboard", "responsive"):
                    UIEnhancerHandler.response_content[key] = dict(empty_response)
                with patch.dict(os.environ, _env_for(server), clear=False), patch(
                    "app.enhancer.time.sleep"
                ):
                    result = enhance_project(
                        {"codegen_mode": "auto"},
                        {"software_name": "测试"},
                        project,
                        Path(directory) / "backup",
                    )
                # 4 步 UI（shell/business/dashboard/responsive）应全部 skipped；
                # theme 步不走 _validate_ui_block（仅校验 UIEnhancementPlan schema），
                # 所以可能 completed，不强制要求。
                target_keys = {"shell", "business", "dashboard", "responsive"}
                for step in result.ui_steps:
                    if step["step"] in target_keys:
                        self.assertEqual(
                            step["status"], "skipped",
                            f"{step['step']} 步空 CSS 应标 skipped，实际 {step['status']}",
                        )
                shell_step = next(s for s in result.ui_steps if s["step"] == "shell")
                self.assertIn("不含任何 CSS 规则", shell_step["summary"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
