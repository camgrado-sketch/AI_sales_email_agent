# CHANGELOG

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
