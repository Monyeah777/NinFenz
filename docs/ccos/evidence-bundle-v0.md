# 证据包 v0（evidence bundle）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-04
> **Status**: v0 已实装（nf evidence pack / verify）· **上位**: docs/ccos/abi-v0.md §4 cc_verify

## 是什么

一个**自包含**的证据包：把「成员字节 + 成员集单根 + 每条 inclusion proof + 信封（attestation）
+ 链头（+ 可选吊销表、有效期）」封进一个 .zip。验证方只需要这个包——
**不需要仓库、不需要联网、不需要复现生产环境**。

为什么需要它（内部差距实测 2026-11-04）：attest / receipts / transparency 三件都在，但都不是
「给外部人一个文件就能验」的形态。缺这一层，「第三方复验」不成立，只剩「你自己跑一遍」。
包里的密码学**一件都不新造**：叶/节点/根取 core.receipts（RFC 6962 域分隔），信封与签名取
core.attest，链节域分隔前缀取 core.transparency_log。

**边界（务必读）**：本包可证「成员未被改动、成员集与根一致、单条可折叠到根、条目顺序未被
插删、信封与主体一致」。本包**不**提供：不可抵赖（需第三方见证/远程日志）、内容质量、
内容真实性。时间戳只有自签 issued_at（无 TSA/RFC3161），第三方无法据此证明「某时点已存在」。

## 布局（zip 成员，全部确定性）

| 成员 | 必有 | 内容 |
|---|---|---|
| bundle.json | 是 | 清单：schema、created_at、producer、root、chain、entries[]、attestations[]、expires_at、boundary |
| payload/<仓相对路径> | 是 | 成员实体（UTF-8 文本，原字节） |
| attest/NNNN.json | 是 | 每个成员一份 nf-attest/1 信封 |
| revocations.json | 否 | 内嵌吊销表（nf-revocation/1），也可用 --revocations 外部给 |

打包确定性：成员名排序 + 固定 zip 时间戳（1980-01-01）+ 不压缩（deflate 输出随 zlib 版本变，
跨机器就不再逐字节一致）。要**逐字节可复现**还须钉 SOURCE_DATE_EPOCH（created_at 取墙钟，
与 nf attest 同一口径）。

## 判定（fail-closed，顺序固定）

| 序 | 检查 | 不过 → |
|---|---|---|
| 1 | 包结构 / schema == nf-evidence/1 | invalid |
| 2 | 每个 payload 的 sha256 == 清单记录 | invalid |
| 3 | 叶复算 → RFC 6962 根 == 清单 root | invalid |
| 4 | 每条 inclusion proof 折叠到同一 root | invalid |
| 5 | 透明日志链头 == 由条目顺序重算的链头 | invalid |
| 6 | 至少一份信封通过（信封摘要自洽 + 主体与成员同源） | invalid |
| 7 | hmac 级：同一密钥在场且 mac 匹配 | invalid（缺密钥**不**降级） |
| 8 | 吊销表命中（按摘要或仓相对路径） | **revoked** |
| 9 | 时效（expires_at 早于判定时点） | **expired** |

判定词表只有四个词：ok / revoked / expired / invalid。退出码：ok=0 / invalid=1 / revoked=2 /
expired=3 / 用法错=4。

## 怎么用

```bash
# 打包（缺省目标 = 01/02/06/07 四件；缺省落点 = 系统临时目录 nf-evidence.zip——
# **不往仓库里落盘**，要入仓请显式 --out；--key-file 即升级到 hmac-sha256 级）
python scripts/nf.py evidence pack 01_核心协议.md STRATEGY.md --out evidence.zip
python scripts/nf.py evidence pack 01_核心协议.md --key-file <密钥> --issuer 作者        --expires-at 2027-01-01T00:00:00Z --revocations <吊销表.json> --out evidence.zip

# 复验（纯读；不需要仓库）
python scripts/nf.py evidence verify evidence.zip
python scripts/nf.py evidence verify evidence.zip --json
python scripts/nf.py evidence verify evidence.zip --key-file <同一密钥>   # hmac 级
python scripts/nf.py evidence verify evidence.zip --revocations <吊销表.json>

# 机制体检（PASS 必过 / 篡改必红 / 吊销必判 revoked / 过期必判 expired）
python scripts/nf.py evidence verify --selfcheck
```

## 判据（可证）

```bash
# 1) 机制体检必须绿（抓不到篡改的校验器就是摆设）
python scripts/nf.py evidence verify --selfcheck          # 退出码 0

# 2) 逐字节可复现
SOURCE_DATE_EPOCH=1700000000 python scripts/nf.py evidence pack 01_核心协议.md --out /tmp/e1.zip
SOURCE_DATE_EPOCH=1700000000 python scripts/nf.py evidence pack 01_核心协议.md --out /tmp/e2.zip
cmp /tmp/e1.zip /tmp/e2.zip

# 3) 四词判定各自可达（单测）
python -m unittest desktop.tests.test_evidence -v          # 23 项全绿
```

## 与既有验证器的关系

scripts/nf_verify.py 是**读者侧零依赖**验证器（纯 stdlib、不 import NF），走的是另一条口径
（直接读回执/信封文件、自成进程）。两者职责不同、**判据必须一致**：
证据包这一层管「容器与判定顺序」，nf_verify.py 那一层管「同一算法的独立复刻」。
两边对同一输入的结论不一致，就是其中一边有 bug——发现即红，不许放过。
