# AI Agent 协同 Git 工作流规范 (Git Workflow)

本文档定义了本仓库在 "人类 (CEO) + Manus (PM/QA) + Claude Code (Dev)" 协同模式下的 Git 管理规范。

## 1. Git 分支模型设计

本仓库采用精简的双层分支模型，取消传统的 `develop` 分支，直接通过功能分支集成到 `main`。

- **`main`**: 项目的唯一主分支，代表"项目最新认知状态"（包含最新文档、稳定代码）。**严禁任何人直接向 main 推送代码修改。**
- **临时分支**: 所有代码修改必须在临时分支进行，完成后通过 Pull Request (PR) 合并回 `main`，合并后立即删除。

## 2. 分支命名规范

| 分支类型 | 命名格式 | 说明 | 负责人 |
| :--- | :--- | :--- | :--- |
| **新功能** | `feature/<task-name>` | 开发新需求（如 `feature/email-template`） | Claude Code |
| **Bug修复** | `fix/<bug-name>` | 修复已知问题（如 `fix/smtp-timeout`） | Claude Code |
| **代码重构** | `refactor/<module>` | 不改变功能的代码结构优化 | Claude Code |
| **紧急修复** | `hotfix/<issue>` | 线上紧急问题修复 | 本地 (CEO) / Claude Code |
| **文档更新** | `docs/<topic>` | 大型文档重构（日常小更新可直接进 main） | Manus |
| **测试完善** | `test/<module>` | 补充或修改测试用例 | Claude Code |

## 3. 分支生命周期

1. **创建**: 每次开始 Task 前，从最新的 `main` 创建分支。(`git checkout -b feature/xxx`)
2. **开发**: 在独立分支上进行代码修改，保持原子化提交。
3. **提交**: 遵循 Conventional Commit 规范进行 `git commit`。
4. **Push**: 将分支推送到远程仓库。(`git push -u origin feature/xxx`)
5. **Pull Request**: 在 GitHub 上发起 PR，关联对应的 Task ID 或 Issue。
6. **Merge**: 由本地 (CEO) 审核通过后，执行 Merge（推荐 Squash and merge）。
7. **删除**: 合并完成后，立即删除远程和本地分支。

## 4. AI Agent 协作流程

- **Manus 职责**: 
  - 负责维护 `docs/`、`tasks/`、`.manus/` 目录。
  - 将 Epic 拆解为 Task 并更新 `TASKS.md`，相关文档变更直接提交并 push 到 `main`。
  - 执行黑盒测试，发现问题生成 Bug Report 并直接提交到 `main`。
- **Claude Code 职责**:
  - 接收到 Task 或 Bug Report 后，**必须先拉取最新 main**。
  - 创建对应的 `feature/` 或 `fix/` 分支。
  - 完成编码和单元测试，按规范 commit 并 push。
  - 输出 `CHANGELOG.md` 总结，并发起 PR 等待审核。
- **本地 (CEO) 职责**:
  - 解决冲突裁决。
  - 审核 PR 并执行合并。

## 5. Commit Message 规范

采用 Conventional Commits 规范，格式为：`type(scope): description`。

**允许的 Type:**
- `feat`: 新功能 (Feature)
- `fix`: 修复 Bug
- `refactor`: 重构 (既不增加新功能，也不修复 bug 的代码变动)
- `docs`: 文档变更 (Documentation)
- `test`: 增加测试
- `chore`: 构建过程或辅助工具的变动 (如更新依赖)

**AI 协作专属前缀 (可选但推荐):**
为了清晰追踪是谁做的修改，可在开头加上角色标识：
- `[Manus] docs(prd): 新增邮件模板需求`
- `[Claude] feat(email): 实现模板变量替换`
- `[Local] chore: 更新 GitHub Actions 配置`
