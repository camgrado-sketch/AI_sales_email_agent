# 架构设计文档 (architecture.md)

> 本文档根据 `docs/PRD.md`、用户本轮架构调整要求更新。
> 核心变更：LLM 仅参与模板结构化，邮件生成改为本地模板变量替换；CLI 设置类命令聚合为“设置”子菜单。

## 1. 设计目标

1. **降低生成阶段算力消耗**：每封邮件不再调用 LLM，仅通过本地正则/字典做硬性变量替换。
2. **模板来源用户可控**：用户将邮件模板放入 `templates/import/`，由脚本拆解并生成中英双语、带标准占位符的激活模板。
3. **LLM 仅做结构识别**：识别正文段落、图片/文件/链接位置、可替换变量；不传输图片/文件二进制。
4. **跨平台预览**：优先使用 Playwright Chromium 自动打开预览，无桌面环境时回退到 PNG 截图/打印路径。
5. **CLI 菜单瘦身**：设置相关命令聚合到“设置”子菜单，新增发送者信息编辑。
6. **保留现有闭环**：生成 → 审核 → 发送 → 查回复，可中断发送与状态栏保持不变。

## 2. 目录结构

```
AI_sales_email_agent/
├── docs/
│   ├── PRD.md                  # 只读
│   ├── architecture.md         # 本文件
│   └── CONFIG_GUIDE.md         # 配置与操作指南
├── tasks/
│   └── TASK.md                 # 任务拆解
├── email_agent/
│   ├── __init__.py
│   ├── config.py               # 配置、路径、sender_profile 加载
│   ├── cli_controller.py       # 交互式 CLI（新菜单结构）
│   ├── sender_profile_editor.py# 发送者信息交互式编辑（新增）
│   ├── llm_client.py           # LLM API 客户端
│   ├── data_store.py           # CSV/JSON 读写抽象
│   ├── interaction_analyzer.py # 销售阶段 + 语言判定（移除 LLM 策略）
│   ├── template_engine.py      # HTML 模板渲染（{{VAR}} / {{IMAGE}} / {{FILE}}）
│   ├── template_importer.py    # 模板扫描、LLM 结构化、双语生成、归档、确认
│   ├── email_generator.py      # 本地变量组装 → 模板渲染 → 写入 drafts.json
│   ├── preview.py              # Playwright Chromium 预览（含兜底）
│   ├── status.py               # 顶部状态栏
│   ├── deliverability.py       # 发送风控
│   ├── sender.py               # SMTP 发送（可中断队列）
│   ├── receiver.py             # IMAP 回复采集
│   └── logger.py               # 日志写入
├── templates/
│   ├── email/                  # 激活模板（config.yaml + template.html + template_en.html）
│   ├── import/                 # 用户上传的 md/docx/pdf
│   ├── archive/                # 归档模板
│   └── sender_profile.md       # 发送者身份（YAML frontmatter）
├── assets/
│   ├── images/                 # 内联图片
│   └── files/                  # 下载文件（新增目录约定）
├── data/
│   ├── customers.csv
│   ├── drafts.json
│   ├── email_logs.csv
│   ├── reply_logs.csv
│   ├── settings.json
│   ├── generation_state.json
│   ├── sending_state.json
│   └── template_import_state.json
├── prompts/
│   └── template_import_prompt.md   # LLM 模板结构化 prompt（新增）
├── main.py
├── README.md
└── requirements.txt
```

## 3. 模块职责

| 模块 | 文件 | 职责 |
|------|------|------|
| 配置中心 | `config.py` | 读取 `.env`、多模型、加载 `sender_profile.md`、定义路径常量。 |
| 数据存储 | `data_store.py` | 读写 CSV/JSON；状态文件管理。 |
| CLI 控制器 | `cli_controller.py` | 新菜单结构、状态栏、调用各子模块。 |
| 发送者编辑器 | `sender_profile_editor.py` | 交互式编辑并保存 `sender_profile.md`。 |
| LLM 客户端 | `llm_client.py` | 统一调用 active model，返回 content + usage；兼容 Moonshot。 |
| 互动分析器 | `interaction_analyzer.py` | **规则判定**销售阶段与语言；不再调用 LLM。 |
| 模板引擎 | `template_engine.py` | 渲染 HTML，替换 `{{VAR}}`、`{{IMAGE:name}}`、`{{FILE:name}}`。 |
| 模板导入器 | `template_importer.py` | 扫描 import → Markdown → LLM 结构化 → 双语 HTML + config.yaml → 归档 → 确认。 |
| 邮件生成器 | `email_generator.py` | 组装 sender/customer 变量 → 本地渲染 → 写入 drafts.json。 |
| 预览器 | `preview.py` | Playwright Chromium 打开草稿/回复/模板预览，含无桌面环境兜底。 |
| 状态计算器 | `status.py` | 顶部红/黄/绿状态栏。 |
| 送达率管理 | `deliverability.py` | 频率、延迟、相似度、SPF、白名单。 |
| 发送器 | `sender.py` | SMTP 发送；支持 pause/resume。 |
| 接收器 | `receiver.py` | IMAP 采集回复。 |

## 4. 数据流

```
templates/import/<file>
  │
  ▼
template_importer.scan_import_folder() → detect_changes()
  │
  ▼
template_importer.extract_to_markdown()  （本地提取文本/图片名/链接名）
  │
  ▼
llm_client.complete_json()  【模板结构化唯一 LLM 调用】
  │ 输入：Markdown + 可用变量字段清单
  │ 输出：{subject_template, cn_html, en_html, variables, images, files}
  ▼
本地写入 templates/email/<name>/
  │
  ▼
Playwright 预览 + 终端确认 → settings.template_confirmed = true


data/customers.csv
  │
  ▼
interaction_analyzer.analyze(customer)  → {stage, template_type, language}
  │
  ▼
email_generator.generate_for_customer(customer)
  ├─ config.load_sender_profile()
  ├─ 读取 customer 行
  ├─ 组装 variables dict（硬性映射，无 LLM）
  ├─ template_engine.render(template_name, variables, language)
  └─ data_store.append_draft(draft)


data/drafts.json (status=approved)
  │
  ▼
sender.process_queue()
  ├─ deliverability.can_send()
  ├─ sender.send_email()
  └─ logger.log_email_send()
```

## 5. 关键数据结构

### 5.1 `data/drafts.json` 单条记录

```json
{
  "draft_id": "20260805-001",
  "customer_id": "001",
  "email": "camgrado@gmail.com",
  "template": "initial_contact",
  "stage": "new_lead",
  "language": "cn",
  "subject": "...",
  "html_body": "<html>...</html>",
  "text_body": "...",
  "images": [{"cid": "hero", "path": "assets/images/hero.jpg"}],
  "files": [{"name": "catalog_pdf", "path": "assets/files/catalog_pdf.pdf"}],
  "personalization_note": "",
  "review_status": "pending",
  "created_at": "2026-08-05 10:00:00",
  "rendered_by": "local"
}
```

### 5.2 `templates/email/<name>/config.yaml`

```yaml
template_name: initial_contact
purpose: [cold_outreach]
customer_type: [designer, distributor]
recommended_stage: [new_lead]
variables:
  - SENDER_NAME
  - SENDER_TITLE
  - SENDER_COMPANY
  - SENDER_EMAIL
  - SENDER_PHONE
  - SENDER_MARKET_REGION
  - CUSTOMER_FIRST_NAME
  - CUSTOMER_NAME
  - CUSTOMER_COMPANY
  - CUSTOMER_POSITION
  - CUSTOMER_LOCATION
  - CUSTOMER_INDUSTRY
  - CURRENT_DATE
images:
  - hero
  - portfolio_grid_1
files:
  - catalog_pdf
rules:
  - 只替换模板中声明的变量，禁止编造信息。
  - 邮件正文语言由 language 参数决定。
```

### 5.3 `templates/sender_profile.md`

```markdown
---
sender_name: "张三"
sender_title: "商务拓展经理"
sender_company: "GRADO CONTRACT"
sender_email: "zhangsan@gradodesign.hk"
sender_phone: "+86 138 0000 0000"
sender_market_region: "大中华区"
---
```

## 6. 关键接口定义

### 6.1 `email_agent/config.py`

```python
AVAILABLE_MODELS: list[dict]
SENDER_PROFILE_FILE: str
IMAGES_DIR: str
FILES_DIR: str          # 新增

def load_available_models() -> list[dict]: ...
def get_active_model() -> dict | None: ...
def load_sender_profile() -> dict: ...
def is_template_confirmed() -> bool: ...
```

### 6.2 `email_agent/template_importer.py`

```python
def scan_import_folder() -> list[ImportCandidate]: ...
def detect_changes() -> list[ImportCandidate]: ...
def extract_to_markdown(path: str) -> str: ...
def structure_template_with_llm(markdown: str, filename: str) -> dict: ...
  # 新增：调用 LLM 返回结构化模板
def write_structured_template(template_name: str, structured: dict, source_lang: str) -> dict: ...
  # 新增：写入 template.html / template_<other>.html / config.yaml
def archive_current_template(template_name: str) -> str | None: ...
def confirm_active_template() -> dict: ...
```

### 6.3 `email_agent/email_generator.py`

```python
def _build_variables(customer: dict, template_config: dict) -> dict: ...
  # 新增：从 sender_profile + customer 硬性映射变量
def generate_for_customer(customer: dict, language: str | None = None) -> dict: ...
def generate_all(customers: list[dict] | None = None) -> list[dict]: ...
```

### 6.4 `email_agent/template_engine.py`

```python
def render(template_name: str, variables: dict, language: str | None = None)
    -> tuple[str, list[dict], list[dict]]:
    # 返回 (html_body, images, files)
```

### 6.5 `email_agent/preview.py`

```python
def open_draft_preview(draft: dict) -> str: ...
def open_template_preview(template_name: str) -> str: ...
def open_replies_preview(replies: list[dict]) -> str: ...
# 内部统一使用 Playwright，失败时回退
```

### 6.6 `email_agent/sender_profile_editor.py`

```python
def edit_sender_profile_interactive() -> dict: ...
```

## 7. 实施顺序

按**一个模块一次提交**原则：

1. **模板导入 LLM 结构化**（`template_importer.py` + `prompts/template_import_prompt.md`）
2. **模板引擎扩展**（`template_engine.py`：变量名规范、`{{FILE:name}}`、返回 files 列表）
3. **发送者信息编辑**（`sender_profile_editor.py` + `config.py` 常量补充）
4. **邮件生成器重构**（`email_generator.py`：本地变量替换，移除 per-customer LLM）
5. **互动分析器简化**（`interaction_analyzer.py`：移除 `_llm_strategy`）
6. **Playwright 预览**（`preview.py` + `requirements.txt`）
7. **CLI 菜单重构**（`cli_controller.py`：设置子菜单、发送者信息入口）
8. **文档更新**（`docs/architecture.md`、`tasks/TASK.md`、`README.md`、`docs/CONFIG_GUIDE.md`、`CHANGELOG.md`）
9. **端到端验证**

## 8. 关键决策与约束

1. **LLM 调用点唯一化**：只有 `template_importer.structure_template_with_llm()` 调用远程 LLM。
2. **变量命名**：统一大写下划线，来源清晰，禁止 LLM invent。
3. **发送者信息唯一可信源**：`templates/sender_profile.md` 覆盖 `.env`。
4. **图片/文件不上传 LLM**：只传名称与位置描述，本地解析真实路径。
5. **语言判定保留规则**：`interaction_analyzer` 继续按 location 后缀/地区判定语言。
6. **模板确认前置**：未确认模板时，生成/发送被状态栏阻断。
7. **预览兜底策略**：Playwright headed 优先 → headless PNG 截图 + 打印路径 → 系统浏览器兜底。
8. **数据层不变**：继续使用 CSV/JSON；状态文件复用现有结构。
9. **客户跳过规则不变**：`name` 以 `#` 开头跳过生成/发送。
10. **不修改 PRD/UserFlow**：仅更新 `architecture.md` 与 `TASK.md`。
11. **归档分类保留**：自动归档仍按 `templates/archive/<template_name>/YYYY/MM/DD/<HHMMSS>/` 执行。

## 9. 验证策略

| 模块 | 验证方法 |
|------|---------|
| template_importer | 放入 `.docx/.md/.pdf`，检查生成的 `template.html`/`template_en.html`/`config.yaml` 是否含标准占位符；预览自动打开。 |
| template_engine | 传入变量 dict，检查所有 `{{VAR}}` 被替换，图片/文件路径正确解析。 |
| email_generator | 生成草稿后检查 `drafts.json`，确认无 per-customer LLM 调用，`rendered_by: local`。 |
| interaction_analyzer | 验证 stage/language 输出正确，不再调用 LLM。 |
| preview | 在有桌面环境验证 Playwright 弹出窗口；无桌面环境验证生成 `data/latest_preview.png`。 |
| cli_controller | 验证新菜单结构、设置子菜单、发送者信息编辑保存。 |
| 端到端 | 导入模板 → 确认 → 生成 → 审核（Playwright 预览）→ 发送（mock 或真实白名单邮箱）。 |
