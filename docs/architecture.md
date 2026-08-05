# 架构设计文档 (architecture.md)

> 本文档根据 `docs/PRD.md`、`tasks/TASK.md` 以及本次功能升级计划更新，目标是在现有闭环基础上增加：**多模型支持、模板导入与确认、浏览器预览、可中断发送、状态栏、生成元数据、严格的内容约束**。

## 1. 设计目标

1. **交互式终端闭环**：用户通过 `python main.py` 进入菜单，完成生成 → 预览审核 → 发送 → 查回复全流程。
2. **多模型灵活切换**：`.env` 支持配置多个 LLM，终端菜单切换，选择持久化到 `data/settings.json`。
3. **模板可管理**：通过 `templates/import/` 拖入 `md/docx/pdf` 自动导入；旧模板按 `YYYY/MM/DD` 归档；新模板需浏览器预览 + 终端确认后才能启用。
4. **生成可控可追溯**：每封草稿记录生成时间、token 消耗、使用的模型；严格基于确认模板填充变量，禁止编造、语言混用、随机寄件人名。
5. **发送可中断**：发送队列支持 Ctrl+C 暂停，通过 `data/sending_state.json` 续跑。
6. **状态可视**：终端顶部红/黄/绿状态栏即时反馈当前能否生成/发送。
7. **客户与语言规则**：`customers.csv` 中 `name` 以 `#` 开头的客户跳过生成/发送；`location` 字段支持 `(中文)` / `(英文)` 后缀覆盖邮件语言。

## 2. 目录结构

```
AI_sales_email_agent/
├── docs/
│   ├── PRD.md              # 产品需求，只读
│   ├── architecture.md     # 本文件
│   └── CONFIG_GUIDE.md     # 配置与操作指南
├── tasks/
│   └── TASK.md             # 任务拆解，只读
├── email_agent/            # 核心代码包
│   ├── __init__.py
│   ├── config.py           # 配置与路径（多模型、sender_profile、模板路径）
│   ├── cli_controller.py   # 交互式 CLI 菜单（状态栏、预览、模型切换、模板导入）
│   ├── llm_client.py       # LLM API 客户端（返回 usage、多模型、Moonshot 兼容）
│   ├── data_store.py       # CSV/JSON 读写抽象
│   ├── interaction_analyzer.py  # 客户阶段 + 语言判定
│   ├── template_engine.py  # YAML/HTML 模板渲染（多语言版本）
│   ├── template_importer.py# 模板导入、归档、双语生成、确认工作流（新增）
│   ├── email_generator.py  # 邮件草稿生成编排（元数据、增量落盘）
│   ├── preview.py          # 浏览器预览 HTML 生成（草稿/回复）（新增）
│   ├── status.py           # 顶部状态栏计算（新增）
│   ├── deliverability.py   # 发送策略与风控
│   ├── sender.py           # SMTP 发送（可中断队列）
│   ├── receiver.py         # IMAP 回复采集（结构化返回）
│   └── logger.py           # 日志写入
├── templates/
│   ├── email/              # 激活的邮件模板
│   │   ├── initial_contact/
│   │   │   ├── config.yaml
│   │   │   ├── template.html
│   │   │   └── template_en.html   # 英文版本（可选）
│   │   ├── follow_up/
│   │   └── final_note/
│   ├── import/             # 用户拖入的模板源文件（md/docx/pdf）
│   ├── archive/            # 历史模板归档 <template_name>/YYYY/MM/DD/<HHMMSS>/
│   └── sender_profile.md   # 寄件人身份变量（新增）
├── assets/
│   └── images/             # 模板内联图片
├── data/
│   ├── customers.csv
│   ├── drafts.json
│   ├── email_logs.csv
│   ├── reply_logs.csv
│   ├── settings.json
│   ├── generation_state.json        # 生成暂停/续跑状态
│   ├── sending_state.json           # 发送暂停/续跑状态（新增）
│   └── template_import_state.json   # 导入目录 checksum（新增）
├── prompts/
│   └── email_generation_prompt.md
├── skills/
│   ├── email_writing_skill.md
│   └── email_writing_skill_concise.md
├── main.py                 # 入口
├── README.md
└── requirements.txt
```

## 3. 模块划分与职责

| 模块 | 文件 | 职责 |
|------|------|------|
| 配置中心 | `email_agent/config.py` | 读取 `.env`、解析多模型块、加载 `sender_profile.md`、定义全部路径与常量。 |
| 数据存储 | `email_agent/data_store.py` | 读写 CSV/JSON；新增 sending/import state、增量追加 draft。 |
| CLI 控制器 | `email_agent/cli_controller.py` | 交互菜单、状态栏、调用各子模块。 |
| LLM 客户端 | `email_agent/llm_client.py` | 统一调用当前 active model，返回 content + usage；兼容 Moonshot。 |
| 互动分析器 | `email_agent/interaction_analyzer.py` | 判断销售阶段 + 邮件语言（大陆中文、海外英文、后缀覆盖）。 |
| 模板引擎 | `email_agent/template_engine.py` | 解析 `config.yaml` + `template.html`；支持 `template_<lang>.html`。 |
| 模板导入器 | `email_agent/template_importer.py` | 扫描 `templates/import/` → Markdown 中间层 → 合并/双语 → 归档 → 预览 → 确认激活。 |
| 邮件生成器 | `email_agent/email_generator.py` | 编排生成：分析 → 选择模板 → LLM 填变量 → 渲染 → 落盘，记录元数据。 |
| 预览器 | `email_agent/preview.py` | 生成自包含 HTML 临时文件并用 `webbrowser` 打开。 |
| 状态计算器 | `email_agent/status.py` | 综合配置、模板确认、草稿/发送状态，输出红/黄/绿。 |
| 送达率管理 | `email_agent/deliverability.py` | 频率、延迟、相似度、SPF、白名单。 |
| 发送器 | `email_agent/sender.py` | SMTP 发送；支持 pause/resume；跳过 `#` 客户。 |
| 接收器 | `email_agent/receiver.py` | IMAP 采集回复，返回结构化列表。 |
| 日志器 | `email_agent/logger.py` | 初始化与追加日志。 |

## 4. 数据流

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────────┐
│  main.py    │────▶│ cli_controller│────▶│  status.py          │
│ (entry)     │     │ (interactive) │     │  (red/yellow/green) │
└─────────────┘     └──────────────┘     └─────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
  ┌─────────────┐    ┌──────────────┐    ┌──────────────┐
  │ Generate    │    │ Review       │    │ Send         │
  │ (browser    │    │ (browser     │    │ (Ctrl+C      │
  │  preview)   │    │  preview)    │    │  pause)      │
  └─────────────┘    └──────────────┘    └──────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                        模板导入工作流                            │
│  templates/import/<file>                                         │
│        │                                                          │
│        ▼                                                          │
│  template_importer.extract_to_markdown()                         │
│        │ 输出：结构化 Markdown（段落、图片/链接占位）             │
│        ▼                                                          │
│  源模板选择（二选一）                                            │
│    [L] 使用最新/基础模板：激活目录优先，否则取最新归档           │
│    [B] 浏览历史归档：模板名 → 年 → 月 → 日 → 归档               │
│        ▼                                                          │
│  template_importer.merge_markdown_into_template()                │
│        │ 保留 {{var}}、{{IMAGE:name}}、<img>、<a>                 │
│        ▼                                                          │
│  template_importer.generate_missing_language()（如需要）         │
│        ▼                                                          │
│  template_importer.archive_current_template()                    │
│        │ 归档到 archive/<template_name>/YYYY/MM/DD/<HHMMSS>/   │
│        ▼                                                          │
│  preview.build_preview_html() → webbrowser                       │
│        ▼                                                          │
│  终端确认 → settings.template_confirmed = true                   │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        生成草稿流程                              │
│  data_store.load_customers() （过滤 # 前缀客户）                 │
│        │                                                          │
│        ▼                                                          │
│  interaction_analyzer.analyze(customer, history)                 │
│        │ 输出：stage, template_type, strategy, language           │
│        ▼                                                          │
│  llm_client.complete_json(...) 填充模板变量 + usage              │
│        │                                                          │
│        ▼                                                          │
│  template_engine.render(template_name, variables, language)      │
│        │ 输出：html_body, images                                  │
│        ▼                                                          │
│  data_store.append_draft(draft) 写入 drafts.json                 │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        发送流程                                  │
│  data_store.load_drafts(status='approved')                       │
│        │                                                          │
│        ▼                                                          │
│  sender.process_queue()                                          │
│        │ 加载 sending_state.json，跳过已发送/#客户               │
│        ▼                                                          │
│  deliverability.can_send(draft, send_history)                    │
│        ▼                                                          │
│  sender.send_email(draft)  HTML + 内联图片                       │
│        ▼                                                          │
│  logger.log_email_send(...) → email_logs.csv                     │
│        ▼                                                          │
│  deliverability.wait_before_next()（可中断短延迟）               │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        回复采集流程                              │
│  receiver.check_replies() 读取 IMAP                              │
│        │ 输出：结构化 reply list                                │
│        ▼                                                          │
│  preview.open_replies_preview() → webbrowser                     │
│        ▼                                                          │
│  终端选择保存/刷新/退出                                          │
│        ▼                                                          │
│  logger.log_reply(...) → reply_logs.csv                          │
└─────────────────────────────────────────────────────────────────┘
```

## 5. 关键数据结构

### 5.1 `data/drafts.json` 单条记录

```json
{
  "draft_id": "20260804-001",
  "customer_id": "001",
  "email": "camgrado@gmail.com",
  "template": "initial_contact",
  "stage": "new_lead",
  "language": "cn",
  "subject": "...",
  "html_body": "<html>...</html>",
  "text_body": "...",
  "images": [
    {"cid": "portfolio_grid_1", "path": "assets/images/portfolio_grid_1.jpg"}
  ],
  "personalization_note": "...",
  "review_status": "pending",
  "created_at": "2026-08-04 10:00:00",
  "model_used": "kimi-k2.6",
  "generation_meta": {
    "generation_time": "2026-08-04T10:00:00",
    "prompt_tokens": 420,
    "completion_tokens": 180,
    "total_tokens": 600
  }
}
```

### 5.2 `data/settings.json`

```json
{
  "skill_mode": "concise",
  "active_model_index": 0,
  "template_confirmed": false,
  "template_confirmed_at": null
}
```

### 5.3 `data/sending_state.json`

```json
{
  "started_at": "2026-08-04T10:00:00",
  "sent_draft_ids": ["20260804-001"],
  "remaining_draft_ids": ["20260804-002"]
}
```

### 5.4 `templates/sender_profile.md`

```markdown
---
sender_name: "张三"
sender_title: "商务拓展经理"
sender_market_region: "大中华区"
sender_phone: "+86 138 0000 0000"
sender_email: "zhangsan@gradodesign.hk"
---

如有其他落款信息可写在这里，供 prompt 引用。
```

## 6. 关键接口定义

### 6.1 `email_agent/config.py`

```python
AVAILABLE_MODELS: list[dict]          # 从 .env 解析
ACTIVE_MODEL_INDEX: int               # 来自 settings.json / .env

def load_available_models() -> list[dict]: ...
def get_active_model() -> dict: ...
def load_sender_profile() -> dict: ...
def is_template_confirmed() -> bool: ...
```

### 6.2 `email_agent/llm_client.py`

```python
def complete(
    system_prompt: str,
    user_prompt: str,
    response_format: dict | None = None,
    temperature: float = 0.7,
) -> dict:  # {"content": str, "usage": {"prompt_tokens": int, ...}}

def complete_json(
    system_prompt: str,
    user_prompt: str,
    schema: dict,
    temperature: float = 0.7,
) -> dict:  # {"content": raw_json_str, "usage": dict}
```

### 6.3 `email_agent/interaction_analyzer.py`

```python
def analyze(customer: dict, history: dict | None = None) -> dict:
    """
    返回：
    {
      "stage": str,
      "template_type": str,
      "strategy": str,
      "reason": str,
      "language": "cn" | "en"
    }
    """
```

### 6.4 `email_agent/template_engine.py`

```python
def get_template_path(template_name: str, language: str | None = None) -> str: ...
def render(template_name: str, variables: dict, language: str | None = None) -> tuple[str, list[dict]]: ...
def list_template_languages(template_name: str) -> list[str]: ...
```

### 6.5 `email_agent/template_importer.py`

```python
def scan_import_folder() -> list[ImportCandidate]: ...
def detect_changes() -> list[ImportCandidate]: ...
def extract_to_markdown(path: str) -> dict: ...
def merge_markdown_into_template(template_name: str, markdown: str, language: str) -> str: ...
def generate_missing_language(template_name: str, source_lang: str, target_lang: str) -> str: ...
def has_unfinished_work(template_name: str) -> tuple[bool, str]: ...
def activate_template(template_name: str, candidate_path: str, source_template_path: str | None = None, force: bool = False) -> dict: ...
```

### 6.6 `email_agent/preview.py`

```python
def open_draft_preview(draft: dict) -> str: ...
def open_replies_preview(replies: list[dict]) -> str: ...
```

### 6.7 `email_agent/status.py`

```python
def compute_status() -> dict:
    """返回 {"color": "red|yellow|green", "label": str, "messages": list[str]}"""
```

### 6.8 `email_agent/sender.py`

```python
def process_queue(drafts: list[dict] | None = None) -> None: ...
```

### 6.9 `email_agent/receiver.py`

```python
def check_replies(dry_run: bool = False) -> list[dict]: ...
```

## 7. 实施顺序

按**一个模块一次提交**原则执行：

### 阶段一：地基与元数据
1. `config.py`：多模型解析、`sender_profile.md`、模板路径。
2. `data_store.py`：sending/import state、`append_draft`。
3. `llm_client.py`：返回 usage、使用 active model。
4. `email_generator.py`：`generation_meta`、`model_used`、增量落盘。

### 阶段二：模板导入与确认
5. `template_importer.py`：扫描、Markdown 中间层、归档、合并、双语。
6. `settings.json`：`template_confirmed`；生成/发送前检查。
7. `template_engine.py`：多语言版本支持。

### 阶段三：生成质量约束
8. 修订 `skills/*.md`、`prompts/email_generation_prompt.md`。
9. `email_generator.py`：强制寄件人身份、跳过 `#` 客户、语言注入。
10. `interaction_analyzer.py`：语言判定逻辑。

### 阶段四：浏览器预览
11. `preview.py`：草稿/回复 HTML 生成与图片内联。
12. `cli_controller.py`：审核菜单调用浏览器预览。
13. `cli_controller.py`：回复菜单调用浏览器列表。

### 阶段五：可中断发送
14. `sender.py`：sending state、pause/resume、Ctrl+C 响应、底部提示。

### 阶段六：状态栏与 CLI 完善
15. `status.py`：红/黄/绿计算逻辑。
16. `cli_controller.py`：顶部状态栏、菜单重排、模型切换、模板导入/确认菜单。

### 阶段七：文档
17. `README.md`：面向新手的部署与操作指南。
18. `docs/CONFIG_GUIDE.md`：详细配置与可调参数说明。

## 8. 关键决策与约束

1. **草稿存储格式**：继续采用 `data/drafts.json`，新增 `generation_meta`、`model_used`、`language` 字段。
2. **多模型配置**：使用 `.env` 编号块 `MODEL_1_NAME/ BASE_URL/ API_KEY/ MODEL/ TEMPERATURE`；无编号块时回退旧变量，保证向后兼容。
3. **模板导入**：必须走“Markdown 中间层 → DOM 合并 → 预览 → 确认”四步，未确认模板禁止生成/发送。
4. **语言规则**：大陆默认中文，香港/台湾/海外默认英文；`location` 后缀可强制覆盖。
5. **寄件人身份**：`templates/sender_profile.md` 优先于 `.env`，LLM 必须严格使用，不得杜撰。
6. **相似度与风控**：保留 `difflib.SequenceMatcher`、SPF 警告、Demo 白名单、随机延迟。
7. **可中断性**：生成与发送均通过 JSON state 文件实现 pause/resume；延迟拆分为短 sleep。
8. **浏览器预览**：标准库 `webbrowser` + 临时 HTML；无桌面环境时打印路径，不阻断流程。
9. **客户跳过**：`name` 以 `#` 开头仅跳过生成/发送，不影响回复记录（回复按 `email_logs.csv` 匹配）。
10. **中文文件名映射**：`.docx/.md/.pdf` 文件名按关键词映射到标准模板名 `initial_contact / follow_up / final_note / other`，文件名本身不作为终端变量或目录名。
11. **归档层级**：归档目录为 `archive/<template_name>/YYYY/MM/DD/<HHMMSS>/`，同时兼容旧结构 `archive/YYYY/MM/DD/<name>_<HHMMSS>/`。
12. **源模板选择**：导入时可从当前激活模板或历史归档中选择合并基准；无可用基准时直接从导入文件生成 baseline HTML。
13. **导入状态过期重置**：当 `templates/email/` 为空但 `templates/import/` 仍有已记录文件时，允许清空 `template_import_state.json` 重新导入。
14. **终端中文化**：所有菜单、提示、状态信息使用中文，快捷键保持英文/数字。
15. **文档边界**：不修改 `docs/PRD.md` 和 `docs/UserFlow.md`；`architecture.md`、README、CONFIG_GUIDE 属于本实现范畴。

## 9. 验证策略

| 模块 | 验证命令 / 方法 |
|------|----------------|
| `config` | `python -c "from email_agent.config import load_available_models, get_active_model, load_sender_profile; print(...)` |
| `llm_client` | 调用后检查返回结构含 `content` + `usage`。 |
| `email_generator` | 生成单条草稿，检查 `drafts.json` 含 `generation_meta`、`model_used`、`language`。 |
| `template_importer` | 放入 `.md/.docx/.pdf`，检查归档、预览、确认流程。 |
| `preview` | 调用后浏览器打开或打印临时文件路径。 |
| `sender` | 发送时按 Ctrl+C，检查 `sending_state.json`；续跑后不再重复发送。 |
| `receiver` | 有回复时返回结构化列表并在浏览器中展示。 |
| `status` | 通过改变 `.env`/模板确认/草稿状态验证红/黄/绿切换。 |
| 端到端 | 完整跑通：模板确认 → 生成 → 浏览器审核 → 发送（中断续跑）→ 查回复。 |
