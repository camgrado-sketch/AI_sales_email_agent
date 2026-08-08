# 架构设计文档 (architecture.md)

> 本文档依据 `docs/PRD.md`（v2.0）与 `docs/UserFlow.md` 重写，反映阶段 A-F 完成后的目标架构。
> 核心原则：**LLM 仅负责模板导入时的一次性结构化解析；批量邮件生成完全通过本地变量替换实现，不消耗 LLM 算力。**

## 1. 设计目标与核心原则

1. **LLM 调用点唯一化**：全系统唯一调用远程 LLM 的位置是 `template_importer.structure_template_with_llm()`。生成、审核、发送、回复环节均为本地执行。
2. **模板选择用户主权**：取消销售阶段自动推荐模板。用户在菜单 6 `[A]` 手动选择"当前生效模板"，写入 `settings.json` 的 `selected_template`，长期生效直至下次手动更改。未选择时生成直接报错，**不做任何自动降级**。
3. **可中断续跑**：生成（`generation_state.json`）与发送（`sending_state.json`）均支持 Ctrl+C 暂停/续跑。
4. **Demo 安全**：白名单收件人 + 日发送上限 + 模板确认门禁（`template_confirmed=true` 才允许生成）。
5. **状态实时可见**：主菜单顶部常驻两行状态栏，每次刷新重新计算，不缓存。

## 2. 目录结构

```
AI_sales_email_agent/
├── docs/
│   ├── PRD.md                  # 只读（Manus 职责）
│   ├── UserFlow.md             # 只读（Manus 职责）
│   ├── architecture.md         # 本文件
│   └── CONFIG_GUIDE.md         # 配置与操作指南
├── tasks/
│   └── TASK.md                 # 只读（Manus 职责）
├── email_agent/
│   ├── __init__.py
│   ├── config.py               # 配置、路径、sender_profile、settings 读写封装
│   ├── cli_controller.py       # 交互式 CLI 菜单
│   ├── sender_profile_editor.py# 发送者信息交互式编辑
│   ├── llm_client.py           # LLM API 客户端（仅被 template_importer 使用）
│   ├── data_store.py           # CSV/JSON 读写唯一出口
│   ├── interaction_analyzer.py # 规则判定销售阶段与语言（无 LLM、无模板推荐）
│   ├── template_engine.py      # HTML 模板渲染（{{VAR}} / {{IMAGE}} / {{FILE}}）
│   ├── template_importer.py    # 模板扫描、图片提取、LLM 结构化、双语生成、归档、确认
│   ├── email_generator.py      # 本地变量组装 → 模板渲染 → 写入 drafts.json
│   ├── preview.py              # Playwright 预览（环境自适应：弹窗/截图）
│   ├── status.py               # 顶部两行状态栏
│   ├── deliverability.py       # 发送风控（白名单、日上限、相似度、延迟）
│   ├── sender.py               # SMTP 发送（可中断队列、CID 内联图片、发送前预检）
│   ├── receiver.py             # IMAP 回复采集
│   └── logger.py               # 日志写入
├── templates/
│   ├── email/                  # 激活模板（config.yaml + template.html + template_<lang>.html）
│   ├── import/                 # 用户上传的 .md/.docx/.pdf
│   ├── archive/                # 归档模板（gitignored，运行时产物）
│   └── sender_profile.md       # 发送者身份（YAML frontmatter）
├── assets/
│   ├── images/                 # 模板内联图片（导入时自动提取）
│   └── files/                  # 模板附件
├── data/                       # gitignored，运行时状态
│   ├── customers.csv
│   ├── drafts.json
│   ├── email_logs.csv
│   ├── reply_logs.csv
│   ├── settings.json
│   ├── generation_state.json
│   ├── sending_state.json
│   ├── template_import_state.json
│   └── latest_preview.png      # 无 GUI 环境截图产物
├── prompts/
│   └── template_import_prompt.md   # LLM 模板结构化 prompt（含语言纯净规则）
├── tests/                      # pytest 测试
├── main.py
├── README.md
└── requirements.txt
```

> `skills/` 与 `prompts/email_generation_prompt.md` 已从生成流程移除，仅作存档，运行时不引用。

## 3. 模块职责与关键接口

| 模块 | 职责 | 关键公开接口 |
|------|------|--------------|
| `main.py` | 入口：argparse 分发 legacy 命令，默认进交互 CLI | `main()` |
| `config.py` | 环境变量、路径常量、多模型、sender profile、settings 读写 | `get_active_model() -> dict`；`load_sender_profile() -> dict`；`is_template_confirmed() -> bool`；`get_selected_template() -> str`；`set_selected_template(name: str) -> None`；`get_template_imported_at(name: str) -> str` |
| `data_store.py` | CSV/JSON 读写唯一出口；状态文件管理 | `load_customers()`；`load_drafts(status=None)`；`append_draft(draft)`；`save_drafts(list)`；`update_draft_status(draft_id, status)`；`delete_draft(draft_id)`；`get_sent_draft_ids() -> set`；`load_settings()/save_settings(dict)`；`load/save/clear_generation_state()`；`load/save/clear_sending_state()`；`count_unviewed_replies() -> int`；`mark_all_replies_viewed() -> None` |
| `interaction_analyzer.py` | 规则化阶段统计 + 语言判定（**无 LLM、无模板推荐**） | `analyze(customer: dict) -> {"stage": str, "language": "cn"\|"en", "reason": str}`；内部 `_detect_language(location)`（含拼音城市映射）、`_rule_based_stage(history)` |
| `template_engine.py` | 纯渲染：占位符替换、资源定位 | `list_templates() -> list[str]`；`get_template_config(name) -> dict`；`get_template_path(name, language=None)`；`render(name, variables, language=None) -> (html, images, files)` |
| `template_importer.py` | 模板导入全链路（**唯一 LLM 调用方**） | `scan_import_folder()`；`detect_changes()`；`extract_to_markdown(path, template_name=None) -> str`；`structure_template_with_llm(markdown, filename) -> dict`；`write_structured_template(name, structured, source_lang) -> dict`；`activate_template(name, candidate_path, force=False) -> dict`（写 `imported_at` 到 settings）；`archive_current_template(name)`；`confirm_active_template()` |
| `email_generator.py` | 变量组装 + 渲染 + 落 drafts.json（**无 LLM、无降级**） | `generate_for_customer(customer, language=None) -> dict`（未设 `selected_template` 即 `RuntimeError`）；`generate_all(customers=None)`；内部 `_build_variables(customer, template_config, language)`（含别名映射与未匹配变量警告）、`_render_subject(config, variables)`、`_current_date(language)` |
| `preview.py` | 高保真预览，环境自适应 | `open_draft_preview(draft)`；`open_template_preview(template_name)`；`open_replies_preview(replies)`；内部 `_has_gui() -> bool`（有 `DISPLAY` 且非 WSL，或 macOS/Windows 原生）；`_open_html()` 入口按 `_has_gui()` 一次决策 headed/headless |
| `sender.py` | SMTP 发送、可中断队列、CID 内联图片 | `create_email_message(draft)`；`send_email(draft) -> bool`；`process_queue(drafts=None)`；`check_draft_images(drafts) -> list[str]`（发送前图片路径预检，缺失时黄色警告 + 确认） |
| `receiver.py` | IMAP 回复匹配采集 | `check_replies(dry_run=False) -> list[dict]` |
| `deliverability.py` | 风控：日上限、间隔、白名单、相似度 | `can_send(draft, history) -> (bool, str)`；`wait_before_next()` |
| `status.py` | 顶部两行状态栏 | `compute_status() -> {"template_name", "imported_at", "confirmed", "send_state": {"state", "remaining"}, "unseen_replies"}`；`print_status_bar()`（每次调用重新计算，无缓存） |
| `cli_controller.py` | 交互菜单 | `run()`；菜单 6 `menu_import_template()` 子项 `[I]导入 [A]选择生效模板 [C]确认/重置 [M]管理归档 [R]重置导入状态 [Q]返回`；设置菜单 `[1]发送者信息 [2]切换模型 [3]切换skill [4]配置检查` |
| `llm_client.py` | OpenAI 兼容客户端（Moonshot 适配） | `complete(system, user, ...)`；`complete_json(system, user, schema, temperature)` |

**代码护栏**：`email_generator`、`sender`、`receiver` 禁止 import `llm_client`，由 `tests/test_no_llm_in_pipeline.py` 静态检查固化。

## 4. 数据流

```
templates/import/<file>.md/.docx/.pdf
  │
  ▼
template_importer
  ├─ 文本 → Markdown；docx 内嵌图片 → assets/images/<name>_img_NN.png
  │   （Markdown 原位插入 {{IMAGE:<name>_img_NN}} 占位符）
  ├─【唯一 LLM 调用】structure_template_with_llm()
  │   输出：{subject_template, cn_html, en_html, variables, images, files}
  └─ 写入 templates/email/<name>/{template.html, template_<lang>.html, config.yaml}
      + settings.json: template_confirmed=false, template_imported_at[<name>]=now
  │
  ▼
菜单6 [A] 选择生效模板  → settings.json: selected_template（长期生效）
菜单6 [C] 预览并确认    → settings.json: template_confirmed=true
  │
  ▼
data/customers.csv
  → interaction_analyzer.analyze()      # 仅 {stage, language, reason}，不驱动模板选择
  → email_generator.generate_for_customer()
      ├─ 读 config.get_selected_template()（空 → RuntimeError）
      ├─ _build_variables()（sender_profile + customer 硬性映射 + 别名映射）
      └─ template_engine.render() → data/drafts.json (review_status=pending)
  │
  ▼
菜单 [2] 逐条审核（Playwright 预览）→ approved / rejected
菜单 [3] 发送 → sender.process_queue()
      ├─ check_draft_images() 预检（缺失警告 + 确认）
      ├─ deliverability.can_send() → send_email()（CID 内联图片）
      └─ logger.log_email_send() → data/email_logs.csv
菜单 [4] 回复 → receiver.check_replies() → data/reply_logs.csv
      （查看后 mark_all_replies_viewed() 清零状态栏计数）

status.compute_status() 每次主菜单刷新实时聚合 settings + drafts + logs + reply_logs
```

## 5. 关键数据结构

### 5.1 `data/settings.json`

```json
{
  "selected_template": "initial_contact",
  "template_confirmed": true,
  "template_confirmed_at": "2026-08-06T10:00:00",
  "template_imported_at": {"initial_contact": "2026-08-01"},
  "active_model_index": 0,
  "skill_mode": "concise"
}
```

> 读侧对缺失键一律给默认值，向后兼容旧版 settings.json。

### 5.2 `data/drafts.json` 单条记录

```json
{
  "draft_id": "20260805-001",
  "customer_id": "001",
  "email": "camgrado@gmail.com",
  "template": "initial_contact",
  "stage": "new_lead",
  "language": "cn",
  "subject": "...",
  "html_body": "<html>...</html>",
  "text_body": "...",
  "images": [{"cid": "initial_contact_img_01", "path": "assets/images/initial_contact_img_01.png"}],
  "files": [{"name": "catalog_pdf", "path": "assets/files/catalog_pdf.pdf"}],
  "personalization_note": "",
  "review_status": "pending",
  "created_at": "2026-08-05 10:00:00",
  "rendered_by": "local"
}
```

> `stage` 字段保留作信息展示，不再驱动模板选择。`review_status`：`pending` / `approved` / `rejected`。

### 5.3 `templates/email/<name>/config.yaml`

```yaml
template_name: initial_contact
purpose: [cold_outreach]
customer_type: [designer, distributor]
subject_template: "{{CUSTOMER_COMPANY}} 商业家具合作提案 | GRADO Contract"   # 非空，导入时强制保证
variables:
  - SENDER_NAME
  - SENDER_TITLE
  - SENDER_COMPANY
  - SENDER_EMAIL
  - SENDER_PHONE
  - SENDER_MARKET_REGION
  - CUSTOMER_FIRST_NAME
  - CUSTOMER_NAME
  - CUSTOMER_COMPANY
  - CUSTOMER_POSITION
  - CUSTOMER_LOCATION
  - CUSTOMER_INDUSTRY
  - CURRENT_DATE
images:
  - initial_contact_img_01
files:
  - catalog_pdf
rules:
  - 只替换模板中声明的变量，禁止编造信息。
  - 邮件正文语言由 language 参数决定。
```

> `recommended_stage` 为废弃字段，读取方不再消费。

### 5.4 `data/reply_logs.csv`

列：`email_id, sender, receive_time, content, status`。`status` 语义：`replied`（未查看）/ `viewed`（已在菜单 4 查看），由 `mark_all_replies_viewed()` 批量维护，状态栏"未查看回复数"据此统计。

### 5.5 `templates/sender_profile.md`

```markdown
---
sender_name: "张三"
sender_title: "商务拓展经理"
sender_company: "GRADO Contract"
sender_email: "zhangsan@gradodesign.hk"
sender_phone: "+86 138 0000 0000"
sender_market_region: "大中华区"
---
```

## 6. LLM 调用约束

1. 唯一调用点：`template_importer.structure_template_with_llm()`；json_schema 输出（Moonshot 走 prompt 注入 + temperature=1.0 特例）。
2. 图片/文件二进制不上传 LLM，只传 `{{IMAGE:name}}` / `{{FILE:name}}` 占位符名。
3. Prompt 强制约束（`prompts/template_import_prompt.md`）：
   - `subject_template` 禁止为空：原文有标题则提取，无标题则依据正文自动生成（≤60 字符）。
   - 语言纯净规则：`en_html` 全英文、零汉字，品牌名统一 `GRADO Contract`；`cn_html` 正文为中文，品牌名用 `GRADO Contract` 或 `格度商业家具`，两者不得并排出现。
4. 代码护栏：`structure_template_with_llm()` 返回后正则扫描 `en_html` 是否含汉字，命中打印警告；`subject_template` 为空时走本地兜底生成。

## 7. 错误处理策略

| 类别 | 策略 |
|------|------|
| 配置类（未设 selected_template、模板目录缺失、模板未确认） | `RuntimeError` 上抛，CLI 层捕获打印中文指引（指明菜单 6 的具体子项），不静默降级 |
| 资源类（图片/附件缺失） | 渲染期保留占位；发送前 `check_draft_images()` 统一预检，黄色警告清单 + Y/n 确认 |
| 变量类（模板声明但无数据源） | 替换为空字符串，`generate_all()` 结束时汇总打印黄色警告清单 |
| 外部服务类（SMTP/IMAP/LLM/Playwright） | try/except 包裹、写日志、批次内单点失败不中断队列 |
| 中断类（KeyboardInterrupt） | 落 state 文件，重入续跑 |

## 8. 关键决策与约束

1. LLM 调用点唯一化（见第 6 节）。
2. 变量命名统一大写下划线（`SENDER_*`、`CUSTOMER_*`）；`email_generator` 内置别名映射（如 `company_name → CUSTOMER_COMPANY`、`DATE → CURRENT_DATE`）兼容外部模板。
3. 发送者信息唯一可信源：`templates/sender_profile.md`。
4. 语言判定规则：`interaction_analyzer._detect_language()` 按 location 后缀/汉字/拼音城市名（beijing、shanghai、guangzhou、shenzhen、chengdu、hangzhou 等）判定；中国大陆客户中文，海外英文。
5. 日期本地化：`CURRENT_DATE` 按当封邮件 language 生成——英文 `August 5, 2026`（无前导零），中文 `2026年8月5日`。
6. 模板确认前置：未确认模板时生成被阻断。
7. 预览环境自适应：`_has_gui()` 为真 → `headless=False` 弹窗；否则 `headless=True` 截图 `data/latest_preview.png`，路径以 ANSI 加粗黄色醒目打印。
8. 图片 CID 内联：HTML 邮件中 `images` 列表以 `Content-ID` 内联附加（`MIMEMultipart("related")`），不出现在附件区。
9. 发送频率控制：随机间隔 30-120 秒。
10. 客户跳过规则：`name` 以 `#` 开头跳过生成/发送。
11. 归档分类：`templates/archive/<template_name>/YYYY/MM/DD/<HHMMSS>/`。
12. 不修改 PRD/UserFlow/tasks（Manus 职责）。

## 9. 状态栏规格（PRD 3.1）

每次进入主菜单时顶部常驻，两行内可读，每次刷新重新计算：

```
─────────────────────────────────────────────────────
模板: initial_contact (2026-08-01) ✅已确认
发送: 部分发送（剩余 12 封）  |  回复: 3 封
─────────────────────────────────────────────────────
```

- 当前模板：`selected_template` + `template_imported_at`；未选择时显示警告。
- 确认状态：`✅ 已确认` / `⚠️ 未确认（需到菜单6确认后才能生成）`。
- 发送状态：`未发送` / `部分发送（剩余 N 封）` / `已全部发送`（approved 草稿集合 vs 已发送 draft_id 集合）。
- 回复情况：`N 封回复待查看`（`reply_logs` 中 `status != "viewed"` 计数）。

## 10. 验证策略

| 模块 | 验证方法 |
|------|---------|
| 单元测试 | `tests/`（pytest）：分析器返回键集合、语言判定、变量映射/别名、日期格式、状态栏计算、图片预检、预览环境决策、LLM 护栏静态检查 |
| template_importer | 放入带图 `.docx`，断言 `assets/images/` 出现 `<name>_img_NN.png`、Markdown 含 `{{IMAGE:}}` 占位符、config.yaml `subject_template` 非空 |
| email_generator | 无 selected_template 必报错；drafts.json 中 `template` 与 settings 完全一致；无 LLM 调用 |
| status | 发送一封后重回主菜单，"剩余数量"立即更新；查看回复后计数归零 |
| preview | 有桌面环境弹窗；无桌面环境生成 `data/latest_preview.png` 且路径醒目 |
| sender | 真实白名单邮箱实发含图邮件，目检图片正文内显示（CID 内联） |
| 端到端 | 导入带图模板 → 菜单6[A]选择 → [C]确认 → [1]生成 → [2]审核 → [3]发送 → [4]回复 |

## 11. TASK-G.4 预研：本地 Web UI 可行性评估（仅评估，未实施）

> 背景：阶段 G 黑盒测试暴露纯 CLI 交互的体验短板（Playwright 环境依赖、终端预览割裂、模板/草稿编辑依赖手工改文件）。本节评估将交互层升级为本地 Web UI（FastAPI + 网页编辑器）的可行性。**本节为预研结论，不代表已立项实施。**

### 11.1 方案

**架构前提（现状有利点）**：系统已是三层结构——交互层（`cli_controller`）→ 业务模块（importer/generator/sender/receiver/status，均为纯函数式服务接口）→ 数据层（`data_store` 唯一读写出口）。Web 化只需**替换交互层**，业务模块与数据层不动，核心原则（LLM 调用点唯一化、模板用户主权、白名单/日上限/确认门禁）原样延续。

**候选方案对比**：

| 方案 | 内容 | 评价 |
|------|------|------|
| A（推荐）| FastAPI + uvicorn 本地服务（仅绑 `127.0.0.1`），Jinja2/原生 HTML+JS 前端，无 node 构建链 | 纯 Python 依赖、与现有技术栈一致；API 即是对现有服务函数的薄封装 |
| B | 继续增强 CLI | 成本最低，但无法解决预览/编辑体验的根本问题 |
| C | 现代 SPA 框架（React/Vue + 构建链） | 交互上限高，但引入 node 工具链，与"轻量 demo"定位不符，弃 |

**方案 A 要点**：

1. **API 面**：现有菜单项一一映射为 REST 端点（状态栏、模板导入/选择/确认/归档、草稿生成/审核、发送队列、回复列表、设置），约 15-20 个端点；业务逻辑零复制——端点内只允许调用现有模块函数，禁止在 Web 层重写业务逻辑。
2. **预览简化**：浏览器本身即 HTML 渲染器，草稿/模板预览由"生成文件 + Playwright 弹窗/截图"退化为直接返回 HTML 响应，**可移除 Playwright 依赖**（`preview.py` 的 `_has_gui()` 自适应逻辑在 Web 形态下自然消解）。
3. **模板编辑器**：定位为"HTML 源码编辑 + 实时预览 + config.yaml 表单化"，**不做富文本所见即所得**（范围黑洞，demo 不需要）。
4. **长任务**：生成/发送队列改为后台任务 + 进度轮询（或 SSE）；CLI 的 Ctrl+C 落 state 续跑机制映射为"取消任务"端点，`generation_state.json`/`sending_state.json` 语义不变。
5. **CLI 保留**：双入口并存，CLI 作为无浏览器环境与脚本化操作的后备；两层共享同一套服务函数与 `data_store`。

### 11.2 成本

| 项 | 估算 |
|----|------|
| 新增依赖 | `fastapi`、`uvicorn`（纯 Python、轻量）；前端原生 JS，无构建链 |
| 后端 | 15-20 个端点薄封装 + 后台任务管理，约 3-5 天 |
| 前端 | 5-8 个页面（状态看板 / 模板管理 / 模板编辑 / 草稿审核 / 发送队列 / 回复 / 设置），约 4-6 天 |
| 测试 | `TestClient` API 测试 + 并发安全测试；现有 120 例单元测试不受影响 |
| 合计 | demo 规模约 **1.5-2 周**单人工作量 |

### 11.3 风险

| 风险 | 等级 | 缓解 |
|------|------|------|
| **并发安全**：`data_store` 现为单线程顺序读写、无文件锁；Web 并发请求下 `drafts.json`/state 文件可能竞写 | 高 | 引入全局读写锁（或单 worker + 请求内串行化）；先行专项加固 data_store 再动交互层 |
| **双入口行为漂移**：CLI 与 Web 各自演化出重复业务逻辑 | 中 | 代码护栏测试固化：Web 层禁止直接读写 `data/` 文件、禁止 import `llm_client`（沿用 §3 护栏模式） |
| **安全边界**：发送能力暴露到本机以外 | 高 | uvicorn 强制 `host=127.0.0.1`；`.env` 凭据仅服务端读取，永不下发前端；白名单/日上限/确认门禁在 `deliverability`/`sender` 层，与交互层无关，天然继承 |
| **范围蔓延**：编辑器向富文本/WYSIWYG 膨胀 | 中 | 立项文档锁定"源码编辑 + 实时预览"范围，超出部分一律拒绝 |
| **中断语义变化**：后台任务取消与续跑状态机比 Ctrl+C 复杂 | 低 | 复用现有 state 文件格式，取消 = 写 state + 停止循环，与续跑共用一套读写 |

### 11.4 留档方案 3（Pillow 图片管线）评估

PR #14 留档的方案 3：引入 Pillow 做 `Image.open()` 识别与自动转码（SVG/HEIC/CMYK → RGB PNG 后再附件）。

- **现状**：魔数探测（`guess_image_subtype`）已覆盖 JPEG（含 ICC/APP2）/PNG/GIF/WebP/BMP/TIFF/ICO/SVG 的**识别**需求，发送崩溃问题已闭环，v1.0 无引入必要。
- **增量价值**：Pillow 解决的是识别之外的**兼容性与体积**问题——CMYK/SVG/HEIC 自动转 RGB PNG（主流邮件客户端兼容）、尺寸/压缩归一（控制邮件体积）、以及 Web UI 上传时的图片校验管线。
- **代价**：新增重量级二进制依赖（wheel 分发，CI 环境需验证）；HEIC 另需 `pillow-heif` 插件。
- **结论**：**v1.0 不引入**。若 Web UI 立项，上传校验管线是 Pillow 的天然落点，届时与 11.1 方案一并评估引入。

### 11.5 结论

1. **技术上可行且架构友好**：现有三层分层使 Web 化成为"换交互层"而非"重写"，核心原则与安全门禁全部自然继承；预览场景反而因浏览器原生渲染而**简化**（可去除 Playwright 依赖）。
2. **建议批准，但排在 v1.0 发布之后**，且第一期收敛为：状态看板 + 草稿审核 + 本地渲染预览；模板编辑/导入 Web 化放第二期。
3. **前置条件**：立项前先做 `data_store` 并发安全加固（11.3 高风险项），并以测试固化。
4. **Pillow（方案 3）随 Web UI 立项一并评估**，v1.0 维持纯魔数方案。
