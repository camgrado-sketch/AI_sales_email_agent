# CHANGELOG

## 2026-08-05

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
