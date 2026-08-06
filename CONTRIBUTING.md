# 项目贡献规范 (Contributing Guidelines)

欢迎参与本项目的开发！为了保证项目在 AI Agent（Manus & Claude Code）与人类协同开发中的代码质量和历史清晰度，请所有参与者（包括 AI）严格遵守以下规范。

## 1. 核心开发流程

1. **阅读任务**: 所有的开发工作必须基于 `tasks/TASKS.md` 中的具体任务或 `docs/bug_report.md` 中的明确 Bug。禁止无边界的"自由优化"。
2. **同步代码**: 任何操作前，必须执行 `git checkout develop && git pull origin develop`，从 `develop` 拉取最新代码后再创建工作分支。
3. **架构先行**: (仅限新功能) 在编写代码前，必须先输出或更新 `docs/architecture.md`。
4. **分支开发**: 必须在规范的 `feature/` 或 `fix/` 分支上工作，PR 目标分支为 `develop`，**不得直接向 `main` 发起 PR**。
5. **测试验证**: 提交前必须运行现有测试，确保未破坏原有功能。
6. **提交 PR**: 开发完成后推送到远程分支，并使用标准模板发起 Pull Request。

## 2. Branch 与 Commit 规则

- **分支规则**: 严禁直接修改 `main` 和 `develop` 分支的业务代码。所有代码变更必须通过 `feature/*` 或 `fix/*` 分支，向 `develop` 发起 PR。详情见 `docs/git-workflow.md`。
- **Commit 规则**: 遵循 `[角色] type(scope): description` 格式。一次提交只做一件事（原子化提交）。

## 3. Pull Request 规范

- PR 标题必须清晰概括本次变更，如 `feat: 支持本地模板变量替换`。
- PR 描述必须使用仓库默认的 `.github/pull_request_template.md` 模板。
- 必须关联对应的 Task ID 或 Bug ID。
- 在 PR 被合并前，必须解决所有的冲突和 CI 失败。

## 4. Code Review 要求

- 所有的代码变更必须经过人类 (CEO) 的审核才能合并。
- 重点关注：
  - 是否越界修改了不相关的文件。
  - 是否硬编码了敏感信息（API Key 等）。
  - 异常处理是否完善。
- 如果收到"你现在是高级代码审查工程师"的指令，Claude Code 需输出 `review.md` 辅助人类审核。

## 5. 测试要求

- 提交新功能时，尽量同步增加对应的测试逻辑。
- Manus 将负责最终的"黑盒验收测试"，开发者（Claude Code）需确保代码在常规路径下不会崩溃。

## 6. AI Agent 开发注意事项

- **冲突处理**: 遇到合并冲突时，AI Agent 必须停止操作并输出冲突报告，等待人类裁决，严禁自动覆盖。
- **敏感信息**: 绝对禁止将任何真实的 API Key、密码、客户邮箱等数据写入代码或提交。必须使用 `.env` 机制。
- **日志维护**: 遇到重要的技术决策或难以解决的坑，及时更新 `docs/decisions.md` 或 `docs/problems.md`。
