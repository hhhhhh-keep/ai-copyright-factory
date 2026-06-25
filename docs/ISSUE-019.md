# ISSUE-019：界面样式增强仍因远程模型读超时而稳定失败

- 状态：`已修复`
- 优先级：`P0`
- 首次记录：2026-06-18
- 复现任务：`20260618113626-a930d5b2`

## 用户反馈

- 主流程已经正常进入 Demo 审查，但进度区 `界面样式` 节点一直显示 `failed`。
- `status.json` 中 `codegen_fallback_reason=frontend/src/style.css: RuntimeError: Code enhancer API read timed out`。

## 排查结论

- README 文档增强成功，说明模型 Key 和接口整体可用。
- 失败集中在 `style.css`：即使改为追加样式块，MiniMax 对 CSS 生成请求仍容易读超时。
- 样式增强属于可选视觉差异化，不应依赖远程模型长文本输出，也不应影响主流程稳定性。

## 修复内容

- `frontend/src/style.css` 改为本地风格追加生成器，不再请求远程模型。
- 本地生成器根据 `planning.ui_plan`、行业、软件名称、模块 key/name 的稳定哈希选择调色板、纹理、圆角和视觉增强规则。
- 追加块覆盖壳层、导航、Hero、KPI 卡片、驾驶舱图表、表格 hover、按钮和模块页面标识，保留原 CSS，不覆盖完整文件。
- `README.md` 继续保留 LLM 文档增强，并继续受子进程硬超时保护。
- 移除公开配置中的 `AI_CODEGEN_STYLE_TIMEOUT`，避免误以为样式节点仍请求远程模型。

## 验收标准

- 新任务中 `界面样式` 节点应快速 `completed`，不再因 MiniMax 读超时失败。
- `frontend/src/style.css` 应保留原内容，并追加 `AI Code Enhancer: style append` 块。
- 模块页面路由和子菜单功能不受样式增强影响。

## 验证

- `python -m unittest tests.test_enhancer -v`：7 项通过，覆盖 style 本地生成、不请求 App.vue / style.css 远程接口、README 容错和硬超时。
