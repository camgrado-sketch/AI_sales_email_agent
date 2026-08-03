# AI Sales Email Agent — 配置与调试指南

> 本文档基于当前代码自动生成，涵盖环境配置、输入参数、运行方式与常见问题排查。

---

## 一、环境配置（`.env`）

项目根目录下创建 `.env` 文件（已从 `.env.example` 复制并填写真实值）。**`.env` 已加入 `.gitignore`，切勿提交到 Git。**

### 必填项

| 变量 | 说明 | 获取方式 |
|------|------|----------|
| `EMAIL_ACCOUNT` | 腾讯企业邮箱地址 | 你的企业邮箱账号，如 `info@gradocontract.com` |
| `EMAIL_PASSWORD` | 客户端授权码 | **不是网页登录密码**。登录企业邮箱网页版 → 设置 → 账户 → 客户端专用密码 |
| `LLM_API_KEY` | LLM API 密钥 | OpenAI 或兼容平台的 API Key |

### 可选项

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_BASE_URL` | `https://api.openai.com/v1` | 若使用第三方兼容接口（如 Azure、中转站），填写其 base URL |
| `LLM_MODEL` | `gpt-5-mini` | 模型名称 |
| `SENDER_NAME` | `[Your Name]` | 发件人姓名，会填入邮件模板变量 `{{sender_name}}` |
| `SENDER_TITLE` | `Partnership Manager` | 发件人头衔，会填入模板变量 `{{sender_title}}` |
| `SENDER_MARKET_REGION` | `Global` | 发件人负责区域，会填入模板变量 `{{market_region}}` |

### 快速检查

```bash
python main.py --init        # 初始化日志文件
python main.py               # 进入交互菜单 → 选 6（配置检查）
```

---

## 二、客户数据输入（`data/customers.csv`）

系统读取该文件作为 CRM 数据源。格式必须与 `data/customers_template.csv` 保持一致。

### 字段说明

| 字段 | 示例 | 用途 |
|------|------|------|
| `id` | `001` | 客户唯一标识 |
| `name` | `王晨` | 客户姓名 |
| `company` | `字节跳动` | 公司名 |
| `position` | `采购经理` | 职位（用于 LLM 判断切入点） |
| `email` | `wang.chen@example.com` | 收件邮箱 |
| `industry` | `互联网科技` | 行业 |
| `location` | `北京 中国` | 地区（LLM 据此决定中英文） |
| `company_type` | `甲方（潜在客户）采购` | 公司类型画像 |

### 修改方法

1. 直接用 Excel / Numbers / VS Code 编辑 `data/customers.csv`
2. 新增客户直接在末尾追加一行
3. **不要在 CSV 里再写 `review_status` 列**（旧版逻辑已废弃，审核改在交互 CLI 里完成）

---

## 三、运行方式

### 方式 1：交互式 CLI（推荐）

```bash
python main.py
```

菜单选项：

| 选项 | 功能 | 关键输入/操作 |
|------|------|---------------|
| `1` | 生成草稿 | 读取 `customers.csv` + 历史日志 → 调用 LLM 生成 `drafts.json` |
| `2` | 逐条审核 | 展示每封邮件的 `subject`、`body preview`、`personalization_note`；按 `Y` 通过 / `N` 拒绝 / `E` 编辑 / `S` 跳过 |
| `3` | 发送已审核邮件 | 读取 `drafts.json` 中 `approved`/`pass` 状态的草稿，经送达率检查后调用 SMTP 发送 |
| `4` | 检查回复 | 连接 IMAP 收件箱，匹配已发邮件的 Message-ID，记录到 `reply_logs.csv` |
| `5` | 查看日志 | 展示最近 5 条发送/回复记录 |
| `6` | 配置检查 | 打印当前 `.env` 加载结果与路径信息 |
| `0` | 退出 | — |

### 方式 2：命令行参数（兼容旧版 / 脚本自动化）

```bash
python main.py --init          # 仅初始化日志文件
python main.py --send          # 直接发送已审核草稿（等同于菜单选项 3）
python main.py --check-replies # 直接检查回复（等同于菜单选项 4）
```

---

## 四、模板系统与富媒体

### 模板目录结构

```
templates/email/
├── initial_contact/          # 新客户首封邮件
│   ├── config.yaml           # 模板配置（变量列表、规则）
│   └── template.html         # HTML 模板
├── follow_up/                # 跟进邮件
└── final_note/               # 最后一封尝试
```

### 模板变量

在 `template.html` 中使用 `{{变量名}}` 占位，由 LLM 填充。例如：

```html
<p>Dear {{customer_first_name}},</p>
<p>My name is {{sender_name}}...</p>
```

### 内联图片

使用 `{{IMAGE:图片名}}`（不含扩展名），系统会自动到 `assets/images/` 匹配 `.jpg/.png/.jpeg/.gif/.webp`：

```html
<div class="image-grid">
  {{IMAGE:portfolio_grid_1}}
  {{IMAGE:portfolio_grid_2}}
</div>
```

**添加新图片**：直接把图片丢进 `assets/images/`，命名与模板占位符一致即可，无需改代码。

### 模板选择逻辑

系统根据客户销售阶段自动匹配：

| 销售阶段 | 触发条件 | 选用模板 |
|----------|----------|----------|
| `new_lead` | 无发送记录 | `initial_contact` |
| `contacted_no_reply` | 已发 1 封，无回复 | `follow_up` |
| `follow_up_no_reply` | 已发 ≥2 封，无回复 | `final_note` |
| `replied` | 有回复记录 | `follow_up` |

如需强制使用特定模板，可在调用 `email_generator.generate_for_customer()` 时传入 `template_name` 参数（需二次开发）。

---

## 五、发送策略与安全设置

### Demo 模式白名单

`email_agent/config.py` 中 `DEMO_MODE = True` 时，**只允许发送到 `ALLOWED_TEST_EMAILS` 列表中的地址**。误发真实客户会被拦截并记录日志。

**修改白名单**：编辑 `email_agent/config.py` 里的 `ALLOWED_TEST_EMAILS` 数组，或在 `.env` 中增加自定义逻辑（需二次开发）。

### 发送频率控制

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MAX_DAILY_SENDS` | `50` | 每日成功发送上限 |
| `MIN_DELAY_SECONDS` | `30` | 每封邮件最小间隔 |
| `MAX_DELAY_SECONDS` | `120` | 每封邮件最大间隔（Demo） |

**调整方法**：直接修改 `email_agent/config.py` 中的常量，然后重启脚本。

### SPF 检查

发送前会自动检查发件域名的 SPF TXT 记录。若缺失，终端会打印警告，**但不会阻断发送**（防止 DNS 故障导致业务中断）。

---

## 六、调试技巧

### 1. 逐模块独立测试

无需跑完整流程，可直接在 Python 中测试单个模块：

```bash
source .venv/bin/activate
PYTHONPATH=$(pwd) python -c "
from email_agent import data_store
print(data_store.load_customers())
"
```

常用测试片段：

```python
# 测试模板渲染
from email_agent import template_engine
html, images = template_engine.render("follow_up", {
    "customer_first_name": "Test",
    "company_name": "Demo Corp",
    "pain_point_solution": "Test solution.",
    "sender_name": "Alex"
})
print(html)

# 测试客户阶段分析
from email_agent import interaction_analyzer, data_store
customer = data_store.load_customers()[0]
print(interaction_analyzer.analyze(customer))

# 测试送达率
from email_agent import deliverability, data_store
allowed, reason = deliverability.can_send(
    {"email": "unknown@example.com", "text_body": "hello"},
    data_store.load_email_logs()
)
print(allowed, reason)
```

### 2. 查看草稿内容

`data/drafts.json` 是结构化 JSON，可直接查看：

```bash
cat data/drafts.json | python -m json.tool
```

关键字段：
- `review_status`: `pending` / `approved` / `rejected`
- `html_body`: 最终发送的 HTML 源码
- `text_body`: 纯文本预览（用于 CLI 审核展示）
- `images`: 内联图片 CID 与路径映射
- `personalization_note`: LLM 生成的个性化策略说明

### 3. 邮件发送日志

`data/email_logs.csv` 记录每一封邮件：

| 字段 | 说明 |
|------|------|
| `status` | `success` / `failed` |
| `error_msg` | 失败原因或成功时的 `MsgID` |
| `message_id` | SMTP 返回的真实 Message-ID（用于回复追踪） |

### 4. LLM 生成调试

若草稿生成失败，检查：
1. `.env` 中 `LLM_API_KEY` 是否已设置
2. 网络是否可连通 LLM 服务端
3. 模型名称是否有效（默认 `gpt-5-mini`，若平台不支持需改成 `gpt-4o-mini` 等）

临时调高可见性的方法（在 `email_agent/email_generator.py` 的 `generate_for_customer` 中加 `print`）：

```python
print("LLM raw response:", raw)
```

### 5. SMTP 发送调试

若发送失败：
1. 确认 `EMAIL_PASSWORD` 是**客户端授权码**，不是网页登录密码
2. 确认腾讯企业邮箱未开启二次验证且已生成专用密码
3. 检查 `email_logs.csv` 中的 `error_msg` 字段
4. Demo 模式下确认收件地址在白名单中

### 6. IMAP 回复调试

若无法采集回复：
1. 确认同一套 `EMAIL_ACCOUNT` / `EMAIL_PASSWORD` 可登录 IMAP
2. 检查收件箱是否有 `Re:` / `回复:` 开头的邮件
3. 检查 `email_logs.csv` 中对应邮件是否有 `message_id`（旧版发送的记录可能缺失）

---

## 七、常见问题速查

| 现象 | 原因 | 解决 |
|------|------|------|
| `ModuleNotFoundError: No module named 'email_agent'` | 未设置 `PYTHONPATH` | 在项目根目录运行，或 `export PYTHONPATH=$(pwd)` |
| `LLM_API_KEY is not set in .env` | 未配置 LLM 密钥 | 在 `.env` 中添加 `LLM_API_KEY=...` |
| `Blocked by Demo Mode` | 收件人不在白名单 | 将测试邮箱加入 `email_agent/config.py` 的 `ALLOWED_TEST_EMAILS` |
| 生成草稿很慢/失败 | LLM 网络或模型不可用 | 检查 `LLM_BASE_URL` 和 `LLM_MODEL`，或更换 API 提供商 |
| 邮件正文没有图片 | `assets/images/` 下缺少对应文件 | 按模板 `config.yaml` 中的 `images` 列表放置图片 |
| `drafts.json` 被覆盖 | `generate_all()` 默认合并而非覆盖 | 如需彻底清空，手动删除 `data/drafts.json` 后重新生成 |

---

## 八、扩展开发提示

- **新增模板**：在 `templates/email/` 下新建目录，放入 `config.yaml` + `template.html`，系统会自动识别
- **新增字段**：如需在 `customers.csv` 中加字段，修改 `email_generator.py` 中 `_build_user_prompt` 即可传入 LLM
- **切换数据库**：当前用 CSV/JSON，如需迁移到 SQLite，重点替换 `email_agent/data_store.py` 的实现层

---

如有其他问题，可直接在交互菜单中选 **6. Configuration check** 快速核对当前环境配置。
