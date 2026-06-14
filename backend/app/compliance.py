import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from docx import Document


def _docx_text(path: Path) -> str:
    document = Document(path)
    parts: List[str] = []
    for section in document.sections:
        parts.extend(paragraph.text for paragraph in section.header.paragraphs)
        parts.extend(paragraph.text for paragraph in section.footer.paragraphs)
    for paragraph in document.paragraphs:
        parts.append(paragraph.text)
    for table in document.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    return "\n".join(parts)


def _check(
    items: List[Dict[str, Any]],
    key: str,
    name: str,
    passed: bool,
    points: int,
    detail: str,
    suggestion: str = "",
) -> None:
    items.append(
        {
            "key": key,
            "name": name,
            "passed": passed,
            "points": points if passed else 0,
            "max_points": points,
            "detail": detail,
            "suggestion": "" if passed else suggestion,
        }
    )


def build_compliance_report(job_dir: Path) -> Dict[str, Any]:
    planning = json.loads((job_dir / "planning.json").read_text(encoding="utf-8"))
    stats = json.loads((job_dir / "code_stats.json").read_text(encoding="utf-8"))
    project = job_dir / "generated_project"
    app_vue = (project / "frontend" / "src" / "App.vue").read_text(
        encoding="utf-8", errors="ignore"
    )
    backend_code = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (project / "backend" / "src" / "main" / "java").rglob("*.java")
    )
    design_text = _docx_text(job_dir / "docs" / "设计说明书.docx")
    manual_text = _docx_text(job_dir / "docs" / "用户操作手册.docx")
    source_path = job_dir / "docs" / "源代码材料.docx"
    screenshots = list((job_dir / "screenshots").glob("*.png"))
    modules = planning["modules"]
    items: List[Dict[str, Any]] = []

    missing_frontend = [
        module["name"] for module in modules if module["name"] not in app_vue
    ]
    _check(
        items,
        "code_frontend_modules",
        "前端代码与规划模块一致",
        not missing_frontend,
        15,
        "全部模块均存在于前端代码"
        if not missing_frontend
        else "前端缺少：" + "、".join(missing_frontend),
        "补齐规划模块对应的菜单和页面。",
    )

    missing_backend = [
        module["key"]
        for module in modules
        if f'/api/{module["key"]}' not in backend_code
    ]
    _check(
        items,
        "code_backend_modules",
        "后端接口与规划模块一致",
        not missing_backend,
        15,
        "全部模块均有后端 API"
        if not missing_backend
        else "后端缺少：" + "、".join(missing_backend),
        "为缺失模块生成 GET/POST API。",
    )

    screenshot_names = [path.stem for path in screenshots]
    missing_screenshots = [
        module["name"]
        for module in modules
        if not any(module["name"] in name for name in screenshot_names)
    ]
    screenshot_base_ok = any("login" in name for name in screenshot_names) and any(
        "dashboard" in name for name in screenshot_names
    )
    _check(
        items,
        "screenshot_modules",
        "截图与规划模块一致",
        not missing_screenshots and screenshot_base_ok,
        15,
        f"共 {len(screenshots)} 张截图"
        if not missing_screenshots and screenshot_base_ok
        else "缺少：" + "、".join(missing_screenshots or ["登录页或首页"]),
        "重新运行截图 Agent，确保登录页、首页及全部确认模块均有截图。",
    )

    missing_design = [
        module["name"] for module in modules if module["name"] not in design_text
    ]
    _check(
        items,
        "design_modules",
        "设计说明书覆盖全部模块",
        not missing_design,
        15,
        "设计说明书模块完整"
        if not missing_design
        else "缺少：" + "、".join(missing_design),
        "按 planning.json 补齐功能设计章节。",
    )

    missing_manual = [
        module["name"] for module in modules if module["name"] not in manual_text
    ]
    _check(
        items,
        "manual_modules",
        "用户手册覆盖全部模块",
        not missing_manual,
        15,
        "用户手册模块完整"
        if not missing_manual
        else "缺少：" + "、".join(missing_manual),
        "按 planning.json 补齐操作说明。",
    )

    _check(
        items,
        "source_material",
        "源码材料有效",
        source_path.exists() and source_path.stat().st_size > 1000 and stats["total_lines"] > 0,
        10,
        f"真实源码 {stats['total_lines']} 行",
        "重新统计源码并生成源码材料。",
    )

    required_docs = {
        "设计说明书.docx",
        "用户操作手册.docx",
        "源代码材料.docx",
        "软件著作权申请信息表.docx",
    }
    current_docs = {path.name for path in (job_dir / "docs").glob("*.docx")}
    missing_docs = sorted(required_docs - current_docs)
    _check(
        items,
        "required_documents",
        "核心申请材料齐全",
        not missing_docs,
        10,
        "核心文档齐全" if not missing_docs else "缺少：" + "、".join(missing_docs),
        "重新执行文档生成阶段。",
    )

    names_consistent = all(
        planning["software_name"] in text
        for text in (design_text, manual_text, _docx_text(source_path))
    )
    _check(
        items,
        "software_name_consistency",
        "软件名称跨材料一致",
        names_consistent,
        5,
        "软件名称一致" if names_consistent else "部分材料未出现标准软件名称",
        "统一 planning.json 与全部文档中的软件名称。",
    )

    score = sum(item["points"] for item in items)
    max_score = sum(item["max_points"] for item in items)
    blockers = [item for item in items if not item["passed"] and item["max_points"] >= 15]
    if blockers:
        grade = "需整改"
    elif score >= 90:
        grade = "优秀"
    elif score >= 80:
        grade = "良好"
    elif score >= 70:
        grade = "基本合格"
    else:
        grade = "需整改"
    return {
        "score": score,
        "max_score": max_score,
        "grade": grade,
        "passed": score >= 80 and not blockers,
        "items": items,
        "summary": {
            "module_count": len(modules),
            "screenshot_count": len(screenshots),
            "source_lines": stats["total_lines"],
            "document_count": len(current_docs),
        },
        "suggestions": [item["suggestion"] for item in items if item["suggestion"]],
    }
