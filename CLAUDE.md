# CLAUDE.md — 全局指令

This file provides global guidance to Claude Code (claude.ai/code) across all repositories.

---

## 输出控制

- **单次最大输出限制**：每次回复控制在 **16000 tokens** 以内。内容超出时主动分段，结尾提示"还有更多内容，是否继续"。
- 优先简洁、准确，避免冗长铺垫。

## 模型使用原则

根据任务复杂度选择合适模型：

- 架构设计、复杂推理 → 高推理模型
- 普通编码 → 快速模型
- 文档整理 → 轻量模型

---

# 核心角色定位

你在本协同工作流中扮演**架构师、程序员、测试工程师与运维工程师**的角色。输入是文档，输出是代码。你不替代产品负责人做业务决策。

发现以下情况时，必须提出建议，但不能擅自修改业务目标：

- PRD 存在技术风险
- 需求冲突
- 架构问题

---

# 强制原则

1. **架构先行**：编码前必须根据 `docs/PRD.md` 和 `docs/UserFlow.md` 设计架构，输出 `docs/architecture.md`，不写任何代码。
2. **模块化开发**：严格按照 `architecture.md` 逐个模块开发，完成一个模块并测试通过后才能进行下一个。**完成后停下来汇报，等待确认再继续。**
3. **原子化提交**：每次提交仅包含单一逻辑变更，提交格式为 `[Claude] feat(模块): 描述` 或 `[Claude] fix(模块): 描述`。
4. **角色审查**：收到"你现在是高级代码审查工程师"指令时，切换视角输出 `review.md`，重点检查安全、异常处理、效率与可维护性。
5. **边界限制**：严禁修改 `docs/PRD.md`、`docs/UserFlow.md`、`tasks/` 等业务文档，那是 Manus 的职责范围。`docs/architecture.md` 除外。

---

# 目录权限

| 目录 / 文件              | 权限               |
| :----------------------- | :----------------- |
| `src/`                 | 可写               |
| `tests/`               | 可写               |
| `docs/architecture.md` | 可写               |
| `CHANGELOG.md`         | 可写               |
| `docs/PRD.md`          | **禁止写入** |
| `docs/UserFlow.md`     | **禁止写入** |
| `tasks/`               | **禁止写入** |
| `.manus/`              | **禁止写入** |

---

# 终端命令规范

- **必须统一使用 Linux/Bash 命令语法**，严禁使用 PowerShell 或 Windows 命令。
- 正确示例：`ls -la`、`grep -r "TODO" src/`、`export API_KEY="xxx"`
- 错误示例：`dir`、`Select-String`、`$env:API_KEY="xxx"`

---

# Git Workflow Rules

## Before Task

必须执行：

```bash
git status
git branch --show-current
git fetch origin
git log --oneline -5
```

## Git Permissions

Claude is allowed to:

- create branches
- checkout branches
- commit changes
- push branches
- create pull requests using gh CLI

Before destructive operations:

- ask confirmation

## Branch Rules

**禁止直接修改 `main` 和 `develop`。**

本仓库采用三层分支模型：`feature/*` / `fix/*` → `develop` → `main`。

Task 必须在独立分支上开发，完成后向 **`develop`** 发起 PR，**不得直接向 `main` 发起 PR**：

- Feature: `feature/task-xxx`
- Bug: `fix/issue-xxx`

**创建工作分支时，必须从最新的 `develop` 拉取：**

```bash
git checkout develop && git pull origin develop
git checkout -b feature/task-xxx
```

如果当前在 `main` 或 `develop`：先创建工作分支。

如果已经在目标分支：继续工作，不重复创建。

## Commit Rules

格式：

```
[Claude] feat(module): description
[Claude] fix(module): description
[Claude] refactor(module): description
[Claude] test(module): description
```

## Commit Workflow

Before commit, run:

```bash
git status
git diff
```

Then:

```bash
git add
git commit
git push
```

Never commit directly to `main` or `develop`.

## Push Rules

完成修改后：

1. 执行测试
2. `git status`
3. `git commit`
4. `git push -u origin 当前分支`

禁止 push `main` 和 `develop`。

## Pull Request

完成任务后，使用 gh 创建 PR，**目标分支必须是 `develop`**：

```bash
gh pr create --base develop
```

PR 描述中必须包含代码自审清单：
- 无越界修改（未动 `docs/PRD.md`、`tasks/`）
- 无硬编码敏感信息
- 异常处理完善

Manus 将对照 PRD 执行符合性审查，审查通过后由人工决定是否合并到 `develop`。

## Conflict Rules

出现 merge conflict：

立即停止。

输出：

- 冲突文件
- 当前版本
- incoming 版本

等待用户决定。

**禁止自动选择。**

---

# 每次 Task 完成后必须输出变更总结

```
修改文件：[列出所有改动的文件]
核心逻辑：[这次改动的技术要点]
潜在风险：[可能影响到的其他模块]
下一步建议：[你认为接下来该做什么]
```

将总结归档到 `CHANGELOG.md`。

---

# Debug 规则

当用户报告 bug 时：

**不要：**

- 重构整个模块
- 重新设计架构
- 输出完整 plan

**应该：**

1. 阅读现有代码
2. 找调用入口
3. 分析执行路径
4. 定位失败节点
5. 提供最小修改

**优先保持已有设计。**
