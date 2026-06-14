import json
import tempfile
import unittest
from pathlib import Path

from docx import Document

from app.compliance import build_compliance_report


class ComplianceTests(unittest.TestCase):
    def test_consistent_materials_score_full_points(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "generated_project"
            docs = root / "docs"
            screenshots = root / "screenshots"
            (project / "frontend/src").mkdir(parents=True)
            (project / "backend/src/main/java/com/example/items").mkdir(parents=True)
            docs.mkdir()
            screenshots.mkdir()

            planning = {
                "software_name": "测试管理系统",
                "modules": [
                    {
                        "key": "items",
                        "name": "信息管理",
                        "pages": ["信息列表"],
                        "fields": ["名称", "状态"],
                    }
                ],
            }
            (root / "planning.json").write_text(
                json.dumps(planning, ensure_ascii=False), encoding="utf-8"
            )
            (root / "code_stats.json").write_text(
                json.dumps({"total_lines": 100}), encoding="utf-8"
            )
            (project / "frontend/src/App.vue").write_text(
                "<template>测试管理系统 信息管理</template>", encoding="utf-8"
            )
            (project / "backend/src/main/java/com/example/items/ItemsController.java").write_text(
                '@RequestMapping("/api/items") class ItemsController {}',
                encoding="utf-8",
            )
            for filename, text in [
                ("设计说明书.docx", "测试管理系统 信息管理"),
                ("用户操作手册.docx", "测试管理系统 信息管理"),
                ("源代码材料.docx", "测试管理系统\n" + "code\n" * 100),
                ("软件著作权申请信息表.docx", "测试管理系统"),
            ]:
                document = Document()
                document.add_paragraph(text)
                document.save(docs / filename)
            (screenshots / "01-login.png").write_bytes(b"png")
            (screenshots / "02-dashboard.png").write_bytes(b"png")
            (screenshots / "03-信息管理.png").write_bytes(b"png")

            report = build_compliance_report(root)
            self.assertEqual(report["score"], 100)
            self.assertTrue(report["passed"])
            self.assertEqual(report["grade"], "优秀")


if __name__ == "__main__":
    unittest.main()
