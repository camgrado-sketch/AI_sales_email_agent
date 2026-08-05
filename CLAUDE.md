# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 全局指令

本仓库同时受 `/home/cam/CLAUDE.md` 全局指令约束。若本文件与全局指令冲突，以全局指令为准；本文件仅补充仓库级细节，并重点明确分支管理策略。

## 项目概述

AI 销售邮件自动化 Demo（家具设计行业 / GRADO 品牌）。当前活跃架构在 `feature/local-template-replace` 分支：

- **LLM 仅用于模板导入结构化**：用户将 `.md/.docx/.pdf` 丢入 `templates/import/`，脚本调用一次 LLM 生成中英双语 HTML 模板与 `config.yaml`。
- **邮件生成完全本地**：从 `data/customers.csv` 与 `templates/sender_profile.md` 硬性映射变量，通过 `template_engine.render()` 替换 `{{VAR}}`、`{{IMAGE:name}}`、`{{FILE:name}}`，**不再调用 LLM**。
- **入口为交互式 CLI**：`main.py` 默认启动菜单，草稿主存储为 `data/drafts.json`。

旧版 `README.md`（Manus 沙盒 + `drafts.csv` 手工流程）已废弃；以当前分支代码和重写后的 `README.md` 为准。

## 常用命令

```bash
# 环境搭建（httpx==0.27.2 的 pin 必须保留，openai 1.46.0 与 httpx 0.28+ 不兼容）
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # 首次必须执行

# 交互式主程序（必须在真实交互式终端运行，菜单依赖 input()）
source .venv/bin/activate && python main.py

# 遗留 CLI 模式
python main.py --init          # 初始化日志文件
python main.py --send          # 直接发送已审核草稿（等同菜单 3）
python main.py --check-replies # 直接检查回复（等同菜单 4）

# 语法检查
python3 -m py_compile main.py email_agent/*.py scripts/*.py

# 清理陈旧缓存（修改后若行为未变化，先执行此命令）
find email_agent -name "__pycache__" -exec rm -rf {} +
```

## 核心数据流

```
data/customers.csv
  → interaction_analyzer.analyze()      # 规则判定销售阶段（new_lead / contacted_no_reply /
                                        #   follow_up_no_reply / replied）与语言
  → template_engine.get_template_config() / render()
                                        # templates/email/<name>/ 下 config.yaml 声明变量与规则，
                                        # template.html 用 {{VAR}} 与 {{IMAGE:name}} 占位符；
                                        # 图片解析为 CID 内联附件（assets/images/）
  → email_generator.generate_all()      # 本地变量替换，组装 draft dict → data/drafts.json；
                                        # 用 data/generation_state.json 支持 Ctrl+C 暂停/续跑
  → cli_controller 菜单 2 人工审核      # approved / rejected
  → sender.process_queue()              # deliverability.can_send() 风控后 SMTP 发送
  → receiver.check_replies()            # IMAP 匹配 In-Reply-To Message-ID 或 "Re:" 主题
```

## 分支管理（重点）

- **`main`**：主分支。当前包含 Manus 初始版本及黑盒测试 Bug Report，是切出新分支的基准。
- **`feature/local-template-replace`**：当前活跃重构分支，承载本地变量替换、LLM 模板结构化、Playwright 预览、设置子菜单等新架构。**新开发与 bug 修复优先在此分支进行**，完成后再合并回 `main`。
- **新任务必须切独立分支**，禁止在 `main` 或 `feature/local-template-replace` 上直接堆积多个逻辑的提交：
  ```bash
  git checkout main
  git pull origin main
  git checkout -b feature/xxx    # 新功能
  git checkout -b fix/issue-xxx  # Bug 修复
  ```
  若修复针对 `feature/local-template-replace` 黑盒测试报告，可基于该分支切出 `fix/issue-xxx`，修复后再合并回 `feature/local-template-replace`。
- **提交格式**：`[Claude] feat(模块): 描述` 或 `[Claude] fix(模块): 描述`，每次仅包含单一逻辑变更。
- **同步与冲突**：合并或继续开发前，在目标分支执行 `git pull origin main` 同步最新变更；若发生冲突，立即停止，输出冲突文件及双方内容，等待用户裁决，不得自行选择保留版本。
- **任务完成总结**：每次 Task 完成后按全局指令格式输出变更总结，并归档到 `CHANGELOG.md`。

## 关键模块职责

- `config.py` — 全部配置与路径；从 `.env` 读取密钥；从 `data/settings.json` 读取持久化设置；加载 `templates/sender_profile.md`。
- `data_store.py` — 唯一数据访问层。CSV/JSON 读写，所有 JSON 加载对空/损坏文件有防御。
- `llm_client.py` — OpenAI 兼容客户端。Moonshot 需 base URL 含 `moonshot`，且不兼容 `json_schema`，会自动走 prompt 注入 + 手动解析。
- `template_importer.py` — 模板扫描、Markdown 提取、LLM 结构化、双语 HTML 写入、归档、确认。
- `template_engine.py` — 本地渲染 HTML，替换 `{{VAR}}`、`{{IMAGE:name}}`、`{{FILE:name}}`。
- `email_generator.py` — 本地变量组装，生成草稿，`rendered_by: "local"`。
- `interaction_analyzer.py` — 规则判定销售阶段与语言，**不再调用 LLM**。
- `preview.py` — Playwright Chromium 预览，headed 优先，无桌面环境回退到 PNG 截图或系统浏览器。
- `cli_controller.py` — 交互式菜单：生成 / 审核 / 发送 / 回复 / 日志 / 导入确认模板 / 设置子菜单 / 删除草稿。
- `sender.py` / `receiver.py` — SMTP_SSL / IMAP4_SSL 腾讯企业邮箱。
- `deliverability.py` — 白名单、日上限、相似度、SPF、随机延迟。

## 目录权限

| 目录 / 文件 | 权限 |
| :--- | :--- |
| `email_agent/`、`scripts/` | 可写 |
| `docs/architecture.md`、`CHANGELOG.md` | 可写 |
| `docs/PRD.md`、`docs/UserFlow.md` | **禁止写入**（Manus 职责） |
| `tasks/` | **禁止写入**（Manus 职责） |
| `.manus/` | **禁止写入** |
| `data/`、`.env` | 已加入 `.gitignore`，严禁提交 |

## 调试与风险

- 用户报告 bug 时：阅读现有代码 → 找调用入口 → 分析执行路径 → 定位失败节点 → 提供最小修改。优先保持已有设计，不重构整个模块。
- 本仓库无测试框架与 lint 配置，修改后使用 `python3 -m py_compile` 做语法检查。
- `EMAIL_PASSWORD` 是腾讯企业邮箱**客户端授权码**，非登录密码。
- `DEMO_MODE = True` 时，非 `ALLOWED_TEST_EMAILS` 白名单收件人一律拦截。
- 模板占位符统一使用**大写下划线**：`{{SENDER_NAME}}`、`{{CUSTOMER_FIRST_NAME}}`、`{{IMAGE:hero}}`、`{{FILE:catalog_pdf}}`。
- `{{FILE:name}}` 默认渲染为本地 `file://` 链接，仅用于预览占位，收件人无法访问；发送前需替换为公网 URL 或改用附件。
- `data/` 中文件损坏或为空时，`data_store.py` 会回退到空集合，不会崩溃。
- Playwright headed 模式在后台/无桌面环境会回退；非交互 shell 运行 `main.py` 会报 `EOFError`。
