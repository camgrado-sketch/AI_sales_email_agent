# AI Sales Email Agent — 配置与调试指南

> 本文档面向实际使用和维护本系统的人，覆盖环境部署、权限准备、可调整配置、模板管理、运行调试与常见问题。

---

## 一、前期环境与权限部署准备

### 1.1 Python 环境

- Python 3.10+
- 建议使用虚拟环境
- 需要能打开浏览器的桌面环境用于预览；WSL/无桌面环境会回退为打印临时文件路径

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> **注意**：`httpx==0.27.2` 的 pin 必须保留。`openai==1.46.0` 与 `httpx 0.28+` 不兼容，会报 `Client.__init__() got an unexpected keyword argument 'proxies'`。

### 1.2 腾讯企业邮箱权限

1. 登录腾讯企业邮箱网页版。
2. 进入「设置 → 账户 → 客户端专用密码」。
3. 生成**客户端授权码**（不是网页登录密码）。
4. 确认 SMTP/IMAP 已开启：
   - SMTP: `smtp.exmail.qq.com:465`
   - IMAP: `imap.exmail.qq.com:993`
5. 若使用 Demo 模式，把测试收件邮箱加入 `email_agent/config.py` 的 `ALLOWED_TEST_EMAILS` 白名单。

### 1.3 LLM API 权限

准备至少一个 OpenAI 兼容 API：

- 获取 API Key。
- 记录 base URL（如 `https://api.openai.com/v1`、`https://api.moonshot.cn/v1`）。
- 记录模型 ID（如 `gpt-4o-mini`、`kimi-k2.6`）。

### 1.4 创建 `.env`

复制 `.env.example` 为 `.env` 并填写：

```bash
cp .env.example .env
```

`.env` 已加入 `.gitignore`，切勿提交。

---

## 二、`.env` 配置详解

### 2.1 邮箱相关（必填）

| 变量 | 说明 | 示例 |
|------|------|------|
| `EMAIL_ACCOUNT` | 腾讯企业邮箱地址 | `info@gradocontract.com` |
| `EMAIL_PASSWORD` | 客户端授权码 | `xxxxxxxxxxxxxxxx` |

### 2.2 寄件人身份（可选，会被 `templates/sender_profile.md` 覆盖）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SENDER_NAME` | 寄件人姓名 | `[Your Name]` |
| `SENDER_TITLE` | 寄件人职位 | `Partnership Manager` |
| `SENDER_MARKET_REGION` | 负责市场区域 | `Global` |
| `SENDER_PHONE` | 联系电话 | `（空）` |
| `SENDER_EMAIL` | 联系邮箱 | 默认与 `EMAIL_ACCOUNT` 相同 |

推荐把这些信息集中到 `templates/sender_profile.md`，非技术人员可直接改 Markdown 文件。

### 2.3 单模型配置（旧版，兼容）

当 `.env` 中没有 `MODEL_*` 编号块时，系统回退使用以下变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | LLM API Key | 必填 |
| `LLM_BASE_URL` | OpenAI 兼容接口地址 | `https://api.openai.com/v1` |
| `LLM_MODEL` | 模型 ID | `gpt-4o-mini` |
| `ACTIVE_MODEL_INDEX` | 可选，强制当前模型索引 | `0` |

### 2.4 多模型配置（推荐）

`.env` 支持按编号配置多个模型，运行时通过菜单 7 切换：

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

MODEL_3_NAME=deepseek
MODEL_3_BASE_URL=https://api.deepseek.com/v1
MODEL_3_API_KEY=sk-...
MODEL_3_MODEL=deepseek-chat
MODEL_3_TEMPERATURE=0.7
```

- 每个模型必须包含 `NAME`、`API_KEY`、`MODEL`。
- `BASE_URL` 为空时默认走 OpenAI 官方地址。
- `TEMPERATURE` 为空时默认 `0.7`。
- `ACTIVE_MODEL_INDEX` 可强制指定启动时的模型索引（优先级高于 `settings.json`）。
- 菜单 7 会显示 `[编号] 模型名 (模型ID)`，输入编号即可切换；当前选择写入 `data/settings.json` 的 `active_model_index`。

### 2.5 快速检查

```bash
source .venv/bin/activate
python main.py
# 进入菜单 6. Configuration check
```

---

## 三、`templates/sender_profile.md` 寄件人身份配置

新建/编辑 `templates/sender_profile.md`：

```markdown
---
sender_name: "张三"
sender_title: "商务拓展经理"
sender_market_region: "大中华区"
sender_phone: "+86 138 0000 0000"
sender_email: "zhangsan@gradocontract.com"
---

（以下可补充个人简介、签名等，供系统或 LLM 参考，不强制使用）
```

- 该文件优先级高于 `.env` 中的 `SENDER_*` 变量。
- 字段为空时会回退到 `.env` 默认值。
- 修改后无需重启，重新生成草稿即可生效。

---

## 四、`data/settings.json` 字段说明

运行时持久化设置：

```json
{
  "skill_mode": "concise",
  "active_model_index": 0,
  "template_confirmed": false,
  "template_confirmed_at": null
}
```

| 字段 | 说明 | 修改方式 |
|------|------|----------|
| `skill_mode` | `full` 或 `concise` | 菜单 9 |
| `active_model_index` | 当前激活模型的索引 | 菜单 7 |
| `template_confirmed` | 模板是否已确认 | 菜单 8 |
| `template_confirmed_at` | 确认时间（ISO 格式） | 自动写入 |

**警告**：除调试外不建议手动改此文件，可能破坏状态一致性。

---

## 五、客户数据输入（`data/customers.csv`）

### 5.1 字段说明

| 字段 | 示例 | 用途 |
|------|------|------|
| `id` | `001` | 客户唯一标识 |
| `name` | `王晨` | 姓名；以 `#` 开头则跳过生成/发送 |
| `company` | `字节跳动` | 公司名 |
| `position` | `采购经理` | 职位 |
| `email` | `wang.chen@example.com` | 收件邮箱 |
| `industry` | `互联网科技` | 行业 |
| `location` | `北京 中国` | 地区，决定邮件语言 |
| `company_type` | `甲方（潜在客户）采购` | 公司类型画像 |

### 5.2 修改方法

1. 用 Excel / Numbers / VS Code 编辑 `data/customers.csv`。
2. 新增客户直接在末尾追加一行。
3. 不要在 CSV 中再写 `review_status` 列（旧版逻辑已废弃）。

### 5.3 跳过规则

- 若 `name` 以 `#` 开头，则该客户在生成和发送阶段被跳过。
- 已发送过的邮件若产生回复，仍会在菜单 4 正常采集。

### 5.4 语言判定规则

| `location` 示例 | 默认语言 | 说明 |
|-----------------|----------|------|
| `北京`、`上海`、`广州` | 中文 | 中国大陆 |
| `香港`、`台湾`、`Taipei` | 英文 | 香港/台湾默认英文 |
| `New York`、`London` | 英文 | 海外 |
| `香港 (中文)` | 中文 | 括号后缀强制覆盖 |
| `上海 (English)` | 英文 | 括号后缀强制覆盖 |

支持的覆盖写法：`(中文)`、`(Chinese)`、`(英文)`、`(English)`，不区分大小写。

---

## 六、模板系统与导入工作流

### 6.1 激活模板目录

```
templates/email/
├── initial_contact/          # 新客户首封邮件
│   ├── config.yaml           # 模板变量与规则
│   ├── template.html         # 默认模板
│   ├── template_cn.html      # 中文版（如存在）
│   └── template_en.html      # 英文版（如存在）
└── ...
```

### 6.2 模板变量

在 HTML 中使用 `{{变量名}}` 占位，由 LLM 填充：

```html
<p>Dear {{customer_first_name}},</p>
<p>My name is {{sender_name}}, {{sender_title}} at GRADO CONTRACT.</p>
```

### 6.3 内联图片

使用 `{{IMAGE:图片名}}`（不含扩展名），系统会自动到 `assets/images/` 匹配 `.jpg/.png/.jpeg/.gif/.webp`：

```html
<div class="image-grid">
  {{IMAGE:portfolio_grid_1}}
  {{IMAGE:portfolio_grid_2}}
</div>
```

添加新图片：直接放入 `assets/images/`，命名与模板占位符一致，无需改代码。

### 6.4 模板导入工作流（菜单 8）

1. 将模板源文件（`.md` / `.docx` / `.pdf`）放入 `templates/import/`。
2. 运行菜单 8，系统检测新文件并列出。
3. 选择要导入的文件，输入模板名称（默认从文件名推断）。
4. 如果当前模板仍有未完成的生成/审核/发送任务，系统会黄色警告并要求二次确认。
5. 系统自动：
   - 把当前激活模板归档到 `templates/archive/YYYY/MM/DD/<name>_<HHMMSS>/`
   - 将源文件解析为 Markdown 中间层
   - 合并到 `template.html`，保留 `{{var}}`、`{{IMAGE:name}}`、`<img>`、`<a>`
   - 若只提供单一语言，自动生成另一语言版本
6. 浏览器打开预览；在终端输入 `Y` 确认后，模板才正式启用。

### 6.5 模板选择逻辑

系统根据客户销售阶段自动匹配模板：

| 销售阶段 | 触发条件 | 选用模板 |
|----------|----------|----------|
| `new_lead` | 无发送记录 | `initial_contact` |
| `contacted_no_reply` | 已发 1 封，无回复 | `follow_up` |
| `follow_up_no_reply` | 已发 ≥2 封，无回复 | `final_note` |
| `replied` | 有回复记录 | `follow_up` |

如需强制使用特定模板，可在调用 `email_generator.generate_for_customer()` 时传入 `template_name` 参数（需二次开发）。

---

## 七、运行方式

### 7.1 交互式 CLI（推荐）

```bash
source .venv/bin/activate
python main.py
```

菜单选项：

| 选项 | 功能 | 关键操作 |
|------|------|----------|
| `1` | 生成草稿 | 读取 `customers.csv`，生成 `drafts.json` |
| `2` | 审核草稿 | 浏览器打开每封邮件，终端输入 Y/N/S/E/Q |
| `3` | 发送已审核邮件 | 风控检查后 SMTP 发送，底部提示 Ctrl+C 暂停 |
| `4` | 检查回复 | IMAP 收件箱匹配，浏览器列表 + 终端 S/R/Q |
| `5` | 查看日志 | 展示最近 5 条发送/回复记录 |
| `6` | 配置检查 | 打印当前 `.env`、模型、寄件人、模板状态 |
| `7` | 切换模型 | 列出多模型配置，输入编号切换 |
| `8` | 导入/确认模板 | 拖入模板源文件后在此导入、预览、确认 |
| `9` | 切换 skill 模式 | `full` 或 `concise` |
| `D` | 删除草稿 | 单条删除或全部清空 |
| `0` | 退出 | — |

### 7.2 命令行参数（兼容旧版 / 脚本自动化）

```bash
python main.py --init          # 仅初始化日志文件
python main.py --send          # 直接发送已审核草稿（等同菜单 3）
python main.py --check-replies # 直接检查回复（等同菜单 4）
```

---

## 八、生成元数据

每封草稿 `drafts.json` 会记录：

```json
{
  "model_used": "kimi-k2.6",
  "language": "cn",
  "generation_meta": {
    "generation_time": "2026-08-04T10:00:00",
    "prompt_tokens": 420,
    "completion_tokens": 180,
    "total_tokens": 600
  }
}
```

- `generation_time`：生成开始时间（ISO 8601）。
- 如果 LLM 接口不返回 usage，三个 token 字段会填 `0`，不会崩溃。

---

## 九、发送策略与安全设置

### 9.1 Demo 模式白名单

`email_agent/config.py` 中 `DEMO_MODE = True` 时，**只允许发送到 `ALLOWED_TEST_EMAILS` 列表中的地址**。误发真实客户会被拦截并记录日志。

修改白名单：编辑 `email_agent/config.py` 里的 `ALLOWED_TEST_EMAILS` 列表，然后重启脚本。

### 9.2 发送频率控制

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MAX_DAILY_SENDS` | `50` | 每日成功发送上限 |
| `MIN_DELAY_SECONDS` | `30` | 每封邮件最小间隔 |
| `MAX_DELAY_SECONDS` | `120` | 每封邮件最大间隔（Demo） |
| `SIMILARITY_THRESHOLD` | `0.90` | 24h 相似度阈值 |

调整方法：直接修改 `email_agent/config.py` 中的常量，然后重启脚本。

### 9.3 可中断发送

菜单 3 发送过程中：

- 终端底部持续显示 `[Ctrl+C to pause]`。
- 按 Ctrl+C 会保存当前进度到 `data/sending_state.json`。
- 重新运行菜单 3 会自动从断点续跑，已发送的草稿不会重复发送。
- 全部完成后自动清除 `sending_state.json`。

如需手动重置，可删除：

```bash
rm data/sending_state.json
```

### 9.4 SPF 检查

发送前会自动检查发件域名的 SPF TXT 记录。若缺失，终端会打印警告，**但不会阻断发送**（防止 DNS 故障导致业务中断）。

---

## 十、顶部状态栏说明

启动后主菜单顶部显示状态栏：

| 颜色 | 含义 | 常见原因 |
|------|------|----------|
| 🔴 红色 | 阻断 | 缺少 `.env` 配置、无客户、无模板、模板未确认 |
| 🟡 黄色 | 可操作但有未完成任务 | 新模板待导入、生成/发送暂停中、有 pending/approved 草稿 |
| 🟢 绿色 | 全部就绪 | 模板已确认且无剩余工作 |

状态按 **红色 > 黄色 > 绿色** 优先级计算，红色条件只要有一条满足就会显示红色。

---

## 十一、调试技巧

### 11.1 逐模块独立测试

```bash
source .venv/bin/activate
PYTHONPATH=$(pwd) python -c "
from email_agent import data_store
print(data_store.load_customers())
"
```

常用片段：

```python
# 测试模板渲染
from email_agent import template_engine
html, images = template_engine.render("initial_contact", {
    "customer_first_name": "Test",
    "company_name": "Demo Corp",
    "sender_name": "Alex"
})
print(html)

# 测试客户阶段与语言分析
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

# 测试多模型解析
from email_agent import config
print(config.load_available_models())
print(config.get_active_model())
```

### 11.2 查看草稿

```bash
cat data/drafts.json | python -m json.tool
```

关键字段：
- `review_status`: `pending` / `approved` / `rejected`
- `html_body`: 最终发送的 HTML 源码
- `text_body`: 纯文本预览
- `images`: 内联图片 CID 与路径映射
- `personalization_note`: 个性化策略说明
- `model_used`: 使用的模型
- `generation_meta`: 生成时间与 token 消耗
- `language`: 邮件语言 `cn` / `en`

### 11.3 邮件发送日志

`data/email_logs.csv` 字段：

| 字段 | 说明 |
|------|------|
| `status` | `success` / `failed` |
| `error_msg` | 失败原因 |
| `message_id` | SMTP 返回的真实 Message-ID（用于回复追踪） |

### 11.4 LLM 生成调试

若草稿生成失败：
1. 检查 `.env` 中 `LLM_API_KEY` / `MODEL_*_API_KEY`。
2. 检查网络是否可连通 LLM 服务端。
3. 检查模型名称是否有效。
4. 若使用 Moonshot，确认 base URL 包含 `moonshot`，且 temperature 被自动钳制到 `1.0`。
5. 临时在 `email_agent/email_generator.py` 的 `generate_for_customer` 中打印 raw response：

```python
print("LLM raw response:", raw)
```

### 11.5 SMTP 发送调试

1. 确认 `EMAIL_PASSWORD` 是**客户端授权码**，不是网页登录密码。
2. 确认腾讯企业邮箱未开启二次验证且已生成专用密码。
3. 检查 `email_logs.csv` 中的 `error_msg`。
4. Demo 模式下确认收件地址在白名单中。

### 11.6 IMAP 回复调试

1. 确认同一套 `EMAIL_ACCOUNT` / `EMAIL_PASSWORD` 可登录 IMAP。
2. 检查收件箱是否有 `Re:` / `回复:` 开头的邮件。
3. 检查 `email_logs.csv` 中对应邮件是否有 `message_id`（旧版发送记录可能缺失）。

---

## 十二、常见问题速查

| 现象 | 原因 | 解决 |
|------|------|------|
| 状态栏红色，提示 Template not confirmed | 模板未确认 | 进入菜单 8 导入/确认模板 |
| 生成/发送菜单被阻断 | 模板未确认 | 同上 |
| 浏览器没有自动弹出 | 无桌面环境 | 手动复制终端打印的临时 HTML 路径到浏览器 |
| `ModuleNotFoundError: No module named 'email_agent'` | 未设置 `PYTHONPATH` | 在项目根目录运行，或 `export PYTHONPATH=$(pwd)` |
| `LLM_API_KEY is not set in .env` | 未配置 LLM 密钥 | 配置单模型变量或多模型块 |
| `Blocked by Demo Mode` | 收件人不在白名单 | 将测试邮箱加入 `ALLOWED_TEST_EMAILS` |
| 生成草稿很慢/失败 | LLM 网络或模型不可用 | 检查 base URL 和 model，或切换模型 |
| 邮件正文没有图片 | `assets/images/` 下缺少对应文件 | 按模板 `config.yaml` 放置图片 |
| 草稿中英文混用 | 语言判定或 prompt 约束未生效 | 检查 `location` 与 `templates/sender_profile.md`；重新确认模板 |
| 草稿中出现随机寄件人名 | `sender_profile.md` 未生效 | 检查该文件 YAML frontmatter 字段名是否正确 |
| 草稿版式与模板差异大 | 模板未确认或 LLM 未遵循约束 | 重新导入并确认模板；必要时使用 `full` skill 模式 |
| `Expecting value: line 1 column 1 (char 0)` | Moonshot 不支持 json_schema 或返回空 | 确认 base URL 含 `moonshot`；清理 `__pycache__` |

清理缓存命令：

```bash
find email_agent -name "__pycache__" -exec rm -rf {} +
```

---

## 十三、扩展开发提示

- **新增模板**：在 `templates/email/` 下新建目录，放入 `config.yaml` + `template.html`。
- **新增客户字段**：如需在 `customers.csv` 中加字段，修改 `email_generator.py` 中 prompt 构建函数。
- **切换数据库**：当前用 CSV/JSON，如需迁移到 SQLite，重点替换 `email_agent/data_store.py` 的实现层。
- **自定义状态栏**：修改 `email_agent/status.py` 的 `compute_status()`。

---

如有其他问题，可在交互菜单中选 **6. Configuration check** 快速核对当前环境配置，或参考 `README.md` 中的操作指引。
