from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math


ROOT = Path(__file__).resolve().parent
EXPORTS = ROOT / "exports"
EXPORTS.mkdir(parents=True, exist_ok=True)

W, H = 1600, 900
BLUE = (0, 133, 208)
DARK = (31, 71, 102)
GREEN = (62, 173, 162)
PALE = (242, 249, 253)
BORDER = (184, 222, 240)
GRAY = (100, 124, 145)
RED = (230, 90, 80)
WHITE = (255, 255, 255)


def font(size: int, bold: bool = False):
    font_dir = Path(r"C:\Windows\Fonts")
    names = ["msyhbd.ttc", "msyh.ttc", "simhei.ttf", "simsun.ttc"] if bold else [
        "msyh.ttc",
        "simhei.ttf",
        "simsun.ttc",
    ]
    for name in names:
        path = font_dir / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


F = {
    "cover": font(58, True),
    "h1": font(42, True),
    "h2": font(30, True),
    "h3": font(24, True),
    "body": font(22),
    "small": font(17),
    "tiny": font(14),
    "num": font(46, True),
}


def draw_wrapped(draw, text, xy, max_width, fnt, fill=DARK, line_gap=8, max_lines=None):
    x, y = xy
    lines, current = [], ""
    for ch in text:
        test = current + ch
        if draw.textbbox((0, 0), test, font=fnt)[2] <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip("，。；、 ") + "…"
    for line in lines:
        draw.text((x, y), line, font=fnt, fill=fill)
        y += fnt.size + line_gap
    return y


def rr(draw, box, r=20, fill=WHITE, outline=BORDER, width=2):
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def arrow(draw, p1, p2, color=BLUE, width=4):
    draw.line([p1, p2], fill=color, width=width)
    x1, y1 = p1
    x2, y2 = p2
    angle = math.atan2(y2 - y1, x2 - x1)
    length = 14
    pts = [
        (x2, y2),
        (x2 - length * math.cos(angle - math.pi / 6), y2 - length * math.sin(angle - math.pi / 6)),
        (x2 - length * math.cos(angle + math.pi / 6), y2 - length * math.sin(angle + math.pi / 6)),
    ]
    draw.polygon(pts, fill=color)


def header(draw, title, desc=None, section="AI软著工厂 · 智能体工作流实践"):
    draw.text((70, 42), title, font=F["h1"], fill=BLUE)
    draw.text((1265, 52), "中国移动风格汇报", font=F["small"], fill=GREEN)
    draw.line((70, 105, 1530, 105), fill=BORDER, width=2)
    if desc:
        draw_wrapped(draw, desc, (72, 124), 1380, F["body"], fill=DARK, line_gap=6, max_lines=2)
    draw.text((70, 846), section, font=F["tiny"], fill=GRAY)
    draw.line((70, 830, 1530, 830), fill=(220, 237, 247), width=1)
    draw.text((1450, 846), "2026", font=F["tiny"], fill=GRAY)


def base(title=None, desc=None):
    image = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, W, 16), fill=BLUE)
    draw.rectangle((0, 16, W, 21), fill=GREEN)
    for i in range(9):
        draw.ellipse((1180 + i * 55, 110 + i * 22, 1440 + i * 55, 370 + i * 22), outline=(226, 244, 251), width=2)
    for x in range(980, 1540, 70):
        draw.line((x, 740, x + 160, 580), fill=(235, 247, 252), width=2)
    if title:
        header(draw, title, desc)
    return image, draw


def save(image, idx, name):
    path = EXPORTS / f"{idx:02d}-{name}.png"
    image.save(path, quality=95)
    return path


def slide_cover():
    im, d = base()
    d.text((82, 92), "AI软著工厂", font=F["cover"], fill=BLUE)
    d.text((86, 168), "从软件名称到完整软著申报包的智能生成流程", font=F["h2"], fill=DARK)
    d.text((90, 224), "面向领导汇报｜流程说明 + 智能体工作流抽象", font=F["body"], fill=GRAY)
    rr(d, (90, 330, 610, 640), 28, PALE, BORDER, 2)
    d.text((130, 372), "核心产出", font=F["h2"], fill=DARK)
    for i, text in enumerate(["可运行 Java/Vue Demo", "在线审查与自然语言返工", "截图、文档、源码材料、申报包"]):
        d.ellipse((136, 438 + i * 54, 152, 454 + i * 54), fill=GREEN)
        d.text((172, 428 + i * 54), text, font=F["body"], fill=DARK)
    rr(d, (700, 300, 1465, 675), 36, (250, 253, 255), BORDER, 2)
    cx, cy = 1085, 490
    for r, c in [(190, (210, 238, 249)), (135, (195, 232, 245)), (80, (174, 224, 239))]:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=c, width=3)
    d.ellipse((cx - 78, cy - 78, cx + 78, cy + 78), fill=BLUE)
    d.text((cx - 30, cy - 30), "AI", font=F["cover"], fill=WHITE)
    for angle, label in [(0, "规划"), (1.25, "代码"), (2.5, "验证"), (3.75, "材料"), (5.0, "审查")]:
        x = cx + 190 * math.cos(angle)
        y = cy + 190 * math.sin(angle)
        d.ellipse((x - 34, y - 34, x + 34, y + 34), fill=WHITE, outline=GREEN, width=3)
        d.text((x - 24, y - 14), label, font=F["small"], fill=DARK)
    d.text((86, 820), "内部过程汇报 · 预览稿", font=F["small"], fill=GRAY)
    return im


def slide_positioning():
    im, d = base(
        "一、软件定位：把软著交付做成可审查的自动化流水线",
        "系统不是简单生成文档，而是围绕“规划、项目、Demo、材料、合规”建立可追溯闭环，降低重复开发和材料整理成本。",
    )
    items = [
        ("输入", "软件名称\n类型/行业\n软件描述"),
        ("规划", "LLM生成规划\nReview人工确认\n版本留痕"),
        ("项目", "Spring Boot\nVue3\nMySQL脚本"),
        ("审查", "在线Demo\nSwagger/日志\n自然语言返工"),
        ("材料", "截图/文档\n源码材料\n申报ZIP"),
    ]
    for i, (title, body) in enumerate(items):
        x, y = 90 + i * 282, 330
        rr(d, (x, y, x + 220, y + 210), 24, WHITE, BORDER, 2)
        d.text((x + 24, y + 24), f"{i + 1:02d}", font=F["num"], fill=BLUE)
        d.text((x + 92, y + 38), title, font=F["h2"], fill=DARK)
        draw_wrapped(d, body, (x + 26, y + 104), 168, F["body"], fill=GRAY, line_gap=6)
        if i < 4:
            arrow(d, (x + 222, y + 104), (x + 266, y + 104), GREEN, 5)
    rr(d, (130, 620, 1470, 750), 22, PALE, BORDER, 2)
    d.text((160, 652), "管理价值", font=F["h2"], fill=BLUE)
    d.text((320, 650), "把“不可控的大模型生成”转为“有规划、有审查、有版本、有验证”的工程化交付链路。", font=F["body"], fill=DARK)
    return im


def slide_workflow():
    im, d = base(
        "二、当前软著工程实现流程",
        "用户先确认规划，再生成真实项目；Demo 审查通过后才进入截图和材料阶段，不符合预期可自然语言返工并重新生成。",
    )
    steps = ["创建任务", "AI规划", "Planning Review", "生成项目", "运行验证", "启动Demo", "人工审查", "材料打包"]
    coords = []
    for i, step in enumerate(steps):
        x, y = 100 + (i % 4) * 360, 270 + (i // 4) * 250
        coords.append((x, y))
        rr(d, (x, y, x + 255, y + 105), 20, WHITE, BORDER, 2)
        d.text((x + 20, y + 18), f"{i + 1}", font=F["h2"], fill=BLUE)
        d.text((x + 72, y + 26), step, font=F["h3"], fill=DARK)
    for i in range(3):
        arrow(d, (coords[i][0] + 255, coords[i][1] + 52), (coords[i + 1][0] - 20, coords[i + 1][1] + 52), BLUE, 4)
    arrow(d, (coords[3][0] + 128, coords[3][1] + 105), (coords[4][0] + 128, coords[4][1] - 30), BLUE, 4)
    for i in range(4, 7):
        arrow(d, (coords[i][0] + 255, coords[i][1] + 52), (coords[i + 1][0] - 20, coords[i + 1][1] + 52), BLUE, 4)
    arrow(d, (coords[6][0] + 60, coords[6][1] + 104), (coords[2][0] + 190, coords[2][1] + 105), RED, 3)
    d.text((760, 705), "不符合预期：自然语言返工 → 新规划版本 → 重新生成", font=F["small"], fill=RED)
    return im


def slide_architecture():
    im, d = base(
        "三、系统架构：LLM规划 + 确定性生成 + 状态化工作流",
        "整体采用前后端分离和文件化任务状态，LLM负责结构化规划，生成器负责稳定落地，流水线负责验证、Demo、截图和材料输出。",
    )
    layers = [
        ("交互层", "首页 / Planning Review / 历史任务 / Demo审查"),
        ("编排层", "FastAPI任务接口 / 状态机 / Worker锁 / 中断恢复"),
        ("智能层", "LLM规划 / 返工建议 / JSON修复 / 结构校验"),
        ("生成层", "Java项目生成 / Vue页面生成 / SQL / 业务动作按钮"),
        ("验证与交付", "npm build / Maven test / Playwright截图 / 文档与ZIP"),
    ]
    for i, (title, body) in enumerate(layers):
        x, y = 150, 205 + i * 112
        rr(d, (x, y, 1450, y + 78), 18, PALE if i % 2 == 0 else WHITE, BORDER, 2)
        d.rectangle((x, y, x + 18, y + 78), fill=BLUE if i < 3 else GREEN)
        d.text((x + 42, y + 16), title, font=F["h3"], fill=DARK)
        d.text((x + 275, y + 20), body, font=F["body"], fill=GRAY)
        if i < 4:
            arrow(d, (800, y + 80), (800, y + 108), GREEN, 4)
    return im


def slide_demo_gate():
    im, d = base(
        "四、关键机制：Demo审查前置，避免材料阶段返工",
        "在线 Demo 是质量闸口：用户看到真实系统后再决定继续生成材料，或提出自然语言修改意见并回退到规划层重新生成。",
    )
    rr(d, (115, 250, 550, 670), 28, WHITE, BORDER, 2)
    d.text((150, 292), "Demo审查台", font=F["h2"], fill=BLUE)
    for i, text in enumerate(["前端地址", "Swagger地址", "运行日志", "下载源码"]):
        rr(d, (155, 365 + i * 58, 495, 405 + i * 58), 12, PALE, BORDER, 1)
        d.text((180, 372 + i * 58), text, font=F["body"], fill=DARK)
    rr(d, (660, 250, 1480, 670), 28, PALE, BORDER, 2)
    flow = [
        ("通过", "截图 / 文档 / 合规 / ZIP", GREEN),
        ("不通过", "自然语言说明问题", RED),
        ("系统处理", "生成变更摘要与新规划", BLUE),
        ("再确认", "重新生成项目并再次审查", GREEN),
    ]
    for i, (title, body, color) in enumerate(flow):
        y = 300 + i * 84
        d.ellipse((710, y, 762, y + 52), fill=color)
        d.text((727, y + 10), str(i + 1), font=F["h3"], fill=WHITE)
        d.text((790, y + 2), title, font=F["h3"], fill=DARK)
        d.text((790, y + 38), body, font=F["body"], fill=GRAY)
        if i < 3:
            arrow(d, (736, y + 55), (736, y + 82), color, 4)
    return im


def slide_quality():
    im, d = base(
        "五、工程化保障：生成结果可验证、可追溯、可回退",
        "围绕任务目录保存状态、规划版本、返工建议、日志和产物，通过自动测试与合规检查提升批量生成的稳定性。",
    )
    blocks = [
        ("结构校验", "Pydantic校验\n坏JSON自动修复\n数据库表自动补齐"),
        ("运行验证", "npm build\nMaven test\nDemo端口检测"),
        ("一致性检查", "规划-代码-截图-文档\n模块覆盖率\n名称一致性"),
        ("原创性增强", "业务化注释\n项目指纹\n原创性报告"),
        ("版本控制", "planning_versions\nrevision_proposals\n历史任务恢复"),
        ("风险控制", "截图不足\n代码不足\n接口缺失预警"),
    ]
    for i, (title, body) in enumerate(blocks):
        x, y = 110 + (i % 3) * 490, 230 + (i // 3) * 230
        rr(d, (x, y, x + 400, y + 160), 22, WHITE, BORDER, 2)
        d.text((x + 24, y + 24), title, font=F["h2"], fill=BLUE if i % 2 == 0 else GREEN)
        draw_wrapped(d, body, (x + 26, y + 78), 330, F["body"], fill=GRAY, line_gap=5)
    return im


def slide_agent_workflow():
    im, d = base(
        "六、抽象方法：智能体搭建工作流的基础流程",
        "从软著工厂可以抽象出一套通用智能体工作流：先把目标结构化，再进入生成、验证、人工闸口和闭环迭代。",
    )
    steps = [
        ("目标输入", "业务目标\n约束条件"),
        ("上下文检索", "知识/历史\n配置/模板"),
        ("结构化规划", "模块/接口\n数据/页面"),
        ("人工确认", "Review\n调整/锁定"),
        ("自动生成", "代码/文档\n配置/脚本"),
        ("自动验证", "测试/构建\n一致性"),
        ("人工闸口", "Demo/报告\n审批"),
        ("交付归档", "版本/日志\n材料/包"),
    ]
    for i, (title, body) in enumerate(steps):
        x, y = 95 + i * 185, 360 + int(40 * math.sin(i))
        color = BLUE if i < 4 else GREEN
        d.ellipse((x, y, x + 128, y + 128), fill=WHITE, outline=color, width=4)
        d.text((x + 34, y + 18), f"{i + 1}", font=F["h2"], fill=color)
        d.text((x + 20, y + 62), title, font=F["small"], fill=DARK)
        if i < 7:
            arrow(d, (x + 130, y + 64), (x + 180, y + 64), GREEN, 3)
        draw_wrapped(d, body, (x - 8, y + 145), 150, F["small"], fill=GRAY, line_gap=4, max_lines=2)
    rr(d, (220, 700, 1380, 775), 20, PALE, BORDER, 2)
    d.text((255, 722), "关键原则：LLM 负责“理解与规划”，工程系统负责“执行与验证”，人负责“确认与决策”。", font=F["body"], fill=DARK)
    return im


def slide_platform():
    im, d = base(
        "七、可复制能力：从单软件生成扩展到行业级智能体工作台",
        "把软著工厂拆成规划智能体、生成智能体、验证智能体和审查智能体，可复用到标书、巡检、运维、数据治理等多类流程。",
    )
    left = [
        ("Planner Agent", "把自然语言需求转成结构化规划"),
        ("Generator Agent", "把规划转成代码、文档或配置"),
        ("Verifier Agent", "执行测试、合规、风险和一致性检查"),
        ("Reviewer Agent", "组织人机审查、返工和版本回退"),
    ]
    for i, (title, body) in enumerate(left):
        y = 225 + i * 130
        rr(d, (105, y, 635, y + 92), 18, WHITE, BORDER, 2)
        d.text((135, y + 15), title, font=F["h3"], fill=BLUE)
        d.text((135, y + 52), body, font=F["body"], fill=GRAY)
    rr(d, (760, 215, 1468, 706), 30, PALE, BORDER, 2)
    d.text((805, 255), "工作流底座", font=F["h2"], fill=DARK)
    for i, text in enumerate(["状态机与任务锁", "上下文与版本管理", "工具调用与执行沙箱", "自动验证与质量闸口", "审计日志与交付归档"]):
        y = 330 + i * 58
        d.rectangle((820, y, 846, y + 26), fill=GREEN if i % 2 else BLUE)
        d.text((870, y - 2), text, font=F["body"], fill=DARK)
    d.text((800, 655), "下一步可沉淀为企业级“智能体工作流平台”：统一接入模型、工具、模板、审批和交付。", font=F["body"], fill=BLUE)
    return im


slides = [
    ("cover", slide_cover),
    ("positioning", slide_positioning),
    ("software-workflow", slide_workflow),
    ("architecture", slide_architecture),
    ("demo-review-loop", slide_demo_gate),
    ("quality", slide_quality),
    ("agent-workflow", slide_agent_workflow),
    ("reusable-platform", slide_platform),
]

paths = [save(factory(), idx, name) for idx, (name, factory) in enumerate(slides, 1)]

thumb_w, thumb_h = 400, 225
sheet = Image.new("RGB", (thumb_w * 2 + 60, thumb_h * 4 + 150), (245, 250, 253))
sd = ImageDraw.Draw(sheet)
sd.text((30, 24), "AI软著工厂汇报PPT缩略图预览", font=F["h2"], fill=BLUE)
sd.text((30, 66), "移动汇报风格｜浅底蓝绿｜流程与智能体工作流抽象", font=F["small"], fill=GRAY)
for i, path in enumerate(paths):
    thumb = Image.open(path).resize((thumb_w, thumb_h))
    x = 30 + (i % 2) * thumb_w
    y = 110 + (i // 2) * (thumb_h + 10)
    sheet.paste(thumb, (x, y))
    sd.rectangle((x, y, x + thumb_w, y + thumb_h), outline=BORDER, width=2)
    sd.text((x + 10, y + 8), f"{i + 1:02d}", font=F["small"], fill=BLUE)

sheet_path = EXPORTS / "00-contact-sheet.png"
sheet.save(sheet_path, quality=95)
print(sheet_path)
for path in paths:
    print(path)
