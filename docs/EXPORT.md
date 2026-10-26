# 出口管制声明（Export Control）

NF 自带与依赖的密码学**只用标准库**：`hashlib` / `hmac` / `secrets`（以及 .NET 的
`SHA256`）。签名能力通过调用**外部** `ssh-keygen` 实现（`nf attest` + `library/anchors/*.sig`），
本仓库**不自制 ed25519 或任何密码算法**。

按美国出口管理条例（EAR）的通行读法，这类「标准公开加密软件」通常落入 **EAR §740.13
（License Exception TSU for operation technology and software）** 或
**Note 4 to Category 5 Part 2 / §742.15(b)** 的公开可得（publicly available）排除范围。
本声明**不构成法律意见**；使用者应就自身司法辖区与用途自行取得专业意见。

仓库内不含：vendored 第三方二进制、挖矿/后门/网络攻击代码、被出口管制的专用硬件驱动。
