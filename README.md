# AI Sales Outreach Agent Demo

这是一个小规模可运行的 AI 销售邮件自动化 Demo。针对家具设计行业客户开发，通过客户基础信息生成个性化商务邮件，并通过腾讯企业邮箱自动发送，同时建立邮件发送记录和回复采集基础。

## 核心架构
- **AI 邮件生成**：在 Manus 沙盒中，基于 `customers.csv` 和预设的 Prompt/Skill 批量生成邮件草稿。
- **邮件发送 (SMTP)**：在本地运行 Python 脚本，读取草稿，连接腾讯企业邮箱发送，并写入日志。
- **回复采集 (IMAP)**：在本地运行 Python 脚本，定时读取收件箱，匹配已发邮件并记录回复。

## 目录结构
- `data/`：存放客户数据、AI生成的草稿、发送日志和回复日志（不提交到 GitHub）。
- `prompts/`：存放 AI 邮件生成的 Prompt 模板。
- `skills/`：存放品牌写作规范，约束 AI 的语气和行业表达。
- `config/`：存放发送规则与策略文档。
- `email_agent/`：Python 核心执行代码（发送、接收、日志、配置）。
- `main.py`：程序的入口脚本。

## 快速开始

### 1. 环境准备
确保你的电脑上安装了 Python，然后安装依赖：
```bash
pip install python-dotenv
```

### 2. 配置文件
在项目根目录创建一个 `.env` 文件（此文件已被 gitignore 忽略，不会提交到仓库）：
```env
EMAIL_ACCOUNT=你的企业邮箱地址
EMAIL_PASSWORD=你的企业邮箱客户端授权码
```
*注意：腾讯企业邮箱必须使用客户端授权码，而不是网页登录密码。*

### 3. 第一步：生成与审核草稿
1. 在 `data/customers.csv` 中准备好测试客户信息。
2. 将 `customers.csv`、`prompts/email_generation_prompt.md` 和 `skills/email_writing_skill.md` 发给 Manus，让其生成草稿。
3. 将生成的草稿保存为 `data/drafts/drafts.csv`。
4. **人工审核**：在 `drafts.csv` 中添加一列 `review_status`，审核通过的行填入 `pass`。

### 4. 第二步：发送邮件
在命令行中运行：
```bash
python main.py --send
```
脚本会自动读取 `review_status` 为 `pass` 的草稿，并在 `data/email_logs.csv` 中记录发送结果。

*安全机制：Demo 阶段默认开启白名单拦截。请在 `email_agent/config.py` 的 `ALLOWED_TEST_EMAILS` 中添加你的测试邮箱地址，否则脚本会拒绝发送。*

### 5. 第三步：检查回复
在命令行中运行：
```bash
python main.py --check-replies
```
脚本会连接 IMAP 服务器，检查收件箱中的回复，并记录到 `data/reply_logs.csv` 中。

## 开发与扩展
本仓库是 Track A 学习计划的 Capstone 实践项目。目前使用 CSV 作为轻量级数据存储，待流程跑通且客户量增加后，可平滑迁移至 SQLite 数据库，并逐步扩展客户画像与商机管理功能。
