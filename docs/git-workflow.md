# AI Agent 协同 Git 工作流规范 (Git Workflow)

本文档定义了本仓库在 "人类 (CEO) + Manus (PM/QA) + Claude Code (Dev)" 协同模式下的 Git 管理规范。

---

## 1. 分支模型

本仓库采用**三层分支模型**，以 `develop` 作为集成缓冲区，保证 `main` 始终是稳定可用的版本。

```
feature/* / fix/*
    │
    ▼  PR（Claude Code 代码审核通过）
develop  ← Manus 做 PRD 符合性审查
    │
    ▼  PR（人工最终审核通过）
main     ← 始终是稳定可用版本
```

| 分支 | 定位 | 直接 push | 合并方式 |
| :--- | :--- | :--- | :--- |
| `main` | 稳定发布版，项目最新认知状态 | **禁止** | 仅接受来自 `develop` 的 PR，普通 Merge（保留完整历史） |
| `develop` | 集成缓冲区，所有功能在此集成验证 | **禁止** | 仅接受来自 `feature/*`/`fix/*` 的 PR，普通 Merge |
| `feature/*` | 新功能开发 | 允许 | 合并到 `develop` 后删除 |
| `fix/*` | Bug 修复 | 允许 | 合并到 `develop` 后删除 |

---

## 2. 分支命名规范

| 分支类型 | 命名格式 | 示例 |
| :--- | :--- | :--- |
| 新功能 | `feature/<task-name>` | `feature/template-selector` |
| Bug 修复 | `fix/<bug-name>` | `fix/language-detection` |
| 代码重构 | `refactor/<module>` | `refactor/email-generator` |
| 紧急修复 | `hotfix/<issue>` | `hotfix/smtp-timeout` |

---

## 3. 完整开发流程

### Step 1 — Claude Code 开发
1. 从最新 `develop` 创建工作分支：
   ```bash
   git checkout develop && git pull origin develop
   git checkout -b feature/task-xxx
   ```
2. 按 TASK.md 完成开发，原子化提交：
   ```bash
   git commit -m "[Claude] feat(module): 描述"
   ```
3. 推送并向 **`develop`** 发起 PR（不是 `main`）：
   ```bash
   git push -u origin feature/task-xxx
   gh pr create --base develop
   ```

### Step 2 — Claude Code 代码自审
在 PR 描述中，Claude Code 需自行完成代码层面的 review，确认：
- 无越界修改（未动 `docs/PRD.md`、`tasks/TASK.md`）
- 无硬编码敏感信息
- 异常处理完善

### Step 3 — Manus PRD 符合性审查
Manus 拉取 PR 分支，对照 `docs/PRD.md` 执行黑盒测试，输出审查报告提交到 `main`：
```bash
git commit -m "[Manus] docs(bug): feature/xxx 符合性审查报告"
```
- 审查通过：在 PR 中标注 `✅ Manus 符合性审查通过`
- 发现问题：在 PR 中列出问题，Claude Code 在原分支修复后重新审查

### Step 4 — 合并到 develop
Manus 审查通过后，由 **人工（您）** 在 GitHub 上执行 Merge PR（普通 Merge，保留完整提交历史）。合并后删除 feature 分支。

### Step 5 — develop → main（发布）
当 `develop` 上积累了足够的功能或修复，由 **人工（您）** 发起 `develop → main` 的 PR，完成最终审核后执行普通 Merge。

---

## 4. 三层审核职责

| 审核层 | 负责人 | 审核内容 | 输出物 |
| :--- | :--- | :--- | :--- |
| 代码审核 | Claude Code | 逻辑正确性、测试覆盖、规范合规 | PR 描述中的自审清单 |
| PRD 符合性审查 | Manus | 功能是否符合 PRD 规范、黑盒测试 | `docs/bug_report.md` |
| 最终审核 | 您（人工） | 业务判断、整体质量把关 | 合并决策 |

---

## 5. Commit Message 规范

格式：`[角色] type(scope): description`

| 角色 | 示例 |
| :--- | :--- |
| Claude Code | `[Claude] feat(template): 支持 docx 图片自动提取` |
| Manus | `[Manus] docs(prd): 更新邮件主题生成规则` |
| 人工 | `[Local] chore: 更新 GitHub Actions 配置` |

**允许的 type**：`feat` / `fix` / `refactor` / `docs` / `test` / `chore`

---

## 6. Manus 文档提交规则

Manus 负责 `docs/`、`tasks/` 目录，文档变更**直接提交到 `main`**，无需经过 `develop`（文档不影响代码运行）：

| 操作 | 目标分支 | Commit 前缀 |
| :--- | :--- | :--- |
| 新增 / 更新 PRD | main | `[Manus] docs(prd):` |
| 更新架构文档 | main | `[Manus] docs(arch):` |
| 提交 Bug Report / 审查报告 | main | `[Manus] docs(bug):` |
| 更新任务列表 | main | `[Manus] docs(task):` |

---

## 7. 冲突处理

发生冲突时，**AI Agent 必须立即停止操作**，输出：
- 冲突文件列表
- 当前版本内容
- 远程版本内容

**禁止自动覆盖**，等待人工裁决后再继续。

---

## 8. 新仓库初始化检查清单

每个新仓库创建后，Manus 必须自动创建以下文件并提交到 `main`，并创建 `develop` 分支：

- [ ] `docs/git-workflow.md`（本文件）
- [ ] `CONTRIBUTING.md`
- [ ] `CLAUDE.md`
- [ ] `.github/pull_request_template.md`
- [ ] `.github/workflows/ci.yml`
- [ ] `.env.example`
- [ ] `develop` 分支（从 `main` 创建并推送）
