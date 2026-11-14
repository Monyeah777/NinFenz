# 可访问性 QA（A11Y_QA，L16）

> ⛔ 操作指令：本件是 `NF-Final §13A L16` 可访问性/人因层的 QA 报告；每条指标须可复跑，未做项如实写 template-only，不写成全绿。
> 状态：v1（G0 · 2026-11-14）· 真源 `protocol/accessibility.json` + `A11Y.md` · 判据 `desktop/tests/test_a11y_i18n_contract.py`

## 质量目标

- 颜色不承载唯一语义（状态用 PASS/WARN/FAIL 文字，`NO_COLOR` 一票否决）。
- 全键盘可操作（CLI/TUI 无鼠标依赖）；窄宽度不丢信息（限长/宽度可配）。
- 错误可识别且有修复指引；AI 输出有人类复核闸门。
- `not-applicable` 项有理由，`partial` 项如实标缺口，违规预算=0。

## QA 活动与实测

| 活动 | 指标 | 判据 | 本轮实测 |
|---|---|---|---|
| WCAG 清单 | 8 条适用项，enforced 必须有测试/门禁证据 | `test_a11y_i18n_contract.py::test_wcag_*` | 通过（6 enforced / 1 partial / 1 n-a） |
| 无色/键盘 | `NO_COLOR` 存在、self_check 存在、TUI 文件在场 | `test_terminal_facts` | `no_color=True`、`self_check=True`、`tui/nf.py`+`_surface.py` |
| PAIR/HAX 评审 | 6 条原则各有控制点+证据 | `test_human_factors` | 通过 |
| 可用性测试 | UT-01/UT-02 为 template-only（未冒充已做） | `test_usability_template` | template-only，如实登记 |
| 违规预算 | violation_budget=0 | `test_registry_valid` | 0 |

## 质量债 / 外部操作

| 项 | 级别 | 说明 | owner | 复审 |
|---|---|---|---|---|
| WCAG-3.1.1 仅 partial | P2 | 正文语言标注未做（当前靠入口切换行/译件） | maintainers | 新增语言面时 |
| 外部可用性测试未执行 | P2 | UT-01/02 只有模板；外部用户实测属外部操作 | user | 有试点时 |
| 屏幕阅读器实测未行 | P2 | CLI 输出为纯文本，未在真实读屏器上抽样 | maintainers | 版本发布前抽查 |

## 结论

- 可访问性面判据可复跑（清单/无色/键盘/人因/模板/预算）；**不声称 WCAG 合规**，`partial` 与未做项显式登记。
