# 项目任务拆解 (TASK.md)

---

## 历史任务（已完成）

以下为 `feature/local-template-replace` 分支已完成的开发工作，保留作为历史记录。

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

### 阶段五至八（已完成）
互动分析器简化、Playwright 预览、CLI 菜单重构、文档更新均已完成，详见 `CHANGELOG.md`。

---

## 新增任务（待开发）

以下任务基于黑盒测试 Bug Report（`docs/bug_report.md`）及 PRD v2.0 新增需求制定。
**所有新任务必须严格遵循以下约束规则**：
1. 不得在邮件生成阶段调用 LLM（LLM 唯一调用点为 `template_importer.py`）。
2. 不得破坏已有的发送、接收、日志模块。
3. 每个任务完成后做一次原子化提交，格式：`[Claude] fix(模块): 描述`。

---

### 新阶段 A：移除阶段逻辑，重构模板选择机制
**目标**：取消"初次/跟进/结束"的阶段推荐逻辑，改为用户手动选择生效模板，长期生效。

| 任务 ID | 任务描述 | 验收标准 |
| :--- | :--- | :--- |
| TASK-A.1 | 删除 `interaction_analyzer.py` 中的 `template_type` 推荐逻辑（`new_lead -> initial_contact` 等映射）。保留语言判定，移除模板推荐。 | `analyze()` 不再返回 `template_type`，只返回 `stage`、`language`、`reason`。 |
| TASK-A.2 | 在 `data_store.py` 和 `config.py` 中新增 `selected_template` 字段的读写支持。 | `settings.json` 中可持久化存储 `selected_template`，重启后不丢失。 |
| TASK-A.3 | 在 `cli_controller.py` 的模板管理菜单（菜单 6）中新增 `[A] 选择生效模板` 选项，列出所有激活模板供用户选择。 | 终端显示模板列表（含名称、导入日期、使用状态），用户输入编号后写入 `settings.json`。 |
| TASK-A.4 | 重构 `email_generator.py` 的模板选择逻辑：读取 `selected_template`，若未设置则报错提示用户先选择模板，不再自动降级。 | 生成草稿时，使用的模板与 `settings.json` 中 `selected_template` 完全一致。 |

### 新阶段 B：修复终端状态栏
**目标**：状态栏简洁、信息全面，包含模板状态、发送状态和回复情况。

| 任务 ID | 任务描述 | 验收标准 |
| :--- | :--- | :--- |
| TASK-B.1 | 重构 `status.py`，计算并输出：当前生效模板名+导入日期、确认状态、发送状态（未发送/部分发送剩余N封/已全部发送）、未查看回复数。 | 状态栏在两行内完整显示，格式与 PRD 示例一致。 |
| TASK-B.2 | 确保主菜单每次刷新时重新计算状态（不缓存旧状态）。 | 发送一封邮件后，重新进入主菜单时"剩余数量"立即更新。 |

### 新阶段 C：修复图片/附件自动提取与嵌入
**目标**：模板导入时自动提取图片，无需用户手动操作；发送时图片正确嵌入邮件。

| 任务 ID | 任务描述 | 验收标准 |
| :--- | :--- | :--- |
| TASK-C.1 | 在 `template_importer.py` 的 `_docx_to_markdown()` 中增加图片提取逻辑：遍历 `.docx` 中的内嵌图片，按 `<template_name>_img_01.png` 格式保存至 `assets/images/`，并在 Markdown 中对应位置插入 `{{IMAGE:<name>}}` 占位符。 | 导入含图 `.docx` 后，`assets/images/` 中出现对应图片，Markdown 中有正确占位符。 |
| TASK-C.2 | 在 `sender.py` 中确保 HTML 邮件发送时，`images` 列表中的图片以 CID 内联方式附加（`Content-ID: <cid>`），而非作为普通附件。 | 收件方邮箱中图片在正文位置正常显示，不出现在附件区。 |
| TASK-C.3 | 在发送前检查 `images` 列表中的每个图片路径是否存在，若缺失则在终端警告并询问是否继续发送。 | 图片缺失时不静默发送，给出明确提示。 |

### 新阶段 D：修复变量映射与语言规则
**目标**：解决变量不匹配和语言判定漏洞，强制执行中英文纯净规则。

| 任务 ID | 任务描述 | 验收标准 |
| :--- | :--- | :--- |
| TASK-D.1 | 在 `email_generator.py` 的 `_build_variables()` 中建立别名映射字典（`company_name -> CUSTOMER_COMPANY` 等），覆盖常见的非标准变量名。 | 使用非标准变量名的模板，生成草稿时占位符被正确替换，不原样输出。 |
| TASK-D.2 | 修复 `_build_variables()` 中 `CURRENT_DATE` 硬编码 `cn` 的 Bug，改为根据当前邮件的 `language` 参数动态生成。 | 英文邮件中日期格式为 `August 5, 2026`，中文邮件为 `2026年8月5日`。 |
| TASK-D.3 | 修复 `interaction_analyzer.py` 的 `_detect_language()`，增加拼音城市名映射（`shanghai`, `beijing`, `guangzhou`, `shenzhen`, `chengdu`, `hangzhou` 等）。 | 客户 Location 为拼音城市时，正确判定为 `cn`。 |
| TASK-D.4 | 在 `prompts/template_import_prompt.md` 中增加语言纯净规则约束：**英文版**所有文字必须全为英文，不得含任何汉字（品牌名统一使用 `GRADO Contract`）；**中文版**正文和标题使用中文，品牌名只允许出现英文名（`GRADO Contract`）或纯中文名（`格度商业家具`），不允许中英混排；变量占位符内容不强制转换。 | LLM 生成的 `en_html` 不含汉字；`cn_html` 正文为中文，品牌名符合规范，经终端预览可验证。 |

### 新阶段 E：修复邮件主题生成
**目标**：确保所有邮件都有主题，且主题语言符合规则。

| 任务 ID | 任务描述 | 验收标准 |
| :--- | :--- | :--- |
| TASK-E.1 | 修改 `prompts/template_import_prompt.md`，强制要求 LLM 必须输出 `subject_template`：若原始模板有标题则提取，若无则根据正文自动生成。 | 所有导入的模板在 `config.yaml` 中均有 `subject_template` 字段，不为空。 |
| TASK-E.2 | 在 `cli_controller.py` 的导入完成提示中，高亮显示生成的 `subject_template`，并提示用户可在确认前修改。 | 终端导入成功后，主题行以高亮颜色显示，用户可选择接受或手动修改。 |

### 新阶段 F：修复浏览器预览自动跳转
**目标**：模板确认和草稿审核时，浏览器窗口必须自动弹出，不能仅打印路径。

| 任务 ID | 任务描述 | 验收标准 |
| :--- | :--- | :--- |
| TASK-F.1 | 在 `preview.py` 的 `_open_html()` 入口处增加环境检测：检查 `DISPLAY` 环境变量和是否为 WSL，有 GUI 时直接使用 `headless=False`，无 GUI 时直接使用 `headless=True`，避免无效的 headed 尝试。 | 在本地 Mac/Windows 环境下，预览时浏览器窗口必须自动弹出；在 WSL/SSH 环境下，终端必须打印截图路径。 |
| TASK-F.2 | 无 GUI 环境下，终端输出截图路径时使用醒目格式显示（如 ANSI 加粗或黄色输出），避免用户错过。 | 无 GUI 环境下预览时，终端输出中包含醒目的截图路径提示，不静默失败。 |

---

## 任务依赖关系

```
新阶段 A（模板选择重构）
  │
  ├── 新阶段 B（状态栏修复）← 依赖 A.2（selected_template 字段）
  │
  ├── 新阶段 C（图片提取）← 可独立执行
  │
  ├── 新阶段 D（变量/语言修复）← 可独立执行
  │
  ├── 新阶段 E（主题生成）← 依赖 D.4（Prompt 更新）
  │
  └── 新阶段 F（浏览器跳转）← 可独立执行
```

## 提交规范

每次任务完成后做一次原子化提交：
```
[Claude] fix(模块): 描述
```
例如：
- `[Claude] fix(analyzer): 移除阶段模板推荐，保留语言判定`
- `[Claude] fix(cli): 新增选择生效模板菜单项`
- `[Claude] fix(importer): 自动提取 docx 图片至 assets/images`
