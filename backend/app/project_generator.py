import json
import re
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _pascal(value: str) -> str:
    return "".join(part.capitalize() for part in value.split("_"))


def _camel(value: str) -> str:
    pascal = _pascal(value)
    return pascal[:1].lower() + pascal[1:]


_ACTION_LABELS = {
    "approve": "通过",
    "reject": "驳回",
    "quick_audit": "快速审核",
    "quickAudit": "快速审核",
    "transfer": "转交",
    "return": "退回补充",
    "archive": "归档",
    "submit": "提交",
    "cancel": "取消",
    "assign": "分派",
    "dispatch": "派发",
    "close": "办结",
    "start": "启动",
    "stop": "停止",
}

_CRUD_ACTION_CODES = {"page", "list", "get", "detail", "create", "update", "delete"}
_HTTP_ANNOTATIONS = {
    "GET": "GetMapping",
    "POST": "PostMapping",
    "PUT": "PutMapping",
    "DELETE": "DeleteMapping",
    "PATCH": "PatchMapping",
}
_JS_HTTP_METHODS = {
    "GET": "get",
    "POST": "post",
    "PUT": "put",
    "DELETE": "delete",
    "PATCH": "patch",
}


def _label_for_action(code: str) -> str:
    if code in _ACTION_LABELS:
        return _ACTION_LABELS[code]
    words = re.split(r"[_-]+", code)
    return "".join(word.capitalize() for word in words if word) or "业务操作"


def _action_method_name(code: str) -> str:
    method = _camel(code.replace("-", "_"))
    if method in {
        "return",
        "class",
        "default",
        "switch",
        "case",
        "try",
        "catch",
        "finally",
        "throw",
        "throws",
        "new",
        "public",
        "private",
        "protected",
        "static",
        "void",
    }:
        return f"{method}Action"
    return method


def _parse_business_actions(planning: Dict[str, Any]) -> Dict[str, List[Dict[str, str]]]:
    actions_by_module = {module["key"]: [] for module in planning.get("modules", [])}
    seen: Dict[str, set] = {key: set() for key in actions_by_module}
    for item in planning.get("api_list", []) or []:
        if not isinstance(item, str):
            continue
        match = re.match(
            r"^(GET|POST|PUT|DELETE|PATCH)\s+/api/([a-zA-Z0-9_]+)/\{id\}/([a-zA-Z0-9_/-]+)$",
            item.strip(),
            re.IGNORECASE,
        )
        if not match:
            continue
        method, module_key, raw_action = match.groups()
        module_key = module_key.lower()
        if module_key not in actions_by_module:
            continue
        code = raw_action.strip("/").split("/")[-1].replace("-", "_")
        if not code or code in _CRUD_ACTION_CODES or code in seen[module_key]:
            continue
        method = method.upper()
        actions_by_module[module_key].append(
            {
                "code": code,
                "label": _label_for_action(code),
                "method": method,
                "java_method": _action_method_name(code),
                "js_function": f"{_action_method_name(code)}{_pascal(module_key)}",
                "js_http_method": _JS_HTTP_METHODS.get(method, "post"),
                "annotation": _HTTP_ANNOTATIONS.get(method, "PostMapping"),
                "path": f"{{id}}/{code}",
            }
        )
        seen[module_key].add(code)
    return actions_by_module


def _planning_with_actions(planning: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(planning)
    actions = _parse_business_actions(planning)
    modules = []
    for module in planning.get("modules", []):
        item = dict(module)
        item["business_actions"] = actions.get(module["key"], [])
        modules.append(item)
    enriched["modules"] = modules
    return enriched


# ----------------- ISSUE-010 / 011：业务化指标、注释、指纹 -----------------


def _stable_seed(value: str, modulo: int = 997) -> int:
    """跨进程稳定 hash，避免 Python 内置 hash() 随进程随机化。"""
    digest = hashlib.sha256((value or "").encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % modulo


_BUSINESS_KEYWORDS: List[Tuple[str, List[str]]] = [
    # (pattern, list of 业务化 KPI 模板)；匹配时按 module.name 包含任一关键词
    ("监区|监所|在押|人员档案", [
        "在押人数", "今日新收", "风险预警", "解除办理", "档案完整率"
    ]),
    ("勤务|排班|值班|交接", [
        "值班人次", "排班冲突", "勤务完成率", "告警处置", "到岗打卡"
    ]),
    ("案件|办案|执法|案卷", [
        "案件总数", "在办案件", "已结案件", "超期案件", "立案受理"
    ]),
    ("车辆|布控|车管|轨迹", [
        "在管车辆", "今日过车", "布控命中", "轨迹回放", "异常告警"
    ]),
    ("视频|监控|图像|点位", [
        "在线点位", "录像完好率", "今日告警", "图像调取", "故障在线"
    ]),
    ("审批|流程|流转|审核", [
        "待审批", "今日办结", "审批耗时", "退回件数", "审批通过率"
    ]),
    ("统计|研判|分析|指标|驾驶舱", [
        "数据更新", "环比变化", "风险等级", "重点对象", "指标告警"
    ]),
    ("预警|告警|风险|事件", [
        "今日告警", "已处置", "待研判", "升级事件", "高风险数"
    ]),
    ("用户|账号|权限|登录", [
        "在线用户", "今日登录", "异常登录", "权限变更", "账号启用"
    ]),
]


def _kpi_indicators_for_planning(planning: Dict[str, Any]) -> List[Dict[str, Any]]:
    """根据模块名称与软件类型生成 4 个业务化 KPI。

    优先匹配模块名中的关键词；若都未匹配，使用 planning["software_type"] 兜底。
    """
    modules = planning.get("modules", [])
    blob = " ".join(
        [planning.get("software_name", ""), planning.get("software_type", "")]
        + [m.get("name", "") for m in modules[:3]]
    )
    chosen: List[str] = []
    for pattern, indicators in _BUSINESS_KEYWORDS:
        if re.search(pattern, blob):
            chosen = indicators[:4]
            break
    if not chosen:
        chosen = [
            "业务总数", "今日新增", "待处理", "本月完成"
        ]
    # 用模块数量与软件名长度做稳定 hash，保证每次生成同款数字
    seed = _stable_seed(planning.get("software_name", ""))
    offsets = [
        1000 + (seed * (i + 1) * 37) % 9000 for i in range(4)
    ]
    return [
        {"label": label, "value": offsets[i], "unit": "项", "trend": "+12%" if i % 2 == 0 else "-3%",
         "trend_dir": "up" if i % 2 == 0 else "down"}
        for i, label in enumerate(chosen)
    ]


def _status_distribution_for_planning(planning: Dict[str, Any]) -> List[Dict[str, Any]]:
    """按 planning 行业生成状态分布（用于环形占比图）。"""
    industry = (planning.get("industry_name") or "") + (planning.get("software_name") or "")
    if any(k in industry for k in ["监所", "在押", "勤务"]):
        labels = ["正常", "关注", "预警", "高危"]
        weights = [58, 22, 14, 6]
    elif any(k in industry for k in ["案件", "执法"]):
        labels = ["受理", "在办", "结案", "归档"]
        weights = [12, 35, 38, 15]
    elif any(k in industry for k in ["车辆", "视频"]):
        labels = ["在线", "正常", "异常", "离线"]
        weights = [78, 14, 6, 2]
    else:
        labels = ["待办", "处理中", "已完成", "已归档"]
        weights = [22, 35, 33, 10]
    return [{"label": l, "weight": w} for l, w in zip(labels, weights)]


def _trend_series_for_planning(planning: Dict[str, Any], days: int = 7) -> List[int]:
    """生成稳定但有起伏的 7 日趋势序列。"""
    seed = _stable_seed(planning.get("software_name", "trend"), 1000)
    return [40 + ((seed * (i + 1) * 13) % 60) for i in range(days)]


def _recent_activities_for_planning(planning: Dict[str, Any]) -> List[Dict[str, Any]]:
    """首页"最近动态"列表，文本来自模块名 + 关键词。"""
    modules = planning.get("modules", [])
    seed = _stable_seed(planning.get("software_name", ""))
    types = ["办理", "新增", "审核", "归档", "告警", "导出"]
    out: List[Dict[str, Any]] = []
    for i, m in enumerate(modules[:4]):
        out.append({
            "module": m.get("name", f"业务模块{i+1}"),
            "action": types[(seed + i) % len(types)],
            "minutes_ago": 6 + i * 9 + (seed % 11),
            "level": ["info", "info", "warn", "danger"][(seed + i) % 4],
        })
    return out


def _module_business_comment(
    module: Dict[str, Any], kind: str
) -> str:
    """返回纯文本业务化中文注释（不含 // 或 -- 或 ** 前缀）。

    kind ∈ {entity, repository, service, controller, vue_page, sql_table}
    """
    name = module.get("name", "业务对象")
    desc = module.get("description") or f"{name}业务管理"
    verb_map = {
        "entity": "实体类，映射数据库表结构并维护字段属性",
        "repository": "数据访问层，提供按主键与业务条件查询的能力",
        "service": "业务层，承载业务规则、跨模块关联与状态流转",
        "controller": "接口层，对外暴露 RESTful API 并完成参数校验",
        "vue_page": "前端页面，承载列表筛选、详情查看和业务表单交互",
        "sql_table": "数据库表结构，存储业务核心字段与索引",
    }
    verb = verb_map.get(kind, "业务模块")
    return f"{name}：{verb}。业务说明：{desc}。"


def _controller_method_comment(module: Dict[str, Any], method: str) -> str:
    """Controller 每个方法一条业务化中文注释。"""
    name = module.get("name", "业务对象")
    desc_map = {
        "list": f"分页查询{name}列表，支持按关键字和业务状态筛选",
        "detail": f"按主键获取{name}完整业务字段和关联数据",
        "create": f"新增{name}，按业务规则校验字段后落库",
        "update": f"按主键更新{name}，对状态变更做业务校验",
        "delete": f"按主键删除{name}，对有业务关联的记录拒绝并提示",
    }
    return desc_map.get(method, f"{name}{method} 操作")


def _field_business_comment(
    module_name: str, field: str, kind: str
) -> str:
    """返回纯文本业务化注释（不含 // 或 -- 或 ** 前缀），由调用方按语言加前缀。

    role_map 列出"业务角色关键词 → 业务角色描述"，关键词同时支持中英文，
    以便 Planner 生成的业务字段名（通常是中文）能命中合适的角色。
    """
    role_map = [
        (["name", "名", "姓名", "标题", "name"], "业务主名称"),
        (["code", "编号", "code", "no", "no."], "业务编号或识别码"),
        (["type", "类别", "分类", "类型", "type"], "业务分类"),
        (["status", "状态", "state", "stage"], "当前业务状态"),
        (["remark", "备注", "说明", "描述", "desc"], "业务补充说明"),
        (["amount", "金额", "数量", "总数", "qty", "amount", "count"], "数量或金额数值"),
        (["time", "时间", "日期", "time", "date", "at"], "业务发生时间"),
    ]
    for keywords, role in role_map:
        for kw in keywords:
            if kw and kw in field:
                return f"{field}：{module_name}的{role}字段"
    return f"{field}：{module_name}的业务属性"


def _project_fingerprint(
    planning: Dict[str, Any],
    job_dir: Path,
    style_version: str = "v1",
) -> Dict[str, Any]:
    """生成 project_fingerprint.json：记录模块命名、字段组合、页面模式、注释风格与差异化参数。"""
    modules = planning.get("modules", [])
    pages: List[Dict[str, Any]] = []
    fields_by_module: Dict[str, List[str]] = {}
    page_patterns: List[str] = []
    tables = planning.get("database_tables") or []
    for index, m in enumerate(modules):
        key = m.get("key", "")
        fields_by_module[key] = list(m.get("fields", []))
        pp = m.get("page_pattern", "table_crud")
        page_patterns.append(pp)
        pages.append({
            "key": key,
            "name": m.get("name", ""),
            "table": tables[index] if index < len(tables) and tables[index] else f"ed_{key}",
            "page_pattern": pp,
            "detail_pattern": m.get("detail_pattern", "master_detail"),
            "edit_pattern": m.get("edit_pattern", "dialog"),
            "field_count": len(m.get("fields", [])),
        })
    return {
        "schema_version": "1.0",
        "style_version": style_version,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "software": {
            "name": planning.get("software_name", ""),
            "type": planning.get("software_type", ""),
            "industry_type": planning.get("industry_type", ""),
            "industry_name": planning.get("industry_name", ""),
        },
        "ui_plan": planning.get("ui_plan", {}),
        "modules": pages,
        "fields_by_module": fields_by_module,
        "page_patterns_used": sorted(set(page_patterns)),
        "comment_style": {
            "language": "zh-CN",
            "target": "业务化中文注释",
            "levels": ["class", "method", "field"],
            "sources": ["module.name", "module.description", "field 名"],
        },
        "differentiation": {
            "seed": _stable_seed(planning.get("software_name", "")),
            "kpi_indicator_strategy": "business-keyword-matching",
            "trend_series_strategy": "deterministic-hash",
        },
    }


def _originality_report(
    planning: Dict[str, Any],
    job_dir: Path,
) -> Dict[str, Any]:
    """生成 originality_report.json：说明原创性来源、模板复用范围、第三方依赖与本项目生成代码边界。"""
    modules = planning.get("modules", [])
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "software_name": planning.get("software_name", ""),
        "originality_sources": {
            "business_kpi_indicators": "根据软件名称、类型和模块名匹配行业关键词生成（见 _BUSINESS_KEYWORDS）",
            "field_business_comments": "根据字段名角色（名称/编号/状态/数量/时间）生成业务化中文注释",
            "module_business_comments": "根据模块名与 description 生成 entity/repository/service/controller/vue_page/sql_table 六类业务化注释",
            "dashboard_visual_components": "KPI 卡 / SVG 环形占比 / SVG 折线趋势 / SVG 分组柱状 / 状态标签 / 最近动态 — 6 类业务化图形组件（ISSUE-010）",
            "ui_shell_variants": "3 种应用壳层 × 3 种首页模式 × 6 种模块页面模式（ISSUE-003）",
        },
        "template_reuse_scope": {
            "deterministic_generator": [
                "Java Controller/Service/Repository/Entity 模板",
                "Vue 页面 + 路由 + 样式模板",
                "SQL DDL 模板",
                "应用壳层与导航结构",
                "Dashboard 业务化组件（KPI / 环形 / 折线 / 柱状 / 标签 / 动态）",
            ],
            "business_personalized": [
                "KPI 指标文案（按行业关键词匹配）",
                "业务化中文注释（按模块与字段名生成）",
                "趋势与状态分布数据（确定性 hash）",
            ],
        },
        "third_party_dependencies": {
            "backend": [
                "Spring Boot 3 / MyBatis Plus / MySQL Connector",
                "Lombok / Validation / JUnit（测试）",
            ],
            "frontend": [
                "Vue 3 / Vue Router / Element Plus / Vite",
            ],
            "build_tool": ["Maven 3.9+", "JDK 17", "Node 18+"],
            "license_summary_path": "generated_project/THIRD_PARTY_NOTICES.md",
        },
        "boundaries": {
            "deterministic_generated_code": "本项目生成器输出的全部源码与样式",
            "third_party_libraries": "上述第三方依赖，按 THIRD_PARTY_NOTICES.md 维护",
            "user_edited_code": "本项目生成后由用户在生成项目目录内修改的部分（不计入本项目原创性范围）",
        },
        "validation": {
            "backend_build": "JDK 17 + Maven 编译通过",
            "frontend_build": "Node 18 + npm run build 通过",
            "documentation_artifacts": [
                "copyright_package.zip",
                "generated_project.zip",
                "THIRD_PARTY_NOTICES.md",
                "project_fingerprint.json",
            ],
        },
    }


def _java_package(software_name: str) -> str:
    ascii_name = re.sub(r"[^a-z0-9]+", "", software_name.lower())
    suffix = ascii_name[:24] or "copyright"
    return f"com.aicopyright.{suffix}"


def _java_type(field: str) -> str:
    if any(token in field for token in ("数量", "时长", "次数", "分数", "率")):
        return "Integer"
    if any(token in field for token in ("金额", "费用", "能耗", "用电量", "用水量")):
        return "BigDecimal"
    if any(token in field for token in ("日期", "时间")):
        return "LocalDateTime"
    return "String"


def _field_name(index: int) -> str:
    return f"field{index + 1}"


def _pom(package_name: str) -> str:
    return f"""
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.3.5</version>
    <relativePath/>
  </parent>
  <groupId>{package_name}</groupId>
  <artifactId>backend</artifactId>
  <version>1.0.0</version>
  <properties>
    <java.version>17</java.version>
    <maven.compiler.release>17</maven.compiler.release>
    <mybatis-plus.version>3.5.7</mybatis-plus.version>
  </properties>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-validation</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springdoc</groupId>
      <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
      <version>2.6.0</version>
    </dependency>
    <dependency>
      <groupId>com.baomidou</groupId>
      <artifactId>mybatis-plus-spring-boot3-starter</artifactId>
      <version>${{mybatis-plus.version}}</version>
    </dependency>
    <dependency>
      <groupId>com.mysql</groupId>
      <artifactId>mysql-connector-j</artifactId>
      <scope>runtime</scope>
    </dependency>
    <dependency>
      <groupId>com.h2database</groupId>
      <artifactId>h2</artifactId>
      <scope>runtime</scope>
    </dependency>
    <dependency>
      <groupId>org.projectlombok</groupId>
      <artifactId>lombok</artifactId>
      <optional>true</optional>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-test</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>
  <build>
    <plugins>
      <plugin>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-maven-plugin</artifactId>
      </plugin>
    </plugins>
  </build>
</project>
"""


def _application(package_name: str) -> str:
    return f"""
package {package_name};

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@MapperScan("{package_name}.module.*.mapper")
@SpringBootApplication
public class CopyrightApplication {{
    public static void main(String[] args) {{
        SpringApplication.run(CopyrightApplication.class, args);
    }}
}}
"""


def _common_files(package_name: str, source_root: Path) -> None:
    _write(
        source_root / "common/ApiResponse.java",
        f"""
package {package_name}.common;

public final class ApiResponse<T> {{
    private final int code;
    private final String message;
    private final T data;

    public ApiResponse(int code, String message, T data) {{
        this.code = code;
        this.message = message;
        this.data = data;
    }}

    public int getCode() {{
        return code;
    }}

    public String getMessage() {{
        return message;
    }}

    public T getData() {{
        return data;
    }}

    public static <T> ApiResponse<T> success(T data) {{
        return new ApiResponse<>(0, "success", data);
    }}
}}
""",
    )
    _write(
        source_root / "common/PageQuery.java",
        f"""
package {package_name}.common;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

public final class PageQuery {{
    @Min(1)
    private final long page;
    @Min(1)
    @Max(100)
    private final long size;
    private final String keyword;

    public PageQuery(long page, long size, String keyword) {{
        this.page = page < 1 ? 1 : page;
        this.size = size < 1 ? 10 : size;
        this.keyword = keyword == null ? "" : keyword.trim();
    }}

    public long page() {{
        return page;
    }}

    public long size() {{
        return size;
    }}

    public String keyword() {{
        return keyword;
    }}
}}
""",
    )
    _write(
        source_root / "common/GlobalExceptionHandler.java",
        f"""
package {package_name}.common;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.stream.Collectors;

@RestControllerAdvice
public class GlobalExceptionHandler {{
    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiResponse<Void> validation(MethodArgumentNotValidException exception) {{
        String message = exception.getBindingResult().getFieldErrors().stream()
            .map(error -> error.getField() + error.getDefaultMessage())
            .collect(Collectors.joining("；"));
        return new ApiResponse<>(400, message, null);
    }}

    @ExceptionHandler(IllegalArgumentException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiResponse<Void> badRequest(IllegalArgumentException exception) {{
        return new ApiResponse<>(400, exception.getMessage(), null);
    }}
}}
""",
    )
    _write(
        source_root / "config/MybatisPlusConfig.java",
        f"""
package {package_name}.config;

import com.baomidou.mybatisplus.annotation.DbType;
import com.baomidou.mybatisplus.extension.plugins.MybatisPlusInterceptor;
import com.baomidou.mybatisplus.extension.plugins.inner.PaginationInnerInterceptor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class MybatisPlusConfig {{
    @Bean
    public MybatisPlusInterceptor mybatisPlusInterceptor() {{
        MybatisPlusInterceptor interceptor = new MybatisPlusInterceptor();
        interceptor.addInnerInterceptor(new PaginationInnerInterceptor(DbType.MYSQL));
        return interceptor;
    }}
}}
""",
    )
    _write(
        source_root / "config/WebConfig.java",
        f"""
package {package_name}.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class WebConfig implements WebMvcConfigurer {{
    @Override
    public void addCorsMappings(CorsRegistry registry) {{
        registry.addMapping("/api/**")
            .allowedOrigins("http://localhost:5173", "http://127.0.0.1:5173")
            .allowedMethods("GET", "POST", "PUT", "DELETE");
    }}
}}
""",
    )
    _write(
        source_root / "common/HealthController.java",
        f"""
package {package_name}.common;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class HealthController {{
    @GetMapping("/health")
    public ApiResponse<Map<String, Object>> health() {{
        Map<String, Object> status = new LinkedHashMap<>();
        status.put("status", "ok");
        status.put("application", "copyright-demo");
        status.put("timestamp", LocalDateTime.now());
        return ApiResponse.success(status);
    }}
}}
""",
    )


def _entity(package_name: str, module: Dict[str, Any], table: str) -> str:
    class_name = _pascal(module["key"])
    imports = {
        "BigDecimal": "java.math.BigDecimal",
        "LocalDateTime": "java.time.LocalDateTime",
    }
    field_types = [_java_type(field) for field in module["fields"]]
    required_imports = sorted({imports[item] for item in field_types if item in imports})
    import_text = "\n".join(f"import {item};" for item in required_imports)
    fields = "\n".join(
        # 用 label 而非 field_name 做 role 匹配，让"档案编号"等真实业务词命中
        f'    /** {_field_business_comment(module.get("name", "业务对象"), label, "field")} */\n'
        f'    @TableField("{_field_name(index)}")\n'
        f"    private {field_types[index]} {_field_name(index)};"
        for index, label in enumerate(module["fields"])
    )
    return f"""
package {package_name}.module.{module["key"]}.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
{import_text}
import java.time.LocalDateTime;

/**
 * {_module_business_comment(module, "entity")}
 */
@Data
@TableName("{table}")
public class {class_name}Entity {{
    /** 主键ID，MyBatis Plus 自增主键 */
    @TableId(type = IdType.AUTO)
    private Long id;
{fields}
    /** 数据创建时间，由数据层自动维护 */
    private LocalDateTime createdAt;
    /** 数据更新时间，由数据层自动维护 */
    private LocalDateTime updatedAt;
}}
"""


def _dto(package_name: str, module: Dict[str, Any]) -> str:
    class_name = _pascal(module["key"])
    imports = {
        "BigDecimal": "java.math.BigDecimal",
        "LocalDateTime": "java.time.LocalDateTime",
    }
    field_types = [_java_type(field) for field in module["fields"]]
    required_imports = sorted({imports[item] for item in field_types if item in imports})
    import_text = "\n".join(f"import {item};" for item in required_imports)
    fields = "\n".join(
        f'    /** {_field_business_comment(module.get("name", "业务对象"), label, "field")} */\n'
        f'    @Schema(description = "{label}")\n'
        + (
            f'    @NotBlank(message = "{label}不能为空")\n'
            if field_types[index] == "String"
            else f'    @NotNull(message = "{label}不能为空")\n'
        )
        + f"    private {field_types[index]} {_field_name(index)};"
        for index, label in enumerate(module["fields"])
    )
    return f"""
package {package_name}.module.{module["key"]}.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;
{import_text}

/**
 * {_module_business_comment(module, "controller")}
 * 用于 Controller 接收并校验前端表单参数，校验失败由 GlobalExceptionHandler 统一处理。
 */
@Data
@Schema(description = "{module["name"]}保存参数")
public class {class_name}DTO {{
{fields}
}}
"""


def _vo(package_name: str, module: Dict[str, Any]) -> str:
    class_name = _pascal(module["key"])
    field_types = [_java_type(field) for field in module["fields"]]
    imports = {
        "BigDecimal": "java.math.BigDecimal",
        "LocalDateTime": "java.time.LocalDateTime",
    }
    required_imports = sorted(
        {imports[item] for item in field_types if item in imports}
        | {"java.time.LocalDateTime"}
    )
    import_text = "\n".join(f"import {item};" for item in required_imports)
    fields = "\n".join(
        f'    @Schema(description = "{label}")\n'
        f"    private {field_types[index]} {_field_name(index)};"
        for index, label in enumerate(module["fields"])
    )
    return f"""
package {package_name}.module.{module["key"]}.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;
{import_text}

@Data
@Schema(description = "{module["name"]}返回数据")
public class {class_name}VO {{
    private Long id;
{fields}
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}}
"""


def _mapper(package_name: str, module: Dict[str, Any]) -> str:
    class_name = _pascal(module["key"])
    return f"""
package {package_name}.module.{module["key"]}.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import {package_name}.module.{module["key"]}.entity.{class_name}Entity;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface {class_name}Mapper extends BaseMapper<{class_name}Entity> {{
}}
"""


def _service(package_name: str, module: Dict[str, Any]) -> str:
    class_name = _pascal(module["key"])
    action_methods = "\n".join(
        f"    void {action['java_method']}(Long id);"
        for action in module.get("business_actions", [])
    )
    if action_methods:
        action_methods = "\n" + action_methods
    return f"""
package {package_name}.module.{module["key"]}.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import {package_name}.common.PageQuery;
import {package_name}.module.{module["key"]}.dto.{class_name}DTO;
import {package_name}.module.{module["key"]}.vo.{class_name}VO;

/**
 * {_module_business_comment(module, "service")}
 */
public interface {class_name}Service {{
    IPage<{class_name}VO> page(PageQuery query);
    {class_name}VO detail(Long id);
    Long create({class_name}DTO dto);
    void update(Long id, {class_name}DTO dto);
    void delete(Long id);
{action_methods}
}}
"""


def _service_impl(package_name: str, module: Dict[str, Any]) -> str:
    class_name = _pascal(module["key"])
    first_field = _field_name(0)
    action_methods = "\n".join(
        f"""
    @Override
    @Transactional
    public void {action['java_method']}(Long id) {{
        // 业务动作：{action['label']}，由规划 api_list 生成并记录到业务字段
        applyBusinessAction(id, "{action['label']}");
    }}
"""
        for action in module.get("business_actions", [])
    )
    action_setters = []
    for index, label in enumerate(module.get("fields", [])):
        if _java_type(label) != "String":
            continue
        if any(keyword in label for keyword in ["状态", "结果", "操作", "意见", "节点"]):
            action_setters.append(f"        entity.set{_pascal(_field_name(index))}(actionLabel);")
    if not action_setters:
        action_setters.append("        // 当前模块未识别到可写状态字段，仅更新时间用于留痕。")
    action_setter_text = "\n".join(action_setters)
    return f"""
package {package_name}.module.{module["key"]}.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import {package_name}.common.PageQuery;
import {package_name}.module.{module["key"]}.dto.{class_name}DTO;
import {package_name}.module.{module["key"]}.entity.{class_name}Entity;
import {package_name}.module.{module["key"]}.mapper.{class_name}Mapper;
import {package_name}.module.{module["key"]}.service.{class_name}Service;
import {package_name}.module.{module["key"]}.vo.{class_name}VO;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

/**
 * {_module_business_comment(module, "service")}
 */
@Service
public class {class_name}ServiceImpl implements {class_name}Service {{
    private final {class_name}Mapper mapper;

    public {class_name}ServiceImpl({class_name}Mapper mapper) {{
        this.mapper = mapper;
    }}

    @Override
    public IPage<{class_name}VO> page(PageQuery query) {{
        // 分页查询：先按关键字模糊匹配核心字段，再按主键倒序
        LambdaQueryWrapper<{class_name}Entity> wrapper = new LambdaQueryWrapper<>();
        if (!query.keyword().isBlank()) {{
            wrapper.like({class_name}Entity::get{_pascal(first_field)}, query.keyword());
        }}
        wrapper.orderByDesc({class_name}Entity::getId);
        return mapper.selectPage(new Page<>(query.page(), query.size()), wrapper)
            .convert(this::toVO);
    }}

    @Override
    public {class_name}VO detail(Long id) {{
        // 详情：按主键查询，记录不存在时抛业务异常
        {class_name}Entity entity = mapper.selectById(id);
        if (entity == null) {{
            throw new IllegalArgumentException("{module["name"]}记录不存在");
        }}
        return toVO(entity);
    }}

    @Override
    @Transactional
    public Long create({class_name}DTO dto) {{
        // 新增：DTO 拷贝到 Entity，事务内写入数据库并回填时间戳
        {class_name}Entity entity = new {class_name}Entity();
        BeanUtils.copyProperties(dto, entity);
        LocalDateTime now = LocalDateTime.now();
        entity.setCreatedAt(now);
        entity.setUpdatedAt(now);
        mapper.insert(entity);
        return entity.getId();
    }}

    @Override
    @Transactional
    public void update(Long id, {class_name}DTO dto) {{
        // 更新：先校验存在性，再按主键更新，事务保证原子性
        detail(id);
        {class_name}Entity entity = new {class_name}Entity();
        BeanUtils.copyProperties(dto, entity);
        entity.setId(id);
        entity.setUpdatedAt(LocalDateTime.now());
        mapper.updateById(entity);
    }}

    @Override
    @Transactional
    public void delete(Long id) {{
        // 删除：未命中则视为业务异常
        if (mapper.deleteById(id) == 0) {{
            throw new IllegalArgumentException("{module["name"]}记录不存在");
        }}
    }}
{action_methods}

    private void applyBusinessAction(Long id, String actionLabel) {{
        {class_name}Entity entity = mapper.selectById(id);
        if (entity == null) {{
            throw new IllegalArgumentException("{module["name"]}记录不存在");
        }}
{action_setter_text}
        entity.setUpdatedAt(LocalDateTime.now());
        mapper.updateById(entity);
    }}

    private {class_name}VO toVO({class_name}Entity entity) {{
        {class_name}VO vo = new {class_name}VO();
        BeanUtils.copyProperties(entity, vo);
        return vo;
    }}
}}
"""


def _controller(package_name: str, module: Dict[str, Any]) -> str:
    class_name = _pascal(module["key"])
    extra_imports = ""
    if any(action["annotation"] == "PatchMapping" for action in module.get("business_actions", [])):
        extra_imports = "import org.springframework.web.bind.annotation.PatchMapping;\n"
    action_endpoints = "\n".join(
        f"""
    /** 执行{module["name"]}业务动作：{action['label']} */
    @{action['annotation']}("/{{id}}/{action['code']}")
    public ApiResponse<Void> {action['java_method']}(@PathVariable Long id) {{
        service.{action['java_method']}(id);
        return ApiResponse.success(null);
    }}
"""
        for action in module.get("business_actions", [])
    )
    return f"""
package {package_name}.module.{module["key"]}.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import {package_name}.common.ApiResponse;
import {package_name}.common.PageQuery;
import {package_name}.module.{module["key"]}.dto.{class_name}DTO;
import {package_name}.module.{module["key"]}.service.{class_name}Service;
import {package_name}.module.{module["key"]}.vo.{class_name}VO;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
{extra_imports}import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * {_module_business_comment(module, "controller")}
 */
@RestController
@RequestMapping("/api/{module["key"]}")
public class {class_name}Controller {{
    private final {class_name}Service service;

    public {class_name}Controller({class_name}Service service) {{
        this.service = service;
    }}

    /** {_controller_method_comment(module, "list")} */
    @GetMapping
    public ApiResponse<IPage<{class_name}VO>> page(
        @RequestParam(defaultValue = "1") long page,
        @RequestParam(defaultValue = "10") long size,
        @RequestParam(defaultValue = "") String keyword
    ) {{
        return ApiResponse.success(service.page(new PageQuery(page, size, keyword)));
    }}

    /** {_controller_method_comment(module, "detail")} */
    @GetMapping("/{{id}}")
    public ApiResponse<{class_name}VO> detail(@PathVariable Long id) {{
        return ApiResponse.success(service.detail(id));
    }}

    /** {_controller_method_comment(module, "create")} */
    @PostMapping
    public ApiResponse<Long> create(@Valid @RequestBody {class_name}DTO dto) {{
        return ApiResponse.success(service.create(dto));
    }}

    /** {_controller_method_comment(module, "update")} */
    @PutMapping("/{{id}}")
    public ApiResponse<Void> update(
        @PathVariable Long id,
        @Valid @RequestBody {class_name}DTO dto
    ) {{
        service.update(id, dto);
        return ApiResponse.success(null);
    }}

    /** {_controller_method_comment(module, "delete")} */
    @DeleteMapping("/{{id}}")
    public ApiResponse<Void> delete(@PathVariable Long id) {{
        service.delete(id);
        return ApiResponse.success(null);
    }}
{action_endpoints}
}}
"""


def _metadata(package_name: str, module: Dict[str, Any]) -> str:
    class_name = _pascal(module["key"])
    entries = "\n".join(
        f"""        fields.add(new FieldMetadata(
            "{_field_name(index)}",
            "{label}",
            "{_java_type(label)}",
            true,
            {index}
        ));"""
        for index, label in enumerate(module["fields"])
    )
    pages = "\n".join(
        f'        pages.add("{page}");' for page in module["pages"]
    )
    return f"""
package {package_name}.module.{module["key"]}.metadata;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public final class {class_name}Metadata {{
    public static final String MODULE_KEY = "{module["key"]}";
    public static final String MODULE_NAME = "{module["name"]}";
    public static final String DESCRIPTION = "{module["description"]}";

    private {class_name}Metadata() {{
    }}

    public static List<FieldMetadata> fields() {{
        List<FieldMetadata> fields = new ArrayList<>();
{entries}
        return Collections.unmodifiableList(fields);
    }}

    public static List<String> pages() {{
        List<String> pages = new ArrayList<>();
{pages}
        return Collections.unmodifiableList(pages);
    }}

    public static final class FieldMetadata {{
        private final String key;
        private final String label;
        private final String javaType;
        private final boolean required;
        private final int order;

        public FieldMetadata(
            String key,
            String label,
            String javaType,
            boolean required,
            int order
        ) {{
            if (key == null || key.isBlank()) {{
                throw new IllegalArgumentException("字段 key 不能为空");
            }}
            if (label == null || label.isBlank()) {{
                throw new IllegalArgumentException("字段名称不能为空");
            }}
            if (javaType == null || javaType.isBlank()) {{
                throw new IllegalArgumentException("字段类型不能为空");
            }}
            if (order < 0) {{
                throw new IllegalArgumentException("字段顺序不能小于零");
            }}
            this.key = key;
            this.label = label;
            this.javaType = javaType;
            this.required = required;
            this.order = order;
        }}

        public String getKey() {{
            return key;
        }}

        public String getLabel() {{
            return label;
        }}

        public String getJavaType() {{
            return javaType;
        }}

        public boolean isRequired() {{
            return required;
        }}

        public int getOrder() {{
            return order;
        }}
    }}
}}
"""


def _operation_enum(package_name: str, module: Dict[str, Any]) -> str:
    class_name = _pascal(module["key"])
    business_entries = ""
    if module.get("business_actions"):
        business_entries = ",\n" + ",\n".join(
            f'    {action["code"].upper()}("{action["code"]}", "{action["label"]}", false)'
            for action in module.get("business_actions", [])
        )
    return f"""
package {package_name}.module.{module["key"]}.metadata;

import java.util.Arrays;
import java.util.Locale;
import java.util.Optional;

public enum {class_name}Operation {{
    QUERY("query", "查询", true),
    DETAIL("detail", "查看详情", true),
    CREATE("create", "新增", false),
    UPDATE("update", "编辑", false),
    DELETE("delete", "删除", false),
    EXPORT("export", "导出", false){business_entries};

    private final String code;
    private final String label;
    private final boolean readOnly;

    {class_name}Operation(String code, String label, boolean readOnly) {{
        this.code = code;
        this.label = label;
        this.readOnly = readOnly;
    }}

    public String getCode() {{
        return code;
    }}

    public String getLabel() {{
        return label;
    }}

    public boolean isReadOnly() {{
        return readOnly;
    }}

    public static Optional<{class_name}Operation> fromCode(String code) {{
        if (code == null || code.isBlank()) {{
            return Optional.empty();
        }}
        String normalized = code.trim().toLowerCase(Locale.ROOT);
        return Arrays.stream(values())
            .filter(item -> item.code.equals(normalized))
            .findFirst();
    }}

    public static boolean supports(String code) {{
        return fromCode(code).isPresent();
    }}
}}
"""


def _java_value(java_type: str, index: int) -> str:
    return {
        "String": f'"测试值{index + 1}"',
        "Integer": str(index + 1),
        "BigDecimal": f'new BigDecimal("{index + 1}.00")',
        "LocalDateTime": "LocalDateTime.of(2026, 1, 1, 10, 0)",
    }[java_type]


def _entity_test(package_name: str, module: Dict[str, Any]) -> str:
    class_name = _pascal(module["key"])
    types = [_java_type(field) for field in module["fields"]]
    imports = []
    if "BigDecimal" in types:
        imports.append("import java.math.BigDecimal;")
    if "LocalDateTime" in types:
        imports.append("import java.time.LocalDateTime;")
    assignments = "\n".join(
        f"""        entity.set{_pascal(_field_name(index))}({_java_value(types[index], index)});
        assertEquals({_java_value(types[index], index)}, entity.get{_pascal(_field_name(index))}());"""
        for index in range(len(module["fields"]))
    )
    return f"""
package {package_name}.module.{module["key"]}.entity;

import org.junit.jupiter.api.Test;
{chr(10).join(imports)}

import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class {class_name}EntityTest {{
    @Test
    void shouldStoreBusinessFieldsAndAuditFields() {{
        {class_name}Entity entity = new {class_name}Entity();
        entity.setId(100L);
{assignments}
        entity.setCreatedAt(LocalDateTime.of(2026, 1, 1, 10, 0));
        entity.setUpdatedAt(LocalDateTime.of(2026, 1, 2, 10, 0));

        assertEquals(100L, entity.getId());
        assertNotNull(entity.getCreatedAt());
        assertNotNull(entity.getUpdatedAt());
    }}

    @Test
    void shouldSupportLombokEqualityContract() {{
        {class_name}Entity first = new {class_name}Entity();
        {class_name}Entity second = new {class_name}Entity();
        first.setId(1L);
        second.setId(1L);
        assertEquals(first, second);
        assertEquals(first.hashCode(), second.hashCode());
    }}
}}
"""


def _dto_test(package_name: str, module: Dict[str, Any]) -> str:
    class_name = _pascal(module["key"])
    types = [_java_type(field) for field in module["fields"]]
    imports = []
    if "BigDecimal" in types:
        imports.append("import java.math.BigDecimal;")
    if "LocalDateTime" in types:
        imports.append("import java.time.LocalDateTime;")
    assignments = "\n".join(
        f"        dto.set{_pascal(_field_name(index))}({_java_value(types[index], index)});"
        for index in range(len(module["fields"]))
    )
    return f"""
package {package_name}.module.{module["key"]}.dto;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
{chr(10).join(imports)}

import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class {class_name}DTOTest {{
    private static Validator validator;

    @BeforeAll
    static void setUpValidator() {{
        validator = Validation.buildDefaultValidatorFactory().getValidator();
    }}

    @Test
    void emptyDtoShouldFailValidation() {{
        {class_name}DTO dto = new {class_name}DTO();
        Set<ConstraintViolation<{class_name}DTO>> violations = validator.validate(dto);
        assertFalse(violations.isEmpty());
        assertEquals({len(module["fields"])}, violations.size());
    }}

    @Test
    void completeDtoShouldPassValidation() {{
        {class_name}DTO dto = new {class_name}DTO();
{assignments}
        Set<ConstraintViolation<{class_name}DTO>> violations = validator.validate(dto);
        assertTrue(violations.isEmpty());
    }}
}}
"""


def _controller_test(package_name: str, module: Dict[str, Any]) -> str:
    class_name = _pascal(module["key"])
    expected_endpoint_count = 5 + len(module.get("business_actions", []))
    action_assertions = "\n".join(
        f"        assertTrue(hasAnnotation(methods, {action['annotation']}.class, \"{action['java_method']}\"));"
        for action in module.get("business_actions", [])
    )
    if action_assertions:
        action_assertions = "\n" + action_assertions
    extra_imports = ""
    if any(action["annotation"] == "PatchMapping" for action in module.get("business_actions", [])):
        extra_imports = "import org.springframework.web.bind.annotation.PatchMapping;\n"
    return f"""
package {package_name}.module.{module["key"]}.controller;

import org.junit.jupiter.api.Test;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
{extra_imports}import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestMapping;

import java.lang.reflect.Method;
import java.util.Arrays;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class {class_name}ControllerContractTest {{
    @Test
    void shouldExposeModuleBasePath() {{
        RequestMapping mapping = {class_name}Controller.class.getAnnotation(RequestMapping.class);
        assertNotNull(mapping);
        assertEquals("/api/{module["key"]}", mapping.value()[0]);
    }}

    @Test
    void shouldExposeCompleteCrudContract() {{
        Method[] methods = {class_name}Controller.class.getDeclaredMethods();
        assertTrue(hasAnnotation(methods, GetMapping.class, "page"));
        assertTrue(hasAnnotation(methods, GetMapping.class, "detail"));
        assertTrue(hasAnnotation(methods, PostMapping.class, "create"));
        assertTrue(hasAnnotation(methods, PutMapping.class, "update"));
        assertTrue(hasAnnotation(methods, DeleteMapping.class, "delete"));
{action_assertions}
    }}

    @Test
    void shouldKeepPlannedBusinessEndpoints() {{
        long endpointCount = Arrays.stream({class_name}Controller.class.getDeclaredMethods())
            .filter(method ->
                method.isAnnotationPresent(GetMapping.class)
                    || method.isAnnotationPresent(PostMapping.class)
                    || method.isAnnotationPresent(PutMapping.class)
                    || method.isAnnotationPresent(DeleteMapping.class)
                    || method.isAnnotationPresent(org.springframework.web.bind.annotation.PatchMapping.class)
            )
            .count();
        assertEquals({expected_endpoint_count}, endpointCount);
    }}

    private boolean hasAnnotation(
        Method[] methods,
        Class<? extends java.lang.annotation.Annotation> annotation,
        String methodName
    ) {{
        return Arrays.stream(methods)
            .filter(method -> method.getName().equals(methodName))
            .anyMatch(method -> method.isAnnotationPresent(annotation));
    }}
}}
"""


def _service_contract_test(package_name: str, module: Dict[str, Any]) -> str:
    class_name = _pascal(module["key"])
    expected_method_count = 5 + len(module.get("business_actions", []))
    action_assertions = "\n".join(
        f'        assertTrue(methods.containsKey("{action["java_method"]}"));'
        for action in module.get("business_actions", [])
    )
    if action_assertions:
        action_assertions = "\n" + action_assertions
    return f"""
package {package_name}.module.{module["key"]}.service;

import {package_name}.module.{module["key"]}.dto.{class_name}DTO;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class {class_name}ServiceContractTest {{
    @Test
    void shouldExposeCompleteCrudMethods() {{
        Map<String, Method> methods = Arrays.stream({class_name}Service.class.getDeclaredMethods())
            .collect(Collectors.toMap(Method::getName, Function.identity()));

        assertTrue(methods.containsKey("page"));
        assertTrue(methods.containsKey("detail"));
        assertTrue(methods.containsKey("create"));
        assertTrue(methods.containsKey("update"));
        assertTrue(methods.containsKey("delete"));
{action_assertions}
        assertEquals({expected_method_count}, methods.size());
    }}

    @Test
    void createShouldAcceptDtoAndReturnIdentifier() throws Exception {{
        Method method = {class_name}Service.class.getDeclaredMethod(
            "create",
            {class_name}DTO.class
        );
        assertEquals(Long.class, method.getReturnType());
        assertEquals(1, method.getParameterCount());
    }}

    @Test
    void updateShouldAcceptIdentifierAndDto() throws Exception {{
        Method method = {class_name}Service.class.getDeclaredMethod(
            "update",
            Long.class,
            {class_name}DTO.class
        );
        assertEquals(Void.TYPE, method.getReturnType());
        assertEquals(2, method.getParameterCount());
    }}

    @Test
    void detailAndDeleteShouldUseLongIdentifier() throws Exception {{
        Method detail = {class_name}Service.class.getDeclaredMethod("detail", Long.class);
        Method delete = {class_name}Service.class.getDeclaredMethod("delete", Long.class);
        assertNotNull(detail.getReturnType());
        assertEquals(Void.TYPE, delete.getReturnType());
    }}
}}
"""


def _mapper_contract_test(package_name: str, module: Dict[str, Any]) -> str:
    class_name = _pascal(module["key"])
    return f"""
package {package_name}.module.{module["key"]}.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import {package_name}.module.{module["key"]}.entity.{class_name}Entity;
import org.apache.ibatis.annotations.Mapper;
import org.junit.jupiter.api.Test;

import java.lang.reflect.ParameterizedType;
import java.lang.reflect.Type;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class {class_name}MapperContractTest {{
    @Test
    void shouldBeMybatisMapper() {{
        Mapper annotation = {class_name}Mapper.class.getAnnotation(Mapper.class);
        assertNotNull(annotation);
        assertTrue(BaseMapper.class.isAssignableFrom({class_name}Mapper.class));
    }}

    @Test
    void shouldBindCorrectEntityType() {{
        Type[] interfaces = {class_name}Mapper.class.getGenericInterfaces();
        assertEquals(1, interfaces.length);
        ParameterizedType baseMapper = (ParameterizedType) interfaces[0];
        assertEquals(BaseMapper.class, baseMapper.getRawType());
        assertEquals({class_name}Entity.class, baseMapper.getActualTypeArguments()[0]);
    }}
}}
"""


def _sql_type(java_type: str) -> str:
    return {
        "Integer": "INT",
        "BigDecimal": "DECIMAL(18,2)",
        "LocalDateTime": "DATETIME",
        "String": "VARCHAR(255)",
    }[java_type]


def _table_sql(module: Dict[str, Any], table: str) -> str:
    columns = ",\n".join(
        f"  -- {_field_business_comment(module.get('name', '业务对象'), label, 'field')}\n"
        f"  {_field_name(index)} {_sql_type(_java_type(label))} NOT NULL COMMENT '{label}'"
        for index, label in enumerate(module["fields"])
    )
    return f"""
-- {_module_business_comment(module, 'sql_table')}
DROP TABLE IF EXISTS {table};
CREATE TABLE {table} (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
{columns},
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='{module["name"]}';
"""


def _h2_table_sql(module: Dict[str, Any], table: str) -> str:
    columns = ",\n".join(
        f"  -- {_field_business_comment(module.get('name', '业务对象'), label, 'field')}\n"
        f"  {_field_name(index)} {_sql_type(_java_type(label))} NOT NULL"
        for index, label in enumerate(module["fields"])
    )
    return f"""
-- {_module_business_comment(module, 'sql_table')}
DROP TABLE IF EXISTS {table};
CREATE TABLE {table} (
  id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
{columns},
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


# ---------- 演示种子数据 ----------
# 固定参考日期，跨 H2/MySQL 一致；用 7 天循环 + 当日小时偏移，模拟最近一周业务
_SEED_BASE_DATE = datetime(2024, 6, 3, 8, 30, 0)
_SEED_NAMES = ["张三", "李四", "王五", "赵六", "钱七", "孙八", "周九", "吴十"]
_SEED_LICENSES = [
    "京A12345", "沪B88888", "粤C66666", "苏D55555", "浙E44444",
    "鲁F33333", "豫G22222", "川H11111",
]
_SEED_BRANDS = ["丰田", "本田", "大众", "日产", "奥迪", "宝马"]
_SEED_COLORS = ["白色", "黑色", "银色", "红色", "蓝色", "灰色"]
_SEED_LEVELS = ["一级", "二级", "三级"]
_SEED_STATUS = ["已处理", "处理中", "已立案", "已结案", "待审核"]
_SEED_TYPES = ["交通事故", "纠纷调解", "刑事案件", "治安案件", "行政案件"]
_SEED_DEPARTMENTS = ["朝阳分局", "海淀分局", "通州分局", "丰台分局", "西城分局", "东城分局"]
_SEED_ADDRESSES = [
    "北京市朝阳区建国路88号", "上海市浦东新区张江路1200号", "广州市天河区珠江新城A座",
    "深圳市福田区华强北路", "杭州市西湖区文三路", "成都市武侯区人民南路",
    "南京市鼓楼区中山路", "武汉市江汉区解放大道", "西安市雁塔区高新路",
    "重庆市渝中区解放碑", "沈阳市和平区南京北街", "青岛市市南区香港中路",
]
_SEED_CASENAMES = [
    "张某盗窃案", "李某诈骗案", "王某交通肇事案", "刘某寻衅滋事案",
    "陈某故意伤害案", "杨某职务侵占案", "黄某非法经营案", "周某合同诈骗案",
]


def _seed_datetime_for(index: int) -> str:
    """按记录序号生成一个 SQL 字面量日期时间字符串（带单引号）。"""
    dt = _SEED_BASE_DATE + timedelta(days=index % 7, hours=index, minutes=index * 7)
    return f"'{dt.strftime('%Y-%m-%d %H:%M:%S')}'"


def _seed_value(field_label: str, index: int, module_key: str) -> str:
    """根据字段中文名生成 SQL 字面量：字符串带单引号，数字裸值。"""
    label = field_label or ""

    # 时间 / 日期
    if any(kw in label for kw in ("时间", "日期")):
        return _seed_datetime_for(index)

    # 处置率 / 完成率 (整数 0-100)
    if "率" in label:
        value = 70 + (index * 3) % 28  # 70 ~ 97
        return str(value)

    # 数量
    if "数量" in label or "次数" in label or "时长" in label or "分数" in label:
        return str(8 + index * 2)

    # 金额 / 费用 / 能耗 (DECIMAL)
    if any(kw in label for kw in ("金额", "费用", "能耗", "用电量", "用水量", "价格")):
        return f"{(500.0 + index * 137.5):.2f}"

    # 车牌
    if "车牌" in label:
        return f"'{_SEED_LICENSES[index % len(_SEED_LICENSES)]}'"

    # 品牌
    if "品牌" in label:
        return f"'{_SEED_BRANDS[index % len(_SEED_BRANDS)]}'"

    # 颜色
    if "颜色" in label:
        return f"'{_SEED_COLORS[index % len(_SEED_COLORS)]}'"

    # 级别
    if "级别" in label:
        return f"'{_SEED_LEVELS[index % len(_SEED_LEVELS)]}'"

    # 状态
    if "状态" in label:
        return f"'{_SEED_STATUS[index % len(_SEED_STATUS)]}'"

    # 案件名称（独立类型，避免和"编号"冲突）
    if "案件名称" in label or "名称" in label:
        return f"'{_SEED_CASENAMES[index % len(_SEED_CASENAMES)]}'"

    # 关联案件
    if "关联案件" in label or "关联" in label:
        return f"'C{2024000 + (index % 8) + 1}'"

    # 主办单位 / 单位 / 部门
    if any(kw in label for kw in ("主办单位", "单位", "部门", "分局")):
        return f"'{_SEED_DEPARTMENTS[index % len(_SEED_DEPARTMENTS)]}'"

    # 类型 / 类别
    if "类型" in label or "类别" in label:
        return f"'{_SEED_TYPES[index % len(_SEED_TYPES)]}'"

    # 地址 / 地点 / 位置 / 现场
    if any(kw in label for kw in ("地址", "地点", "位置", "现场", "场所")):
        return f"'{_SEED_ADDRESSES[index % len(_SEED_ADDRESSES)]}'"

    # 姓名 / 当事人 / 老师 / 学生 / 司机 / 车主
    if any(kw in label for kw in ("姓名", "当事人", "老师", "学生", "司机", "车主", "操作人")):
        return f"'{_SEED_NAMES[index % len(_SEED_NAMES)]}'"

    # 编号 / 单号 / 任何含"号"的
    if any(kw in label for kw in ("编号", "单号")) or (
        "号" in label and "车牌" not in label and "编号" not in label
    ):
        return f"'{module_key.upper()}{index:04d}'"

    # 兜底
    return f"'{module_key}示例{index}'"


def _seed_sql(module: Dict[str, Any], table: str, count: int = 15) -> str:
    """为单个表生成 INSERT 种子语句。H2 与 MySQL 通用（同 DATETIME/TIMESTAMP 字面量）。"""
    fields = module.get("fields") or []
    if not fields:
        return ""
    columns = ", ".join(_field_name(idx) for idx in range(len(fields)))
    statements: List[str] = []
    for i in range(1, count + 1):
        values = ", ".join(
            _seed_value(label, i, module["key"]) for label in fields
        )
        statements.append(f"INSERT INTO {table} ({columns}) VALUES ({values});")
    return "\n".join(statements) + "\n"


def _api_file(module: Dict[str, Any]) -> str:
    key = module["key"]
    action_exports = "\n".join(
        f"export const {action['js_function']} = id => request.{action['js_http_method']}(`/{key}/${{id}}/{action['code']}`)"
        for action in module.get("business_actions", [])
    )
    if action_exports:
        action_exports = "\n" + action_exports
    return f"""
import request from './request'

export const page{_pascal(key)} = params => request.get('/{key}', {{ params }})
export const get{_pascal(key)} = id => request.get(`/{key}/${{id}}`)
export const create{_pascal(key)} = data => request.post('/{key}', data)
export const update{_pascal(key)} = (id, data) => request.put(`/{key}/${{id}}`, data)
export const delete{_pascal(key)} = id => request.delete(`/{key}/${{id}}`)
{action_exports}
"""


def _vue_page(module: Dict[str, Any]) -> str:
    key = module["key"]
    pascal = _pascal(key)
    actions = module.get("business_actions", [])
    action_imports = "".join(f", {action['js_function']}" for action in actions)
    action_map = ", ".join(
        f"{json.dumps(action['code'], ensure_ascii=False)}: {action['js_function']}"
        for action in actions
    )
    action_buttons = "\n".join(
        f'            <el-button link type="success" :data-action="\'{action["code"]}\'" @click="runBusinessAction(row, \'{action["code"]}\', \'{action["label"]}\')">{action["label"]}</el-button>'
        for action in actions
    )
    if action_buttons:
        action_buttons = "\n" + action_buttons
    action_column_width = 160 + len(actions) * 72
    field_defs = json.dumps(
        [
            {"key": _field_name(index), "label": label}
            for index, label in enumerate(module["fields"])
        ],
        ensure_ascii=False,
    )
    pattern = module.get("page_pattern", "table_crud")
    pattern_content = {
        "master_detail": """
      <div class="master-detail-preview"><div><b>业务对象</b><p v-for="row in rows.slice(0,4)" :key="row.id">#{{row.id}} · {{row[fields[0]?.key]}}</p></div><aside><b>详情摘要</b><p>选择左侧记录查看完整业务信息和办理状态。</p></aside></div>
""",
        "tree_detail": """
      <div class="tree-detail-preview"><nav><b>分类目录</b><p>全部数据</p><p>待处理</p><p>已完成</p></nav><div><b>目录内容</b><p>按业务目录组织数据，并在右侧维护详细信息。</p></div></div>
""",
        "workflow_timeline": """
      <div class="workflow-preview"><b>业务办理流程</b><div><span>1</span>登记受理<i></i><span>2</span>审核办理<i></i><span>3</span>办结归档</div></div>
""",
        "kanban": """
      <div class="kanban-preview"><article v-for="status in ['待处理','处理中','已完成']" :key="status"><b>{{status}}</b><p v-for="index in 2" :key="index">{{status}}任务 {{index}}</p></article></div>
""",
        "dashboard": """
      <div class="module-dashboard"><article v-for="(field,index) in fields.slice(0,4)" :key="field.key"><header><i class="m-icon"></i><b>{{field.label}}</b></header><strong>{{128 + index * 36}}</strong><footer><span class="m-trend-up">+{{4 + index}}%</span></footer></article><div class="mini-trend"><svg viewBox="0 0 200 80" class="mini-trend-svg"><polyline points="0,52 30,40 60,46 90,28 120,34 150,18 180,24" fill="none" stroke="#2678c9" stroke-width="2"/><polyline points="0,62 30,56 60,60 90,42 120,50 150,38 180,42" fill="none" stroke="#39b275" stroke-width="2" stroke-dasharray="4 3"/></svg></div><div class="mini-status"><span class="tag tag-warn">预警</span><span class="tag tag-info">在办</span><span class="tag tag-success">完成</span></div></div>
""",
    }.get(pattern, "")
    return f"""
<!-- {_module_business_comment(module, 'vue_page')} -->
<script setup>
// {_module_business_comment(module, 'vue_page')}
import {{ onMounted, reactive, ref }} from 'vue'
import {{ ElMessage, ElMessageBox }} from 'element-plus'
import {{ fields }} from '../config/{key}'
import {{
  page{pascal}, create{pascal}, update{pascal}, delete{pascal}{action_imports}
}} from '../api/{key}'

const loading = ref(false)
const dialogVisible = ref(false)
const editingId = ref(null)
const rows = ref([])
const total = ref(0)
const query = reactive({{ page: 1, size: 10, keyword: '' }})
const form = reactive(Object.fromEntries(fields.map(item => [item.key, ''])))
const businessActionHandlers = {{{action_map}}}
const rules = Object.fromEntries(fields.map(item => [
  item.key,
  [{{ required: true, message: `请输入${{item.label}}`, trigger: 'blur' }}]
]))
const formRef = ref()

async function load() {{
  loading.value = true
  try {{
    const response = await page{pascal}(query)
    rows.value = response.data.records
    total.value = response.data.total
  }} finally {{
    loading.value = false
  }}
}}

function openCreate() {{
  editingId.value = null
  fields.forEach(item => form[item.key] = '')
  dialogVisible.value = true
}}

function openEdit(row) {{
  editingId.value = row.id
  fields.forEach(item => form[item.key] = row[item.key] ?? '')
  dialogVisible.value = true
}}

async function submit() {{
  await formRef.value.validate()
  if (editingId.value) await update{pascal}(editingId.value, form)
  else await create{pascal}(form)
  ElMessage.success('保存成功')
  dialogVisible.value = false
  load()
}}

async function remove(row) {{
  await ElMessageBox.confirm('确认删除该记录吗？', '删除确认', {{ type: 'warning' }})
  await delete{pascal}(row.id)
  ElMessage.success('删除成功')
  load()
}}

async function runBusinessAction(row, actionCode, actionLabel) {{
  const handler = businessActionHandlers[actionCode]
  if (!handler) {{
    ElMessage.warning('当前操作暂未配置')
    return
  }}
  await ElMessageBox.confirm(`确认对该记录执行「${{actionLabel}}」操作吗？`, '业务操作确认', {{ type: 'warning' }})
  await handler(row.id)
  ElMessage.success(`${{actionLabel}}成功`)
  load()
}}

onMounted(load)
</script>

<template>
  <section class="module-page pattern-{pattern}" data-module-key="{key}">
    <div class="page-heading">
      <div><h2>{module["name"]}</h2><p>{module["description"]}</p></div>
      <el-button type="primary" data-action="create" @click="openCreate">新增记录</el-button>
    </div>
    <el-card shadow="never">
{pattern_content}
      <div class="filters">
        <el-input v-model="query.keyword" placeholder="输入关键词查询" clearable @keyup.enter="load" />
        <el-button type="primary" @click="load">查询</el-button>
        <el-button @click="query.keyword='';load()">重置</el-button>
      </div>
      <el-table v-loading="loading" :data="rows" stripe>
        <el-table-column type="index" label="序号" width="70" />
        <el-table-column v-for="field in fields" :key="field.key" :prop="field.key" :label="field.label" min-width="140" />
        <el-table-column label="操作" width="{action_column_width}" fixed="right">
          <template #default="{{ row }}">
            <el-button link type="primary" data-action="edit" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" data-action="delete" @click="remove(row)">删除</el-button>
{action_buttons}
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="query.page"
        v-model:page-size="query.size"
        layout="total, prev, pager, next"
        :total="total"
        @current-change="load"
      />
    </el-card>
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑{module["name"]}' : '新增{module["name"]}'" width="560px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item v-for="field in fields" :key="field.key" :label="field.label" :prop="field.key">
          <el-input v-model="form[field.key]" :placeholder="`请输入${{field.label}}`" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible=false">取消</el-button>
        <el-button type="primary" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>
"""


def _frontend_config(module: Dict[str, Any]) -> str:
    definitions = [
        {
            "key": _field_name(index),
            "label": label,
            "required": True,
            "type": _java_type(label),
            "searchable": index == 0,
            "width": 140,
        }
        for index, label in enumerate(module["fields"])
    ]
    business_operations = "".join(
        f",\n  {{code: {json.dumps(action['code'], ensure_ascii=False)}, label: {json.dumps(action['label'], ensure_ascii=False)}, readOnly: false}}"
        for action in module.get("business_actions", [])
    )
    return f"""
export const moduleKey = '{module["key"]}'
export const moduleName = '{module["name"]}'
export const moduleDescription = '{module["description"]}'
export const fields = {json.dumps(definitions, ensure_ascii=False, indent=2)}
export const operations = [
  {{code: 'query', label: '查询', readOnly: true}},
  {{code: 'detail', label: '查看详情', readOnly: true}},
  {{code: 'create', label: '新增', readOnly: false}},
  {{code: 'update', label: '编辑', readOnly: false}},
  {{code: 'delete', label: '删除', readOnly: false}},
  {{code: 'export', label: '导出', readOnly: false}}
{business_operations}
]

export function emptyForm() {{
  return Object.fromEntries(fields.map(field => [field.key, '']))
}}

export function validationRules() {{
  return Object.fromEntries(fields.map(field => [
    field.key,
    field.required
      ? [{{required: true, message: `请输入${{field.label}}`, trigger: 'blur'}}]
      : []
  ]))
}}
"""


def _frontend_files(root: Path, planning: Dict[str, Any]) -> None:
    frontend = root / "frontend"
    modules = planning["modules"]
    _write(
        frontend / "package.json",
        """
{
  "name": "copyright-demo-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {"dev": "vite --host 127.0.0.1", "build": "vite build"},
  "dependencies": {
    "@element-plus/icons-vue": "^2.3.1",
    "@vitejs/plugin-vue": "^5.2.1",
    "axios": "^1.7.9",
    "element-plus": "^2.8.8",
    "vite": "^6.0.5",
    "vue": "^3.5.13",
    "vue-router": "^4.5.0"
  },
  "devDependencies": {}
}
""",
    )
    _write(
        frontend / "vite.config.js",
        """
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  root: dirname(fileURLToPath(import.meta.url)),
  plugins: [vue()],
  server: {
    proxy: {'/api': {target: process.env.VITE_BACKEND_TARGET || 'http://127.0.0.1:9001', changeOrigin: true}}
  }
})
""",
    )
    _write(
        frontend / "index.html",
        f"""<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>{planning["software_name"]}</title></head><body><div id="app"></div><script type="module" src="/src/main.js"></script></body></html>""",
    )
    _write(
        frontend / "src/main.js",
        """
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './style.css'
import App from './App.vue'
import router from './router'

createApp(App).use(ElementPlus).use(router).mount('#app')
""",
    )
    _write(
        frontend / "src/api/request.js",
        """
import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({baseURL: '/api', timeout: 10000})
request.interceptors.response.use(
  response => response.data,
  error => {
    ElMessage.error(error.response?.data?.message || '请求失败')
    return Promise.reject(error)
  }
)
export default request
""",
    )
    imports = []
    routes = []
    menu = []
    for module in modules:
        pascal = _pascal(module["key"])
        imports.append(f"import {pascal}Page from './views/{pascal}Page.vue'")
        routes.append(
            f"{{path: '/{module['key']}', name: '{module['key']}', component: {pascal}Page}}"
        )
        menu.append({"key": module["key"], "name": module["name"]})
        _write(frontend / f"src/api/{module['key']}.js", _api_file(module))
        _write(frontend / f"src/config/{module['key']}.js", _frontend_config(module))
        _write(frontend / f"src/views/{pascal}Page.vue", _vue_page(module))
    _write(
        frontend / "src/views/HomeDashboardPage.vue",
        _dashboard_vue(planning, menu),
    )
    _write(
        frontend / "src/router.js",
        "\n".join(imports)
        + "\nimport HomeDashboardPage from './views/HomeDashboardPage.vue'\n"
        + f"""
import {{ createRouter, createWebHistory }} from 'vue-router'
const routes = [
  {{path: '/', name: 'home', component: HomeDashboardPage}},
  {",".join(routes)}
]
export default createRouter({{history: createWebHistory(), routes}})
""",
    )
    _write(
        frontend / "src/App.vue",
        _app_vue(planning, menu),
    )
    _write(
        frontend / "src/style.css",
        _frontend_style(planning),
    )
    _write(
        root / "THIRD_PARTY_NOTICES.md",
        """# Third-Party Notices

Generated projects use the following runtime dependencies:

- Vue.js (MIT License)
- Vue Router (MIT License)
- Element Plus (MIT License)
- Axios (MIT License)
- Vite (MIT License)

The generated application templates, business structure, sample data and styling are
produced by AI Copyright Factory and do not copy third-party demo branding or pages.
""",
    )
    # ISSUE-011：生成项目指纹和原创性报告
    _write(
        root / "project_fingerprint.json",
        json.dumps(
            _project_fingerprint(planning, root), ensure_ascii=False, indent=2
        ),
    )
    _write(
        root / "originality_report.json",
        json.dumps(
            _originality_report(planning, root), ensure_ascii=False, indent=2
        ),
    )


def _svg_donut(distribution: List[Dict[str, Any]]) -> str:
    """生成 SVG 环形占比图。"""
    total = sum(item["weight"] for item in distribution) or 1
    radius = 50
    circumference = 2 * 3.14159 * radius
    segments: List[str] = []
    cumulative = 0.0
    palette = ["#2678c9", "#39b275", "#e8a13a", "#d65a5a", "#7b6cd9"]
    for index, item in enumerate(distribution):
        fraction = item["weight"] / total
        dash = fraction * circumference
        gap = circumference - dash
        offset = -cumulative
        cumulative += dash
        color = palette[index % len(palette)]
        segments.append(
            f'<circle r="{radius}" cx="70" cy="70" fill="transparent" '
            f'stroke="{color}" stroke-width="18" '
            f'stroke-dasharray="{dash:.2f} {gap:.2f}" '
            f'stroke-dashoffset="{offset:.2f}" />'
        )
    legend = "".join(
        f'<li><i style="background:{palette[index % len(palette)]}"></i>'
        f'<span>{item["label"]}</span><b>{item["weight"]}%</b></li>'
        for index, item in enumerate(distribution)
    )
    return (
        f'<svg viewBox="0 0 140 140" class="donut-svg">'
        f'<circle r="{radius}" cx="70" cy="70" fill="transparent" stroke="#eef3f8" stroke-width="18"/>'
        f'{"".join(segments)}'
        f'<text x="70" y="68" text-anchor="middle" class="donut-center">{total}</text>'
        f'<text x="70" y="86" text-anchor="middle" class="donut-sub">总占比</text>'
        f'</svg><ul class="donut-legend">{legend}</ul>'
    )


def _svg_line_trend(series: List[int], labels: List[str]) -> str:
    """生成 SVG 折线趋势图（最近 N 天）。"""
    if not series:
        return '<div class="trend-empty">暂无趋势数据</div>'
    width = 360
    height = 140
    max_v = max(series) or 1
    min_v = min(series)
    span = max(max_v - min_v, 1)
    points: List[str] = []
    fill_points: List[str] = []
    step = width / max(len(series) - 1, 1)
    for i, value in enumerate(series):
        x = i * step
        y = height - ((value - min_v) / span) * (height - 20) - 10
        points.append(f"{x:.1f},{y:.1f}")
        fill_points.append(f"{x:.1f},{height}")
    fill_points.append(f"{width},{height}")
    last_value = series[-1]
    return (
        f'<svg viewBox="0 0 {width} {height}" class="trend-svg">'
        f'<polygon points="{" ".join(points + fill_points)}" class="trend-area"/>'
        f'<polyline points="{" ".join(points)}" class="trend-line"/>'
        f'<circle cx="{(len(series)-1)*step:.1f}" cy="{height - ((last_value-min_v)/span)*(height-20) - 10:.1f}" r="4" class="trend-dot"/>'
        + "".join(
            f'<text x="{i*step:.1f}" y="{height+18}" class="trend-label">{labels[i]}</text>'
            for i in range(len(series))
        )
        + "</svg>"
    )


def _svg_bar_groups(
    distribution: List[Dict[str, Any]], series: List[int]
) -> str:
    """生成 SVG 分组柱状图（按状态对比）。"""
    width = 360
    height = 140
    bars: List[str] = []
    palette = ["#2678c9", "#39b275", "#e8a13a", "#d65a5a"]
    bar_w = width / (len(distribution) * 2 + 2)
    for i, item in enumerate(distribution):
        x = (i * 2 + 1) * bar_w
        h = (item["weight"] / 100) * (height - 30)
        y = height - h - 20
        color = palette[i % len(palette)]
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
            f'fill="url(#barGrad{i})" class="bar-rect" />'
            f'<text x="{x + bar_w/2:.1f}" y="{y-4:.1f}" text-anchor="middle" class="bar-value">{item["weight"]}%</text>'
            f'<text x="{x + bar_w/2:.1f}" y="{height-2:.1f}" text-anchor="middle" class="bar-label">{item["label"]}</text>'
            f'<defs><linearGradient id="barGrad{i}" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="{color}" stop-opacity="0.95"/><stop offset="100%" stop-color="{color}" stop-opacity="0.55"/></linearGradient></defs>'
        )
    return f'<svg viewBox="0 0 {width} {height}" class="bar-svg">{"".join(bars)}</svg>'


def _dashboard_vue(planning: Dict[str, Any], menu: List[Dict[str, str]]) -> str:
    pattern = planning.get("ui_plan", {}).get("home_pattern", "metric_dashboard")
    kpis = _kpi_indicators_for_planning(planning)
    distribution = _status_distribution_for_planning(planning)
    trend_series = _trend_series_for_planning(planning, days=7)
    trend_labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    activities = _recent_activities_for_planning(planning)
    kpi_cards = "".join(
        f'<article class="kpi-card kpi-trend-{k["trend_dir"]}">'
        f'<header><i class="kpi-icon">{_kpi_icon_svg(i)}</i><b>{k["label"]}</b></header>'
        f'<div class="kpi-value">{k["value"]:,}<small>{k["unit"]}</small></div>'
        f'<footer><span class="kpi-trend">{k["trend"]} 较上期</span></footer>'
        f"</article>"
        for i, k in enumerate(kpis)
    )
    if pattern == "task_dashboard":
        body = f"""
    <div class="task-workbench">
      <el-card class="kpi-row"><h3>核心业务指标</h3><div class="kpi-grid">{kpi_cards}</div></el-card>
      <el-card><h3>我的待办</h3><p v-for="(item,index) in modules.slice(0,4)" :key="item.key"><b>{{{{index + 1}}}}</b>{{{{item.name}}}}待处理事项 <span>{{{{8 + index * 3}}}}</span></p></el-card>
      <el-card><h3>业务流程</h3><div class="flow-line"><i>受理</i><em></em><i>办理</i><em></em><i>审核</i><em></em><i>归档</i></div></el-card>
      <el-card class="dashboard-trend-card"><h3>近 7 日业务办理趋势</h3>{_svg_line_trend(trend_series, trend_labels)}</el-card>
      <el-card class="dashboard-activities"><h3>最近动态</h3><ul>{"".join(f'<li class="activity-{a["level"]}"><span class="dot"></span><b>{a["action"]}</b><em>{a["module"]}</em><small>{a["minutes_ago"]} 分钟前</small></li>' for a in activities)}</ul></el-card>
    </div>
"""
    elif pattern == "analysis_dashboard":
        body = f"""
    <div class="analysis-workbench">
      <div class="kpi-row"><h3>核心业务指标</h3><div class="kpi-grid">{kpi_cards}</div></div>
      <el-card class="trend-panel"><h3>近 7 日业务指标趋势</h3>{_svg_line_trend(trend_series, trend_labels)}</el-card>
      <el-card class="status-panel"><h3>业务状态分布</h3><div class="status-row">{_svg_donut(distribution)}</div></el-card>
      <el-card class="bar-panel"><h3>业务状态分布柱状对比</h3>{_svg_bar_groups(distribution, trend_series)}</el-card>
      <el-card class="ranking-panel"><h3>业务模块排名</h3><p v-for="(item,index) in modules" :key="item.key"><span>{{{{index + 1}}}}. {{{{item.name}}}}</span><b>{{{{98 - index * 7}}}}%</b></p></el-card>
    </div>
"""
    else:
        body = f"""
    <div class="kpi-row"><h3>核心业务指标</h3><div class="kpi-grid">{kpi_cards}</div></div>
    <div class="dashboard-row">
      <el-card class="trend-panel"><h3>近 7 日业务趋势</h3>{_svg_line_trend(trend_series, trend_labels)}</el-card>
      <el-card class="status-panel"><h3>业务状态分布</h3><div class="status-row">{_svg_donut(distribution)}</div></el-card>
    </div>
    <div class="dashboard-row">
      <el-card class="bar-panel"><h3>业务模块数量对比</h3>{_svg_bar_groups(distribution, trend_series)}</el-card>
      <el-card class="activity-panel"><h3>最近业务动态</h3><ul>{"".join(f'<li class="activity-{a["level"]}"><span class="dot"></span><b>{a["action"]}</b><em>{a["module"]}</em><small>{a["minutes_ago"]} 分钟前</small></li>' for a in activities)}</ul></el-card>
    </div>
"""
    return f"""
<script setup>
const modules = {json.dumps(menu, ensure_ascii=False)}
</script>
<template>
  <section class="dashboard dashboard-{pattern}">
    <div class="hero"><div><p>系统运行概览</p><h1>{planning["software_name"]}</h1><span>Spring Boot 3 + Vue 3 业务管理平台</span></div><b>{{{{modules.length}}}}<small>业务模块</small></b></div>
{body}
  </section>
</template>
"""


def _kpi_icon_svg(index: int) -> str:
    """返回 4 个内联 KPI 图标 SVG。"""
    icons = [
        '<svg viewBox="0 0 24 24"><path d="M3 13h4v8H3zM10 3h4v18h-4zM17 9h4v12h-4z"/></svg>',
        '<svg viewBox="0 0 24 24"><path d="M4 18l8-8 4 4 4-4v6H4z" fill="none" stroke-width="2" stroke="currentColor"/></svg>',
        '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 7v5l3 2" stroke="currentColor" stroke-width="2" fill="none"/></svg>',
        '<svg viewBox="0 0 24 24"><path d="M12 2l9 4-9 4-9-4 9-4zM3 11l9 4 9-4M3 15l9 4 9-4" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
    ]
    return icons[index % len(icons)]


def _app_vue(planning: Dict[str, Any], menu: List[Dict[str, str]]) -> str:
    shell = planning.get("ui_plan", {}).get("shell", "sidebar_admin")
    common = f"""
<script setup>
import {{ ref }} from 'vue'
const loggedIn = ref(false)
const modules = {json.dumps(menu, ensure_ascii=False)}
</script>
<template>
  <div v-if="!loggedIn" class="login-page">
    <div class="login-brand"><h1>{planning["software_name"]}</h1><p>{planning["industry_name"]}行业数字化管理平台</p></div>
    <el-card class="login-card" shadow="always"><h2>欢迎登录</h2><p>请输入管理员账号进入系统</p><el-input model-value="admin" /><el-input type="password" model-value="123456" show-password /><el-button type="primary" @click="loggedIn=true">登录系统</el-button><small>演示账号：admin / 123456</small></el-card>
  </div>
"""
    if shell == "top_workspace":
        layout = f"""
  <div v-else class="shell shell-top">
    <header><div><b>{planning["software_name"]}</b><small>业务协同工作台</small></div><nav><router-link to="/">工作台</router-link><router-link v-for="item in modules" :key="item.key" :to="'/'+item.key" :data-module-key="item.key">{{{{item.name}}}}</router-link></nav><span>管理员</span></header>
    <main><router-view /></main>
  </div>
"""
    elif shell == "split_console":
        layout = f"""
  <div v-else class="shell shell-split">
    <aside><h2>{planning["software_name"]}</h2><p>业务对象</p><router-link to="/">综合态势</router-link><router-link v-for="item in modules" :key="item.key" :to="'/'+item.key" :data-module-key="item.key">{{{{item.name}}}}</router-link></aside>
    <main><header><b>业务控制台</b><span>实时运行中</span></header><router-view /></main>
    <section class="context-panel"><b>快捷信息</b><p>待处理事项 12</p><p>今日新增 28</p><p>运行告警 3</p></section>
  </div>
"""
    else:
        layout = f"""
  <el-container v-else class="shell shell-side">
    <el-aside width="240px"><h2>{planning["software_name"]}</h2><p>智慧业务管理中心</p><el-menu router default-active="/"><el-menu-item index="/">运营首页</el-menu-item><el-menu-item v-for="item in modules" :key="item.key" :index="'/'+item.key" :data-module-key="item.key">{{{{item.name}}}}</el-menu-item></el-menu></el-aside>
    <el-container><el-header><b>{planning["software_name"]}</b><span>管理员</span></el-header><el-main><router-view /></el-main></el-container>
  </el-container>
"""
    return common + layout + """
</template>
"""


def _frontend_style(planning: Dict[str, Any]) -> str:
    density = planning.get("ui_plan", {}).get("density", "standard")
    padding = {"compact": "16px", "comfortable": "32px"}.get(density, "24px")
    base = """
*{box-sizing:border-box}body{margin:0;font-family:"Microsoft YaHei",Arial;color:#203044;background:#f4f7fb}.login-page{min-height:100vh;display:flex;align-items:center;justify-content:center;gap:120px;background:linear-gradient(125deg,#0c356d,#1689c8);color:#fff}.login-brand h1{font-size:38px;margin:0 0 12px}.login-brand p{opacity:.75;letter-spacing:3px}.login-card{width:390px;padding:22px;color:#26384d}.login-card .el-input{margin:10px 0}.login-card .el-button{width:100%;margin:16px 0}.login-card small{color:#8391a3}.shell{min-height:100vh}.el-aside{background:linear-gradient(180deg,#123d76,#09264d);color:#fff;padding:24px 14px}.el-aside h2{font-size:20px;margin:0 8px 4px}.el-aside>p{font-size:12px;opacity:.6;margin:0 8px 22px}.el-aside .el-menu{border:0;background:transparent}.el-aside .el-menu-item{color:#cbd8e8;border-radius:7px;margin:4px 0}.el-aside .el-menu-item:hover,.el-aside .el-menu-item.is-active{color:#fff;background:#1d5b9f}.el-header{display:flex;align-items:center;justify-content:space-between;background:#fff;border-bottom:1px solid #e5ebf2}.el-header span{background:#edf5ff;color:#2466ad;padding:8px 14px;border-radius:18px}.el-main{padding:24px 28px}.page-heading{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-heading h2{margin:0}.page-heading p{margin:8px 0 0;color:#7c8a9c}.filters{display:flex;gap:10px;margin-bottom:18px}.filters .el-input{width:300px}.el-pagination{justify-content:flex-end;margin-top:18px}.hero{display:flex;justify-content:space-between;align-items:center;padding:28px 34px;border-radius:12px;background:linear-gradient(120deg,#176bc4,#28a2d8);color:#fff}.hero h1{margin:8px 0}.hero b{font-size:38px;text-align:center}.hero small{display:block;font-size:13px}.metric-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:18px 0}.metric-grid span,.metric-grid small{display:block;color:#7c8a9c}.metric-grid strong{display:block;font-size:28px;margin:12px 0}.bars{height:220px;display:flex;align-items:flex-end;gap:32px;padding:28px 45px 0;border-bottom:1px solid #dfe6ef}.bars i{flex:1;background:linear-gradient(#55adeb,#1970c4);border-radius:6px 6px 0 0}
.shell-top>header{height:76px;padding:0 30px;background:#fff;display:grid;grid-template-columns:260px 1fr 100px;align-items:center;border-bottom:1px solid #e2e8f0}.shell-top>header div{display:grid}.shell-top>header small{color:#8795a7}.shell-top nav{display:flex;gap:8px;overflow:auto}.shell-top nav a,.shell-split a{color:#40546b;text-decoration:none;padding:10px 13px;border-radius:7px}.shell-top nav a.router-link-active{background:#e8f2ff;color:#1769bd}
"""
    variants = f"""
.shell-top>main{{padding:{padding}}}.shell-split{{display:grid;grid-template-columns:220px 1fr 220px;background:#eef3f8}}.shell-split>aside{{background:#132f50;color:#fff;padding:{padding};display:flex;flex-direction:column;gap:7px}}.shell-split>aside a{{color:#cbd8e7}}.shell-split>aside a.router-link-active{{background:#245b8f;color:#fff}}.shell-split>main>header{{height:64px;background:#fff;display:flex;justify-content:space-between;align-items:center;padding:0 {padding}}}.shell-split>main>.module-page,.shell-split>main>.dashboard{{padding:{padding}}}.context-panel{{background:#fff;padding:{padding};border-left:1px solid #dde5ee}}.context-panel p{{padding:12px;background:#f3f7fb;border-radius:7px}}
.master-detail-preview,.tree-detail-preview{{display:grid;grid-template-columns:1fr 1.6fr;gap:12px;margin-bottom:18px}}.master-detail-preview>div,.master-detail-preview aside,.tree-detail-preview>*{{padding:16px;background:#f5f8fc;border:1px solid #e0e7ef;border-radius:8px}}.workflow-preview{{padding:18px;background:#f7f9fc;border-radius:8px;margin-bottom:18px}}.workflow-preview>div{{display:flex;align-items:center;margin-top:14px}}.workflow-preview span{{width:30px;height:30px;border-radius:50%;background:#2678c9;color:#fff;display:grid;place-items:center}}.workflow-preview i{{height:2px;background:#9fc5e8;flex:1}}.kanban-preview{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:18px}}.kanban-preview article{{background:#eef3f8;padding:14px;border-radius:8px}}.kanban-preview p{{background:#fff;padding:10px;border-radius:6px}}.module-dashboard{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}}.module-dashboard article{{padding:16px;background:#f3f8fe;border-radius:8px;border:1px solid #e0e7ef;position:relative}}.module-dashboard article header{{display:flex;align-items:center;gap:8px;margin-bottom:6px}}.module-dashboard article b{{font-size:13px;color:#52627a;font-weight:500}}.module-dashboard article strong{{font-size:24px;color:#1d5b9f;display:block;margin:6px 0}}.module-dashboard article .m-trend-up{{color:#39b275;font-size:12px}}.m-icon{{display:inline-block;width:8px;height:24px;border-radius:2px;background:linear-gradient(#2678c9,#39b275)}}.mini-trend{{grid-column:1/-1;background:#f8fafc;padding:14px;border-radius:6px}}.mini-trend-svg{{width:100%;height:70px}}.mini-status{{grid-column:1/-1;display:flex;gap:8px;padding:8px 0 0}}.mini-status .tag{{padding:3px 10px;border-radius:14px;font-size:12px}}.tag-warn{{background:#fff4d9;color:#a06b00}}.tag-info{{background:#e8f2ff;color:#2466ad}}.tag-success{{background:#e1f4e7;color:#1d7a3a}}.tag-danger{{background:#fde2e2;color:#a32424}}
.task-workbench{{display:grid;grid-template-columns:1fr 1.4fr;gap:16px;margin-top:18px}}.task-workbench>.el-card:last-child{{grid-column:1/-1}}.task-workbench p{{display:grid;grid-template-columns:30px 1fr auto;align-items:center;padding:10px;border-bottom:1px solid #edf1f5}}.task-workbench p b{{width:24px;height:24px;display:grid;place-items:center;background:#e8f2ff;color:#2872b8;border-radius:50%}}.flow-line{{display:flex;align-items:center;padding:40px 20px}}.flow-line i{{font-style:normal;background:#2678c9;color:#fff;padding:12px;border-radius:50%}}.flow-line em{{height:2px;background:#9fc5e8;flex:1}}.quick-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.quick-grid a{{padding:16px;background:#f0f6fc;color:#2469aa;text-decoration:none;border-radius:8px}}.analysis-workbench{{display:grid;grid-template-columns:2fr 1fr;gap:16px;margin-top:18px}}.analysis-metrics{{grid-column:1/-1;display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.analysis-metrics article{{padding:18px;background:#152f52;color:#fff;border-radius:9px}}.analysis-metrics span,.analysis-metrics small,.analysis-metrics b{{display:block}}.analysis-metrics b{{font-size:28px;margin:10px 0}}.ranking-panel p{{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #edf1f5}}
.dashboard{{padding:24px 28px 32px}}.kpi-row{{margin:18px 0 22px}}.kpi-row h3{{margin:0 0 12px;font-size:16px}}.kpi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}}.kpi-card{{padding:18px 18px 16px;background:linear-gradient(135deg,#fff,#f0f6fc);border-radius:10px;border:1px solid #e0e7ef;box-shadow:0 1px 0 rgba(20,60,120,.04)}}.kpi-card header{{display:flex;align-items:center;gap:8px;color:#52627a;font-size:13px;margin-bottom:8px}}.kpi-card header b{{font-weight:500}}.kpi-icon{{width:24px;height:24px;display:inline-grid;place-items:center;color:#2678c9;background:#e8f2ff;border-radius:6px}}.kpi-icon svg{{width:14px;height:14px;fill:currentColor;stroke:currentColor}}.kpi-value{{font-size:28px;font-weight:600;color:#1d2c44}}.kpi-value small{{font-size:12px;color:#7c8a9c;margin-left:6px;font-weight:400}}.kpi-trend{{font-size:12px;color:#7c8a9c}}.kpi-trend-up .kpi-trend{{color:#39b275}}.kpi-trend-down .kpi-trend{{color:#d65a5a}}.dashboard-row{{display:grid;grid-template-columns:1.4fr 1fr;gap:16px;margin-bottom:18px}}.trend-panel,.status-panel,.bar-panel,.activity-panel{{padding:18px}}.trend-panel h3,.status-panel h3,.bar-panel h3,.activity-panel h3{{margin:0 0 12px;font-size:15px}}.trend-svg{{width:100%;height:140px}}.trend-area{{fill:rgba(38,120,201,.12)}}.trend-line{{fill:none;stroke:#2678c9;stroke-width:2}}.trend-dot{{fill:#fff;stroke:#2678c9;stroke-width:2}}.trend-label{{font-size:11px;fill:#7c8a9c}}.donut-svg{{width:200px;height:200px;display:block;margin:0 auto}}.donut-center{{font-size:22px;fill:#1d2c44;font-weight:600}}.donut-sub{{font-size:11px;fill:#7c8a9c}}.status-row{{display:grid;grid-template-columns:200px 1fr;gap:18px;align-items:center}}.donut-legend{{list-style:none;padding:0;margin:0}}.donut-legend li{{display:grid;grid-template-columns:14px 1fr auto;align-items:center;gap:8px;padding:6px 0;border-bottom:1px dashed #e0e7ef}}.donut-legend i{{width:10px;height:10px;border-radius:2px;display:inline-block}}.donut-legend b{{color:#1d2c44}}.bar-svg{{width:100%;height:140px}}.bar-rect{{filter:drop-shadow(0 1px 2px rgba(20,60,120,.1))}}.bar-value{{font-size:11px;fill:#1d2c44;font-weight:600}}.bar-label{{font-size:11px;fill:#7c8a9c}}.activity-panel ul{{list-style:none;padding:0;margin:0}}.activity-panel li{{display:grid;grid-template-columns:8px 60px 1fr auto;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid #edf1f5}}.activity-panel li .dot{{width:8px;height:8px;border-radius:50%;background:#2678c9}}.activity-info .dot{{background:#2678c9}}.activity-warn .dot{{background:#e8a13a}}.activity-danger .dot{{background:#d65a5a}}.activity-panel li b{{color:#1d2c44;font-weight:600}}.activity-panel li em{{color:#52627a;font-style:normal}}.activity-panel li small{{color:#94a3b8;font-size:12px}}.dashboard-activities ul{{list-style:none;padding:0;margin:0}}.dashboard-activities li{{display:grid;grid-template-columns:8px 60px 1fr auto;gap:10px;padding:8px 0}}
@media(max-width:1000px){{.shell-split{{grid-template-columns:190px 1fr}}.context-panel{{display:none}}.shell-top>header{{grid-template-columns:1fr auto}}.shell-top nav{{grid-row:2;grid-column:1/-1}}.module-dashboard{{grid-template-columns:1fr 1fr}}.kpi-grid{{grid-template-columns:repeat(2,1fr)}}.dashboard-row{{grid-template-columns:1fr}}.status-row{{grid-template-columns:1fr}}.analysis-workbench{{grid-template-columns:1fr}}}}
"""
    return base + variants


def generate_java_project(job_dir: Path) -> None:
    planning = _planning_with_actions(json.loads((job_dir / "planning.json").read_text(encoding="utf-8")))
    root = job_dir / "generated_project"
    backend = root / "backend"
    source_root = backend / "src/main/java"
    package_name = _java_package(planning["software_name"])
    package_root = source_root / Path(package_name.replace(".", "/"))

    _write(backend / "pom.xml", _pom(package_name))
    _write(package_root / "CopyrightApplication.java", _application(package_name))
    _common_files(package_name, package_root)
    sql_parts: List[str] = [
        "CREATE DATABASE IF NOT EXISTS copyright_demo DEFAULT CHARACTER SET utf8mb4;",
        "USE copyright_demo;",
    ]
    h2_sql_parts: List[str] = []
    for index, module in enumerate(planning["modules"]):
        table = planning["database_tables"][index]
        module_root = package_root / "module" / module["key"]
        class_name = _pascal(module["key"])
        _write(module_root / f"entity/{class_name}Entity.java", _entity(package_name, module, table))
        _write(module_root / f"dto/{class_name}DTO.java", _dto(package_name, module))
        _write(module_root / f"vo/{class_name}VO.java", _vo(package_name, module))
        _write(module_root / f"mapper/{class_name}Mapper.java", _mapper(package_name, module))
        _write(module_root / f"service/{class_name}Service.java", _service(package_name, module))
        _write(module_root / f"service/impl/{class_name}ServiceImpl.java", _service_impl(package_name, module))
        _write(module_root / f"controller/{class_name}Controller.java", _controller(package_name, module))
        _write(module_root / f"metadata/{class_name}Metadata.java", _metadata(package_name, module))
        _write(module_root / f"metadata/{class_name}Operation.java", _operation_enum(package_name, module))
        test_module_root = backend / "src/test/java" / Path(package_name.replace(".", "/")) / "module" / module["key"]
        _write(test_module_root / f"entity/{class_name}EntityTest.java", _entity_test(package_name, module))
        _write(test_module_root / f"dto/{class_name}DTOTest.java", _dto_test(package_name, module))
        _write(test_module_root / f"controller/{class_name}ControllerContractTest.java", _controller_test(package_name, module))
        _write(test_module_root / f"service/{class_name}ServiceContractTest.java", _service_contract_test(package_name, module))
        _write(test_module_root / f"mapper/{class_name}MapperContractTest.java", _mapper_contract_test(package_name, module))
        sql_parts.append(_table_sql(module, table))
        sql_parts.append(_seed_sql(module, table))
        h2_sql_parts.append(_h2_table_sql(module, table))
    _write(root / "sql/init.sql", "\n".join(sql_parts))
    _write(backend / "src/main/resources/schema-demo.sql", "\n".join(h2_sql_parts))
    # data-demo.sql 仅含 INSERT（H2 库由 schema-demo.sql 先建好，data-locations 后跑直接写数据）。
    _seed_only_parts = [
        _seed_sql(module, planning["database_tables"][idx])
        for idx, module in enumerate(planning["modules"])
    ]
    _write(backend / "src/main/resources/data-demo.sql", "\n".join(_seed_only_parts))
    _write(
        backend / "src/main/resources/application.yml",
        """
server:
  port: 9001
spring:
  application:
    name: copyright-demo
  datasource:
    driver-class-name: com.mysql.cj.jdbc.Driver
    url: ${MYSQL_URL:jdbc:mysql://127.0.0.1:3306/copyright_demo?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai}
    username: ${MYSQL_USERNAME:root}
    password: ${MYSQL_PASSWORD:root}
mybatis-plus:
  configuration:
    map-underscore-to-camel-case: true
  global-config:
    banner: false
""",
    )
    _write(
        backend / "src/test/resources/application.yml",
        """
spring:
  datasource:
    driver-class-name: org.h2.Driver
    url: jdbc:h2:mem:copyright;MODE=MySQL;DB_CLOSE_DELAY=-1
    username: sa
    password:
  sql:
    init:
      mode: never
""",
    )
    _write(
        backend / "src/main/resources/application-demo.yml",
        """
spring:
  datasource:
    driver-class-name: org.h2.Driver
    url: jdbc:h2:mem:copyright_demo;MODE=MySQL;DB_CLOSE_DELAY=-1;DATABASE_TO_LOWER=TRUE
    username: sa
    password:
  sql:
    init:
      mode: always
      encoding: utf-8
      schema-locations: classpath:schema-demo.sql
      data-locations: classpath:data-demo.sql
""",
    )
    _write(
        backend / "src/test/java" / Path(package_name.replace(".", "/")) / "CopyrightApplicationTests.java",
        f"""
package {package_name};

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest
class CopyrightApplicationTests {{
    @Test
    void contextLoads() {{
    }}
}}
""",
    )
    _frontend_files(root, planning)
    _write(
        root / "README.md",
        f"""
# {planning["software_name"]}

技术栈：Java 17、Spring Boot 3、MyBatis Plus、MySQL、Vue 3、Element Plus。

## 数据库

- **生产 / MySQL**：执行 `sql/init.sql`（含 15 条/表的演示数据），或设置 `MYSQL_URL`、`MYSQL_USERNAME`、`MYSQL_PASSWORD`。
- **演示 / H2**：启动时使用 `demo` profile，自动加载 `schema-demo.sql` 建表 + `data-demo.sql` 灌入 15 条/表的演示数据，无需手动初始化。

## 后端

```powershell
cd backend
mvn test
mvn spring-boot:run
# 演示模式（自带 15 条/表数据，H2 内存库）
mvn spring-boot:run -Dspring-boot.run.profiles=demo
```

## 前端

```powershell
cd frontend
npm.cmd install
npm.cmd run dev -- --port 9002
```
""",
    )
