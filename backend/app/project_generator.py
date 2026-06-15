import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _pascal(value: str) -> str:
    return "".join(part.capitalize() for part in value.split("_"))


def _camel(value: str) -> str:
    pascal = _pascal(value)
    return pascal[:1].lower() + pascal[1:]


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
        f'    @TableField("{_field_name(index)}")\n'
        f"    private {field_types[index]} {_field_name(index)};"
        for index in range(len(module["fields"]))
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

@Data
@TableName("{table}")
public class {class_name}Entity {{
    @TableId(type = IdType.AUTO)
    private Long id;
{fields}
    private LocalDateTime createdAt;
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
    return f"""
package {package_name}.module.{module["key"]}.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import {package_name}.common.PageQuery;
import {package_name}.module.{module["key"]}.dto.{class_name}DTO;
import {package_name}.module.{module["key"]}.vo.{class_name}VO;

public interface {class_name}Service {{
    IPage<{class_name}VO> page(PageQuery query);
    {class_name}VO detail(Long id);
    Long create({class_name}DTO dto);
    void update(Long id, {class_name}DTO dto);
    void delete(Long id);
}}
"""


def _service_impl(package_name: str, module: Dict[str, Any]) -> str:
    class_name = _pascal(module["key"])
    first_field = _field_name(0)
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

@Service
public class {class_name}ServiceImpl implements {class_name}Service {{
    private final {class_name}Mapper mapper;

    public {class_name}ServiceImpl({class_name}Mapper mapper) {{
        this.mapper = mapper;
    }}

    @Override
    public IPage<{class_name}VO> page(PageQuery query) {{
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
        {class_name}Entity entity = mapper.selectById(id);
        if (entity == null) {{
            throw new IllegalArgumentException("{module["name"]}记录不存在");
        }}
        return toVO(entity);
    }}

    @Override
    @Transactional
    public Long create({class_name}DTO dto) {{
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
        if (mapper.deleteById(id) == 0) {{
            throw new IllegalArgumentException("{module["name"]}记录不存在");
        }}
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
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/{module["key"]}")
public class {class_name}Controller {{
    private final {class_name}Service service;

    public {class_name}Controller({class_name}Service service) {{
        this.service = service;
    }}

    @GetMapping
    public ApiResponse<IPage<{class_name}VO>> page(
        @RequestParam(defaultValue = "1") long page,
        @RequestParam(defaultValue = "10") long size,
        @RequestParam(defaultValue = "") String keyword
    ) {{
        return ApiResponse.success(service.page(new PageQuery(page, size, keyword)));
    }}

    @GetMapping("/{{id}}")
    public ApiResponse<{class_name}VO> detail(@PathVariable Long id) {{
        return ApiResponse.success(service.detail(id));
    }}

    @PostMapping
    public ApiResponse<Long> create(@Valid @RequestBody {class_name}DTO dto) {{
        return ApiResponse.success(service.create(dto));
    }}

    @PutMapping("/{{id}}")
    public ApiResponse<Void> update(
        @PathVariable Long id,
        @Valid @RequestBody {class_name}DTO dto
    ) {{
        service.update(id, dto);
        return ApiResponse.success(null);
    }}

    @DeleteMapping("/{{id}}")
    public ApiResponse<Void> delete(@PathVariable Long id) {{
        service.delete(id);
        return ApiResponse.success(null);
    }}
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
    EXPORT("export", "导出", false);

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
    return f"""
package {package_name}.module.{module["key"]}.controller;

import org.junit.jupiter.api.Test;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
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
    }}

    @Test
    void shouldKeepFivePublicBusinessEndpoints() {{
        long endpointCount = Arrays.stream({class_name}Controller.class.getDeclaredMethods())
            .filter(method ->
                method.isAnnotationPresent(GetMapping.class)
                    || method.isAnnotationPresent(PostMapping.class)
                    || method.isAnnotationPresent(PutMapping.class)
                    || method.isAnnotationPresent(DeleteMapping.class)
            )
            .count();
        assertEquals(5, endpointCount);
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
        assertEquals(5, methods.size());
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
        f"  {_field_name(index)} {_sql_type(_java_type(field))} NOT NULL COMMENT '{field}'"
        for index, field in enumerate(module["fields"])
    )
    return f"""
DROP TABLE IF EXISTS {table};
CREATE TABLE {table} (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
{columns},
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='{module["name"]}';
"""


def _h2_table_sql(module: Dict[str, Any], table: str) -> str:
    columns = ",\n".join(
        f"  {_field_name(index)} {_sql_type(_java_type(field))} NOT NULL"
        for index, field in enumerate(module["fields"])
    )
    return f"""
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
    return f"""
import request from './request'

export const page{_pascal(key)} = params => request.get('/{key}', {{ params }})
export const get{_pascal(key)} = id => request.get(`/{key}/${{id}}`)
export const create{_pascal(key)} = data => request.post('/{key}', data)
export const update{_pascal(key)} = (id, data) => request.put(`/{key}/${{id}}`, data)
export const delete{_pascal(key)} = id => request.delete(`/{key}/${{id}}`)
"""


def _vue_page(module: Dict[str, Any]) -> str:
    key = module["key"]
    pascal = _pascal(key)
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
      <div class="module-dashboard"><article v-for="(field,index) in fields.slice(0,4)" :key="field.key"><span>{{field.label}}</span><b>{{128 + index * 36}}</b></article><div class="mini-trend"><i v-for="height in [38,62,48,76,58,88]" :style="{height:height+'%'}"></i></div></div>
""",
    }.get(pattern, "")
    return f"""
<script setup>
import {{ onMounted, reactive, ref }} from 'vue'
import {{ ElMessage, ElMessageBox }} from 'element-plus'
import {{ fields }} from '../config/{key}'
import {{
  page{pascal}, create{pascal}, update{pascal}, delete{pascal}
}} from '../api/{key}'

const loading = ref(false)
const dialogVisible = ref(false)
const editingId = ref(null)
const rows = ref([])
const total = ref(0)
const query = reactive({{ page: 1, size: 10, keyword: '' }})
const form = reactive(Object.fromEntries(fields.map(item => [item.key, ''])))
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
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{{ row }}">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
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
        frontend / "src/views/DashboardPage.vue",
        _dashboard_vue(planning, menu),
    )
    _write(
        frontend / "src/router.js",
        "\n".join(imports)
        + "\nimport DashboardPage from './views/DashboardPage.vue'\n"
        + f"""
import {{ createRouter, createWebHistory }} from 'vue-router'
const routes = [
  {{path: '/', name: 'dashboard', component: DashboardPage}},
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


def _dashboard_vue(planning: Dict[str, Any], menu: List[Dict[str, str]]) -> str:
    pattern = planning.get("ui_plan", {}).get("home_pattern", "metric_dashboard")
    if pattern == "task_dashboard":
        body = """
    <div class="task-workbench">
      <el-card><h3>我的待办</h3><p v-for="(item,index) in modules.slice(0,4)" :key="item.key"><b>{{index + 1}}</b>{{item.name}}待处理事项 <span>{{8 + index * 3}}</span></p></el-card>
      <el-card><h3>业务流程</h3><div class="flow-line"><i>受理</i><em></em><i>办理</i><em></em><i>审核</i><em></em><i>归档</i></div></el-card>
      <el-card><h3>快捷入口</h3><div class="quick-grid"><router-link v-for="item in modules" :key="item.key" :to="'/'+item.key">{{item.name}}</router-link></div></el-card>
    </div>
"""
    elif pattern == "analysis_dashboard":
        body = """
    <div class="analysis-workbench">
      <div class="analysis-metrics"><article v-for="(item,index) in modules.slice(0,4)" :key="item.key"><span>{{item.name}}</span><b>{{356 + index * 89}}</b><small>较上期 +{{4 + index}}%</small></article></div>
      <el-card class="trend-panel"><h3>核心指标趋势</h3><div class="bars"><i v-for="height in [32,48,42,68,61,82,74,91]" :style="{height:height+'%'}"></i></div></el-card>
      <el-card class="ranking-panel"><h3>业务排行</h3><p v-for="(item,index) in modules" :key="item.key"><span>{{index + 1}}. {{item.name}}</span><b>{{98 - index * 7}}%</b></p></el-card>
    </div>
"""
    else:
        body = """
    <div class="metric-grid"><el-card v-for="(item,index) in modules" :key="item.key" shadow="hover"><span>{{item.name}}</span><strong>{{128 + index * 37}}</strong><small>数据状态正常</small></el-card></div>
    <el-card shadow="never"><h3>近七日业务趋势</h3><div class="bars"><i v-for="height in [42,58,51,76,68,86,73]" :style="{height:height+'%'}"></i></div></el-card>
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
.master-detail-preview,.tree-detail-preview{{display:grid;grid-template-columns:1fr 1.6fr;gap:12px;margin-bottom:18px}}.master-detail-preview>div,.master-detail-preview aside,.tree-detail-preview>*{{padding:16px;background:#f5f8fc;border:1px solid #e0e7ef;border-radius:8px}}.workflow-preview{{padding:18px;background:#f7f9fc;border-radius:8px;margin-bottom:18px}}.workflow-preview>div{{display:flex;align-items:center;margin-top:14px}}.workflow-preview span{{width:30px;height:30px;border-radius:50%;background:#2678c9;color:#fff;display:grid;place-items:center}}.workflow-preview i{{height:2px;background:#9fc5e8;flex:1}}.kanban-preview{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:18px}}.kanban-preview article{{background:#eef3f8;padding:14px;border-radius:8px}}.kanban-preview p{{background:#fff;padding:10px;border-radius:6px}}.module-dashboard{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}}.module-dashboard article{{padding:16px;background:#f3f8fe;border-radius:8px}}.module-dashboard article span,.module-dashboard article b{{display:block}}.module-dashboard article b{{font-size:24px;margin-top:8px}}.mini-trend{{grid-column:1/-1;height:120px;display:flex;align-items:flex-end;gap:18px;padding:18px;background:#f8fafc}}.mini-trend i{{flex:1;background:#2d82cf;border-radius:4px 4px 0 0}}
.task-workbench{{display:grid;grid-template-columns:1fr 1.4fr;gap:16px;margin-top:18px}}.task-workbench>.el-card:last-child{{grid-column:1/-1}}.task-workbench p{{display:grid;grid-template-columns:30px 1fr auto;align-items:center;padding:10px;border-bottom:1px solid #edf1f5}}.task-workbench p b{{width:24px;height:24px;display:grid;place-items:center;background:#e8f2ff;color:#2872b8;border-radius:50%}}.flow-line{{display:flex;align-items:center;padding:40px 20px}}.flow-line i{{font-style:normal;background:#2678c9;color:#fff;padding:12px;border-radius:50%}}.flow-line em{{height:2px;background:#9fc5e8;flex:1}}.quick-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.quick-grid a{{padding:16px;background:#f0f6fc;color:#2469aa;text-decoration:none;border-radius:8px}}.analysis-workbench{{display:grid;grid-template-columns:2fr 1fr;gap:16px;margin-top:18px}}.analysis-metrics{{grid-column:1/-1;display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.analysis-metrics article{{padding:18px;background:#152f52;color:#fff;border-radius:9px}}.analysis-metrics span,.analysis-metrics small,.analysis-metrics b{{display:block}}.analysis-metrics b{{font-size:28px;margin:10px 0}}.ranking-panel p{{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #edf1f5}}
@media(max-width:1000px){{.shell-split{{grid-template-columns:190px 1fr}}.context-panel{{display:none}}.shell-top>header{{grid-template-columns:1fr auto}}.shell-top nav{{grid-row:2;grid-column:1/-1}}.module-dashboard{{grid-template-columns:1fr 1fr}}}}
"""
    return base + variants


def generate_java_project(job_dir: Path) -> None:
    planning = json.loads((job_dir / "planning.json").read_text(encoding="utf-8"))
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
