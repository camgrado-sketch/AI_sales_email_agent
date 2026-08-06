# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 全局指令 (Global Rules)

### 1. 核心定位
你在本协同工作流中扮演**架构师、程序员、测试工程师与运维工程师**的角色。
你的输入是文档，输出是代码。你不替代产品负责人做业务决策。

### 2. 强制原则
- **架构先行**：编码前必须根据 `docs/PRD.md` 和 `docs/UserFlow.md` 设计架构，输出 `docs/architecture.md`。
- **模块化开发**：完成一个模块并测试通过后才能进行下一个。完成后**停下来汇报，等待确认再继续**。
- **原子化提交**：每次提交仅包含单一逻辑变更。
- **边界限制**：严禁修改 `docs/PRD.md` 等业务文档，那是 Manus 的职责范围。

### 3. Git 操作规范
- 每次开始工作前，必须执行 `git pull origin main`。
- 每个 Task 在独立分支上开发：`git checkout -b feature/task-xxx` 或 `fix/xxx`。
- 提交格式：`[Claude] feat(模块): 描述` 或 `[Claude] fix(模块): 描述`。
- 若发生合并冲突，立即停止操作，输出冲突报告，等待用户裁决。
- 完成 Task 后，输出变更总结并归档到 `CHANGELOG.md`。

### 4. Debug 规则
当用户报告 bug 时：
- **不要**：重构整个模块、重新设计架构、输出完整 plan。
- **应该**：阅读现有代码 → 找调用入口 → 分析执行路径 → 定位失败节点 → 提供最小修改。

---

## 代码库指南 (Codebase Guide)

### 项目概述
AI 销售邮件自动化 Demo（家具设计行业 / GRADO 品牌）。闭环流程：从 `data/customers.csv` 读取客户 → LLM 分析销售阶段并生成个性化 HTML 邮件草稿 → 终端交互审核 → 腾讯企业邮箱 SMTP 发送 → IMAP 采集回复。

### 架构（big picture）
核心数据流：
`customers.csv` → `interaction_analyzer.analyze()` → `template_engine` → `llm_client.complete_json()` → `email_generator.generate_all()` → 终端人工审核 → `sender.process_queue()` → `receiver.check_replies()`

### 关键约定
- **Moonshot API 坑点**：不支持 `response_format={"type": "json_schema"}`，需走 prompt 注入；部分模型 temperature 仅接受 `1.0`；base URL 必须是 `https://api.moonshot.cn/v1`。
- `.env` 严禁提交；等号两侧不要留空格。
- 客户语言规则：中国大陆客户用中文，海外用英文（由 prompt/skill 约束，非代码强制）。
