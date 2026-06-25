# ruanzhu-agent-methodology-report - Design Spec

> Human-readable design narrative - rationale, audience, style, color choices, content outline. Read once by downstream roles for context.
>
> Machine-readable execution contract: `spec_lock.md` (color / typography / icon / image short form). Executor re-reads `spec_lock.md` before every SVG page to resist context-compression drift. Keep both in sync; on divergence, `spec_lock.md` wins.

## I. Project Information

| Item | Value |
| ---- | ----- |
| **Project Name** | ruanzhu-agent-methodology-report |
| **Canvas Format** | PPT 16:9 (1280x720) |
| **Page Count** | 6 |
| **Design Style** | C) Top Consulting + 政企科技汇报风 |
| **Target Audience** | 公司领导、管理层 |
| **Use Case** | 内部阶段汇报、成果展示、方法论沉淀 |
| **Created Date** | 2026-06-18 |

---

## II. Canvas Specification

| Property | Value |
| -------- | ----- |
| **Format** | PPT 16:9 |
| **Dimensions** | 1280x720 |
| **viewBox** | `0 0 1280 720` |
| **Margins** | left/right 48px, top 40px, bottom 28px |
| **Content Area** | 1184x612 inside the safe margin, with a 40px title band and 28px footer reserve |

---

## III. Visual Theme

### Theme Style

- **Style**: C) Top Consulting + 政企科技汇报风
- **Theme**: Light theme
- **Tone**: 稳重、理性、科技感、面向管理决策

### Color Scheme

| Role | HEX | Purpose |
| ---- | --- | ------- |
| **Background** | `#F7F9FC` | Page background |
| **Secondary bg** | `#FFFFFF` | Card background, highlight block background |
| **Primary** | `#0B3A82` | Top bar, major titles, key shapes |
| **Accent** | `#18A0A6` | Focus highlights, strategic keywords |
| **Secondary accent** | `#7C8FB3` | Secondary diagrams, helper labels |
| **Body text** | `#1F2A44` | Main body text |
| **Secondary text** | `#5B6780` | Annotations, subtitles |
| **Tertiary text** | `#8A96AA` | Footers, minor captions |
| **Border/divider** | `#D9E1EC` | Card borders, separator lines |
| **Success** | `#1F9D55` | Positive management value cues |
| **Warning** | `#D94F4F` | Structural challenge cues |

### Gradient Scheme

```xml
<!-- Title gradient -->
<linearGradient id="titleGradient" x1="0%" y1="0%" x2="100%" y2="0%">
  <stop offset="0%" stop-color="#0B3A82"/>
  <stop offset="100%" stop-color="#18A0A6"/>
</linearGradient>

<!-- Background decorative gradient -->
<radialGradient id="bgDecor" cx="82%" cy="8%" r="45%">
  <stop offset="0%" stop-color="#7C8FB3" stop-opacity="0.16"/>
  <stop offset="100%" stop-color="#7C8FB3" stop-opacity="0"/>
</radialGradient>
```

---

## IV. Typography System

### Font Plan

**Typography direction**: 咨询式标题对比 + 中文无衬线正文，兼顾领导汇报的稳重感与现代感

| Role | Chinese | English | Fallback tail |
| ---- | ------- | ------- | ------------- |
| **Title** | `"Microsoft YaHei"` | `Georgia` | `serif` |
| **Body** | `"Microsoft YaHei"` | `Arial` | `sans-serif` |
| **Emphasis** | `SimSun` | `Georgia` | `serif` |
| **Code** | - | `Consolas, "Courier New"` | `monospace` |

**Per-role font stacks**:

- Title: `Georgia, "Microsoft YaHei", serif`
- Body: `"Microsoft YaHei", Arial, sans-serif`
- Emphasis: `Georgia, SimSun, serif`
- Code: `Consolas, "Courier New", monospace`

### Font Size Hierarchy

**Baseline**: Body font size = 22px

| Purpose | Ratio to body | Example @ body=24 (relaxed) | Example @ body=18 (dense) | Weight |
| ------- | ------------- | --------------------------- | ------------------------- | ------ |
| Cover title (hero headline) | 2.5-5x | 60-120px | 45-90px | Bold / Heavy |
| Chapter / section opener | 2-2.5x | 48-60px | 36-45px | Bold |
| Page title | 1.5-2x | 36-48px | 27-36px | Bold |
| Hero number (consulting KPIs) | 1.5-2x | 36-48px | 27-36px | Bold |
| Subtitle | 1.2-1.5x | 29-36px | 22-27px | SemiBold |
| **Body content** | **1x** | **24px** | **18px** | Regular |
| Annotation / caption | 0.7-0.85x | 17-20px | 13-15px | Regular |
| Page number / footnote | 0.5-0.65x | 12-16px | 9-12px | Regular |

---

## V. Layout Principles

### Page Structure

- **Header area**: 40px top gradient bar + 56px title band for assertion-style headings
- **Content area**: 520px centered content zone for diagrams, cards, and methods
- **Footer area**: 24px footer line with source / confidentiality / page number

### Layout Pattern Library (combine or break as content demands)

| Pattern | Suitable Scenarios |
| ------- | ----------------- |
| **Single column centered** | Cover, closing principle emphasis |
| **Asymmetric split (3:7 / 2:8)** | Takeaway + supporting structure |
| **Three/four column cards** | Management value, principle clusters |
| **Matrix grid (2x2)** | Four-step method or categorized insights |
| **Z-pattern / waterfall** | Storytelling transitions between pain, mechanism, method |
| **Center-radiating** | Method framework anchor concept |
| **Negative-space-driven** | Final principle page for emphasis |

### Spacing Specification

**Universal**:

| Element | Recommended Range | Current Project |
| ------- | ---------------- | --------------- |
| Safe margin from canvas edge | 40-60px | 48px |
| Content block gap | 24-40px | 28px |
| Icon-text gap | 8-16px | 10px |

**Card-based layouts**:

| Element | Recommended Range | Current Project |
| ------- | ---------------- | --------------- |
| Card gap | 20-32px | 24px |
| Card padding | 20-32px | 24px |
| Card border radius | 8-16px | 14px |
| Single-row card height | 530-600px | 560px |
| Double-row card height | 265-295px each | 276px |
| Three-column card width | 360-380px each | 372px |

**Non-card containers**:

- 通过留白、标题与结论框的对比建立层次，不依赖密集底板。
- 正文行高控制在 1.45x 左右，保证屏幕展示下的阅读舒适度。
- 方法论页和原则页优先使用“少元素 + 强结论”的负空间策略。

---

## VI. Icon Usage Specification

### Source

- **Built-in icon library**: `templates/icons/`
- **Usage method**: SVG placeholder `<use data-icon="library/icon-name" .../>`; only approved icons may appear

### Recommended Icon List

| Purpose | Icon Path | Page |
| ------- | --------- | ---- |
| 汇报目标 / 对准方向 | `chunk-filled/target` | Slide 01, 05 |
| 效率与加速 | `chunk-filled/bolt` | Slide 04 |
| 管理与协同 | `chunk-filled/users` | Slide 02, 06 |
| 安全与可控 | `chunk-filled/shield` | Slide 04, 06 |
| 数据与流程 | `chunk-filled/chart-bar` | Slide 03, 04 |
| 方法与洞察 | `chunk-filled/lightbulb` | Slide 05, 06 |

---

## VII. Visualization Reference List (if needed)

Catalog read: 71 templates

| Page | Template | Path | Summary-quote (verbatim from `charts_index.json`) | Usage |
| ---- | -------- | ---- | ------------------------------------------------- | ----- |
| P02 | vertical_list | `templates/charts/vertical_list.svg` | "Pick for 3-6 numbered key points each with a short description - design principles, core tenets, action items, key takeaways, recommendations, executive summary points. Skip for icon-style cards (use icon_grid) or sequential steps (use numbered_steps)." | 传统软著制作的四类核心痛点，适合纵向分层陈述 |
| P03 | chevron_process | `templates/charts/chevron_process.svg` | "Pick for 3-6 phase methodology with chunky arrow-chain progression and deliverables per phase. Skip for <=2 phases or non-linear flow (use process_flow), or chain ending in an aggregate outcome wedge (use chevron_chain_with_tail)." | 展示软著智能化流程的阶段推进与闭环逻辑 |
| P04 | kpi_cards | `templates/charts/kpi_cards.svg` | "Pick for 4-8 standalone numeric metrics shown as overview cards (2x2 or 1x4) - exec summary opener, dashboard headline, quarterly recap, results-at-a-glance. Skip if metrics have target baselines (use bullet_chart) or single hero number (use gauge_chart)." | 用四张管理价值卡呈现标准化、可控性、效率、可复制性 |
| P05 | numbered_steps | `templates/charts/numbered_steps.svg` | "Pick for 3-6 horizontal sequential steps with numeric emphasis - how-it-works section, getting-started guide, methodology overview, implementation phases. Skip if steps need connector arrows (use process_flow) or named output artifacts (use pipeline_with_stages)." | 呈现智能体方法论的四步结构，强化顺序感 |
| P06 | labeled_card | `templates/charts/labeled_card.svg` | "Pick for 3-4 parallel aspects of one subject with per-aspect titles + short body (self-introduction, four-pillar overview, capability quadrant). Skip for plain feature lists (use icon_grid), sequential steps (use numbered_steps), or strategic quadrants (use quadrant_text_bullets / matrix_2x2)." | 用四项原则并列收束整套方法论，形成高层可记忆框架 |

**Runners-up considered**:

- `icon_grid` | rejected for P02: 能做并列要点，但不如 `vertical_list` 适合表达“问题递进与管理挑战”
- `process_flow` | rejected for P03: 线性流程是对的，但 `chevron_process` 的阶段感和领导汇报气质更强
- `comparison_columns` | rejected for P04: 适合套餐或层级比较，不如 `kpi_cards` 适合四个管理价值的“结果概览”
- `arc_anchored_list` | rejected for P05: 结构有新意，但会削弱四步方法的标准化顺序表达
- `vertical_list` | rejected for P06: 虽可表达原则，但 `labeled_card` 更适合做收束页的并列原则框架

---

## VIII. Image Resource List (if needed)

本项目不使用外部图片、AI 图片或网页素材。整套汇报以结构图、图标、卡片、流程线和重点结论框为主，保证风格克制、适合领导阅读。

---

## IX. Content Outline

### Part 1: 汇报主线

#### Slide 01 - 项目背景与汇报目标

- **Layout**: Single column centered
- **Title**: 从软著制作到智能体方法沉淀
- **Core message**: 这次汇报的价值不只在于完成一次软著交付，而在于沉淀出可复制的智能体工作方法。
- **Content**:
  - 以一次真实软著生产实践为载体，我们验证了从需求输入、规划生成、项目生成、Demo 审查到材料交付的完整链路。
  - 本次汇报聚焦两条主线：一条是软著流程如何实现智能闭环，另一条是如何从交付过程中提炼出组织可复用的方法论。
  - 关键词 / 流程闭环 / 智能体方法 / 可复制能力

#### Slide 02 - 传统模式的效率与管理挑战

- **Layout**: Asymmetric split (3:7 / 2:8)
- **Title**: 传统模式的效率与管理挑战
- **Core message**: 传统软著制作的真正问题，不是单点工作量，而是链路长、协同散、质量控制依赖个人经验。
- **Visualization**: vertical_list
- **Content**:
  - 前期需求理解依赖人工沟通，容易出现多轮确认和方向偏差。
  - 中间环节分散在规划、开发、截图、文档、打包等多个动作中，协同成本高。
  - 质量把控更多依赖个人经验，过程不透明，结果难追溯。
  - 每做一个项目都像重新搭一次班子，难以形成稳定复制机制。

#### Slide 03 - 软著生产的智能闭环流程

- **Layout**: Top-bottom split
- **Title**: 软著生产的智能闭环流程
- **Core message**: 我们把原来分散的人工作业，重构为“AI 提效、人工把关、系统留痕”的端到端闭环流程。
- **Visualization**: chevron_process
- **Content**:
  - 输入软件名称、类型和描述后，系统先自动生成结构化规划，再进入人工审核确认。
  - 规划确认后自动生成项目并启动 Demo，由人工完成可视化验收，确保结果符合预期。
  - 审核通过后，系统继续自动完成截图、文档、合规检查和打包交付，形成完整闭环。

### Part 2: 管理价值与方法论

#### Slide 04 - 从单次交付走向流程化生产

- **Layout**: Matrix grid (2x2)
- **Title**: 从单次交付走向流程化生产
- **Core message**: 这套机制带来的核心变化，是把一次次分散交付升级成一条可管理、可复用的生产机制。
- **Visualization**: kpi_cards
- **Content**:
  - 标准化：把原来离散的动作串联成统一流程，减少协同摩擦。
  - 可控性：把关键质量控制点前置到规划确认和 Demo 审核两个关口。
  - 效率提升：规划、生成、截图、文档与打包的大量环节实现自动化。
  - 可复制：换一个软件主题，依然能够复用同一套流程和机制。

#### Slide 05 - 智能体落地的四步方法

- **Layout**: Single column centered
- **Title**: 智能体落地的四步方法
- **Core message**: 智能体真正可落地，不是让 AI 直接做完，而是让 AI 按照方法参与组织工作。
- **Visualization**: numbered_steps
- **Content**:
  - 第一步，结构化输入：先把需求边界说清楚，降低理解偏差。
  - 第二步，规划先行：先生成规划并审核，再进入执行，保证方向受控。
  - 第三步，分阶段推进：规划、生成、验证、审查、交付逐段推进。
  - 第四步，人机协同闭环：AI 负责提效，人工负责判断与最终确认。

#### Slide 06 - 可复制的智能体建设原则

- **Layout**: Negative-space-driven
- **Title**: 可复制的智能体建设原则
- **Core message**: 智能体建设的重点，不是追求全自动替代，而是构建一套可控自动化体系。
- **Visualization**: labeled_card
- **Content**:
  - 原则一：先规划、后执行，避免一开始就直接产出结果。
  - 原则二：关键节点必须可审核、可回退、可修正。
  - 原则三：全过程必须留痕，保证每一步都能追踪和复盘。
  - 原则四：真正有价值的不是做成一次，而是沉淀长期可复制能力。

---

## X. Speaker Notes Requirements

One speaker note file per page, saved to `notes/`:

- **Filename**: match SVG name (e.g., `01_项目背景与汇报目标.md`)
- **Content**: 面向领导的自然口播稿，每页 2-4 句，结论先行、语言克制

---

## XI. Technical Constraints Reminder

### SVG Generation Must Follow:

1. viewBox: `0 0 1280 720`
2. Background uses `<rect>` elements
3. Text wrapping uses `<tspan>` (`<foreignObject>` FORBIDDEN)
4. Transparency uses `fill-opacity` / `stroke-opacity`; `rgba()` FORBIDDEN
5. FORBIDDEN: `mask`, `<style>`, `class`, `foreignObject`
6. FORBIDDEN: `textPath`, `animate*`, `script`
7. Text characters: write typography and symbols as raw Unicode; XML reserved chars must be escaped
8. `marker-start` / `marker-end` only when compliant with shared standards
9. `clipPath` allowed only on `<image>` elements

### PPT Compatibility Rules:

- `<g opacity="...">` FORBIDDEN
- Image transparency uses overlay mask layer
- Inline styles only; external CSS and `@font-face` FORBIDDEN
