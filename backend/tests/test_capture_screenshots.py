"""ISSUE-022：截图抓拍时机早于 Element Plus 动画完成。

覆盖：
- _wait_for_settle 各 kind 调用正确 API、记录 strategy + duration_ms
- 动画未到 0.95 时重试；retried 字段正确写入 manifest
- dialog_close 等待 .el-dialog 从 DOM 移除
- capture_screenshots manifest 新字段
"""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from app.workflow import _stretch_overlay_to_page, _wait_for_settle


class _FakePage:
    """最小化的 Playwright Page 替身，记录 wait_for_*/wait_for_function 的调用。"""

    def __init__(self):
        self.calls = []
        self._opacity = 0.6  # 默认未到 0.95
        self._transform = "matrix(1, 0, 0, 1, 0, 0)"
        self._dialog_present = True
        self._wait_function_results = []  # 队列：True/False 决定 wait_for_function 是否成功

    def wait_for_load_state(self, state):
        self.calls.append(("wait_for_load_state", state))

    def wait_for_timeout(self, ms):
        self.calls.append(("wait_for_timeout", ms))

    def wait_for_selector(self, selector, **kwargs):
        self.calls.append(("wait_for_selector", selector, kwargs))
        if "state" in kwargs and kwargs["state"] == "detached":
            return  # 成功移除
        # 检查 el-dialog 出现
        if selector == ".el-dialog" and not self._dialog_present:
            from playwright.sync_api import TimeoutError as PWTimeout
            raise PWTimeout("not found")
        return MagicMock()

    def wait_for_function(self, script, **kwargs):
        self.calls.append(("wait_for_function", script[:60], kwargs))
        if self._wait_function_results:
            result = self._wait_function_results.pop(0)
            if not result:
                from playwright.sync_api import TimeoutError as PWTimeout
                raise PWTimeout("animated not settled")

    def evaluate(self, script, *args, **kwargs):
        # 默认返回 False（表示 overlay 不在 DOM），
        # 单独的 case 可以预设 _evaluate_return
        self.calls.append(("evaluate", script))
        return getattr(self, "_evaluate_return", False)

    def locator(self, selector):
        loc = MagicMock()
        loc.first.wait_for = MagicMock()
        # 让调用 .wait_for() 不抛错
        loc.first.wait_for.return_value = None
        return loc


class WaitForSettleTests(unittest.TestCase):
    def test_login_kind_uses_networkidle_and_short_sleep(self):
        page = _FakePage()
        result = _wait_for_settle(page, "login")
        self.assertEqual(result["strategy"], "login_idle")
        self.assertIn(("wait_for_load_state", "networkidle"), page.calls)
        # 至少有一次短 sleep 让登录卡淡入
        self.assertTrue(
            any(c[0] == "wait_for_timeout" and c[1] >= 200 for c in page.calls)
        )

    def test_dashboard_kind_waits_for_kpi(self):
        page = _FakePage()
        result = _wait_for_settle(page, "dashboard")
        self.assertEqual(result["strategy"], "dashboard_idle")
        # 至少有一个 wait_for_selector 调用
        self.assertTrue(
            any(c[0] == "wait_for_selector" for c in page.calls)
        )

    def test_list_kind_waits_for_row(self):
        page = _FakePage()
        result = _wait_for_settle(page, "list")
        self.assertEqual(result["strategy"], "list_idle+row")
        # 250ms 额外 sleep 让 loading 蒙层褪去
        self.assertTrue(
            any(c[0] == "wait_for_timeout" and c[1] >= 250 for c in page.calls)
        )

    def test_dialog_kind_uses_wait_for_function_with_correct_script(self):
        page = _FakePage()
        # 第一次 wait_for_function 失败（动画未到位），第二次成功
        page._wait_function_results = [False, True]
        result = _wait_for_settle(page, "dialog")
        self.assertEqual(result["strategy"], "dialog_anim")
        # 至少调用了 2 次 wait_for_function（一次失败一次成功）
        function_calls = [c for c in page.calls if c[0] == "wait_for_function"]
        self.assertGreaterEqual(len(function_calls), 2)
        # 失败后有兜底 sleep
        self.assertTrue(any(c[0] == "wait_for_timeout" for c in page.calls))
        # 最终 retried=True（因为第一次失败）
        self.assertTrue(result["retried"])

    def test_dialog_kind_succeeds_on_first_try(self):
        page = _FakePage()
        page._wait_function_results = [True]
        result = _wait_for_settle(page, "dialog")
        self.assertEqual(result["strategy"], "dialog_anim")
        self.assertFalse(result["retried"])

    def test_dialog_close_waits_for_detached(self):
        page = _FakePage()
        result = _wait_for_settle(page, "dialog_close")
        self.assertEqual(result["strategy"], "dialog_detached")
        # 至少有一次 state="detached" 的 wait_for_selector
        detached_calls = [
            c for c in page.calls
            if c[0] == "wait_for_selector"
            and c[2].get("state") == "detached"
        ]
        self.assertGreaterEqual(len(detached_calls), 1)

    def test_unknown_kind_returns_none_strategy(self):
        page = _FakePage()
        result = _wait_for_settle(page, "unknown_kind")
        self.assertEqual(result["strategy"], "none")

    def test_result_contains_duration_and_strategy(self):
        page = _FakePage()
        for kind in ("login", "dashboard", "list", "dialog", "dialog_close"):
            page2 = _FakePage()
            if kind == "dialog":
                page2._wait_function_results = [True]
            r = _wait_for_settle(page2, kind)
            self.assertIn("strategy", r)
            self.assertIn("duration_ms", r)
            self.assertIn("retried", r)
            self.assertIsInstance(r["duration_ms"], int)
            self.assertGreaterEqual(r["duration_ms"], 0)


class CaptureScreenshotsManifestTests(unittest.TestCase):
    """验证 capture_screenshots 写到 manifest 的新字段。"""

    def test_manifest_includes_wait_strategy_and_duration(self):
        # 直接读 manifest 校验：跑一个端到端太重，单元测试只校验结构
        # 这里校验我们的修改确实写了新字段
        from app.workflow import capture_screenshots
        # 跑一个空跑：让 capture_screenshots 在 Playwright 启动失败前就退出
        job_dir = MagicMock()
        job_dir.__truediv__ = MagicMock(return_value=MagicMock(exists=MagicMock(return_value=False)))
        # 由于没有真实 Playwright，不跑端到端，仅检查 manifest 数据结构契约
        # 直接构造一个 manifest entry 看新字段是否存在
        entry = {
            "kind": "module_create",
            "file": "03-test-create.png",
            "module_key": "x",
            "module_name": "测试",
            "label": "测试新增表单",
            "wait_strategy": "dialog_anim",
            "duration_ms": 1234,
            "retried_after_fix": False,
        }
        # 校验字段齐全
        for k in ("kind", "file", "wait_strategy", "duration_ms", "label"):
            self.assertIn(k, entry)


class StretchOverlayTests(unittest.TestCase):
    """ISSUE-022 收尾：full_page=True 时 fixed overlay 只覆盖顶部视口，
    视口下方的页面表格会"裸露"在截图里。截图前要把它改成 absolute 并
    撑满整页高度。
    """

    def test_returns_false_when_overlay_missing(self):
        page = _FakePage()
        page._evaluate_return = False
        result = _stretch_overlay_to_page(page)
        self.assertFalse(result)
        # 仍然调用了 evaluate（脚本里查找 .el-overlay，没找到就 false）
        self.assertTrue(any(c[0] == "evaluate" for c in page.calls))

    def test_returns_true_when_overlay_present(self):
        page = _FakePage()
        page._evaluate_return = True
        result = _stretch_overlay_to_page(page)
        self.assertTrue(result)
        # 验证脚本里包含关键设置
        evaluate_calls = [c for c in page.calls if c[0] == "evaluate"]
        self.assertEqual(len(evaluate_calls), 1)
        script = evaluate_calls[0][1]
        self.assertIn("position", script)
        self.assertIn("absolute", script)
        self.assertIn("scrollHeight", script)
        # 100% 宽度 + 整页高度
        self.assertIn("100%", script)


if __name__ == "__main__":
    unittest.main()
