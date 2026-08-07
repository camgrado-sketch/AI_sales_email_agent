# 项目任务拆解 (TASK.md)

---

## 历史任务（已完成）

以下为 `feature/local-template-replace` 和 `feature/task-stage-a-f` 分支已完成的开发工作，保留作为历史记录。

### 阶段零：架构与任务文档（已完成）
| 任务 ID | 任务描述 | 状态 |
| :--- | :--- | :--- |
| TASK-0.1 | 重写 `docs/architecture.md`，反映本地变量替换架构。 | ✅ 已完成 |
| TASK-0.2 | 重写 `tasks/TASK.md`，按模块化阶段拆解任务。 | ✅ 已完成 |

### 阶段一：模板导入 LLM 结构化（已完成）
| 任务 ID | 任务描述 | 状态 |
| :--- | :--- | :--- |
| TASK-1.1 | 编写 `prompts/template_import_prompt.md`，定义 LLM 输出 schema。 | ✅ 已完成 |
| TASK-1.2 | 实现 `structure_template_with_llm()`，调用 LLM 返回结构化 JSON。 | ✅ 已完成 |
| TASK-1.3 | 实现 `write_structured_template()`，写入双语 HTML + config.yaml。 | ✅ 已完成 |
| TASK-1.4 | 接入归档与确认流程，导入后自动标记 `template_confirmed = False`。 | ✅ 已完成 |

### 阶段二：模板引擎与变量规范（已完成）
| 任务 ID | 任务描述 | 状态 |
| :--- | :--- | :--- |
| TASK-2.1 | 规范模板变量命名（`SENDER_*`、`CUSTOMER_*`），统一大写识别。 | ✅ 已完成 |
| TASK-2.2 | 扩展 `render()`，支持 `{{FILE:name}}` 并返回 files 列表。 | ✅ 已完成 |
| TASK-2.3 | 保持 `{{IMAGE:name}}` 现有行为，返回 images 列表。 | ✅ 已完成 |
| TASK-2.4 | 缺失变量时不崩溃，保留占位符并打印警告。 | ✅ 已完成 |

### 阶段三：发送者信息管理（已完成）
| 任务 ID | 任务描述 | 状态 |
| :--- | :--- | :--- |
| TASK-3.1 | 新增 `sender_profile_editor.py`，实现交互式编辑并保存 `sender_profile.md`。 | ✅ 已完成 |
| TASK-3.2 | 在 `config.py` 补充 `FILES_DIR` 与 `SENDER_COMPANY` 默认值路径。 | ✅ 已完成 |

### 阶段四：邮件生成器重构（已完成）
| 任务 ID | 任务描述 | 状态 |
| :--- | :--- | :--- |
| TASK-4.1 | 实现 `_build_variables()`，从 `sender_profile.md` 与 `customers.csv` 映射变量。 | ✅ 已完成 |
| TASK-4.2 | 移除 `generate_for_customer()` 中的 LLM 调用，改为直接 `template_engine.render()`。 | ✅ 已完成 |
| TASK-4.3 | 简化 `generate_all()` 中的错误处理与状态保存，保留可中断续跑。 | ✅ 已完成 |
| TASK-4.4 | 移除 `skills/` 与 `prompts/email_generation_prompt.md` 在生成流程中的使用。 | ✅ 已完成 |

### 阶段 A-F（已完成）
移除阶段逻辑、修复状态栏、图片自动提取、语言纯净规则、标题生成、浏览器跳转等均已完成，详见 `CHANGELOG.md`。
### 阶段零至阶段 F（已完成）
架构重写、LLM 结构化导入、变量规范、发送者管理、生成器重构、状态栏修复、图片提取、语言纯净规则、标题生成、浏览器跳转等均已完成。

---

## 新增任务（待开发）

以下任务基于人工黑盒测试 Bug Report（`docs/bug_report.md`）制定，修复交互体验、模板双语预览和图片提取失效等问题。
**所有新任务必须严格遵循以下约束规则**：
1. 不得在邮件生成阶段调用 LLM（LLM 唯一调用点为 `template_importer.py`）。
2. 不得破坏已有的发送、接收、日志模块。
3. 每个任务完成后做一次原子化提交，格式：`[Claude] fix(模块): 描述`。

---

### 新阶段 G：体验优化与图片提取加固

**目标**：解决人工测试中发现的界面不友好、预览不完整、图片提取失败等问题。

| 任务 ID | 任务描述 | 验收标准 |
| :--- | :--- | :--- |
| TASK-G.1 | **终端 UI 与文案净化**：在 `cli_controller.py` 各菜单入口加入清屏（clear）操作；在 `preview.py` 捕获 Playwright 缺失异常，屏蔽大段英文栈，输出简短友好的中文提示；清理 `cli_controller.py` 中关于"强制生效模板"、"覆盖自动阶段"等晦涩文案，统一改为"设为当前生效模板"。 | 菜单切换时屏幕清爽；无 Playwright 环境时不打印大段英文错误；终端提示语通俗易懂。 |
| TASK-G.2 | **双语模板分离预览与确认**：重构 `template_importer.py` 和 `preview.py` 的预览逻辑，在确认模板时（`_confirm_template_flow`），必须依次打开 `template_cn.html` 和 `template_en.html` 供用户分别预览；同时排查 `language 生成失败` 的潜在异常，增加容错日志。 | 确认环节能弹出两个预览窗口（中英文各一）；导入生成时不再出现无法理解的 language 报错。 |
| TASK-G.3 | **docx 图片提取机制加固**：优化 `template_importer.py` 的 `_docx_to_markdown` 图片提取逻辑，支持遍历文档所有 shape 和 inline 图片，兼容不同版本的 Word 嵌入方式；同时强化 `template_import_prompt.md`，明确要求 LLM 绝对禁止改变图片和文件占位符的相对位置与数量。 | 导入人工测试使用的含图 `.docx` 后，图片被正确提取到 `assets/images/`，生成的 HTML 中占位符数量和位置与原文档一致。 |
| TASK-G.4 | **可视化编辑器预研（架构评估）**：在 `docs/architecture.md` 中新增章节，评估从纯 CLI 升级为本地 Web UI（如 FastAPI + 简单网页编辑器）的可行性，用于直接修改模板文字和变量内容。 | 仅输出架构设计与可行性分析，不编写业务代码。 |

---

以下任务基于人工黑盒测试反馈，修复交互体验、模板双语预览和图片提取/清理失效等问题。

### 新阶段 G：体验优化与资源加固

**目标**：解决人工测试中发现的界面不友好、预览不完整、图片资源意外丢失等问题。

| 任务 ID | 任务描述 | 验收标准 |
| :--- | :--- | :--- |
| TASK-G.1 | **终端 UI 与文案净化** | 菜单切换清屏，屏蔽 Playwright 英文报错，文案统一为"当前生效模板"。 |
| TASK-G.2 | **双语模板分离预览与确认** | 确认环节依次弹出中英文预览窗口，修复 language 字段解析容错。 |
| TASK-G.3 | **docx 图片提取与清理机制加固** | (1) 优化 `_docx_to_markdown` 提取逻辑，支持所有 Shape/Inline 图片；(2) **修复图片丢失 Bug**：修改 `_cleanup_template_images`，若当前模板存在“待审核”或“待发送”的草稿，禁止清理对应的图片资源。 |
| TASK-G.4 | **可视化编辑器预研（架构评估）** | 在 `docs/architecture.md` 中评估从 CLI 升级为本地 Web UI 的可行性。 |

---

## 提交规范

每次任务完成后做一次原子化提交：
```
[Claude] fix(模块): 描述
```
例如：
- `[Claude] fix(cli): 净化交互文案并增加清屏机制`
- `[Claude] fix(importer): 实现双语模板分离预览与确认`
- `[Claude] fix(importer): 加固 docx 图片提取兼容性`
- `[Claude] fix(importer): 加固图片提取兼容性并修复清理导致的资源丢失`
