"""ISSUE-010 / 011：dashboard 视觉增强与源码原创性测试。"""

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from app.workflow import (
    OUTPUT_ROOT,
    _json_read,
    _json_write,
    _now,
    create_job,
    generate_java_project,
)


def _make_planning(name: str = "监所管理系统") -> dict:
    return {
        "software_name": name,
        "description": "用于监所人员档案、案件关联、勤务管理和统计研判",
        "software_type": "管理系统",
        "industry_type": "public_security",
        "industry_name": "公安",
        "target_users": "监所民警",
        "ui_plan": {
            "shell": "top_workspace",
            "home_pattern": "metric_dashboard",
            "navigation": "top",
            "density": "standard",
        },
        "modules": [
            {
                "key": "detainee_archives",
                "name": "在押人员档案",
                "description": "在押人员基本信息与变动",
                "pages": ["档案列表", "档案详情"],
                "fields": ["档案编号", "姓名", "入所时间", "状态", "风险等级"],
                "page_pattern": "master_detail",
                "detail_pattern": "workflow_timeline",
                "edit_pattern": "drawer",
            },
            {
                "key": "duty_arrangement",
                "name": "勤务安排",
                "description": "民警值班、交接班、巡更路线",
                "pages": ["值班表", "交接记录"],
                "fields": ["班次", "值班人", "交接时间", "巡更路线", "备注"],
                "page_pattern": "workflow_timeline",
                "detail_pattern": "master_detail",
                "edit_pattern": "form_wizard",
            },
            {
                "key": "cell_management",
                "name": "监室管理",
                "description": "监室分配、床位、违规记录",
                "pages": ["监室列表", "分配记录"],
                "fields": ["监室号", "床位数", "当前人数", "负责人", "违规次数"],
                "page_pattern": "tree_detail",
                "detail_pattern": "master_detail",
                "edit_pattern": "dialog",
            },
            {
                "key": "statistics",
                "name": "统计研判",
                "description": "在押人数趋势、案件关联、风险预警",
                "pages": ["数据概览", "趋势分析"],
                "fields": ["统计日期", "在押人数", "案件关联数", "风险等级", "同比"],
                "page_pattern": "dashboard",
                "detail_pattern": "master_detail",
                "edit_pattern": "dialog",
            },
        ],
        "database_tables": [
            "ed_detainee_archives",
            "ed_duty_arrangement",
            "ed_cell_management",
            "ed_statistics",
        ],
        "api_list": [
            "GET /api/detainee_archives",
            "POST /api/detainee_archives",
            "GET /api/duty_arrangement",
            "GET /api/statistics",
        ],
        "screenshots": ["登录页", "首页", "在押人员档案", "勤务安排", "监室管理", "统计研判"],
        "document_outline": [
            "系统概述", "总体架构", "功能设计", "数据设计", "接口设计", "部署说明"
        ],
    }


class DashboardVisualTests(unittest.TestCase):
    """ISSUE-010：dashboard 至少 3 类视觉组件同时出现 + 业务化 KPI 文案差异化。"""

    def setUp(self):
        self.tmp = OUTPUT_ROOT / "_test_dashboard"
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_metric_dashboard_has_kpi_donut_line_trend_and_activities(self):
        from app.project_generator import _dashboard_vue

        planning = _make_planning()
        menu = [
            {"key": m["key"], "name": m["name"]}
            for m in planning["modules"]
        ]
        vue = _dashboard_vue(planning, menu)
        # KPI 卡片（4 张）
        self.assertEqual(vue.count("kpi-card"), 4)
        # 业务化 KPI 文案应包含监所关键词
        self.assertIn("在押人数", vue)
        # SVG 折线趋势
        self.assertIn("trend-svg", vue)
        self.assertIn("trend-line", vue)
        # SVG 环形
        self.assertIn("donut-svg", vue)
        # 状态分布图例
        self.assertIn("donut-legend", vue)
        # 分组柱状
        self.assertIn("bar-svg", vue)
        # 最近动态
        self.assertIn("最近业务动态", vue)
        self.assertIn("activity-", vue)

    def test_different_industries_produce_different_kpi(self):
        from app.project_generator import _kpi_indicators_for_planning

        jian = _kpi_indicators_for_planning(_make_planning("监所人员档案管理系统"))
        anjian = _kpi_indicators_for_planning({
            "software_name": "案件管理",
            "software_type": "案件系统",
            "modules": [
                {
                    "key": "cases",
                    "name": "案件管理",
                    "description": "案件",
                    "pages": ["x"],
                    "fields": ["x"],
                }
            ],
        })
        # 不同行业关键词应触发不同的 KPI 文案
        self.assertNotEqual(
            [k["label"] for k in jian],
            [k["label"] for k in anjian],
        )
        self.assertIn("在押人数", [k["label"] for k in jian])
        self.assertIn("案件总数", [k["label"] for k in anjian])

    def test_status_distribution_uses_industry_specific_labels(self):
        from app.project_generator import _status_distribution_for_planning

        jian = _status_distribution_for_planning(_make_planning("监所管理系统"))
        anjian = _status_distribution_for_planning(
            {**_make_planning(), "software_name": "案件管理系统"}
        )
        # 监所行业应含"高危"等业务化标签
        self.assertIn("高危", [d["label"] for d in jian])
        # 案件应含"在办"等
        self.assertIn("在办", [d["label"] for d in anjian])

    def test_trend_series_is_deterministic_and_non_trivial(self):
        from app.project_generator import _trend_series_for_planning

        s1 = _trend_series_for_planning(_make_planning())
        s2 = _trend_series_for_planning(_make_planning())
        # 同一软件名应产生相同序列（确定性）
        self.assertEqual(s1, s2)
        # 序列应有起伏
        self.assertGreater(max(s1) - min(s1), 10)
        # 默认 7 天
        self.assertEqual(len(s1), 7)

    def test_trend_series_is_stable_across_python_processes(self):
        code = (
            "from app.project_generator import _trend_series_for_planning, _project_fingerprint;"
            "from pathlib import Path;"
            "p={'software_name':'监所管理系统','software_type':'管理系统','modules':[]};"
            "print(_trend_series_for_planning(p));"
            "print(_project_fingerprint(p, Path('x'))['differentiation']['seed'])"
        )
        first = subprocess.check_output(
            [sys.executable, "-c", code],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
        )
        second = subprocess.check_output(
            [sys.executable, "-c", code],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
        )

        self.assertEqual(first, second)

    def test_module_dashboard_preview_uses_svg_and_tags(self):
        from app.project_generator import _vue_page

        stats = next(
            m for m in _make_planning()["modules"] if m["key"] == "statistics"
        )
        vue = _vue_page(stats)
        # 模块 dashboard 也应该用 SVG 折线和业务化标签
        self.assertIn("mini-trend-svg", vue)
        self.assertIn("m-trend-up", vue)
        self.assertIn("tag-warn", vue)
        self.assertIn("业务说明", vue)


class BusinessCommentTests(unittest.TestCase):
    """ISSUE-011：Java/Vue/SQL 加入业务化中文注释。"""

    def setUp(self):
        self.tmp = OUTPUT_ROOT / "_test_comments"
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_java_entity_has_business_class_comment(self):
        from app.project_generator import _entity

        planning = _make_planning()
        module = planning["modules"][0]
        java = _entity("com.test", module, "ed_" + module["key"])
        # 业务类注释
        self.assertIn("在押人员档案", java)
        # 字段业务注释（Javadoc + 中文 label + 业务角色）
        # 档案编号 应匹配"业务编号或识别码"
        self.assertIn("档案编号：在押人员档案的业务编号或识别码字段", java)
        # 姓名 应匹配"业务主名称"
        self.assertIn("姓名：在押人员档案的业务主名称字段", java)

    def test_java_service_impl_has_method_business_comments(self):
        from app.project_generator import _service_impl

        planning = _make_planning()
        module = planning["modules"][1]
        java = _service_impl("com.test", module)
        # 类级业务注释
        self.assertIn("勤务安排：", java)
        # 方法内业务注释
        self.assertIn("// 分页查询", java)
        self.assertIn("// 新增：", java)
        self.assertIn("// 更新：", java)
        self.assertIn("// 删除：", java)

    def test_java_controller_has_method_business_comments(self):
        from app.project_generator import _controller

        planning = _make_planning()
        module = planning["modules"][0]
        java = _controller("com.test", module)
        # 类级业务注释
        self.assertIn("controller", java.lower())
        # 每个方法有 Javadoc 业务注释（实际包含"按主键"等前缀）
        self.assertIn("分页查询在押人员档案", java)
        self.assertIn("按主键获取在押人员档案", java)
        self.assertIn("新增在押人员档案", java)
        self.assertIn("按主键更新在押人员档案", java)
        self.assertIn("按主键删除在押人员档案", java)

    def test_sql_table_has_business_comment(self):
        from app.project_generator import _table_sql

        planning = _make_planning()
        module = planning["modules"][0]
        sql = _table_sql(module, "ed_detainee_archives")
        # 表级业务注释
        self.assertIn("-- 在押人员档案", sql)
        # 字段级注释（用 label 命中业务角色）
        self.assertIn("档案编号：", sql)
        self.assertIn("业务编号或识别码", sql)
        # 时间戳注释
        self.assertIn("记录创建时间", sql)
        self.assertIn("记录更新时间", sql)

    def test_vue_page_has_business_comment(self):
        from app.project_generator import _vue_page

        planning = _make_planning()
        module = planning["modules"][0]
        vue = _vue_page(module)
        # Vue 页面头部业务注释
        self.assertIn("<!-- 在押人员档案", vue)
        # 业务说明注释
        self.assertIn("业务说明", vue)


class ProjectFingerprintTests(unittest.TestCase):
    """ISSUE-011：生成 project_fingerprint.json 与 originality_report.json。"""

    def setUp(self):
        self.tmp = OUTPUT_ROOT / "_test_fingerprint"
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_project_fingerprint_records_modules_and_patterns(self):
        from app.project_generator import _project_fingerprint

        planning = _make_planning()
        fp = _project_fingerprint(planning, Path("dummy"))
        # 必须含核心字段
        self.assertEqual(fp["software"]["name"], "监所管理系统")
        self.assertEqual(fp["ui_plan"]["home_pattern"], "metric_dashboard")
        self.assertEqual(len(fp["modules"]), 4)
        self.assertEqual(fp["modules"][0]["table"], "ed_detainee_archives")
        # 字段组合按模块汇总
        self.assertIn("detainee_archives", fp["fields_by_module"])
        self.assertEqual(
            len(fp["fields_by_module"]["detainee_archives"]), 5
        )
        # 页面模式去重
        self.assertIn("master_detail", fp["page_patterns_used"])
        self.assertIn("workflow_timeline", fp["page_patterns_used"])
        self.assertIn("dashboard", fp["page_patterns_used"])
        # 注释风格
        self.assertEqual(fp["comment_style"]["language"], "zh-CN")
        # 差异化参数
        self.assertIn("seed", fp["differentiation"])
        self.assertIsInstance(fp["differentiation"]["seed"], int)

    def test_project_fingerprint_uses_actual_database_tables(self):
        from app.project_generator import _project_fingerprint

        planning = _make_planning()
        planning["database_tables"] = [
            "custom_detainee_table",
            "custom_duty_table",
            "custom_cell_table",
            "custom_statistics_table",
        ]

        fp = _project_fingerprint(planning, Path("dummy"))

        self.assertEqual(fp["modules"][0]["table"], "custom_detainee_table")
        self.assertEqual(fp["modules"][3]["table"], "custom_statistics_table")

    def test_originality_report_distinguishes_third_party_from_generated(self):
        from app.project_generator import _originality_report

        planning = _make_planning()
        report = _originality_report(planning, Path("dummy"))
        # 必须有原创性来源说明
        self.assertIn("business_kpi_indicators", report["originality_sources"])
        # 模板复用范围明确
        self.assertIn(
            "Java Controller/Service/Repository/Entity 模板",
            report["template_reuse_scope"]["deterministic_generator"],
        )
        # 业务化个性化
        self.assertIn(
            "KPI 指标文案（按行业关键词匹配）",
            report["template_reuse_scope"]["business_personalized"],
        )
        # 第三方依赖：backend 是列表，按项检查
        backend_text = " ".join(report["third_party_dependencies"]["backend"])
        self.assertIn("Spring Boot 3", backend_text)
        frontend_text = " ".join(report["third_party_dependencies"]["frontend"])
        self.assertIn("Vue 3", frontend_text)
        # 边界划分
        self.assertIn("deterministic_generated_code", report["boundaries"])
        self.assertIn("third_party_libraries", report["boundaries"])
        # 验证清单
        self.assertIn("project_fingerprint.json", report["validation"]["documentation_artifacts"])

    def test_generate_java_project_emits_fingerprint_files(self):
        # 端到端：调用 generate_java_project 检查产物
        with patch("app.workflow.OUTPUT_ROOT", self.tmp):
            job = create_job(
                {
                    "software_name": "测试软件",
                    "description": "测试",
                    "software_type": "管理系统",
                    "industry_type": "education",
                }
            )
            planning = _make_planning(name="测试系统")
            planning["software_name"] = "测试系统"
            planning["industry_type"] = "education"
            planning["industry_name"] = "教育"
            _json_write(self.tmp / job["job_id"] / "planning.json", planning)
            generate_java_project(self.tmp / job["job_id"])
        # 检查 project_fingerprint.json 与 originality_report.json
        root = self.tmp / job["job_id"] / "generated_project"
        self.assertTrue((root / "project_fingerprint.json").exists())
        self.assertTrue((root / "originality_report.json").exists())
        # 检查 THIRD_PARTY_NOTICES.md 仍存在
        self.assertTrue((root / "THIRD_PARTY_NOTICES.md").exists())
        # 校验 fingerprint JSON
        fp = _json_read(root / "project_fingerprint.json")
        self.assertEqual(fp["software"]["name"], "测试系统")
        # 校验 originality_report JSON
        report = _json_read(root / "originality_report.json")
        self.assertEqual(report["software_name"], "测试系统")
        self.assertIn("project_fingerprint.json", report["validation"]["documentation_artifacts"])


if __name__ == "__main__":
    unittest.main()
