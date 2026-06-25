## canvas
- viewBox: 0 0 1280 720
- format: PPT 16:9

## colors
- bg: #F7F9FC
- secondary_bg: #FFFFFF
- primary: #0B3A82
- accent: #18A0A6
- secondary_accent: #7C8FB3
- text: #1F2A44
- text_secondary: #5B6780
- text_tertiary: #8A96AA
- border: #D9E1EC
- success: #1F9D55
- warning: #D94F4F

## typography
- font_family: "Microsoft YaHei", Arial, sans-serif
- title_family: Georgia, "Microsoft YaHei", serif
- body_family: "Microsoft YaHei", Arial, sans-serif
- emphasis_family: Georgia, SimSun, serif
- code_family: Consolas, "Courier New", monospace
- body: 22
- title: 36
- subtitle: 26
- annotation: 15
- cover_title: 70
- hero_number: 44

## icons
- library: chunk-filled
- inventory: target, bolt, users, shield, chart-bar, lightbulb

## page_rhythm
- P01: anchor
- P02: dense
- P03: anchor
- P04: dense
- P05: anchor
- P06: breathing

## page_charts
- P02: vertical_list
- P03: chevron_process
- P04: kpi_cards
- P05: numbered_steps
- P06: labeled_card

## forbidden
- Mixing icon libraries
- rgba()
- `<style>`, `class`, `<foreignObject>`, `textPath`, `@font-face`, `<animate*>`, `<script>`, `<iframe>`, `<symbol>`+`<use>`
- `<g opacity>` (set opacity on each child element individually)
- HTML named entities in text (`&nbsp;`, `&mdash;`, `&copy;`, `&ndash;`, `&reg;`, `&hellip;`, `&bull;`)
