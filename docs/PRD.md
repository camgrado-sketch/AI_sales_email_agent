# 产品需求文档 (PRD) - AI 销售邮件自动化系统

**版本**：v2.0（基于 feature/local-template-replace 黑盒测试结果重构）

---

## 1. 项目背景与目标

将原本依赖外部沙盒的半自动邮件生成流程，升级为内部闭环的自动化系统。核心设计原则：

> **LLM 仅负责模板导入时的一次性结构化解析；批量邮件生成完全通过本地变量替换实现，不消耗 LLM 算力。**

本次重构在原有架构基础上，重点解决以下问题：模板选择失控、变量命名断层、语言判定漏洞、图片/附件未嵌入、阶段逻辑过度复杂、预览窗口未自动弹出。

---

## 2. 核心设计原则变更

### 2.1 移除销售阶段逻辑

原系统将模板与"销售阶段"（初次联系/跟进/结束）强绑定，导致模板选择被代码写死。**新版取消此机制**，改为：

- 用户导入模板后，手动选择一个模板作为"当前生效模板"（长期生效，直到下次手动更改）。
- 邮件生成时，所有客户统一使用当前生效模板，不再自动按阶段切换。
- `interaction_analyzer.py` 保留语言判定逻辑，但移除模板推荐逻辑。

### 2.2 LLM 调用点唯一化

系统中唯一的 LLM 调用点是 `template_importer.structure_template_with_llm()`，负责将用户上传的模板文件解析为标准化的双语 HTML 模板。其余所有环节（生成、审核、发送）均为本地执行。

---

## 3. 功能需求

### 3.1 终端状态栏（顶部常驻）

每次进入主菜单时，顶部必须显示以下状态信息，格式简洁、两行内可读：

| 状态项 | 内容说明 |
| :--- | :--- |
| 当前模板 | 模板名称 + 导入日期，如 `initial_contact (2026-08-01)` |
| 模板确认状态 | `✅ 已确认` / `⚠️ 未确认（需到菜单6确认后才能生成）` |
| 发送状态 | `未发送` / `部分发送（剩余 N 封）` / `已全部发送` |
| 回复情况 | `N 封回复待查看` |

示例：
```
─────────────────────────────────────────────────────
模板: initial_contact (2026-08-01) ✅已确认
发送: 部分发送（剩余 12 封）  |  回复: 3 封
─────────────────────────────────────────────────────
```

### 3.2 模板导入与图片/附件自动处理

用户将模板文件（`.md/.docx/.pdf`）放入 `templates/import/`，系统执行以下流程：

1. **文本提取**：将文件内容提取为 Markdown。
2. **图片自动提取与命名**：若文件为 `.docx` 或 `.pdf`，系统自动提取其中嵌入的图片，保存至 `assets/images/`，并按顺序自动命名（如 `initial_contact_img_01.png`）。同时在解析出的 Markdown 中，将图片位置替换为对应的 `{{IMAGE:initial_contact_img_01}}` 占位符。
3. **LLM 结构化**：将 Markdown（含图片占位符）传给 LLM，解析出 `subject_template`、`cn_html`、`en_html`、`variables`、`images`、`files`。
4. **写入激活模板**：生成 `template.html`（源语言）、`template_<other>.html`（对应语言）和 `config.yaml`。

**约束**：图片和文件的二进制内容不上传 LLM，只传名称和位置描述。

### 3.3 模板选择与确认（长期生效）

- 用户在模板管理菜单（菜单 6）中选择一个模板作为"当前生效模板"，选择后写入 `settings.json` 的 `selected_template` 字段。
- 此设置长期生效，直到用户下次手动更改。
- 模板必须经过"确认"操作后才能用于生成（`template_confirmed: true`）。
- 菜单中显示每个模板的名称、导入日期及当前使用状态（未发送/部分发送/已全部发送）。

### 3.4 邮件主题（Subject）生成规则

- LLM 在解析模板时，必须生成 `subject_template` 并写入 `config.yaml`。
- 若用户提供的原始模板中包含明确的邮件标题，则直接提取。
- 若原始模板中没有邮件标题，LLM 需根据正文内容自动生成一个简洁的标题，并在导入后的终端预览中高亮提示，供用户确认。
- 标题语言遵循下方的中英文规则。

### 3.5 中英文语言规则

语言由客户的 `location` 字段决定，规则如下：

- **英文版**：正文和标题必须**全为英文**，不允许出现任何汉字，包括品牌名（统一使用 `GRADO Contract`，不得出现中文）。
- **中文版**：正文和标题使用中文；品牌名只允许出现英文名（`GRADO Contract`）或纯中文名（`格度商业家具`），不允许中英混排（如"GRADO Contract 格拉多"此类写法不允许出现）；变量填充后的内容（如客户姓名、公司名等）保持原始格式，不强制转换。
- **语言判定修复**：`_detect_language` 必须同时支持中文汉字和拼音城市名（`shanghai`, `beijing`, `guangzhou`, `shenzhen`, `chengdu`, `hangzhou` 等）映射为 `cn`。

### 3.6 统一变量命名空间

系统注入的标准变量统一使用大写下划线格式（`SENDER_*`、`CUSTOMER_*`）。为兼容用户自定义模板中可能出现的非标准变量名，`email_generator.py` 必须实现别名映射机制，常见映射如下：

| 用户模板中的变量 | 映射到系统变量 |
| :--- | :--- |
| `{{company_name}}` | `CUSTOMER_COMPANY` |
| `{{market_region}}` | `SENDER_MARKET_REGION` |
| `{{customer_name}}` | `CUSTOMER_NAME` |
| `{{first_name}}` | `CUSTOMER_FIRST_NAME` |
| `{{sender_name}}` | `SENDER_NAME` |

若变量无法匹配，不得原样输出，必须替换为空字符串并在终端打印警告。

### 3.7 Playwright 预览与浏览器自动跳转

模板确认和草稿审核步骤中，必须自动弹出浏览器窗口展示 HTML 预览，不能仅打印路径。具体机制如下：

- **有桌面环境（本地 Mac/Windows）**：检测到 `DISPLAY` 环境变量或非 WSL 环境时，直接以 `headless=False` 模式启动 Playwright Chromium，自动打开预览页面，用户关闭窗口后终端继续。
- **无桌面环境（WSL/SSH）**：检测到无 `DISPLAY` 时，自动切换为 `headless=True` 生成截图至 `data/latest_preview.png`，并在终端以醒目格式打印截图路径，提示用户手动打开。
- **关键修复**：当前代码在 `_open_html()` 入口处缺少环境检测，导致 `headless=False` 无效时仍会尝试并静默失败。需在入口处增加 `DISPLAY` 检测，根据环境直接选择正确模式，避免无效尝试造成的延迟。

### 3.8 模板与草稿管理（保留现有功能）

以下功能为现有实现，不得在新阶段开发中被移除或破坏：

- **模板归档管理**：菜单 6 中的 `[M] 管理归档` 功能，支持查看和删除历史归档版本。
- **草稿删除**：主菜单 `[D] 删除草稿` 功能，支持按编号删除单条或清空全部草稿。

---

## 4. 数据结构

| 文件 | 说明 |
| :--- | :--- |
| `data/customers.csv` | 客户主数据（id, name, company, position, industry, location, email） |
| `data/drafts.json` | 邮件草稿（含 html_body, images, files, review_status） |
| `data/email_logs.csv` | 发送历史 |
| `data/reply_logs.csv` | 回复记录 |
| `data/settings.json` | 系统设置（含 `selected_template`, `template_confirmed`） |
| `assets/images/` | 模板嵌入图片（自动提取命名） |
| `assets/files/` | 模板附件 |

---

## 5. 外部接口依赖

- **LLM API**：仅在 `template_importer.py` 中调用，用于模板结构化解析。
- **SMTP/IMAP**：腾讯企业邮箱，用于收发邮件。
- **Playwright Chromium**：用于草稿和模板的高保真本地预览，必须自动弹出窗口。
