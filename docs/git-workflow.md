# Git 与三角色协同工作流

## 1. 角色

| 角色 | 决策范围 | 主要输出 |
|---|---|---|
| 用户 | 最终业务裁决、重大风险、合并与发布 | 批准/拒绝 |
| Manus（PM） | WHY / WHAT | `docs/PRD.md`、`docs/UserFlow.md`、`tasks/TASK.md`、验收与 PRD 符合性审查 |
| Codex（CTO） | HOW | Architecture、Technical Spec、ADR、技术风险、架构审查 |
| Claude Code（Senior Engineer） | BUILD | 实现、测试、Debug、自审、PR |

角色不得互相覆盖：Manus 不改技术架构；Codex 不改业务目标且不承担常规编码；Claude Code 不改产品目标或核心架构。

## 2. 三层分支

```text
feature/* 或 fix/*
        ↓ PR + CI + 所需审查
develop
        ↓ 发布 PR + 用户最终确认
main
```

| 分支 | 定位 | 直接 commit/push |
|---|---|---|
| `main` | 稳定发布基线 | 禁止 |
| `develop` | 日常集成与验收 | 禁止 |
| `feature/*` | 产品、架构、功能、重构、治理 | 允许 |
| `fix/*` | Bug 修复 | 允许 |

产品文档、技术文档和代码遵循同一流程。原有“文档直接提交 main”规则废止，避免 `main` 与 `develop` 产生认知分叉。

## 3. Task 门禁

Task 必须记录：

```yaml
codex_required: true | false
codex_reason: "判断依据"
technical_spec: docs/technical-specs/TASK-XXX.md | N/A
approval_status: Draft | Approved | Blocked | Done
```

以下任一情形必须经过 Codex：新模块/服务、公共 API、跨模块依赖、Schema/迁移、核心数据语义、安全/隐私、关键依赖、部署/CI、性能/容量/可靠性、跨模块重构、Architecture/ADR 变化或技术不确定性。

只有单一既有模块、默认不超过 3 个实现文件、不触及上述边界、可回滚且可测试的任务才可跳过 Codex。

## 4. 标准交接

### 复杂任务

```text
Manus Product Approved Task
→ Codex Approved Technical Spec
→ Claude Code 实现、测试、自审、PR
→ Codex 架构审查
→ Manus 黑盒验收与 PRD 符合性审查
→ 用户决定是否合并到 develop
```

### 小任务

```text
Manus Approved Task（codex_required: false）
→ Claude Code 实现、测试、自审、PR
→ Manus 验收
→ 用户决定是否合并到 develop
```

### 发布

由用户发起或批准 `develop → main` PR。

## 5. 审查状态

触发架构门禁的 PR 标记 `architecture-review-required`，Codex 给出 `Approved`、`Changes Requested` 或 `Blocked`。未 Approved 前，Manus 不给出最终 Accepted。

Manus 的验收结论：`Accepted`、`Accepted with Known Limitations`、`Changes Requested` 或 `Blocked`。

## 6. 提交前缀

```text
[Manus] docs(prd|flow|task|research|acceptance|governance): description
[Codex] docs(arch|spec|adr|risk): description
[Codex] review(arch): description
[Claude] feat|fix|refactor|test|docs|chore(scope): description
```

## 7. 冲突

任何 merge、rebase、cherry-pick、文件所有权或语义冲突都必须立即停止。报告冲突文件、当前版本、incoming 版本、来源和影响，等待用户决定。禁止自动选择、覆盖、强推或重写历史。
