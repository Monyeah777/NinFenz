# 演示签名者（demo signers）
> 最后更新：2026-11-14（复核）

**这不是作者身份，是用于演示「馆藏条目签名锚」全链的**一次性**密钥对**——私钥不入库
（在本地 `.rivet/scratch/nf_demo_ssh/`），此处只公布**公钥与 allowed_signers**，
让任何读者都能端到端复现验证：

```bash
# 读者侧独立验证（纯标准库，不依赖 NF 代码）
python scripts/nf_verify.py --entry NF-1 --ssh-allowed-signers protocol/demo_signers/allowed_signers
# 仓库侧同语义校验
python scripts/nf.py library verify --ssh-allowed-signers protocol/demo_signers/allowed_signers --ssh-identity nf-demo@local
```

**生产使用**：作者应以**自己的密钥**重签并公布对应公钥：
`python scripts/nf.py library attest <编号> --ssh-key <你的私钥> --ssh-identity <你的身份>`
（或改用 `--key-file` 的 hmac 级）。演示锚只证明「机制可跑通」，不构成任何身份背书。
>
> **复核（2026-11-14）**：公钥与 `allowed_signers` 复核不变；但**实测发现一处口径过强**——NF-1 当前**未挂签名锚**，
> 所以上面两条命令跑出来是「可验证通过 + 真实性**未验**」（exit 0），**并不构成「端到端签名验证通过」**。
> 要真正走通 anchor 面，必须由作者用**自己的密钥**重签（命令见下）。本轮把这个落差写清，避免读者把「机制可跑」误读成「已签名」。

## 现状对照（2026-11-14 · 以实跑与 `allowed_signers` 实读为准）

| 面 | 当前口径 | 复核方式 |
|---|---|---|
| `allowed_signers` | **1 条**：`nf-demo@local` · `ssh-ed25519` · 与第三列身份同名 | 文件实读 |
| NF-1 锚状态 | **未挂签名锚**（输出显示「该条未挂签名锚（仅包含关系可验）」） | `nf_verify.py --entry NF-1` 实跑 |
| 两条命令的结论 | 均 **exit 0**，但口径是「**真实性未验**」——只证包含关系与内容绑定 | 实跑输出 |
| 私钥位置 | 本地 `.rivet/scratch/nf_demo_ssh/`（**不入库**；fresh clone 没有它属预期） | 目录约定 |
| 生产口径 | 作者用自己的密钥重签并公布公钥；演示锚**不构成身份背书** | 本文末段 |

**一句话**：演示锚证明「这条链能跑」，不证明「这条已经被签名」。两者差一个 anchor 面。

## 复现与引用口径

```bash
python scripts/nf_verify.py --entry NF-1 --ssh-allowed-signers protocol/demo_signers/allowed_signers
python scripts/nf.py library verify --ssh-allowed-signers protocol/demo_signers/allowed_signers --ssh-identity nf-demo@local
python scripts/nf_verify.py --entry NF-1            # 不给 allowed_signers 也 exit 0（仅包含关系）
```

- 引用本页时：`allowed_signers` 是**允许清单**，不是签名；「验不过」与「没挂锚」是两种状态，前者红、后者只标「未验」。
