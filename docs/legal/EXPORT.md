# 出口 / 加密组件（EXPORT）

> ⛔ 操作指令：本件是出口/制裁风险面的工程登记；机读在 `protocol/legal.json` 的 `export` 段，判据 `desktop/tests/test_legal_contract.py`。**不构成出口/制裁法律意见**。
> 状态：v1（G0 · 2026-11-14）· 依据：`NF-Final-方案-2026-11-13.md` §15A.2

## 加密组件清单

| 组件 | 用途 | 形态 |
|---|---|---|
| `desktop/src/core/ed25519.py` | 数字签名（Ed25519） | 仓内纯 Python 实现 |
| `desktop/src/core/timestamp.py` | RFC 3161 时间戳（离线验证） | 标准协议客户端/验证器 |
| `desktop/src/core/trust/dsse.py` | DSSE/PAE 签名信封 | 标准格式 |
| `desktop/src/core/trust/keys.py` | issuer/key 注册与生命周期 | 密钥管理（不自造密码学） |
| `desktop/src/core/trust/key_material.py` | 密钥材料落盘与权限（0600） | 密钥管理 |
| `desktop/src/core/trust/public_anchor.py` | 透明日志包含证明/SET 验证 | 标准协议验证器 |

## 双用途与评审触发

- 双用途：数字签名、时间戳、透明日志包含证明均可用于一般内容真实性证明；不设计为攻击工具。
- **触发评审**（任一发生即须先做出口/制裁影响核对，再合入/分发）：
  1. 新增密码算法/密钥交换/加密库；
  2. 对外分发含签名/时间戳能力的构建物（含 npm/容器/二进制）；
  3. 引入新的外部 TSA/CA/透明日志依赖；
  4. 客户所在司法辖区有额外出口/制裁要求。

## 纪律

- 本仓**不自造密码学**：算法/协议复用成熟标准（DSSE、RFC 3161、RFC 6962、Ed25519）。
- 本清单只做工程登记；是否构成受控物项、是否需要许可，由人工/律师按适用法律判定。
- 与 `SECURITY.md`、`docs/legal/LEGAL.md`、`docs/legal/VENDORS.md` 交叉引用；发现缺件走 `SECURITY.md` 通道。
