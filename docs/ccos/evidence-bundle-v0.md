# 证据包 v0（evidence bundle）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-04
> **Status**: v0 已实装（pack / verify / bench · 三种可验形态）· **上位**: docs/ccos/abi-v0.md §4 cc_verify

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
| bundle.json | 是 | 清单：schema、created_at、producer、root、chain、entries[]、attestations[]、expires_at、boundary（+ 可选 decision） |
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
| 5 | chain 段**必填**：head 非空、count == 成员数，且链头 == 由条目顺序重算 | invalid |
| 6 | payload 里**不得**多出未登记成员（多出来的字节没有回执背书） | invalid |
| 7 | 清单内**每一份**信封都必须通过，且每个成员至少被一份信封覆盖 | invalid |
| 8 | hmac 级：同一密钥在场且 mac 匹配 | invalid（缺密钥**不**降级） |
| 8b | decision（若声明）：形状合法、object 在成员里、与相符信封内同一块、两侧都存在 | invalid |
| 9 | 包内吊销表（若在）可解析且 schema 正确 | invalid（坏件**不能**当「无吊销」） |
| 10 | 吊销表命中（按摘要或仓相对路径） | **revoked** |
| 11 | 时效（expires_at 早于判定时点） | **expired** |
| 12 | 给了外部锚点时：包不得被截断、该位置链头相符、包内声明与材料一致 | invalid |
| 13 | **容器结构安全**：成员路径无双点段/盘符、无重名成员、解压不超上限 | invalid |

第 12 条解决的是**整链截断**：攻击者把包回滚成「更早但自洽」的版本，前 11 条全过——只有外部锚点
（上一条链的 `{count, head}`）能把它戳穿。不给锚点材料时不判死也不抬高：warning + `anchor_verified=false`。

三条**严格**口径（都是 2026-11-04 攻击矩阵实测出来的「坏件冒充合格」）：

- 第 5 条：旧实现「有链头才比」——删掉 chain 段或把 head 置空就能绕过，等于把「顺序不可证」
  伪装成「顺序没问题」。**缺证据 ≠ 证据成立**。
- 第 7 条：不容忍「有一份信封过了就算过」——证据强度只由最弱那一环决定，挑最好看的报
  等于给「悄悄塞一份坏信封」留容错面。
- 第 9 条：吊销表坏件曾被折成「无吊销」，于是把吊销表写坏就能让已吊销证据判 ok。

判定词表只有四个词：ok / revoked / expired / invalid。退出码：ok=0 / invalid=1 / revoked=2 /
expired=3 / 用法错=4。证据强度（level）如实回填，词表 = digest_only / receipts_only /
hmac-sha256 / ssh-sig / sigstore-keyless。

## 三种可验形态（cc_verify 的输入面）

形态由**文档 schema** 判定，不由扩展名或文件名判定——判据不依赖命名约定。

| 形态 | 输入 | 判什么 | level |
|---|---|---|---|
| bundle | nf evidence pack 的 .zip / 解包目录 | 上面 10 条全判 | 取通过的最强信封档 |
| receipts | nf-receipts/1（nf receipts --scope protocol 产出） | 成员摘要 → 叶 → 根 → 每条包含证明 | receipts_only |
| attest | nf-attest/1 或 nf-attest-set/1（nf attest 产出） | 每份信封自洽 + 指向真实成员 | 取通过的最强档 |

后两种是**单 JSON + 成员根目录**形态（--root 指成员根，缺省 = 该 JSON 所在目录）；
容器（.zip / 目录）里也可以直接放这两种文档，自动识别。

## 怎么用

> **decision 证据绑定（v0，可选）**：`--decision <json>` 把 `{syscall, policy_digest,
> verdict, object_sha256}` 绑定进包（声明面 + 相符信封的绑定面，进信封摘要）。可证「与一次
> cc_check 判定自洽且被签发面覆盖」；**不证策略内容正确**（验方须用自己信任的 policy 重算
> `policy_digest` 后比对）。换策略/删一侧 = invalid；旧包无 decision 仍为 ok（status=absent）。

```bash
# 打包（缺省目标 = 01/02/06/07 四件；缺省落点 = 系统临时目录 nf-evidence.zip——
# 不往仓库里落盘，要入仓请显式 --out；--key-file 即升级到 hmac-sha256 级）
python scripts/nf.py evidence pack 01_核心协议.md STRATEGY.md --out evidence.zip
python scripts/nf.py evidence pack 01_核心协议.md --key-file <密钥> --issuer 作者 \
       --expires-at 2027-01-01T00:00:00Z --revocations <吊销表.json> --out evidence.zip


## 跨语言一致性：判定向量集

`results/ccos/evidence_verdict_vectors.json` 把「证据包字节 → 期望判定 + 退出码」固化成 18 条与实现
无关的用例：**任何语言**的 `cc_verify` 都可以只读这份 JSON 自证对不对（无需本仓工具链）。
生成与复核：`python scripts/evidence_vectors.py --write|--check`，判据
`python -m unittest desktop.tests.test_evidence_vectors`（8 项，含双实现同判）。详见
[evidence-vectors-v0.md](evidence-vectors-v0.md)。

# 复验（纯读；不需要仓库）——三种形态同一个入口
python scripts/nf.py evidence verify evidence.zip
python scripts/nf.py evidence verify protocol/RECEIPTS.json --root .        # 回执形态
python scripts/nf.py evidence verify <信封集.json> --root <成员根> --key-file <同一密钥>
python scripts/nf.py evidence verify evidence.zip --json
python scripts/nf.py evidence verify evidence.zip --revocations <吊销表.json>
python scripts/nf.py evidence verify evidence.zip --kind bundle             # 显式指定形态

# 机制体检（PASS 必过 / 篡改必红 / 吊销必判 revoked / 过期必判 expired）
python scripts/nf.py evidence verify --selfcheck

# 攻击矩阵基准（38 条已知攻击，逐条比对期望判定；写 Markdown 报告）
python scripts/nf.py evidence bench
python scripts/nf.py evidence bench --out /tmp/evidence-bench.md
```
## 判据（可证）

```bash
# 1) 复验机制体检必须绿（抓不到篡改的校验器就是摆设）
python scripts/nf.py evidence verify --selfcheck          # 退出码 0

# 2) 攻击矩阵基准必须 38/38（任何一条不达期望即 exit 1）
python scripts/nf.py evidence bench

# 3) 逐字节可复现
SOURCE_DATE_EPOCH=1700000000 python scripts/nf.py evidence pack 01_核心协议.md --out /tmp/e1.zip
SOURCE_DATE_EPOCH=1700000000 python scripts/nf.py evidence pack 01_核心协议.md --out /tmp/e2.zip
cmp /tmp/e1.zip /tmp/e2.zip

# 4) 单测（四词判定各自可达 + 三形态 + 夹带成员 + 基准）
python -m unittest desktop.tests.test_evidence             # 58 项全绿（含零依赖复验器一致性）
```

## 攻击矩阵基准 v0（防「看起来能验」）

对同一份金丝雀证据包施加 25 种已知攻击/退化，逐条断言「期望判定 vs 实际判定」：
改字节、截断、等长替换、删成员、夹带成员、改清单摘要/根/叶、删清单条目、翻/截包含证明、
改链头、换条目顺序、删信封、改信封主体摘要、改 hmac、缺密钥、错密钥、改包版本、非包输入、
吊销命中、过期，以及**良性重排**（必须仍然 ok）。

它是自测基准，不是安全证明：证明「这些已知攻击都判得出来」，**不**证明「所有攻击都判得出来」。
不可抵赖与可信时间戳仍需第三方见证——这条边界写进包内 boundary 字段，也写进报告页脚。

## 与既有验证器的关系（两套独立实现，判据必须一致）

scripts/nf_verify.py 是**读者侧零依赖**验证器：纯标准库、**不 import 任何 NF 模块**，
单文件拷走即可运行——这是「免费验证器 / 可嵌入」的形态要求（发布物不该带整条工具链）。
两种用法：

```bash
# 馆藏单条（原有口径）
python scripts/nf_verify.py --entry NF-1 --json

# 证据文档整体（与 nf evidence verify 同一套四词判定）
python scripts/nf_verify.py --evidence evidence.zip --json
python scripts/nf_verify.py --evidence protocol/RECEIPTS.json --root . --json
python scripts/nf_verify.py --evidence <信封集.json> --root <成员根> --key-file <密钥>
```

退出码与 ABI 对齐：ok=0 / invalid=1 / revoked=2 / expired=3 / 用法错=4。

职责分工：core/evidence.py 管「容器与判定顺序」，nf_verify.py 管「同一算法的独立复刻」。
**判据必须一致**——`desktop/tests/test_evidence.py::TestStandaloneParity` 用同一批夹具
跑两边（含真实仓内 67 件回执），结论不同即红：两套实现不一致说明至少一边有 bug，
那时「第三方复验」的结论就不可信。

边界：零依赖复验器不调外部工具，故 ssh-sig / sigstore 信封一律 fail-closed（缺锚不降级）；
要验这两档请用带外挂验证器的那一层。
