# 本地化 QA（I18N_QA，L16）

> ⛔ 操作指令：本件是 `NF-Final §13A L16` i18n 层的 QA 报告；覆盖/时区/bidi 指标须可复跑，未做项如实登记。
> 状态：v1（G0 · 2026-11-14）· 真源 `protocol/locales.json` + `protocol/i18n.json` + `I18N.md` · 判据 `desktop/tests/test_a11y_i18n_contract.py`

## 质量目标

- 语言面覆盖可核：locale 数、入口、文档译件镜像与 `source_sha256` 新鲜度。
- 安全时间戳一律 UTC；显示转换不写进证据。
- 语言面正文无 bidi/零宽控制字符；RTL 策略显式（当前无 RTL locale，不冒充支持）。

## QA 活动与实测

| 活动 | 指标 | 判据 | 本轮实测 |
|---|---|---|---|
| locale 覆盖 | locale ≥3、入口 ≥3、文档译件组 ≥6 | `test_i18n_coverage` | zh/en/ja；3 入口；6 组译件 |
| 镜像一致 | `docs/en` 与 `docs/ja` 文件集相等 | `test_i18n_coverage` | 6/6 镜像 |
| 译件新鲜度 | `source_sha256` 与源件一致 | `python scripts/nf.py locales --json` | 见命令输出（不改源即不变） |
| 时区口径 | UTC ISO-8601 样例可解析 | `test_i18n_timezone` | `is_iso_instant("...Z")=True` |
| bidi/零宽 | 语言面扫描零命中、无 skipped | `test_i18n_bidi_clean` | 0 命中 / 0 skipped |
| RTL | 当前无 RTL locale；新增须先过扫描+渲染 | `test_i18n_rtl_policy` | 策略在场，planned |

## 质量债 / 外部操作

| 项 | 级别 | 说明 | owner | 复审 |
|---|---|---|---|---|
| 无 RTL locale | P2 | 阿拉伯语/希伯来语未支持；新增前必须过 bidi 扫描与 RTL 渲染测试 | maintainers | 新增语言时 |
| 译件为仓内维护 | P2 | 未用 ISO 17100 外部语言服务，不冒充专业翻译 | maintainers | 对外发布前 |
| 本地化法律差异 | P2 | 合同/隐私文案按适用法律本地化（当前模板仅中文/英译） | user | 涉外签约时 |

## 结论

- i18n 面判据可复跑（覆盖/镜像/时区/bidi/RTL 策略）；**不声称完整 i18n/RTL 支持**，缺口显式登记。
