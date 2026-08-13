# 贡献规范

## 三角色协同

- Manus（PM）：维护 `docs/PRD.md`、`docs/UserFlow.md`、`tasks/TASK.md`、范围和验收标准。
- Codex（CTO）：维护 Architecture、Technical Spec、ADR、技术风险并审查架构相关 PR。
- Claude Code（Senior Engineer）：按批准文档实现、测试、Debug、自审并创建 PR。
- 用户：最终裁决和合并。

## 开发门禁

1. 工作必须关联 Approved Task。
2. Task 必须包含 `codex_required`、原因和 Technical Spec 路径。
3. `codex_required: true` 时，Technical Spec 必须为 `Approved for Implementation`。
4. 小任务只有在单模块、无接口/Schema/安全/关键依赖/基础设施/非功能目标变化且可回滚时才能跳过 Codex。
5. 实现中触发架构变化时立即停止并升级，不得边设计边编码。

## 分支与提交

所有文档和代码统一走 `feature/*` / `fix/* → develop → main`。禁止直接 commit/push `main`、`develop`。

提交前缀：

- `[Manus] docs(...): ...`
- `[Codex] docs(arch|spec|adr|risk): ...`
- `[Codex] review(arch): ...`
- `[Claude] feat|fix|refactor|test|docs|chore(...): ...`

每个提交只包含一个逻辑变更。PR 必须指向 `develop`，提供文档引用、测试证据、风险、回滚方法和所需审查。只有用户可以最终合并。

## 安全与冲突

不得提交密钥、真实用户数据或本机私有信息。冲突时停止，说明当前版本、incoming 版本及影响，等待用户裁决；禁止自动覆盖或重写共享历史。
