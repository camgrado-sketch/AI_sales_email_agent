# 架构设计文档 (architecture.md)

> 本架构根据 `docs/PRD.md` 第 2 章用户流及 `tasks/TASK.md` 四个阶段任务拆解设计。目标是在现有 `email_agent/` 与 `templates/email/` 基础上，升级为**完全内部闭环运行的 AI 销售邮件自动化系统**。

## 1. 设计目标

1. **交互式终端闭环**：用户通过 `python main.py` 进入菜单，无需手动修改 CSV 中的 `review_status`。
2. **数据直连**：从 `data/customers.csv`、`data/email_logs.csv`、`data/reply_logs.csv` 自动读取客户与互动历史。
3. **智能分析与模板匹配**：由 LLM 判断客户销售阶段，并匹配 `templates/email/` 下的 YAML/HTML 模板。
4. **富媒体邮件**：支持 `{{IMAGE:xxx}}` 占位符，自动嵌入 `assets/images/` 中的图片为 CID 内联图片。
5. **安全发送**：频率控制、随机延迟、相似度检测、SPF DNS 校验、白名单拦截。
6. **可测试与可扩展**：每个模块独立开发、独立测试，便于后续迁移到 SQLite。

## 2. 目录结构

```
AI_sales_email_agent/
├── docs/
│   ├── PRD.md              # 产品需求，只读
│   └── architecture.md     # 本文件
├── tasks/
│   └── TASK.md             # 任务拆解，只读
├── email_agent/            # 核心代码包
│   ├── __init__.py
│   ├── config.py           # 配置与路径（扩展）
│   ├── cli_controller.py   # 交互式 CLI 菜单（新增）
│   ├── llm_client.py       # LLM API 客户端（新增）
│   ├── data_store.py       # CSV/JSON 读写抽象（新增）
│   ├── interaction_analyzer.py  # 客户阶段分析（新增）
│   ├── template_engine.py  # YAML/HTML 模板渲染（新增）
│   ├── email_generator.py  # 邮件草稿生成编排（新增）
│   ├── deliverability.py   # 发送策略与风控（新增）
│   ├── sender.py           # SMTP 发送（重构：HTML + 内联图片）
│   ├── receiver.py         # IMAP 回复采集（轻微重构）
│   └── logger.py           # 日志写入（扩展）
├── templates/email/        # 模板目录（已存在）
│   ├── initial_contact/
│   │   ├── config.yaml
│   │   └── template.html
│   ├── follow_up/
│   └── final_note/
├── assets/
│   └── images/             # 模板内联图片（新增）
├── data/
│   ├── customers.csv
│   ├── drafts.json         # 结构化草稿（新增，替代 drafts.csv）
│   ├── email_logs.csv
│   └── reply_logs.csv
├── prompts/
│   └── email_generation_prompt.md
├── skills/
│   └── email_writing_skill.md
├── main.py                 # 入口：启动 CLI
└── requirements.txt
```

## 3. 模块划分与职责

| 模块 | 文件 | 职责 |
|------|------|------|
| 配置中心 | `email_agent/config.py` | 统一管理路径、SMTP/IMAP、白名单、频率限制等常量。 |
| 数据存储 | `email_agent/data_store.py` | 读写 `customers.csv`、`email_logs.csv`、`reply_logs.csv`、`drafts.json`，屏蔽底层格式。 |
| CLI 控制器 | `email_agent/cli_controller.py` | 提供交互式菜单：生成草稿、逐条审核、发送队列、查看日志、配置检查。 |
| LLM 客户端 | `email_agent/llm_client.py` | 统一封装 OpenAI 兼容 API 调用，支持 `.env` 配置与 JSON schema 输出。 |
| 互动分析器 | `email_agent/interaction_analyzer.py` | 根据客户历史邮件与回复，判断销售阶段（new_lead / contacted_no_reply / follow_up_no_reply / replied 等）。 |
| 模板引擎 | `email_agent/template_engine.py` | 解析 `templates/email/<name>/config.yaml` 与 `template.html`；替换 `{{var}}` 与 `{{IMAGE:xxx}}` 为 CID 内联图片。 |
| 邮件生成器 | `email_agent/email_generator.py` | 编排：读取客户 → 分析阶段 → 选择模板 → 调用 LLM 填充变量 → 模板引擎渲染 → 输出 `drafts.json`。 |
| 送达率管理 | `email_agent/deliverability.py` | 频率上限、随机延迟、相似度检测、SPF DNS 校验、白名单过滤。 |
| 发送器 | `email_agent/sender.py` | 通过 SMTP 发送 HTML + 内联图片，记录 `email_logs.csv`。 |
| 接收器 | `email_agent/receiver.py` | 通过 IMAP 采集回复，记录 `reply_logs.csv`。 |
| 日志器 | `email_agent/logger.py` | 初始化与追加写入日志文件。 |

## 4. 数据流

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────────┐
│  main.py    │────▶│ cli_controller│────▶│     data_store      │
│ (entry)     │     │ (interactive) │     │ (customers/logs)    │
└─────────────┘     └──────────────┘     └─────────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                        生成草稿流程                              │
│  data_store.load_customers()                                      │
│        │                                                          │
│        ▼                                                          │
│  interaction_analyzer.analyze(customer, history)                  │
│        │ 输出：stage, template_type, strategy                     │
│        ▼                                                          │
│  llm_client.complete(...) 填充模板变量                            │
│        │                                                          │
│        ▼                                                          │
│  template_engine.render(template_name, variables)                 │
│        │ 输出：html_body, images[(cid, path)]                     │
│        ▼                                                          │
│  data_store.save_drafts([draft, ...]) 写入 drafts.json            │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        审核流程                                  │
│  cli_controller.review_drafts()                                   │
│  逐条展示 subject + html_body（可选纯文本摘要）                   │
│  用户按键：Y 通过 / N 拒绝 / E 编辑                              │
│  data_store.update_draft_status(draft_id, status)                │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        发送流程                                  │
│  data_store.load_drafts(status='approved')                        │
│        │                                                          │
│        ▼                                                          │
│  deliverability.can_send(draft, send_history)                     │
│  （频率、相似度、SPF、白名单）                                   │
│        │                                                          │
│        ▼                                                          │
│  sender.send(draft)  HTML + 内联图片                              │
│        │                                                          │
│        ▼                                                          │
│  logger.log_email_send(...)                                       │
│        │                                                          │
│        ▼                                                          │
│  deliverability.wait_before_next() 随机延迟                       │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        回复采集流程                              │
│  receiver.check_replies() 读取 IMAP                               │
│  匹配已发送邮件（优先 Message-ID，回退 recipient）               │
│  logger.log_reply(...) 写入 reply_logs.csv                       │
└─────────────────────────────────────────────────────────────────┘
```

## 5. 关键接口定义

### 5.1 数据存储 `email_agent/data_store.py`

```python
def load_customers() -> list[dict]: ...
def load_email_logs() -> list[dict]: ...
def load_reply_logs() -> list[dict]: ...
def load_drafts(status: str | None = None) -> list[dict]: ...
def save_drafts(drafts: list[dict]) -> None: ...
def update_draft_status(draft_id: str, status: str) -> None: ...
def get_customer_history(customer_id: str) -> dict: ...
```

`drafts.json` 单条记录示例：

```json
{
  "draft_id": "20260803-001",
  "customer_id": "001",
  "email": "camgrado@gmail.com",
  "template": "initial_contact",
  "stage": "new_lead",
  "subject": "...",
  "html_body": "<html>...</html>",
  "text_body": "...",
  "images": [
    {"cid": "portfolio_grid_1", "path": "assets/images/portfolio_grid_1.jpg"}
  ],
  "personalization_note": "...",
  "review_status": "pending",
  "created_at": "2026-08-03 10:00:00"
}
```

### 5.2 LLM 客户端 `email_agent/llm_client.py`

```python
def complete(
    system_prompt: str,
    user_prompt: str,
    response_format: dict | None = None,
    temperature: float = 0.7,
) -> str: ...
```

支持通过 `.env` 配置：
- `LLM_API_KEY`
- `LLM_BASE_URL`（可选，默认 OpenAI）
- `LLM_MODEL`（默认 `gpt-5-mini`）

### 5.3 互动分析器 `email_agent/interaction_analyzer.py`

```python
def analyze(customer: dict, history: dict) -> dict:
    """
    返回：
    {
      "stage": "new_lead" | "contacted_no_reply" | "follow_up_no_reply" | "replied" | ...,
      "template_type": "initial_contact" | "follow_up" | "final_note",
      "strategy": "str",  # 给生成器的策略提示
      "reason": "str"     # 简短判定依据
    }
    """
```

实现策略：
1. 先按规则快速判定：有成功回复 → `replied`；有多次发送无回复 → `follow_up_no_reply`；有一次发送无回复 → `contacted_no_reply`；无发送记录 → `new_lead`。
2. 边界情况或新客户交由 LLM 根据客户画像输出 `stage` 与 `strategy`。

### 5.4 模板引擎 `email_agent/template_engine.py`

```python
def list_templates() -> list[str]: ...
def get_template_config(template_name: str) -> dict: ...
def render(template_name: str, variables: dict) -> tuple[str, list[dict]]:
    """
    返回：(html_body, images)
    html_body 中 {{IMAGE:xxx}} 已替换为 cid:xxx 引用。
    images 包含每个内联图片的 cid 与本地路径，供发送器构造 MIME。
    """
```

渲染规则：
- 普通变量 `{{var}}` 直接替换。
- 图片占位符 `{{IMAGE:portfolio_grid_1}}` 替换为 `<img src="cid:portfolio_grid_1" alt="...">`。
- 图片默认搜索路径：`assets/images/<name>.jpg/.png/.jpeg`。
- 若模板 `config.yaml` 声明了 `images` 列表但文件缺失，记录警告但不阻断（发送时跳过该图片）。

### 5.5 邮件生成器 `email_agent/email_generator.py`

```python
def generate_all(customers: list[dict] | None = None) -> list[dict]: ...
def generate_for_customer(customer: dict) -> dict: ...
```

生成步骤：
1. 调用 `interaction_analyzer.analyze` 得到 `stage` 与 `template_type`。
2. 读取对应模板 `config.yaml`，获取变量列表与规则。
3. 构造 system prompt（融合 `email_writing_skill.md` + `email_generation_prompt.md` + 模板规则）与 user prompt（客户信息 + 历史）。
4. 调用 `llm_client.complete` 让 LLM 返回 JSON（包含所有模板变量值）。
5. 调用 `template_engine.render` 生成 HTML。
6. 组装 `draft` 字典并追加到 `drafts.json`。

### 5.6 送达率管理 `email_agent/deliverability.py`

```python
def can_send(draft: dict, send_history: list[dict]) -> tuple[bool, str]: ...
def wait_before_next() -> None: ...
def check_spf(domain: str) -> bool: ...
def is_similar_to_recent(draft: dict, recent_drafts: list[dict], threshold: float = 0.9) -> bool: ...
```

策略（来自 `config/email_policy.md`）：
- 每日上限：50 封。
- 随机间隔：30 秒 ~ 10 分钟（demo 可配置为 30 秒 ~ 2 分钟）。
- 相似度：对过去 24 小时内已发送邮件文本计算相似度，超过阈值则阻止。
- SPF：发送前检查发件域名 SPF 记录，失败仅警告不阻断（避免网络问题导致完全不可用）。
- 白名单：`config.DEMO_MODE` 开启时仅允许 `ALLOWED_TEST_EMAILS`。

### 5.7 发送器 `email_agent/sender.py`

```python
def send_email(draft: dict) -> bool: ...
def process_queue(drafts: list[dict] | None = None) -> None: ...
```

重构要点：
- 输入从 `drafts.csv` 改为 `drafts.json`。
- 使用 `MIMEMultipart('related')` 包装 HTML 部分与内联图片（`MIMEImage` + `Content-ID`）。
- 保留 Message-ID 生成，用于回复追踪。
- 在 `process_queue` 中调用 `deliverability.can_send` 与 `wait_before_next`。

### 5.8 CLI 控制器 `email_agent/cli_controller.py`

```python
def run() -> None: ...
def menu_generate() -> None: ...
def menu_review() -> None: ...
def menu_send() -> None: ...
def menu_logs() -> None: ...
def menu_config() -> None: ...
```

菜单选项：
1. 生成草稿
2. 逐条审核
3. 发送已审核邮件
4. 检查回复
5. 查看发送/回复日志
6. 配置检查
7. 退出

## 6. 模块开发顺序（与 TASK.md 对齐）

按**一个模块一次提交**原则执行：

### 阶段一：基础架构重构与 CLI 交互界面
1. `email_agent/config.py` 扩展：新增 LLM、模板、草稿 JSON、assets 路径、频率限制常量。
2. `email_agent/data_store.py`：统一 CSV/JSON 数据读写。
3. `email_agent/llm_client.py`：LLM API 客户端。
4. `email_agent/cli_controller.py`：交互式 CLI。
5. `main.py` 重构：默认进入 CLI；保留 `--send` / `--check-replies` 兼容旧入口。

### 阶段二：模板引擎与富媒体支持
6. `email_agent/template_engine.py`：YAML/HTML 解析与图片占位符渲染。
7. `assets/images/` 目录初始化（README / .gitkeep）。
8. 调整 `data/drafts.json` 格式并迁移现有 `drafts.csv` 数据。

### 阶段三：智能分析与闭环生成
9. `email_agent/interaction_analyzer.py`：客户阶段分析。
10. `email_agent/email_generator.py`：端到端草稿生成。
11. CLI 审核功能集成。

### 阶段四：送达率优化与发送队列
12. `email_agent/deliverability.py`：频率/延迟/相似度/SPF。
13. `email_agent/sender.py` 重构：HTML + 内联图片 + 队列。
14. `email_agent/receiver.py` 重构：优先 Message-ID 匹配。
15. `email_agent/logger.py` 扩展：记录更完整字段（如 html_length、image_count）。

## 7. 验证策略

每个模块完成后进行**黑盒测试**：

| 模块 | 验证命令 / 方法 |
|------|----------------|
| `data_store` | `python -c "from email_agent.data_store import *; print(load_customers()[:1])"` |
| `llm_client` | CLI → 配置检查 → 测试 LLM 调用返回非空文本。 |
| `cli_controller` | `python main.py` 能看到菜单，输入选项可跳转。 |
| `template_engine` | `python -c "from email_agent.template_engine import render; print(render('initial_contact', {...}))"` |
| `interaction_analyzer` | 为同一客户构造不同历史，验证阶段输出符合预期。 |
| `email_generator` | CLI → 生成草稿 → 检查 `drafts.json` 字段完整。 |
| `deliverability` | 连续调用 `can_send` 与 `wait_before_next`，验证延迟在区间内。 |
| `sender` | 发送一封测试邮件到白名单邮箱，确认收到 HTML + 图片。 |
| `receiver` | 对测试收件箱运行 `python main.py --check-replies`，确认回复被记录。 |
| 端到端 | 完整跑通：生成 → 审核 → 发送 → 查回复。 |

## 8. 关键决策与约束

1. **草稿存储格式**：采用 `data/drafts.json` 替代原 `drafts.csv`，因为需要保存 HTML 源码与图片映射；`sender.py` 相应改为读取 JSON。
2. **模板变量语言**：当前三套模板均为英文。中文客户仍由 LLM 在变量层面生成中文内容，模板 HTML 结构与落款保持英文框架；后续可新增中文模板。
3. **相似度算法**：使用 `difflib.SequenceMatcher` 简单文本相似度，后续可升级为国密/hash/simhash。
4. **SPF 检查**：使用 `dns.resolver` 查询 `TXT` 记录，失败仅作警告，不阻断发送，防止 DNS 故障导致业务完全停滞。
5. **Demo 白名单**：保留 `config.DEMO_MODE` 与 `ALLOWED_TEST_EMAILS`，默认开启。
6. **`.env` 敏感信息**：LLM API 密钥与邮箱密码均从 `.env` 读取，永不入代码库。

## 9. 与现有代码的继承关系

- 保留 `email_agent/config.py`、`email_agent/logger.py` 的接口与路径约定。
- `sender.py` 与 `receiver.py` 的核心 SMTP/IMAP 逻辑保留，仅做输入格式与 HTML 内联图片改造。
- `scripts/generate_drafts.py` 被 `email_agent/email_generator.py` 替代，可在升级完成后移除或归档。
- `data/drafts/drafts.csv` 在首次升级时读取并迁移到 `data/drafts.json`，之后新系统只写 JSON。
