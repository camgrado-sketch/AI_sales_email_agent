# Bug Report: `feature/local-template-replace` 黑盒测试报告

**测试分支**：`feature/local-template-replace`
**测试时间**：2026年8月5日
**测试场景**：模拟用户提供图文模板后，系统生成变量模板，然后导入模板生成邮件草稿的完整流程。

---

## 核心 Bug 列表与分析

### 1. 界面交互缺陷：缺乏可视化的弹窗/菜单选择反馈
*   **现象**：用户期望在终端有弹窗界面交互，但实际操作中，系统在预览和模板选择时，只是将路径打印在终端，或尝试静默启动浏览器截图，没有真正的“界面反馈”或“模板选择列表”。
*   **代码定位**：
    *   `email_agent/cli_controller.py` 中，`_confirm_template_flow()` (Line 459) 会一次性自动打开所有激活模板的预览，然后仅在终端给出一个全局的 `(Y/n)` 确认。
    *   `email_agent/preview.py` 中，预览机制依赖 Playwright 的 Headless 截图或系统浏览器启动。如果环境不支持（如纯终端/无 GUI），只会打印一个 `data/latest_preview.png` 的路径。
*   **问题本质**：系统缺乏真正的“模板选择”UI 交互。用户只能“全局确认”所有模板，无法在界面上直观地“选择哪个模板生效”。

### 2. 模板选择缺陷：无法手动指定生效模板
*   **现象**：用户无法判断哪一个模板被调用，也无法手动选择生效模板。
*   **代码定位**：
    *   `email_agent/config.py` 中的 `is_template_confirmed()` 只是一个全局的布尔值 (`True/False`)。
    *   `email_agent/email_generator.py` 中的 `generate_for_customer()` 完全依赖 `interaction_analyzer.analyze()` 的硬编码规则（如 `new_lead` -> `initial_contact`）来自动决定模板。
*   **问题本质**：模板选择被写死在代码规则中，且 `settings.json` 中没有 `active_template` 或 `selected_template` 字段，导致用户失去了控制权。

### 3. 变量匹配缺陷：模板占位符与系统变量名不一致
*   **现象**：生成的邮件内容跟已有的模板完全不匹配，大量占位符（如 `{{market_region}}`）原样输出。
*   **代码定位**：
    *   `email_agent/template_engine.py` 的 `_normalize_variables()` 会将字典键转换为全大写（如 `MARKET_REGION`）。
    *   但 `email_agent/email_generator.py` 的 `_build_variables()` 中，赋值的键名是 `SENDER_MARKET_REGION`、`CUSTOMER_COMPANY` 等。
    *   用户模板中的 `{{market_region}}` 和 `{{company_name}}` 无法与生成器中的 `SENDER_MARKET_REGION` 和 `CUSTOMER_COMPANY` 匹配。
*   **修复建议**：需要统一变量命名空间。建议在 `_build_variables` 中增加对 `config.yaml` 中声明的 `variables` 的宽容匹配逻辑，或者强制 LLM 在导入模板时使用标准的系统变量名。

### 4. 语言设定缺陷：中英文判定逻辑漏洞
*   **现象**：生成的邮件没有遵循中英文语言设定的原则（如针对上海客户生成了英文邮件，或日期始终是中文）。
*   **代码定位**：
    *   **位置判定失效**：`email_agent/interaction_analyzer.py` 的 `_detect_language()` 中，判断中文城市的关键词是汉字（`['上海', '北京', ...]`）。如果客户资料的 Location 写的是拼音（如 `Shanghai`, `Beijing`），将无法匹配，从而错误地回退到默认语言 `en`。
    *   **日期语言硬编码**：`email_agent/email_generator.py` 的 `_build_variables()` (Line 47) 硬编码了 `"CURRENT_DATE": _current_date(language="cn")`，导致无论什么语言的邮件，日期格式默认都是中文（尽管后面有覆盖逻辑，但初始化时存在隐患）。

### 5. 标题生成缺陷：`config.yaml` 缺失 `subject_template`
*   **现象**：生成的草稿邮件可能没有主题（Subject 为空）。
*   **代码定位**：测试发现 `templates/email/*/config.yaml` 中缺失了 `subject_template` 字段。`email_generator.py` 的 `_render_subject()` 在读取不到该字段时会返回空字符串。

---

## 修复建议 (Action Items for Claude Code)

1.  **重构模板选择逻辑 (UI & State)**：
    *   在 `cli_controller.py` 中新增“选择激活模板”的交互菜单。
    *   在 `settings.json` 中增加 `selected_template` 字段，允许用户覆盖自动规则。
2.  **修复变量映射 (Template Engine)**：
    *   修改 `email_generator.py` 的 `_build_variables`，建立从标准系统变量（如 `CUSTOMER_COMPANY`）到用户自定义变量（如 `company_name`）的映射别名机制。
3.  **修复语言判定 (Analyzer)**：
    *   在 `_detect_language` 的判断列表中加入拼音支持（`shanghai`, `beijing`, `guangzhou` 等）。
4.  **补充模板元数据 (Config)**：
    *   确保所有 `config.yaml` 包含 `subject_template` 字段。
