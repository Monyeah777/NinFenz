# 治理附件模式（WP-32，G3）

> ⛔ 操作指令：本件是 WP-32 附件模式的人读说明；机读真源 `protocol/attachment.json`（`nf-attachment/1`），判据 `desktop/tests/test_attachment_contract.py`，实现 `desktop/src/core/attachment.py`。附件策略不得改变生产输出。
> 状态：v1（G3 · 2026-11-15）· 依据：G3 WP-32（Attachment：none/observe/require + 独立性测试）

## 模式

| 模式 | 阻塞 | 记录观察 | 语义 |
|---|---|---|---|
| `none` | ✗ | ✗ | 治理不介入；生产照常 |
| `observe` | ✗ | ✓ | 记录证据在场/等级；**绝不阻塞**（WARN 不等于通过治理） |
| `require` | ✓ | ✓ | 证据必须存在、验证 ok、等级 ≥ `min_level`（默认 T1），否则拒收 exit 2 |

## API

```python
from core import attachment as at
at.evaluate("observe", {"bundle_present": False})   # passed=True + WARN
at.evaluate("require", {"bundle_present": True,
                        "verification": {"ok": True, "level": "T1"}})  # passed
at.check_registry()                                  # 模式表自检
```

## 拒绝码（exit 2 + 修复指引）

- `ATTACHMENT-MISSING`：require 下证据不在场；
- `ATTACHMENT-NOT-VERIFIED`：证据在场但验证未通过；
- `ATTACHMENT-LEVEL-LOW`：等级低于 min_level；
- `MODE-UNKNOWN`：未知模式。

## 独立性

- `evaluate` 是**纯函数**：不读写生产产物；
- 判据断言：同 intent/adapter 的装配记录在三种模式下 `digest` 逐字节一致（治理开关不改变生产输出）。

## 边界

- observe ≠「通过治理」；require 只做证据/等级门，不评价内容质量。
- 治理报告/审计包（WP-33）不在此件；适配层见 WP-31。
