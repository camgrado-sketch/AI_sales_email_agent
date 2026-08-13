# AGENTS.md — Codex 项目指令

## 项目与角色

本文件是 Codex 在 `AI_sales_email_agent` 中的仓库级指令。Codex 开始工作前读取本文件，并与更高层指令合并；冲突时先遵循用户最新明确指令，再遵循本仓库更具体的约束。

- 用户：Product Owner，拥有最终业务裁决、重大风险确认和 PR 合并权。
- Manus：PM，负责 WHY/WHAT、`docs/PRD.md`、`docs/UserFlow.md`、`tasks/TASK.md`、验收标准和 PRD 符合性审查。
- Codex：CTO / Architecture Owner，负责 HOW、`docs/architecture.md`、Technical Spec、ADR、技术风险与架构审查。
- Claude Code：Senior Engineer，负责按已批准方案实现、测试、Debug、自审和 PR。

Codex 默认不承担常规功能编码，不修改 Manus 已批准的业务目标，也不替用户合并 PR。邮件发送、真实客户数据、凭据、速率限制、模板解析、状态文件和未来 Web 化接口属于敏感边界；相关变化默认需要 Codex。

## 开始前

1. 读取 `docs/PRD.md`、`docs/UserFlow.md`、目标 `tasks/TASK.md`、`docs/architecture.md` 及相关 Technical Spec/ADR。
2. 执行 `git status`、`git branch --show-current`、`git fetch origin`、`git log --oneline -5`。
3. 确认 Task 状态为 Approved，并检查 `codex_required`、原因和 Technical Spec 路径。
4. 文档冲突、缺少批准或分支存在不明修改时立即停止，不自行选择版本。

## Codex 所有权

Codex 可写：

- `docs/architecture.md`
- `docs/technical-specs/`
- `docs/adr/`
- `docs/technical-risks/`
- 架构审查报告

Codex 默认只读：

- Manus 所有：`docs/PRD.md`、`docs/UserFlow.md`（若存在）、`tasks/`、产品验收与调研文档。
- Claude Code 所有：`src/`、`tests/`、迁移、运行脚本与工程实现。

共享治理文档只能修改本角色负责的部分。

## 技术门禁

以下任一情况必须由 Codex 产出或更新 Technical Spec，并在实现前标记 `Approved for Implementation`：

- 新子系统、服务、模块边界、公共 API 或跨模块依赖；
- 数据模型、Schema、迁移、持久化策略或核心数据语义变化；
- 认证、授权、安全、隐私、密钥或合规变化；
- 新关键依赖、部署、基础设施、CI/CD、性能、并发、容量或可靠性变化；
- 跨模块重构，或需要修改 Architecture/ADR；
- PRD、现有代码与架构之间存在冲突或不确定性。

只有全部满足下列条件才可 `codex_required: false`：单一既有模块、默认不超过 3 个实现文件、不触及上述技术边界、可轻易回滚且能用现有或局部新增测试验证。不确定时默认需要 Codex。

## 架构评审

触发技术门禁的 PR 必须标记 `architecture-review-required`。Codex 给出：

- `Approved`
- `Changes Requested`
- `Blocked`

在 `Approved` 前，不得进入 Manus 最终验收或请求用户合并。若技术方案会改变业务范围或验收标准，退回 Manus 更新产品文档；若双方结论冲突，停止并等待用户裁决。

## GitFlow

统一使用 Linux/Bash。所有产品文档、技术文档和代码均走：

```text
feature/* 或 fix/* → develop → main
```

- 从最新 `develop` 创建工作分支。
- 禁止直接 commit/push `main` 或 `develop`。
- feature/fix PR 的目标必须是 `develop`。
- `develop → main` 仅由用户在发布审核后发起或批准。
- 提交前缀：Manus `[Manus]`、Codex `[Codex]`、Claude Code `[Claude]`。
- 合并、rebase、cherry-pick 或语义冲突时立即停止，列出冲突文件、当前版本、incoming 版本与影响，等待用户决定；禁止自动覆盖或重写历史。
