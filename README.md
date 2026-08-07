# AI Sales Email Agent

面向家具设计行业（GRADO CONTRACT）的 AI 销售邮件自动化 Demo。从 `data/customers.csv` 读取客户，基于已确认的 HTML 邮件模板做**本地变量替换**生成邮件草稿，经浏览器预览 + 终端审核后，通过腾讯企业邮箱 SMTP 发送，再用 IMAP 采集回复。

> **注意**：旧版 `README.md` 描述的 Manus 沙盒 + `drafts.csv` 手工流程已废弃。当前版本为应用内 LLM 直连（**仅用于模板结构化**）、草稿主存储为 `data/drafts.json`、入口为交互式 CLI。

---

## 目录

- [前期环境及权限部署准备](#前期环境及权限部署准备)
- [安装与启动](#安装与启动)
- [核心交互流程](#核心交互流程)
- [后期可修改和调整的内容](#后期可修改和调整的内容)
- [模板导入工作流](#模板导入工作流)
- [多模型配置](#多模型配置)
- [状态栏说明](#状态栏说明)
- [客户清单规则](#客户清单规则)
- [常见问题](#常见问题)
- [目录结构](#目录结构)

---

## 前期环境及权限部署准备

### 1. 基础环境

- Python 3.10+
- 建议使用虚拟环境
- 用于预览的桌面环境（可选）：项目使用 Playwright Chromium 自动打开预览；无桌面环境时会自动生成 PNG 截图或打印临时文件路径

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

> `httpx==0.27.2` 的 pin 必须保留，`openai==1.46.0` 与 `httpx 0.28+` 不兼容，否则会报 `Client.__init__() got an unexpected keyword argument 'proxies'`。

> 模板导入功能依赖 `python-docx`（Word 文档解析）与 `pdfplumber`（PDF 文本提取），两者均已包含在 `requirements.txt` 中，上面的命令会一并安装。若你使用的是旧环境或需要单独补装，执行：`pip install python-docx pdfplumber`。

### 2. 腾讯企业邮箱权限准备

1. 登录腾讯企业邮箱网页版。
2. 进入「设置 → 账户 → 客户端专用密码」，生成一个**客户端授权码**。
3. 确保 SMTP/IMAP 服务已开启（默认端口：SMTP 465，IMAP 993）。
4. 在 `email_agent/config.py` 的 `ALLOWED_TEST_EMAILS` 中填入你的测试收件邮箱。

### 3. LLM API 准备

LLM 仅用于**模板导入时的结构识别**，不再参与每封邮件的生成。配置一个 OpenAI 兼容接口即可。详见下文 [多模型配置](#多模型配置)。

### 4. 配置文件 `.env`

复制 `.env.example` 为 `.env` 并填写：

```env
EMAIL_ACCOUNT=info@gradocontract.com
EMAIL_PASSWORD=your_client_auth_code

LLM_API_KEY=your_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

SENDER_NAME=Your Name
SENDER_TITLE=Partnership Manager
SENDER_COMPANY=GRADO CONTRACT
SENDER_MARKET_REGION=Global
```

`.env` 已加入 `.gitignore`，切勿提交。

---

## 安装与启动

```bash
source .venv/bin/activate
python main.py
```

**必须在真实交互式终端中运行**，菜单依赖 `input()`，后台/非交互 shell 会报 `EOFError`。

启动后顶部会显示红/黄/绿状态栏，菜单选项如下：

| 选项 | 功能 |
|------|------|
| `1` | 生成草稿 |
| `2` | 审核草稿（浏览器预览 + 终端 Y/N/S/E/Q） |
| `3` | 发送已审核邮件（Ctrl+C 暂停） |
| `4` | 检查回复（浏览器列表 + 终端 S/R/Q） |
| `5` | 查看日志 |
| `6` | 导入 / 确认邮件模板 |
| `S` | 设置（发送者信息 / 切换模型 / 切换 skill / 配置检查） |
| `D` | 删除草稿 |
| `0` | 退出 |

---

## 核心交互流程

### 1. 导入并确认邮件模板（菜单 6）

首次使用或更新模板时，必须完成此步骤：

1. 将模板源文件（`.md` / `.docx` / `.pdf`）放入 `templates/import/`。
2. 运行菜单 6，系统会检测新文件并提示导入。
3. 系统自动归档旧模板到 `templates/archive/<template_name>/YYYY/MM/DD/<HHMMSS>/`。
4. 系统将源文件解析为 Markdown 后，**调用一次 LLM** 识别邮件主体、图片/文件/链接位置、可替换变量，输出中英双语 HTML 模板。
5. 本地脚本写入 `templates/email/<name>/`：
   - `template.html`（源语言）
   - `template_en.html` 或 `template_cn.html`（另一语言）
   - `config.yaml`（变量/图片/文件清单）
6. 浏览器自动打开模板预览；在终端输入 `Y` 确认后，模板才正式启用。

**未确认模板时，菜单 1（生成）和菜单 3（发送）会被红色状态栏阻断。**

### 2. 生成草稿（菜单 1）

- 系统读取 `data/customers.csv`。
- `name` 以 `#` 开头的客户会被跳过。
- 根据客户 `location` 判断邮件语言：中国大陆默认中文；香港、台湾、海外默认英文；可用 `(中文)` / `(英文)` 后缀强制覆盖。
- **不再调用 LLM**：从 `templates/sender_profile.md` 与 `customers.csv` 硬性映射变量，直接替换模板占位符。
- 每封草稿记录 `rendered_by: "local"`。
- 支持 Ctrl+C 暂停，重新运行会从断点续跑。

### 3. 审核草稿（菜单 2）

每封草稿会自动在浏览器中打开完整 HTML 预览（图片内联为 base64），终端显示：

```
[Y] 通过  [N] 拒绝  [S] 跳过  [E] 编辑  [Q] 退出审核
```

### 4. 发送已审核邮件（菜单 3）

- 仅发送 `review_status` 为 `approved` 的草稿。
- 发送前经过风控检查：Demo 白名单、日发送上限、24h 相似度、邮箱凭证。
- 发送过程中底部持续显示 `Ctrl+C to pause`；中断后会在 `data/sending_state.json` 中保存进度，重新运行即可续跑。
- `name` 以 `#` 开头的客户不会被发送。

### 5. 检查回复（菜单 4）

- 连接 IMAP 收件箱，匹配 `In-Reply-To` Message-ID 或 `Re:` / `回复:` 主题。
- 浏览器列表展示原邮件主题、回复主题、发件人、时间及前 50 词摘要。
- 终端选择 `S` 保存到 `reply_logs.csv`，`R` 刷新，`Q` 退出。

---

## 后期可修改和调整的内容

### 寄件人身份

推荐通过菜单 `S` → `1` 编辑发送者信息，保存到 `templates/sender_profile.md`。也可直接编辑该文件：

```markdown
---
sender_name: "张三"
sender_title: "商务拓展经理"
sender_company: "GRADO CONTRACT"
sender_market_region: "大中华区"
sender_phone: "+86 138 0000 0000"
sender_email: "zhangsan@gradodesign.hk"
---
```

此文件优先级高于 `.env` 中的同名变量。

### 客户清单

直接编辑 `data/customers.csv`。字段说明：

| 字段 | 说明 |
|------|------|
| `id` | 客户唯一编号 |
| `name` | 姓名；以 `#` 开头则跳过生成/发送 |
| `company` | 公司名 |
| `position` | 职位 |
| `email` | 收件邮箱 |
| `industry` | 行业 |
| `location` | 地区；可加 `(中文)` / `(英文)` 后缀覆盖语言 |
| `company_type` | 公司类型画像 |

### 邮件模板

- 激活模板存放于 `templates/email/<name>/`（`config.yaml` + `template.html` + 双语变体）。
- 更新模板请通过菜单 6 导入，系统会自动归档旧版本。
- 模板占位符统一使用**大写下划线**：
  - 发送者：`{{SENDER_NAME}}`、`{{SENDER_TITLE}}`、`{{SENDER_COMPANY}}` 等
  - 客户：`{{CUSTOMER_FIRST_NAME}}`、`{{CUSTOMER_NAME}}`、`{{CUSTOMER_COMPANY}}` 等
  - 图片：`{{IMAGE:hero}}`
  - 文件下载链接：`{{FILE:catalog_pdf}}`

### 风控参数

编辑 `email_agent/config.py`：

| 常量 | 默认值 | 说明 |
|------|--------|------|
| `MAX_DAILY_SENDS` | 50 | 每日发送上限 |
| `MIN_DELAY_SECONDS` | 30 | 最小发送间隔 |
| `MAX_DELAY_SECONDS` | 120 | 最大发送间隔 |
| `SIMILARITY_THRESHOLD` | 0.90 | 24h 相似度阈值 |
| `ALLOWED_TEST_EMAILS` | 3 个测试邮箱 | Demo 白名单 |

### LLM 模型

- 通过 `.env` 的 `MODEL_*` 编号块配置多个模型（详见 [多模型配置](#多模型配置)）。
- 运行时通过菜单 `S` → `2` 切换，选择持久化到 `data/settings.json`。

### Skill 模式

菜单 `S` → `3` 可在 `full` 与 `concise` 之间切换。当前 skill 文件仅在模板导入时作为参考，不再用于每封邮件生成。

### 清理状态

如需重置生成/发送进度，可删除对应 JSON 文件：

```bash
rm data/generation_state.json
rm data/sending_state.json
rm data/template_import_state.json
```

---

## 模板导入工作流

```
templates/import/<file>.md|docx|pdf
        │
        ▼
extract_to_markdown()           → Markdown 中间层
        │
        ▼
structure_template_with_llm()   → {subject_template, cn_html, en_html, variables, images, files}
        │
        ▼
write_structured_template()     → templates/email/<name>/
                                    ├── config.yaml
                                    ├── template.html
                                    └── template_en.html / template_cn.html
        │
        ▼
archive_current_template()      → templates/archive/<name>/YYYY/MM/DD/<HHMMSS>/
        │
        ▼
浏览器预览 + 终端确认 → template_confirmed = true
```

导入前若当前模板仍有未完成的生成/审核/发送任务，系统会弹出黄色警告并要求二次确认。

---

## 多模型配置

`.env` 支持编号模型块，格式如下：

```env
MODEL_1_NAME=moonshot
MODEL_1_BASE_URL=https://api.moonshot.cn/v1
MODEL_1_API_KEY=sk-...
MODEL_1_MODEL=kimi-k2.6
MODEL_1_TEMPERATURE=1.0

MODEL_2_NAME=openai
MODEL_2_BASE_URL=https://api.openai.com/v1
MODEL_2_API_KEY=sk-...
MODEL_2_MODEL=gpt-4o-mini
MODEL_2_TEMPERATURE=0.7
```

- 无编号块时自动回退到旧版单模型变量 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`。
- 菜单 `S` → `2` 会显示 `[编号] 模型名 (模型ID)`，输入编号即可切换。
- 当前选择保存在 `data/settings.json` 的 `active_model_index`。

---

## 状态栏说明

| 颜色 | 含义 | 常见原因 |
|------|------|----------|
| 🔴 红色 | 无法生成/发送 | 缺少 `.env` 配置、无客户、无模板、模板未确认 |
| 🟡 黄色 | 可以操作，但有未完成任务 | 有新模板待导入、有 pending/approved 草稿、发送暂停中 |
| 🟢 绿色 | 全部就绪 | 模板已确认且无剩余工作 |

---

## 客户清单规则

- `name` 以 `#` 开头：跳过生成和发送，但历史发送记录的回复仍会被采集。
- `location` 语言覆盖：
  - `北京`、`上海`、`广州` 等 → 中文
  - `香港`、`台湾`、`New York` 等 → 英文
  - `香港 (中文)`、`Tokyo (English)` → 强制使用括号内语言

---

## 常见问题

**Q: 启动后状态栏红色，提示 Template not confirmed。**  
A: 先通过菜单 6 导入/确认模板。

**Q: 浏览器没有自动弹出预览。**  
A: 项目使用 Playwright Chromium。无桌面环境时会自动生成 `data/latest_preview.png` 并打印路径；也可在 `.env` 中设置 `BROWSER` 作为兜底。

**Q: 导入模板时 LLM 返回空或报错 `Expecting value: line 1 column 1`。**  
A: 若使用 Moonshot，确保 `LLM_BASE_URL` 含 `moonshot`；如使用其他厂商，确保其支持 `json_schema` 或改走 prompt 注入。清理 `__pycache__`：

```bash
find email_agent -name "__pycache__" -exec rm -rf {} +
```

**Q: 邮件发送被拦截。**  
A: Demo 模式下只允许发送到 `ALLOWED_TEST_EMAILS`；检查收件邮箱是否在白名单。

**Q: 草稿中出现未替换的 `{{VAR}}`。**  
A: 检查 `templates/sender_profile.md` 与 `data/customers.csv` 是否包含对应字段；重新导入模板以生成最新占位符。

**Q: 文件下载链接在收件人那里无法点击。**  
A: `{{FILE:name}}` 默认渲染为本地 `file://` 链接，仅方便本地预览。发送前请替换为公网可访问的 URL，或改用邮件附件方式。

---

## 目录结构

```
AI_sales_email_agent/
├── data/                       # 运行时数据（gitignore）
│   ├── customers.csv
│   ├── drafts.json
│   ├── email_logs.csv
│   ├── reply_logs.csv
│   ├── settings.json
│   ├── generation_state.json
│   ├── sending_state.json
│   └── template_import_state.json
├── docs/
│   ├── PRD.md                  # 产品需求（只读）
│   ├── architecture.md         # 架构设计
│   └── CONFIG_GUIDE.md         # 详细配置指南
├── email_agent/                # 核心代码
│   ├── config.py
│   ├── cli_controller.py
│   ├── sender_profile_editor.py
│   ├── data_store.py
│   ├── llm_client.py
│   ├── interaction_analyzer.py
│   ├── template_engine.py
│   ├── template_importer.py
│   ├── email_generator.py
│   ├── preview.py
│   ├── status.py
│   ├── deliverability.py
│   ├── sender.py
│   ├── receiver.py
│   └── logger.py
├── templates/
│   ├── email/                  # 激活的邮件模板
│   ├── import/                 # 用户拖入的模板源文件
│   ├── archive/                # 历史模板归档
│   └── sender_profile.md       # 寄件人身份配置
├── assets/
│   ├── images/                 # 模板内联图片
│   └── files/                  # 模板文件下载占位
├── prompts/
│   ├── email_generation_prompt.md
│   └── template_import_prompt.md
├── skills/
│   ├── email_writing_skill.md
│   └── email_writing_skill_concise.md
├── main.py
├── README.md
├── CHANGELOG.md
├── requirements.txt
└── .env.example
```

---

如需更详细的配置参数、调试命令与模块测试示例，请参考 [`docs/CONFIG_GUIDE.md`](docs/CONFIG_GUIDE.md)。
