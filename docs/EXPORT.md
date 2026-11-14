# 出口管制声明（Export Control）

> **最后复核：2026-11-13**（本声明随仓库密码学面演进同步；2026-11-13 修正一处与仓库事实不符的表述，见下）

NF 自带与依赖的密码学只用**标准公开算法 + 标准库实现**：

- 摘要/认证：`hashlib`（SHA-2）/ `hmac` / `secrets`（以及 .NET 的 `System.Security.Cryptography.SHA256`）；
- 公钥签名：**Ed25519（RFC 8032）**——仓库内为**纯标准库自写实现**（`desktop/src/core/ed25519.py`，
  只依赖 `hashlib`；判据 `desktop/tests/test_ed25519.py`：RFC 8032 黄金向量 + 篡改必拒 + 与
  `cryptography` 库的**可选**交叉验证（该库不在场时跳过，不冒充已验））；
- 外部签名/验证：签名能力可调用**外部** `ssh-keygen`（`nf library attest <编号> --ssh-key …`，锚落 `library/anchors/*.sig`；内容级 `nf attest --key-file` 为 HMAC 路径）。

> **修正（2026-11-13）**：本声明此前写「本仓库**不自制 ed25519 或任何密码算法**」——与仓库事实不符：
> 2026-11-07 起仓库确有 **RFC 8032 Ed25519 的纯标准库自写实现**（用于跨组织吊销的公钥签名）。
> 该实现是**公开标准算法的教科书实现**（不引入任何第三方密码库），但「不自制」的表述已删除，
> 以免读者据此误判实现面。

按美国出口管理条例（EAR）的通行读法，这类「标准公开加密软件」（公开可得源码）通常落入
**EAR §740.13（License Exception TSU for operation technology and software）** 或
**Note 4 to Category 5 Part 2 / §742.15(b)** 的公开可得（publicly available）排除范围。
**本声明不构成法律意见**；使用者应就自身司法辖区与用途自行取得专业意见。

仓库内不含：vendored 第三方二进制、第三方密码库、挖矿/后门/网络攻击代码、被出口管制的专用硬件驱动。

## 声明与仓库事实对照（机检面）

| 声明项 | 仓库事实 / 判据 |
|---|---|
| 只用标准库/公开算法 | `core/ed25519.py` 仅 `import hashlib`；`core/attest.py` 摘要用标准库；.NET 侧用 `System.Security.Cryptography.SHA256` |
| 不引入第三方密码库 | import 面判据：purity **R5**（第三方 import 须登记，`core/purity_scan.py` 的 `HARD_ALLOW`/`SOFT_IMPORTS`）；`cryptography` 仅出现在**测试的可选交叉验证**里（缺库即跳过） |
| 不自制「未公开/私有」算法 | 自写仅限 RFC 8032 Ed25519（公开标准）；无自定义密码算法、无 X25519/预哈希等扩展 |
| 外调 ssh-keygen | `desktop/src/core/attest.py` 的 `ssh-keygen -Y sign/verify`（argv 列表、无 shell）；读者侧 `nf_verify.py` |
| 签名锚在仓 | `library/anchors/*.sig`（如 `NF-1.sig`） |
| 无 vendored 二进制/攻击代码 | 仓库扫描 + purity **R6**（`eval`/`exec`/`os.system`/不安全反序列化等 sink 面须登记，`SINK_ALLOW` 带 CWE 对齐） |

## 复现与引用口径

```bash
python scripts/nf.py attest --help        # 三级信任签名（含 --ssh-key 外调路径）
python -m pytest desktop/tests/test_ed25519.py -q   # RFC 8032 向量/篡改/形状（12 例）
python scripts/nf.py explain check27      # 纯度体检（R5 import 面 / R6 sink 面）
```

- 引用本声明时：以「标准公开算法 + 纯标准库 + 可选 ssh-keygen 外调」为准；**不得**再转述旧版
  旧版「本仓库不自制密码算法」的表述。
- 实现变更（新增任何密码算法/第三方密码库）必须先更新本声明并同步机检面，否则视为声明漂移。
