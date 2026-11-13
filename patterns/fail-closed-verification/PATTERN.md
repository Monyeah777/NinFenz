---
id: fail-closed-verification
name: 缺验证器即拒绝，不静默降级
status: active
scope:
  - 代码层
  - 协议层
applies_to:
  - desktop/src/core/attest.py
  - desktop/src/core/driver.py
  - desktop/src/core/approval.py
  - scripts/nf_verify.py
rules:
  - 校验路径遇到"验证器/密钥/锚缺失"时必须判不可信，不得降级成"通过"
  - 降级只允许由使用者显式选择（如改用另一级签名方案），且必须在输出里写明当前信任级
  - 内容被改后旧锚即失效（判 FAIL），不保留"曾经有效"的通行权
evidence:
  - check33
  - docs/attest.md
  - docs/receipts.md
---

## 为什么

安全面上最贵的错误不是"拒绝了好东西"，而是"放过了坏东西"。缺 cosign、缺 hmac 密钥、
缺 allowed_signers 都是**证据缺失**，证据缺失不等于证据成立。

## 怎么用（2026-11-14 实测校正）

```bash
python scripts/nf_verify.py --entry NF-1
# 实测：inclusion/content/anchor 三行 + 「=> 可验证通过」，exit 0
# 同段会打印口径：「真实性**未验**——该条未挂签名锚（仅包含关系可验）」
python scripts/nf_verify.py --entry NF-1 --ssh-allowed-signers protocol/demo_signers/allowed_signers
# 显式给允许签名者：三行同上；NF-1 未挂锚，真实性口径仍是「未验」
```

> **校正说明（历史留痕）**：原文写「缺允许签名者 → 如实报 exit 1」，**实测不符**——NF-1 未挂签名锚时，
> 工具的行为是 **exit 0 + 显式标注「真实性未验」**，即「可验面与不可验面分开报」，而不是整条拒绝。
> 真正 fail-closed 的是**该验而验不了**的路径（要验签名却缺 allowed_signers、密钥/锚损坏等），不是「没挂锚」本身。

## 反例

把"验证器未安装"当成"跳过校验"，或在输出里把 `digest_only` 级说成"已验证"。

## 现状对照（2026-11-14 · 以实测与 check 实读为准）

| 面 | 当前口径 | 复核方式 |
|---|---|---|
| 门禁接线 | **check33**（`verify.sh` 中定义；`nf verify --only 33` 可单跑） | 命令实跑 |
| 证据件 | `docs/attest.md` · `docs/receipts.md`（均在盘） | 文件实读 |
| 三级信任 | `attest.py`：内容摘要 → 包含证明 → 签名锚（外挂锚 = 外部验证器，未知方案 fail-closed） | 模块头部与常量 |
| 缺锚行为 | **exit 0 + 显式标注「真实性未验」**（可验面与不可验面分开报） | `nf_verify.py --entry NF-1` 实测 |
| 超时行为 | 验证器挂住时**超时即 fail-closed**（不无限期挂住） | `attest.py` 超时常量 |

- **本文不钉运行时状态**：NF-1 是否挂锚、当前信任级以命令输出为准；本文只固化「缺什么就报什么」的机制。
- 「fail-closed」的准确含义：**该验而验不了 → 判不可信**；不是「没锚就把整条判死」（那会把只读包含证明一并否掉）。

## 复现与引用口径

```bash
python scripts/nf_verify.py --entry NF-1          # 三面逐项 + 真实性口径（exit 0 也可能「未验」）
python scripts/nf.py verify --only 33           # 单跑 check33（attest/回执面）
```
