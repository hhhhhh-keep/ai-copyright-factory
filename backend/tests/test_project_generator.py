import json
import tempfile
import unittest
from pathlib import Path

from app.project_generator import generate_java_project


class ProjectGeneratorTests(unittest.TestCase):
    def test_generates_java_crud_layers_vue_pages_and_mysql_sql(self):
        planning = {
            "software_name": "涉案车辆管理系统",
            "industry_name": "公安",
            "ui_plan": {
                "shell": "top_workspace",
                "home_pattern": "analysis_dashboard",
                "navigation": "top",
                "density": "comfortable",
            },
            "modules": [
                {
                    "key": "vehicles",
                    "name": "车辆管理",
                    "description": "维护涉案车辆信息",
                    "pages": ["车辆列表", "车辆登记"],
                    "fields": ["车牌号", "车辆品牌", "登记时间"],
                    "page_pattern": "master_detail",
                },
                {
                    "key": "cases",
                    "name": "案件管理",
                    "description": "维护案件信息",
                    "pages": ["案件列表", "案件登记"],
                    "fields": ["案件编号", "案件名称", "案件状态"],
                    "page_pattern": "workflow_timeline",
                },
                {
                    "key": "analysis",
                    "name": "统计研判",
                    "description": "统计业务数据",
                    "pages": ["研判概览"],
                    "fields": ["统计日期", "案件数量", "处置率"],
                    "page_pattern": "dashboard",
                },
            ],
            "database_tables": [
                "case_vehicles",
                "police_cases",
                "police_analysis_daily",
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            job_dir = Path(directory)
            (job_dir / "planning.json").write_text(
                json.dumps(planning, ensure_ascii=False),
                encoding="utf-8",
            )
            generate_java_project(job_dir)
            root = job_dir / "generated_project"
            java_root = root / "backend/src/main/java/com/aicopyright/copyright"
            module = java_root / "module/vehicles"
            for relative in (
                "entity/VehiclesEntity.java",
                "dto/VehiclesDTO.java",
                "vo/VehiclesVO.java",
                "mapper/VehiclesMapper.java",
                "service/VehiclesService.java",
                "service/impl/VehiclesServiceImpl.java",
                "controller/VehiclesController.java",
            ):
                self.assertTrue((module / relative).exists(), relative)
            self.assertTrue((root / "frontend/src/views/VehiclesPage.vue").exists())
            self.assertTrue((root / "frontend/src/api/vehicles.js").exists())
            sql = (root / "sql/init.sql").read_text(encoding="utf-8")
            self.assertIn("CREATE TABLE case_vehicles", sql)
            pom = (root / "backend/pom.xml").read_text(encoding="utf-8")
            self.assertIn("mybatis-plus-spring-boot3-starter", pom)
            self.assertIn("mysql-connector-j", pom)
            app_vue = (root / "frontend/src/App.vue").read_text(encoding="utf-8")
            self.assertIn("shell-top", app_vue)
            dashboard = (
                root / "frontend/src/views/DashboardPage.vue"
            ).read_text(encoding="utf-8")
            self.assertIn("analysis-workbench", dashboard)
            vehicle_page = (
                root / "frontend/src/views/VehiclesPage.vue"
            ).read_text(encoding="utf-8")
            self.assertIn("master-detail-preview", vehicle_page)
            self.assertTrue((root / "THIRD_PARTY_NOTICES.md").exists())


if __name__ == "__main__":
    unittest.main()
