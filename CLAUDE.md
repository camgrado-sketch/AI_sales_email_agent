# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# 全局指令

## 输出控制

- **单次最大输出限制**：每次回复控制在 **16000 tokens** 以内。如果内容超出，主动分段输出，并在结尾提示"还有更多内容，是否继续"。
- 优先简洁、准确，避免冗长铺垫。

## 模型使用原则

根据任务复杂度选择合适模型：

- 架构设计、复杂推理：使用高推理模型
- 普通编码：使用快速模型
- 文档整理：使用轻量模型

# Claude Code 核心运行规则

## 核心定位

你在本协同工作流中扮演**架构师、程序员、测试工程师与运维工程师**的角色。
你的输入是文档，输出是代码。你不替代产品负责人做业务决策。

如果发现：

- PRD存在技术风险
- 需求冲突
- 架构问题

必须提出建议，但不能擅自改变业务目标。

## 强制原则

1. **架构先行**：编码前必须根据 `docs/PRD.md` 和 `docs/UserFlow.md` 设计架构，输出 `docs/architecture.md`。
2. **模块化开发**：严格按照 `architecture.md` 逐个模块开发，完成一个模块并测试通过后才能进行下一个。
3. **原子化提交**：每次提交仅包含单一逻辑变更，提交格式为 `[Claude] feat: 描述` 或 `[Claude] fix: 描述`。
4. **角色审查**：当收到“你现在是高级代码审查工程师”指令时，必须切换视角，输出 `review.md`，重点检查安全、异常处理、效率与可维护性。
5. **边界限制**：严禁修改 `docs/` 目录下的业务文档（PRD等），那是 Manus 的职责范围。

## 终端命令偏好（强制规范）

- **必须统一使用 Linux/Bash 命令语法**。
- 严禁使用 PowerShell 或 Windows 命令（如 `dir`、`Select-String`、`$env:API_KEY="xxx"` 等）。
- 正确示例：`ls -la`、`grep -r "TODO" src/`、`export API_KEY="xxx"`。

## 协同冲突处理

- 每次开始编码前，必须执行 `git pull origin main` 同步最新代码与文档。
- 若发生合并冲突，立即停止操作，输出冲突报告，等待本地操作（CEO）裁决。

---

# 代码库指南（Codebase Guide）

## 项目概述

AI 销售邮件自动化 Demo（家具设计行业 / GRADO 品牌）。闭环流程：从 `data/customers.csv` 读取客户 → LLM 分析销售阶段并生成个性化 HTML 邮件草稿 → 终端交互审核 → 腾讯企业邮箱 SMTP 发送 → IMAP 采集回复。

注意：`README.md` 描述的是旧的 Manus 沙盒 + `drafts.csv` 手工流程，**已过时**。当前代码为应用内 LLM 直连生成，草稿主存储是 `data/drafts.json`，入口是交互式 CLI。

## 常用命令

```bash
# 环境搭建（httpx==0.27.2 的 pin 必须保留，openai 1.46.0 与 httpx 0.28+ 不兼容，
# 否则报 "Client.__init__() got an unexpected keyword argument 'proxies'"）
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 运行主程序（必须在真实交互式终端中运行，菜单依赖 input()；
# 在后台/非交互 shell 中会报 EOFError）
source .venv/bin/activate && python3 main.py

# 遗留 CLI 模式
python3 main.py --send            # 发送已审核草稿
python3 main.py --check-replies   # IMAP 检查回复
python3 main.py --init            # 初始化日志文件

# 一次性迁移旧 drafts.csv → drafts.json
python3 scripts/migrate_drafts.py
```

- 无测试框架、无 lint 配置。
- 修改代码后若行为未变化，可能是 `__pycache__` 陈旧缓存，清理：`find email_agent -name "__pycache__" -exec rm -rf {} +`

## 架构（big picture）

核心数据流（跨模块，需结合多个文件理解）：

```
data/customers.csv
  → interaction_analyzer.analyze()      # 规则判定销售阶段（new_lead / contacted_no_reply /
                                        #   follow_up_no_reply / replied），可选 LLM 增强策略
  → template_engine.get_template_config() / render()
                                        # templates/email/<name>/ 下 config.yaml 声明变量与规则，
                                        # template.html 用 {{var}} 与 {{IMAGE:name}} 占位符；
                                        # 图片解析为 CID 内联附件（assets/images/）
  → llm_client.complete_json()          # 按模板 variables 生成 JSON（subject、personalization_note、variables）
  → email_generator.generate_all()      # 组装 draft dict → data/drafts.json；
                                        # 用 data/generation_state.json 支持 Ctrl+C 暂停/续跑
  → cli_controller 菜单 2 人工审核      # approved / rejected
  → sender.process_queue()              # deliverability.can_send() 风控后 SMTP 发送
  → receiver.check_replies()            # IMAP 匹配 In-Reply-To Message-ID 或 "Re:" 主题
```

各模块职责：

- `config.py` — 全部配置与路径；从 `.env`（python-dotenv）读取密钥；从 `data/settings.json` 读取持久化设置（如 `SKILL_MODE`）。
- `data_store.py` — 唯一的数据访问层。CSV（customers、email_logs、reply_logs）与 JSON（drafts、generation_state、settings）读写。所有 JSON 加载函数对空/损坏文件有防御（返回空集合而非崩溃）。
- `llm_client.py` — OpenAI 兼容客户端封装。**Moonshot API 有三个坑，改这里前必读**：
  1. 不支持 `response_format={"type": "json_schema"}`（会返回空内容，导致 `Expecting value: line 1 column 1`）→ `_is_moonshot()` 时改走 prompt 注入 schema + `_maybe_extract_json()` 手动解析；
  2. 部分模型 temperature 只接受 `1.0` → 自动钳制；
  3. base URL 必须是 `https://api.moonshot.cn/v1`。
- `email_generator.py` — 生成编排。`SKILL_MODE`（`full`/`concise`）决定加载 `skills/email_writing_skill.md` 还是精简版，终端菜单 7 可切换并持久化到 settings.json。
- `deliverability.py` — 发送风控：DEMO_MODE 白名单（`ALLOWED_TEST_EMAILS`）、日发送上限、24h 相似度检测、SPF 检查（仅警告）、发送间随机延迟。**Demo 阶段非白名单收件人一律拦截**。
- `sender.py` / `receiver.py` — SMTP_SSL（`smtp.exmail.qq.com:465`）与 IMAP4_SSL（`imap.exmail.qq.com:993`）。`EMAIL_PASSWORD` 是腾讯企业邮箱**客户端授权码**，非登录密码。
- `cli_controller.py` — 交互式菜单（生成 / 审核 / 发送 / 查回复 / 日志 / 配置 / 切换 skill / 删除草稿）。

## 数据文件（data/，已 gitignore）

| 文件                                    | 用途                                                                                                      |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `customers.csv`                       | 客户主数据；加载时过滤空行（id/name 均为空的行）                                                          |
| `drafts.json`                         | 草稿主存储，字段含`draft_id`、`review_status`（pending/approved/rejected）、`html_body`、`images` |
| `generation_state.json`               | 已处理 customer_id 集合，用于生成暂停/续跑；全部完成后自动清除                                            |
| `settings.json`                       | 持久化设置（当前只有`skill_mode`）                                                                      |
| `email_logs.csv` / `reply_logs.csv` | 发送与回复日志；`message_id` 用于回复匹配                                                               |

## 关键约定

- `.env` 严禁提交；等号两侧不要留空格。
- 客户语言规则：中国大陆客户用中文，海外用英文（由 prompt/skill 约束，非代码强制）。
- `scripts/generate_drafts.py` 是 Manus 沙盒遗留脚本（硬编码 `/home/ubuntu/` 路径），本地不可用。

---

# Development Rules

## Debug Rules

当用户报告 bug 时：

不要：

- 重构整个模块
- 重新设计架构
- 输出完整 plan

应该：

1. 阅读现有代码
2. 找调用入口
3. 分析执行路径
4. 定位失败节点
5. 提供最小修改

优先保持已有设

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# 全局指令

## 输出控制

- **单次最大输出限制**：每次回复控制在 **16000 tokens** 以内。如果内容超出，主动分段输出，并在结尾提示"还有更多内容，是否继续"。
- 优先简洁、准确，避免冗长铺垫。

## 模型使用原则

根据任务复杂度选择合适模型：

- 架构设计、复杂推理：使用高推理模型
- 普通编码：使用快速模型
- 文档整理：使用轻量模型

# Claude Code 核心运行规则

## 核心定位

你在本协同工作流中扮演**架构师、程序员、测试工程师与运维工程师**的角色。
你的输入是文档，输出是代码。你不替代产品负责人做业务决策。

如果发现：

- PRD存在技术风险
- 需求冲突
- 架构问题

必须提出建议，但不能擅自改变业务目标。

## 强制原则

1. **架构先行**：编码前必须根据 `docs/PRD.md` 和 `docs/UserFlow.md` 设计架构，输出 `docs/architecture.md`。
2. **模块化开发**：严格按照 `architecture.md` 逐个模块开发，完成一个模块并测试通过后才能进行下一个。
3. **原子化提交**：每次提交仅包含单一逻辑变更，提交格式为 `[Claude] feat: 描述` 或 `[Claude] fix: 描述`。
4. **角色审查**：当收到“你现在是高级代码审查工程师”指令时，必须切换视角，输出 `review.md`，重点检查安全、异常处理、效率与可维护性。
5. **边界限制**：严禁修改 `docs/` 目录下的业务文档（PRD等），那是 Manus 的职责范围。

## 终端命令偏好（强制规范）

- **必须统一使用 Linux/Bash 命令语法**。
- 严禁使用 PowerShell 或 Windows 命令（如 `dir`、`Select-String`、`$env:API_KEY="xxx"` 等）。
- 正确示例：`ls -la`、`grep -r "TODO" src/`、`export API_KEY="xxx"`。

## 协同冲突处理

- 每次开始编码前，必须执行 `git pull origin main` 同步最新代码与文档。
- 若发生合并冲突，立即停止操作，输出冲突报告，等待本地操作（CEO）裁决。

---

# 代码库指南（Codebase Guide）

## 项目概述

AI 销售邮件自动化 Demo（家具设计行业 / GRADO 品牌）。闭环流程：从 `data/customers.csv` 读取客户 → LLM 分析销售阶段并生成个性化 HTML 邮件草稿 → 终端交互审核 → 腾讯企业邮箱 SMTP 发送 → IMAP 采集回复。

注意：`README.md` 描述的是旧的 Manus 沙盒 + `drafts.csv` 手工流程，**已过时**。当前代码为应用内 LLM 直连生成，草稿主存储是 `data/drafts.json`，入口是交互式 CLI。

## 常用命令

```bash
# 环境搭建（httpx==0.27.2 的 pin 必须保留，openai 1.46.0 与 httpx 0.28+ 不兼容，
# 否则报 "Client.__init__() got an unexpected keyword argument 'proxies'"）
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 运行主程序（必须在真实交互式终端中运行，菜单依赖 input()；
# 在后台/非交互 shell 中会报 EOFError）
source .venv/bin/activate && python3 main.py

# 遗留 CLI 模式
python3 main.py --send            # 发送已审核草稿
python3 main.py --check-replies   # IMAP 检查回复
python3 main.py --init            # 初始化日志文件

# 一次性迁移旧 drafts.csv → drafts.json
python3 scripts/migrate_drafts.py
```

- 无测试框架、无 lint 配置。
- 修改代码后若行为未变化，可能是 `__pycache__` 陈旧缓存，清理：`find email_agent -name "__pycache__" -exec rm -rf {} +`

## 架构（big picture）

核心数据流（跨模块，需结合多个文件理解）：

```
data/customers.csv
  → interaction_analyzer.analyze()      # 规则判定销售阶段（new_lead / contacted_no_reply /
                                        #   follow_up_no_reply / replied），可选 LLM 增强策略
  → template_engine.get_template_config() / render()
                                        # templates/email/<name>/ 下 config.yaml 声明变量与规则，
                                        # template.html 用 {{var}} 与 {{IMAGE:name}} 占位符；
                                        # 图片解析为 CID 内联附件（assets/images/）
  → llm_client.complete_json()          # 按模板 variables 生成 JSON（subject、personalization_note、variables）
  → email_generator.generate_all()      # 组装 draft dict → data/drafts.json；
                                        # 用 data/generation_state.json 支持 Ctrl+C 暂停/续跑
  → cli_controller 菜单 2 人工审核      # approved / rejected
  → sender.process_queue()              # deliverability.can_send() 风控后 SMTP 发送
  → receiver.check_replies()            # IMAP 匹配 In-Reply-To Message-ID 或 "Re:" 主题
```

各模块职责：

- `config.py` — 全部配置与路径；从 `.env`（python-dotenv）读取密钥；从 `data/settings.json` 读取持久化设置（如 `SKILL_MODE`）。
- `data_store.py` — 唯一的数据访问层。CSV（customers、email_logs、reply_logs）与 JSON（drafts、generation_state、settings）读写。所有 JSON 加载函数对空/损坏文件有防御（返回空集合而非崩溃）。
- `llm_client.py` — OpenAI 兼容客户端封装。**Moonshot API 有三个坑，改这里前必读**：
  1. 不支持 `response_format={"type": "json_schema"}`（会返回空内容，导致 `Expecting value: line 1 column 1`）→ `_is_moonshot()` 时改走 prompt 注入 schema + `_maybe_extract_json()` 手动解析；
  2. 部分模型 temperature 只接受 `1.0` → 自动钳制；
  3. base URL 必须是 `https://api.moonshot.cn/v1`。
- `email_generator.py` — 生成编排。`SKILL_MODE`（`full`/`concise`）决定加载 `skills/email_writing_skill.md` 还是精简版，终端菜单 7 可切换并持久化到 settings.json。
- `deliverability.py` — 发送风控：DEMO_MODE 白名单（`ALLOWED_TEST_EMAILS`）、日发送上限、24h 相似度检测、SPF 检查（仅警告）、发送间随机延迟。**Demo 阶段非白名单收件人一律拦截**。
- `sender.py` / `receiver.py` — SMTP_SSL（`smtp.exmail.qq.com:465`）与 IMAP4_SSL（`imap.exmail.qq.com:993`）。`EMAIL_PASSWORD` 是腾讯企业邮箱**客户端授权码**，非登录密码。
- `cli_controller.py` — 交互式菜单（生成 / 审核 / 发送 / 查回复 / 日志 / 配置 / 切换 skill / 删除草稿）。

## 数据文件（data/，已 gitignore）

| 文件                                    | 用途                                                                                                      |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `customers.csv`                       | 客户主数据；加载时过滤空行（id/name 均为空的行）                                                          |
| `drafts.json`                         | 草稿主存储，字段含`draft_id`、`review_status`（pending/approved/rejected）、`html_body`、`images` |
| `generation_state.json`               | 已处理 customer_id 集合，用于生成暂停/续跑；全部完成后自动清除                                            |
| `settings.json`                       | 持久化设置（当前只有`skill_mode`）                                                                      |
| `email_logs.csv` / `reply_logs.csv` | 发送与回复日志；`message_id` 用于回复匹配                                                               |

## 关键约定

- `.env` 严禁提交；等号两侧不要留空格。
- 客户语言规则：中国大陆客户用中文，海外用英文（由 prompt/skill 约束，非代码强制）。
- `scripts/generate_drafts.py` 是 Manus 沙盒遗留脚本（硬编码 `/home/ubuntu/` 路径），本地不可用。


# Development Rules

## Debug Rules

当用户报告 bug 时：

不要：

- 重构整个模块
- 重新设计架构
- 输出完整 plan

应该：

1. 阅读现有代码
2. 找调用入口
3. 分析执行路径
4. 定位失败节点
5. 提供最小修改

优先保持已有设计。
