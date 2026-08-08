# CHANGELOG

## 2026-08-08

### 修复：图片附件 MIME 探测加固（ICC 配置 JPEG 导致发送崩溃）

- **修改文件**：`email_agent/sender.py`、`tests/test_sender_image_mime.py`（新增）
- **问题定位**：发送含图邮件时 `MIMEImage(img_data)` 抛 `TypeError: Could not guess image MIME subtype` 且进程崩溃。根因：`MIMEImage` 依赖标准库 `imghdr.what()`，其 `test_jpeg` 仅识别 JFIF/Exif APP 标记与 `\xff\xd8\xff\xdb` 裸 DQT 开头；本项目 docx 提取图片为**内嵌 ICC 色彩配置的 JPEG**（APP2/`0xFFE2` 开头），两条判定全部落空。已用真实素材 `assets/images/信01_img_*.jpg` 复现（`imghdr` 返回 `None`）。另发现：崩溃点在 `send_email` 的 try/except 之外，失败不落 `email_logs.csv` 且中断整个发送队列。
- **核心逻辑**：
  - 新增 `sender.guess_image_subtype(img_data, path)`：魔数优先（JPEG 按 `\xff\xd8\xff` SOI 通配判定，不限 APP 标记；另覆盖 PNG/GIF/WebP/BMP/TIFF/ICO/SVG），扩展名兜底，均失败则抛出指明具体文件与开头字节的中文 `ValueError`；彻底移除对已弃用（Python 3.13 将移除）的 `imghdr` 的隐式依赖；
  - `_attach_images()` 改为 `MIMEImage(img_data, _subtype=guess结果)`，CID/inline 逻辑不变；
  - `send_email()` 将 `create_email_message()` 纳入独立 try/except：构建失败 → 记 failed 日志（含"邮件构建失败"与具体原因）、跳过该封、队列继续。
- **潜在风险**：
  - 扩展名兜底在"魔数未知 + 扩展名已知"时信任扩展名（改名文件可能发出错误 Content-Type，属低概率运维风险）；
  - SVG 探测仅按 XML/`<svg` 头部粗判，主流邮件客户端对 SVG 渲染支持有限，建议素材仍用位图；
  - `send_email()` 失败路径新增一种 error_msg 前缀（"邮件构建失败："），依赖日志文本匹配的下游需注意（当前无此类消费方）。
- **验证**：pytest 104/104（新增 14 例：ICC-JPEG 根因回归、常见格式探测、扩展名兜底、未知格式中文异常、端到端 CID 附件、构建失败隔离）；flake8 硬门禁（E9,F63,F7,F82）零命中；sender.py 风格告警与 develop 基线持平（11）。
- **留档（方案 3，本次未实施）**：引入 Pillow 做 `Image.open()` 识别与自动转码（SVG/HEIC/CMYK → RGB PNG 后再附件），并作为 G.4 Web UI 用户上传校验管线的基础；代价为新增重量级二进制依赖，留待 TASK-G.4 预研时在 `docs/architecture.md` 一并评估。
- **下一步建议**：合并本 PR 后，重新发送 `信01` 草稿验证真实邮件渲染；随后进入 TASK-G.4（Web UI 预研）。

## 2026-08-07

### TASK-G.3：docx 图片提取与清理机制加固

- **修改文件**：`email_agent/template_importer.py`、`prompts/template_import_prompt.md`、`tests/test_stage_g.py`
- **核心逻辑**：
  - **提取加固（`_docx_to_markdown`）**：
    - drawing 查找由"仅直接子元素"改为后代搜索，兼容 Word 2010+ 用 `mc:AlternateContent` 包裹图片的嵌入方式（此前该类文档的图片被整条跳过，即"部分 Word 版本取不到图"的主因）；run 内无现代 drawing 时才回退解析旧版 VML（`w:pict`/`v:imagedata`），避免 Choice/Fallback 双份引用造成重复提取；
    - blip 改为遍历 drawing 下全部（组合图形含多个），并同时支持 `r:embed` 与 `r:link` 两种引用；`related_parts.get()` 失败时增加 rels 表兜底解析；
    - 新增包级兜底扫描：遍历文档包全部图片部件，表格、文本框、页眉页脚等 `doc.paragraphs` 之外的图片不再静默丢失（追加占位符至模板末尾并打印中文警告；`/docProps/` 缩略图不属于正文内容，明确排除）；
  - **图片丢失 Bug 修复（`_cleanup_template_images`）**：新增 `_images_used_by_active_drafts()`，收集"待审核"（`review_status=pending`）与"待发送"（`approved` 且无成功发送记录）草稿引用的图片文件名；重新导入模板清理旧图片时，被引用的图片禁止删除并打印保留提示，其余正常清理；
  - **prompt 强化（`template_import_prompt.md`）**：新增"占位符位置锁定（强制）"规则与对应禁止事项——`{{IMAGE:...}}`/`{{FILE:...}}` 占位符数量不得增减、相对位置不得移动、禁止合并拆分改名，双语版本与 `images`/`files` 列表必须逐一对应，返回前逐个自检。
- **潜在风险**：
  - 兜底扫描会把页眉/页脚中的图片（如公司 Logo）也提取并追加到 Markdown 末尾，属"宁多勿漏"的设计取舍，终端有明确警告；
  - 兜底提取的图片占位符位于 Markdown 末尾而非原文位置，依赖 LLM 按 prompt 约束保留；
  - 图片保护按草稿 `template` 字段过滤，历史草稿若缺失该字段则视为可能匹配而保留其图片（保守策略）。
- **验证**：pytest 98/98 全绿（新增 8 个 G.3 测试：inline 提取、AlternateContent 包裹回归、表格图片兜底、真实素材 `开发信带图版.docx` 端到端、清理保护 4 例）；flake8 硬门禁（E9,F63,F7,F82）零命中；两文件风格告警数与 develop 基线持平（54/18）。
- **下一步建议**：TASK-G.3 合入后进入 TASK-G.4（Web UI 预研，仅架构文档）。

### TASK-G.2：双语模板分离预览与确认

- **修改文件**：`email_agent/template_importer.py`、`email_agent/preview.py`、`email_agent/cli_controller.py`、`tests/test_stage_g.py`
- **核心逻辑**：
  - **双语分离预览**：新增 `template_importer.resolve_template_preview_files()`，按「中文在前、英文在后」解析各语言预览文件，解析规则与 `template_engine.render()` 一致（优先 `template_<lang>.html`，缺失时回退 `template.html`——即源语言文件）；`preview.open_template_preview()` 改为依次打开每个语言版本的独立预览窗口并显示进度（如"正在打开中文版模板预览（1/2）"），返回打开的文件路径列表；`build_preview_html()` 新增 `language` 参数，预览页标题/横幅标注语言；
  - **缺失/空文件明确提示**：语言变体文件缺失时提示"缺少 template_<lang>.html，将显示默认 template.html"；变体文件存在但内容为空（LLM 生成缺失的后果）时警告并回退默认模板；完全无可用文件时跳过该语言预览并警告，不再静默打开空窗口；
  - **"language 生成失败"容错**：`structure_template_with_llm()` 对 LLM 返回做三层防护——缺少 `content` 字段、JSON 解析失败（原报 `Expecting value: line 1 column 1`）、返回非对象，均抛出可理解的中文错误并建议重试/切换模型；字段命名不符（如 `chinese_html`/`zh_html`/`html_cn`）自动归一化为 `cn_html`/`en_html` 并提示；任一语言 HTML 为空时打印明确中文警告；
  - **写盘防护**：`write_structured_template()` 源语言 HTML 为空时抛出 `ValueError`（禁止写出空 `template.html`）；目标语言为空时不再写空文件，`other_path` 返回 `None` 并警告，CLI 导入结果展示相应改为"未生成（见上方警告）"；
  - **元数据**：`config.yaml` 新增持久化 `source_language` 字段，供后续预览与诊断使用。
- **潜在风险**：
  - `open_template_preview()` 返回类型由单个路径字符串变为路径列表（现网唯一调用方 `_confirm_template_flow` 已同步更新；测试桩返回字符串不受影响）；
  - 旧模板（手写、仅含 `template.html`）确认时只打开一个预览窗口并提示缺少变体文件，属预期行为；
  - `config.yaml` 新增字段为纯增量，现有读取方均用 `.get()`，无兼容性问题。
- **下一步建议**：进入 TASK-G.3（docx 图片提取机制加固）。

## 2026-08-06

### TASK-G.1：终端 UI 与文案净化

- **修改文件**：`email_agent/cli_controller.py`、`email_agent/preview.py`、`tests/test_stage_g.py`（新增）
- **核心逻辑**：
  - **清屏机制**：所有 `menu_*` 菜单入口及设置/模板两个子菜单循环的每轮迭代起始处调用 `_clear_screen()`，保证每次进入新菜单时界面清爽；`_clear_screen()` 增加 `sys.stdout.isatty()` 守卫，非交互环境（测试/管道/重定向）自动跳过，不产生清屏转义与 TERM 噪音；
  - **Playwright 报错净化**：`preview._open_with_playwright()` 捕获启动异常后不再打印原始英文异常栈，headed 失败输出"未检测到本地浏览器环境，将尝试截图或手动查看"，headless 失败输出含 `playwright install chromium` 指引的一句中文提示，后续降级逻辑不变；
  - **文案统一**：模板确认/选择流程中"设为生效模板"统一为"设为当前生效模板"；经全仓 grep 确认"强制生效""覆盖自动阶段"等旧概念文案在当前代码中已无残留（早先的阶段 A 提交已移除，人工测试记录中为旧版行为）。
- **潜在风险**：
  - 清屏依赖 `clear`/`cls` 系统命令，极端精简容器环境可能无效但不影响功能；
  - Playwright 失败提示不再包含异常细节，深度排障需手动运行 `playwright install chromium` 或查看日志。
- **下一步建议**：进入 TASK-G.2（双语模板分离预览与确认）。

### 修复 test_stage_d 英文日期断言跨日失败

- **修改文件**：`tests/test_stage_d.py`
- **核心逻辑**：
  - `test_english_date_has_no_leading_zero` 原断言硬编码编写当日日期（`"August 6, 2026"`），跨日即失败（2026-08-07 基线跑出 1 failed/74 passed）；
  - 改为按 `email_generator._current_date()` 的英文格式（`f"{now.strftime('%B')} {now.day}, {now.year}"`）动态计算期望值；仅当 `now.day < 10` 时校验无前导零形式，保持原测试意图不变。
- **潜在风险**：无（测试断言与被测代码使用同一格式逻辑，若未来 `_current_date` 英文格式变更，测试将同步暴露）。
- **下一步建议**：合入后 develop 基线恢复 75/75 全绿，可进入阶段 G.1。

### TASK-R2：README 补充模板导入依赖说明

- **修改文件**：`README.md`
- **核心逻辑**：
  - 在「前期环境及权限部署准备 → 1. 基础环境」章节补充说明：模板导入功能依赖 `python-docx`（Word 解析）与 `pdfplumber`（PDF 提取），两者已包含在 `requirements.txt`，随 `pip install -r requirements.txt` 一并安装；旧环境可单独补装 `pip install python-docx pdfplumber`；
  - 收尾 2026-08-06 复合性审查报告（`docs/bug_report.md` 历史版本 98921b3）遗留的 Minor 项②。安装主命令不变。
- **潜在风险**：无（纯文档变更）。
- **下一步建议**：等待 R1/R2 两个 PR 合入 develop 后，进入阶段 G.1（终端 UI 与文案净化）。

### TASK-R1：修正 .gitignore 并归档人工测试记录

- **修改文件**：`.gitignore`、`templates/email/.gitkeep`（新增）、`docs/manual_test_record.md`（由 `tests/人工测试_test.md` 移动归档）
- **核心逻辑**：
  - 删除 `.gitignore` 中的 `tests` 忽略规则——本分支已跟踪 11 个测试文件，该规则会静默吞掉未来新增的测试文件，造成测试套件缺口；
  - 保留 `.claude` 忽略项（本地工具状态，不入库）；
  - 新增 `templates/email/*` + `!templates/email/.gitkeep`：模板导入器的运行时产物不入库（镜像既有 `templates/archive/` 模式），本地 `templates/email/开发信测试/` 保留作为阶段 G.2/G.3 的缺陷复现素材；
  - 将未跟踪的手工测试记录 `tests/人工测试_test.md` 移入 `docs/manual_test_record.md` 归档，避免与自动化测试目录混淆。
- **潜在风险**：
  - `templates/email/` 被整体忽略，若未来有需入库的预置邮件模板，需用 `git add -f` 或调整规则；
  - 人工测试记录移入 `docs/` 后，原路径引用（如有）需更新。
- **下一步建议**：继续 TASK-R2（README 补充 python-docx/pdfplumber 依赖说明），随后进入阶段 G 修复。

### 阶段 E：邮件主题非空兜底与导入后用户编辑

- **修改文件**：`email_agent/template_importer.py`、`email_agent/cli_controller.py`、`prompts/template_import_prompt.md`、`tests/test_stage_e.py`
- **核心逻辑**：
  - 模板导入 prompt 新增邮件主题强制规则：`subject_template` 禁止为空，无标题时按正文首段/首句自动生成 ≤60 字符主题；
  - `template_importer.activate_template()` 对 LLM 返回的空 `subject_template` 自动按 Markdown 首标题/首行兜底，打印黄色警告；
  - `cli_controller._import_template_flow()` 导入成功后以 ANSI 加粗青色高亮当前主题，支持 `[Enter]` 接受或直接输入新主题回写 `config.yaml`；
- **潜在风险**：
  - 自动兜底主题依赖 Markdown 结构，若原文既无标题也无正文将回退到固定英文默认主题；
  - 用户编辑主题时只更新 `config.yaml`，不会同步修改已生成草稿的主题（已生成草稿保留旧主题）。
- **下一步建议**：进入阶段 C（DOCX 图片提取与发送前缺失图片预检）或阶段 F（Playwright GUI 检测），请确认优先执行哪一项。

### 阶段 E 优化（同步 main 文档后）

- **修改文件**：`email_agent/email_generator.py`、`email_agent/template_importer.py`、`prompts/template_import_prompt.md`、`tests/test_stage_e.py`
- **核心逻辑**：
  - 按 PRD §3.4 与 TASK-E.1 细化 prompt：明确主题来源（有标题提取/无标题自动生成）、可选变量（`CUSTOMER_COMPANY`、`CUSTOMER_FIRST_NAME`、`CUSTOMER_INDUSTRY`、`SENDER_MARKET_REGION`）、自然融入原则、禁止生硬拼接、长度约束（英文 ≤10 词/中文 ≤20 字）；
  - `email_generator._render_subject()` 支持缺失变量替换为空并收集，与正文使用同一变量字典，确保最终 `subject` 不含未解析 `{{...}}`；
  - `template_importer.activate_template()` 在英文模板主题中检测到汉字时追加语言纯净度警告；
- **潜在风险**：
  - 长度/自然度规则依赖 LLM 遵循，导入侧只做兜底和空值警告，无法 100% 拦截不符合要求的主题；
  - 英文主题汉字警告仅针对 source_lang == "en" 的模板，中文模板不强制检测英文混入。
- **下一步建议**：进入阶段 C 或阶段 F，请确认优先执行哪一项。

### 阶段 C：图片/附件自动提取、CID 内联与发送前预检

- **修改文件**：`email_agent/template_importer.py`、`email_agent/sender.py`、`tests/test_stage_c.py`
- **核心逻辑**：
  - `_docx_to_markdown()` 遍历 DOCX 段落 run，识别 `w:drawing` 内联图片，按 `<template_name>_img_NN.<ext>` 保存到 `assets/images/`，并在 Markdown 对应位置插入 `{{IMAGE:<name>}}`；
  - `extract_to_markdown()` 新增 `template_name` 参数并透传；`activate_template()` 导入前先清理该模板旧图，避免序号与文件残留；
  - `sender.create_email_message()` 以 `MIMEImage` + `Content-ID` + `Content-Disposition: inline` 方式附加图片，实现正文 CID 内联显示；
  - 新增 `sender.check_draft_images()`，`process_queue()` 发送循环前检查图片路径，缺失时黄色清单警告并 `(y/N)` 询问是否继续；
- **潜在风险**：
  - 当前仅处理 DOCX 正文段落内联图，未覆盖表格、页眉页脚、VML 旧格式图片；PDF 图片提取也未实现；
  - 缺失图片继续发送后，邮件客户端会在原位置显示空白或红叉。
- **下一步建议**：进入阶段 F（Playwright GUI 检测与醒目截图路径），确认后继续。

### 阶段 F：Playwright 预览环境检测与无 GUI 截图路径高亮

- **修改文件**：`email_agent/preview.py`、`tests/test_stage_f.py`
- **核心逻辑**：
  - 新增 `preview._has_gui()`：macOS/Windows 默认有 GUI；Linux 需 `DISPLAY` 环境变量且非 WSL；WSL 一律视为无 GUI。
  - `_open_html()` 入口处根据 `_has_gui()` 直接选择模式：有 GUI 先试 `headless=False`，失败再回退 `headless=True`；无 GUI 直接走 `headless=True` 截图，避免无效的 headed 尝试与延迟。
  - 无 GUI 截图路径使用 ANSI 加粗黄色高亮输出，防止用户错过。
- **潜在风险**：
  - 在 WSLg 等带 DISPLAY 的 WSL 环境会被强制视为无 GUI，需手动打开截图；如需支持 WSLg，可后续放宽 `_is_wsl()` 判断。
  - -headed 失败回退截图时，终端已输出失败警告，可能让用户误以为预览出错。
- **下一步建议**：进入 Step 4 全量测试 + 手动验收 + CHANGELOG 归档 + PR #2。

## 2026-08-05

### Bug Report 修复（feature/local-template-replace 黑盒测试）

- **修改文件**：`email_agent/cli_controller.py`、`email_agent/config.py`、`email_agent/email_generator.py`、`email_agent/interaction_analyzer.py`、`templates/email/initial_contact/config.yaml`、`templates/email/follow_up/config.yaml`、`templates/email/final_note/config.yaml`、`CLAUDE.md`
- **核心逻辑**：
  - 在设置菜单新增 `[5] 选择生效模板`，将 `selected_template` 持久化到 `data/settings.json`；生成草稿时优先使用用户选择的模板，未选择时仍按销售阶段自动匹配；
  - 重构模板确认流程：多模板场景下列出可选模板，支持确认单个模板并一键设为生效模板，避免只能全局确认所有模板；
  - 修复变量命名空间不一致：`email_generator._build_variables()` 增加别名映射（`COMPANY_NAME` → `CUSTOMER_COMPANY`、`MARKET_REGION` → `SENDER_MARKET_REGION` 等），兼容外部导入模板中的非标准占位符；
  - 修复语言判定漏洞：`interaction_analyzer._detect_language()` 增加拼音城市名支持（Shanghai、Beijing、Guangzhou 等）；移除 `email_generator._build_variables()` 中 `CURRENT_DATE` 初始硬编码中文的隐患；
  - 补充 `subject_template`：为 `initial_contact`、`follow_up`、`final_note` 三个旧模板写入默认主题模板；`email_generator._render_subject()` 增加空主题兜底，避免草稿无主题；
  - 更新 `CLAUDE.md`，补充全局指令引用、仓库级架构、常用命令，并重点明确 `main` 与 `feature/local-template-replace` 分支分工及独立分支开发规范。
- **潜在风险**：
  - `selected_template` 会覆盖阶段自动匹配，用户忘记恢复自动选择时所有客户都使用同一模板；
  - 变量别名目前覆盖最常见的非标准占位符，若外部模板使用其他命名，可能仍需扩展别名表；
  - 模板确认流程改为单模板确认后，批量导入多个模板时需要逐条确认。
- **下一步建议**：在本地交互式终端运行 `source .venv/bin/activate && python main.py`，依次验证菜单 `S` → `5` 选择模板、菜单 `6` 确认单个模板并设为生效、菜单 `1` 生成草稿主题与语言正确。

### TASK-9: 端到端验证

- **修改文件**：无代码修改，仅验证
- **核心逻辑**：
  - `python3 -m py_compile main.py email_agent/*.py scripts/*.py` 全量语法检查通过；
  - `python3 main.py --init` 初始化成功；
  - 模块冒烟测试通过：加载 sender_profile、customers、template 列表、template_engine.render() 本地替换、interaction_analyzer.analyze() 规则判定；
  - `email_generator.generate_all()` 在无 LLM 调用情况下生成 3 封草稿，`rendered_by: "local"`；
  - `preview.open_draft_preview()` 成功处理预览（ headed 或系统浏览器回退）；
  - 测试草稿与生成状态已清理，未污染用户数据。
- **潜在风险**：
  - 完整交互流程（菜单 6 导入 → 确认 → 菜单 1 生成 → 菜单 2 审核 → 菜单 3 发送）需在真实交互式终端中由用户运行，当前后台会话无法执行 `input()` 菜单；
  - 发送真实邮件前请确认 `ALLOWED_TEST_EMAILS` 已包含测试收件箱。
- **下一步建议**：在本地交互式终端运行 `source .venv/bin/activate && python main.py`，依次执行菜单 6 → 1 → 2 → 3 完成全流程验证。

### TASK-8: 文档更新

- **修改文件**：`README.md`、`docs/CONFIG_GUIDE.md`
- **核心逻辑**：
  - 重写 `README.md`：反映本地模板变量替换新工作流、LLM 仅用于模板结构化、Playwright 预览、设置子菜单、发送者信息编辑、`{{FILE:name}}` 占位符与归档分类保留；
  - 重写 `docs/CONFIG_GUIDE.md`：更新菜单速查、`.env` 变量说明、模板变量规范、文件下载占位说明、Playwright 安装与回退行为、发送者信息管理、删除过时的 `generation_meta` 章节、补充文件链接仅本地占位等 FAQ。
- **潜在风险**：
  - 旧文档中的菜单编号（6/7/8/9）已变更，用户需要适应新布局；
  - 文件下载占位 `{{FILE:name}}` 默认 `file://` 链接对收件人不可访问，文档已明确说明。
- **下一步建议**：进行 TASK-9 端到端验证（导入 → 确认 → 生成 → 审核 → 发送白名单测试邮箱）。

### TASK-7: CLI 菜单重构

- **修改文件**：`email_agent/cli_controller.py`
- **核心逻辑**：
  - 第一层菜单重构为 `[1]生成 [2]审核 [3]发送 [4]回复 [5]日志 [6]导入/确认模板 [S]设置 [D]删除 [0]退出`；
  - 新增 `[S] 设置` 子菜单：`[1]发送者信息 [2]切换当前模型 [3]切换 skill 模式 [4]配置检查 [0]返回`；
  - 配置检查增加发送者公司、邮箱、电话字段与文件目录显示；
  - 导入流程移除不再需要的源模板选择（ headed by the new LLM-only importer），简化交互；
  - 模板确认预览改为调用 `preview.open_template_preview()`。
- **潜在风险**：
  - 用户习惯于旧菜单编号（7/8/9）需要适应新布局；
  - 导入流程不再支持基于旧模板合并样式，由 LLM 直接生成完整 HTML。
- **下一步建议**：更新 README.md、CONFIG_GUIDE.md 等用户文档。

### TASK-6: Playwright 浏览器预览

- **修改文件**：`email_agent/preview.py`、`requirements.txt`
- **核心逻辑**：
  - `preview.py` 主路径改为使用 Playwright Chromium（headed）打开本地临时 HTML；
  - 无桌面环境时自动回退到 headless PNG 截图（`data/latest_preview.png`）；
  - 再失败则回退到系统浏览器 / `webbrowser` / WSL 专用命令；
  - 新增 `open_template_preview(template_name)` 用于模板确认预览；
  - `requirements.txt` 增加 `playwright` 依赖。
- **潜在风险**：
  - 首次运行需要执行 `playwright install chromium` 下载浏览器二进制；
  - headed 模式在有 GUI 环境下会阻塞终端等待用户关闭浏览器或按 Enter，这是预期行为。
- **下一步建议**：重构 `cli_controller.py`，实现设置子菜单与发送者信息入口。

### TASK-5: 互动分析器简化

- **修改文件**：`email_agent/interaction_analyzer.py`
- **核心逻辑**：
  - 删除 `_llm_strategy()` 及 `llm_client` 导入，不再调用远程 LLM；
  - `analyze()` 仅基于 `_rule_based_stage()` 与 `_detect_language()` 返回 stage、template_type、language、strategy；
  - strategy 改为本地规则映射，保持与原有 LLM 策略语义一致。
- **潜在风险**：
  - 对客户阶段/策略的判定不再有个性化 LLM 推理，但规则逻辑与之前一致，不影响生成流程；
  - 若未来需要 LLM 增强策略，可在本模块重新注入，不影响其他模块。
- **下一步建议**：改造 `preview.py`，接入 Playwright Chromium 预览。

### TASK-4: 邮件生成器重构（核心）

- **修改文件**：`email_agent/email_generator.py`、`email_agent/template_importer.py`
- **核心逻辑**：
  - 移除 `email_generator.py` 中的 per-customer LLM 调用；
  - 新增 `_build_variables()`，从 `templates/sender_profile.md` 与 `data/customers.csv` 硬性映射大写变量；
  - 新增 `_render_subject()`，根据 `config.yaml` 中的 `subject_template` 本地渲染主题；
  - 草稿字段新增 `files`、`rendered_by: "local"`，移除 `model_used` 与 `generation_meta`；
  - `template_importer.py` 生成的 `config.yaml` 中增加 `subject_template` 字段。
- **潜在风险**：
  - 旧草稿中的 `model_used`/`generation_meta` 字段不再生成，但读取旧数据不会崩溃；
  - 若 `config.yaml` 缺少 `subject_template`，主题行为空，需重新导入模板。
- **下一步建议**：简化 `interaction_analyzer.py`，移除 `_llm_strategy()`。

### TASK-3: 发送者信息管理

- **修改文件**：`email_agent/sender_profile_editor.py`、`email_agent/config.py`
- **核心逻辑**：
  - 新增 `email_agent/sender_profile_editor.py`，提供 `edit_sender_profile_interactive()` 交互式编辑发送者信息；
  - 读取现有 `templates/sender_profile.md`，逐项提示，回车保留原值，保存为 YAML frontmatter；
  - `config.py` 新增 `SENDER_COMPANY` 默认值，并纳入 `load_sender_profile()` 返回字典。
- **潜在风险**：
  - 若 `templates/sender_profile.md` 已存在但 frontmatter 格式异常，会回退到 `.env` 默认值；
  - 编辑后仅刷新内存中的 `config.*` 值，不影响已生成的草稿。
- **下一步建议**：重构 `email_generator.py`，移除 per-customer LLM，改为本地变量替换。

### TASK-2: 模板引擎扩展

- **修改文件**：`email_agent/template_engine.py`、`email_agent/config.py`
- **核心逻辑**：
  - `template_engine.render()` 现在返回三元组 `(html_body, images, files)`；
  - 新增 `{{FILE:name}}` 占位符支持，在 `assets/files/` 中匹配文件并渲染为本地 `file://` 下载链接；
  - 变量 dict 键统一归一化为大写，占位符匹配改为大写下划线风格（`{{SENDER_NAME}}`、`{{CUSTOMER_FIRST_NAME}}` 等）；
  - `config.py` 新增 `FILES_DIR` 路径常量。
- **潜在风险**：
  - 旧模板中的小写占位符（如 `{{sender_name}}`）将不会被替换，需要通过导入流程重新生成模板；
  - `file://` 链接对邮件收件人不可访问，后续需在 CONFIG_GUIDE 中说明应替换为公网 URL 或改用附件。
- **下一步建议**：实现 `email_agent/sender_profile_editor.py` 与发送者信息编辑。

### TASK-1: 模板导入 LLM 结构化

- **修改文件**：`email_agent/template_importer.py`、`email_agent/config.py`、`prompts/template_import_prompt.md`
- **核心逻辑**：
  - 新增 `prompts/template_import_prompt.md`，定义 LLM 结构化模板输出 schema；
  - `template_importer.py` 新增 `structure_template_with_llm()`，调用远程 LLM 将 Markdown 转换为双语 HTML 模板（含 `{{VAR}}`、`{{IMAGE:name}}`、`{{FILE:name}}` 占位符）；
  - 新增 `write_structured_template()`，根据源语言写入 `template.html` 与 `template_<other>.html`，并自动生成 `config.yaml`；
  - `activate_template()` 改为基于 LLM 结构化输出写入激活模板，旧模板仍自动归档；
  - `config.py` 新增 `TEMPLATE_IMPORT_PROMPT_FILE` 路径常量。
- **潜在风险**：
  - 移除了旧的 `merge_markdown_into_template()` 与 `generate_missing_language()` 函数，仅 `template_importer.py` 内部使用，外部无引用；
  - `activate_template()` 的 `source_template_path` 参数暂时保留但不再用于合并 HTML，TASK-7 重构 CLI 时会决定保留或移除对应交互。
- **下一步建议**：扩展 `template_engine.py` 支持 `{{FILE:name}}` 与大写变量占位符。

### TASK-0: 更新 architecture.md 与 TASK.md

- **修改文件**：`docs/architecture.md`、`tasks/TASK.md`、`CHANGELOG.md`
- **核心逻辑**：根据本轮架构重构目标重写设计文档。明确 LLM 仅参与模板结构化、邮件生成改为本地模板变量替换、Playwright 预览兜底、CLI 设置子菜单、发送者信息编辑、归档分类保留等关键决策。
- **潜在风险**：无，仅文档变更。
- **下一步建议**：实现 `prompts/template_import_prompt.md` 与 `template_importer.py` 的 LLM 结构化功能。
