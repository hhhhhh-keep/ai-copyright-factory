import unittest

from app.workflow import STEPS


class WorkflowOrderTests(unittest.TestCase):
    def test_demo_starts_before_screenshot(self):
        keys = [key for key, _ in STEPS]
        self.assertLess(keys.index("run"), keys.index("demo"))
        self.assertLess(keys.index("demo"), keys.index("screenshot"))
        self.assertLess(keys.index("screenshot"), keys.index("package"))


if __name__ == "__main__":
    unittest.main()
