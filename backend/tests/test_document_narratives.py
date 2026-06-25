import unittest
from unittest.mock import patch

from app.document_narratives import build_document_narratives


class DocumentNarrativeTests(unittest.TestCase):
    def setUp(self):
        self.planning = {
            "software_name": "测试系统", "software_type": "管理软件", "target_users": "业务人员",
            "modules": [{"key": "items", "name": "信息管理", "description": "维护信息", "pages": ["信息列表"], "fields": ["名称", "状态"]}],
        }
        self.actions = {"items": ["查询", "新增", "编辑"]}

    @patch("app.document_narratives._call")
    def test_valid_llm_output_is_used(self, call):
        call.return_value = '{"modules":[{"key":"items","overview":"信息管理模块用于维护名称和状态等已提供字段，并支持在已生成页面中完成查询和数据维护。","preconditions":["已登录系统"],"steps":[{"action":"进入信息管理","expected_result":"显示功能页"},{"action":"输入关键词","expected_result":"显示匹配记录"},{"action":"填写名称和状态","expected_result":"可保存业务信息"},{"action":"提交保存","expected_result":"列表刷新"}],"notes":["仅使用已生成操作"]}]}'
        narratives, meta = build_document_narratives(self.planning, self.actions)
        self.assertEqual(meta["mode"], "llm")
        self.assertEqual(len(narratives["items"]["steps"]), 4)

    @patch("app.document_narratives._call")
    def test_invalid_llm_output_falls_back_to_facts(self, call):
        call.return_value = '{"modules":[{"key":"unknown","overview":"x","steps":[]}]}'
        narratives, meta = build_document_narratives(self.planning, self.actions)
        self.assertEqual(meta["mode"], "template")
        self.assertIn("名称", narratives["items"]["overview"])
        self.assertEqual(len(narratives["items"]["steps"]), 4)


if __name__ == "__main__":
    unittest.main()
