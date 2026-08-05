# CHANGELOG

## 2026-08-05

### TASK-0: 更新 architecture.md 与 TASK.md

- **修改文件**：`docs/architecture.md`、`tasks/TASK.md`
- **核心逻辑**：根据本轮架构重构目标重写设计文档。明确 LLM 仅参与模板结构化、邮件生成改为本地模板变量替换、Playwright 预览兜底、CLI 设置子菜单、发送者信息编辑、归档分类保留等关键决策。
- **潜在风险**：无，仅文档变更。
- **下一步建议**：实现 `prompts/template_import_prompt.md` 与 `template_importer.py` 的 LLM 结构化功能。
