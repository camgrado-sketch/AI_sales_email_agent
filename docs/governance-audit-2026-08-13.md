# AI Sales Email Agent — 三角色治理审计

- 审计日期：2026-08-13
- 审计范围：远程仓库治理文件、分支模型和 Agent 职责
- 不在范围：业务代码重构、历史文档补写、Git 历史重写、Branch Protection 变更

## 当前发现

- 旧 `CLAUDE.md` 要求 Claude Code 自行设计/更新架构。
- 旧 `docs/git-workflow.md` 明确取消 `develop`，与远程已有 `develop` 及新的三层规则冲突。
- 旧规则允许 Manus 文档直推 `main`，并把架构文档更新列为 Manus/Claude 可执行事项。
- 仓库缺少根目录 `AGENTS.md`，Codex 没有项目级 CTO 权限边界。
- 邮件发送、凭据与真实客户数据风险尚未进入架构门禁字段。
- 现有 pre-commit 仅警告 main 直提，未阻止直接提交。

## 本次迁移

- 新增 Codex `AGENTS.md`，明确邮件安全与数据边界。
- 将 Claude Code 收敛为 Senior Engineer。
- 把双层流程迁移为 `feature/fix → develop → main`。
- 增加 Task、PR 门禁和 Architecture Owner 元数据。
- 收紧 pre-commit，阻止直接提交 `main`/`develop`。

## 风险控制

- 所有修改位于独立 `feature/*` 分支，并通过草稿 PR 提交到 `develop`。
- 不修改业务代码、运行配置、依赖、CI 逻辑或历史 Task。
- 不自动合并，不删除分支，不调整 Branch Protection。
- 新规则自本 PR 合并后创建的 Task 起生效；历史 Task 只保留记录，不追溯重写。

## 回滚

关闭 PR 即可完整放弃本次迁移；合并后可通过独立 revert PR 回退治理文件，不影响业务代码和数据。
