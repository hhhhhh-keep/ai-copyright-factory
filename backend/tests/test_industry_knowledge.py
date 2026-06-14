import unittest

from app.industry_knowledge import (
    clarification_for,
    detect_industry,
    load_industries,
    planning_context,
)


class IndustryKnowledgeTests(unittest.TestCase):
    def test_loads_all_v1_industries(self):
        self.assertEqual(
            set(load_industries()),
            {"public_security", "justice", "industry", "education"},
        )

    def test_detects_public_security_from_software_name(self):
        industry = detect_industry("涉案车辆管理系统")
        self.assertEqual(industry["key"], "public_security")

    def test_clarification_returns_module_questions(self):
        result = clarification_for(
            "设备巡检系统",
            industry_key="industry",
        )
        self.assertEqual(result["industry"]["name"], "工业")
        self.assertGreaterEqual(len(result["questions"]), 5)
        self.assertTrue(all(item["question"] for item in result["questions"]))

    def test_context_uses_confirmed_modules_only(self):
        context = planning_context(
            {
                "software_name": "考试分析平台",
                "description": "用于考试和成绩分析",
                "industry_type": "education",
                "clarification_answers": {
                    "students": True,
                    "teachers": False,
                    "courses": True,
                    "exams": True,
                    "scores": True,
                    "analysis": False,
                },
            }
        )
        self.assertEqual(
            context["allowed_module_keys"],
            ["students", "courses", "exams", "scores"],
        )

    def test_rejects_less_than_three_modules(self):
        with self.assertRaisesRegex(ValueError, "至少需要选择 3 个"):
            planning_context(
                {
                    "software_name": "智慧校园",
                    "industry_type": "education",
                    "clarification_answers": {
                        "students": True,
                        "teachers": True,
                        "courses": False,
                        "exams": False,
                        "scores": False,
                        "analysis": False,
                    },
                }
            )


if __name__ == "__main__":
    unittest.main()
