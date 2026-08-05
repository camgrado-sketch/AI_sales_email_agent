# 项目任务拆解 (TASK.md)

本轮重构核心：将每封邮件的 LLM 生成改为本地模板变量替换；LLM 仅用于模板导入时的结构识别；CLI 设置命令聚合并新增发送者信息编辑。

## 阶段零：架构与任务文档
**目标**：先更新 `docs/architecture.md` 与 `tasks/TASK.md`，作为本轮重构的基准。

| 任务 ID | 任务描述 | 验收标准 |
| :--- | :--- | :--- |
| TASK-0.1 | 重写 `docs/architecture.md`，反映本地变量替换、LLM 模板结构化、Playwright 预览、设置子菜单、归档保留。 | 文档结构完整，与 PRD 不冲突。 |
| TASK-0.2 | 重写 `tasks/TASK.md`，按模块化阶段拆解任务，每阶段含验收标准。 | 任务可执行，依赖关系清晰。 |

## 阶段一：模板导入 LLM 结构化
**目标**：用户上传模板后，脚本能自动拆解并输出中英双语、带标准占位符的激活模板。

| 任务 ID | 任务描述 | 验收标准 |
| :--- | :--- | :--- |
| TASK-1.1 | 编写 `prompts/template_import_prompt.md`，定义 LLM 输出 schema（subject_template、cn_html、en_html、variables、images、files）。 | Prompt 明确约束：只识别文字主体、图片/文件/链接位置，不上传二进制；忽略页眉页脚注释。 |
| TASK-1.2 | 在 `template_importer.py` 实现 `structure_template_with_llm(markdown, filename)`，调用 `llm_client.complete_json()` 返回结构化 JSON。 | 对 `.md/.docx/.pdf` 均能返回合法结构化 dict。 |
| TASK-1.3 | 实现 `write_structured_template(template_name, structured, source_lang)`，写入 `template.html` + `template_<other>.html` + `config.yaml`。 | 生成的 HTML 只含标准占位符，config.yaml 正确列出 variables/images/files。 |
| TASK-1.4 | 接入现有归档与确认流程；导入后自动标记 `template_confirmed = False` 并打开 Playwright 预览。 | 旧模板被归档，终端可确认/取消确认。 |

## 阶段二：模板引擎与变量规范
**目标**：支持新的变量占位符与文件占位符，渲染完全本地执行。

| 任务 ID | 任务描述 | 验收标准 |
| :--- | :--- | :--- |
| TASK-2.1 | 规范模板变量命名（`SENDER_*`、`CUSTOMER_*`、`CURRENT_DATE`），在 `template_engine.py` 中统一识别。 | 使用大写下划线占位符的模板能被正确替换。 |
| TASK-2.2 | 扩展 `template_engine.render()`，支持 `{{FILE:name}}` 并在 `assets/files/` 中匹配文件，返回 files 列表。 | 渲染结果包含可点击下载链接，files 元数据完整。 |
| TASK-2.3 | 保持 `{{IMAGE:name}}` 现有行为，返回 images 列表用于 SMTP 内联。 | 现有带图模板继续可用。 |
| TASK-2.4 | 缺失变量时不崩溃，保留占位符并打印警告。 | 冒烟测试通过。 |

## 阶段三：发送者信息管理
**目标**：在 CLI 设置子菜单中提供发送者信息编辑。

| 任务 ID | 任务描述 | 验收标准 |
| :--- | :--- | :--- |
| TASK-3.1 | 新增 `email_agent/sender_profile_editor.py`，实现交互式编辑并保存 `templates/sender_profile.md`。 | 能读取现有值，逐项提示，回车保留，保存后 YAML frontmatter 正确。 |
| TASK-3.2 | 在 `config.py` 补充 `FILES_DIR` 与 `SENDER_COMPANY` 默认值路径。 | 常量可用，不影响现有 `load_sender_profile()`。 |

## 阶段四：邮件生成器重构（核心）
**目标**：移除 per-customer LLM，改为本地硬性变量替换。

| 任务 ID | 任务描述 | 验收标准 |
| :--- | :--- | :--- |
| TASK-4.1 | 在 `email_generator.py` 实现 `_build_variables(customer, template_config)`，从 `sender_profile.md` 与 `customers.csv` 映射变量。 | 变量 dict 完整，禁止编造。 |
| TASK-4.2 | 移除 `generate_for_customer()` 中的 LLM 调用，改为直接 `template_engine.render()`。 | 生成过程不调用 LLM；`drafts.json` 中 `rendered_by: local`。 |
| TASK-4.3 | 简化 `email_generator.generate_all()` 中的错误处理与状态保存，保留可中断续跑。 | Ctrl+C 暂停后重新生成可续跑。 |
| TASK-4.4 | 移除或弱化 `skills/` 与 `prompts/email_generation_prompt.md` 在生成流程中的使用。 | 代码不再读取 skill 文件用于 per-customer 生成。 |

## 阶段五：互动分析器简化
**目标**：保留规则判定，移除 LLM 策略调用。

| 任务 ID | 任务描述 | 验收标准 |
| :--- | :--- | :--- |
| TASK-5.1 | 删除 `interaction_analyzer.py` 中的 `_llm_strategy()` 及相关调用。 | `analyze()` 仍返回 stage/template_type/language/strategy/reason，但 strategy 来自规则映射。 |
| TASK-5.2 | 保留 `_rule_based_stage()` 与 `_detect_language()`。 | 历史发送次数与地区判定逻辑正确。 |

## 阶段六：Playwright 浏览器预览
**目标**：降低对系统默认浏览器的依赖，自动跳转显示审核内容。

| 任务 ID | 任务描述 | 验收标准 |
| :--- | :--- | :--- |
| TASK-6.1 | 改造 `preview.py`，统一使用 Playwright Chromium 打开本地临时 HTML。 | 有桌面环境时自动弹出窗口显示草稿/模板/回复。 |
| TASK-6.2 | 实现无桌面环境回退：headless 生成 PNG 截图（`data/latest_preview.png`）并打印文件路径，保留系统浏览器最后兜底。 | WSL/SSH 环境下不崩溃，用户可手动打开。 |
| TASK-6.3 | 在 `requirements.txt` 增加 `playwright`，并在 `README.md`/`CONFIG_GUIDE.md` 补充安装命令。 | `pip install -r requirements.txt && playwright install chromium` 可运行。 |

## 阶段七：CLI 菜单重构
**目标**：第一层菜单瘦身，设置类命令聚合，新增发送者信息编辑入口。

| 任务 ID | 任务描述 | 验收标准 |
| :--- | :--- | :--- |
| TASK-7.1 | 重构 `cli_controller.py` 第一层菜单为 `[1]生成 [2]审核 [3]发送 [4]回复 [5]日志 [6]导入/确认模板 [S]设置 [D]删除 [0]退出`。 | 菜单显示与快捷键正确。 |
| TASK-7.2 | 实现 `[S] 设置` 子菜单：`[1]发送者信息 [2]切换当前模型 [3]切换 skill 模式 [4]配置检查 [0]返回`。 | 子菜单可正常进入/返回。 |
| TASK-7.3 | `[S][1] 发送者信息` 调用 `sender_profile_editor.edit_sender_profile_interactive()`。 | 编辑后 `templates/sender_profile.md` 更新，配置检查中可见。 |
| TASK-7.4 | 原 `menu_config()` / `menu_switch_model()` / `menu_toggle_skill()` 从主菜单移除，仅作为设置子命令保留。 | 原菜单 6/7/9 不再直接显示。 |

## 阶段八：文档与验证
**目标**：更新用户手册与说明文档，完成端到端验证。

| 任务 ID | 任务描述 | 验收标准 |
| :--- | :--- | :--- |
| TASK-8.1 | 更新 `README.md`，重写用户使用手册：新工作流（模板导入 → 本地生成 → Playwright 预览 → 发送）、安装命令（含 `playwright install chromium`）、设置子菜单说明。 | README 内容与重构后的 CLI 流程一致。 |
| TASK-8.2 | 更新 `docs/CONFIG_GUIDE.md`：补充 Playwright 无桌面环境 PNG 回退、发送者信息编辑、模板变量规范、`{{FILE:name}}` 用法、归档分类说明。 | CONFIG_GUIDE 覆盖新功能与常见问题。 |
| TASK-8.3 | 按提交记录更新 `CHANGELOG.md`，记录每次模块变更。 | CHANGELOG 与 git log 对应。 |
| TASK-8.4 | 端到端验证：导入模板 → 确认 → 生成 → 审核（Playwright 预览）→ 发送（白名单测试邮箱）。 | 全流程跑通，无 per-customer LLM 调用。 |

## 依赖关系

```
TASK-0 (文档)
  │
  ├── TASK-1 (导入结构化)
  │     │
  ├── TASK-2 (模板引擎)
  │     │
  ├── TASK-3 (发送者编辑)
  │     │
  ├── TASK-5 (互动分析器) ──┐
  │                        │
  ├── TASK-6 (Playwright) ──┤
  │                        ▼
  └── TASK-4 (生成器重构) ← 依赖 TASK-1/2/3/5
                              │
                              ▼
                         TASK-7 (CLI 重构) ← 依赖 TASK-3/4/6
                              │
                              ▼
                         TASK-8 (文档与验证) ← 依赖 TASK-1~7
```

## 提交规范

每次任务完成后按 `CLAUDE.md` 要求做一次原子化提交：

```
[Claude] feat(模块): 描述
```

例如：
- `[Claude] feat(template): LLM 结构化导入模板`
- `[Claude] feat(engine): 支持 {{FILE:name}} 与本地变量替换`
- `[Claude] feat(cli): 设置子菜单与发送者信息编辑`
- `[Claude] docs: 更新 README 与 CONFIG_GUIDE`
