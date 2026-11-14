# 馆藏回执与单根（receipts）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-13
> **复核（2026-11-13）**：算法（叶/内部/根三式）、O(log n) 折叠、边界（不提供不可抵赖性）**复核不变**；补可核现状：
> 馆藏回执 **3 条**（`library/RECEIPTS.json`，根前 16 位 `6afa7b1a02e044ea`）· 协议回执 **66 件**
> （`protocol/RECEIPTS.json`）· 透明链 **66 节**（`protocol/generated/receipt_chain.json`；**链头随回执刷新而变，不钉值**，以 `nf transparency` 输出为准）·
> 读者侧验证器 `nf_verify.py` 输出三项（inclusion / content / anchor）。见「§现状对照」。

## 是什么

逐条 **inclusion proof + 一个全馆根**（RFC 6962 域分隔）。读者只拿「该条内容 + 它的回执」
即可本地折叠验证是否属于本馆，**不必取全馆**（线性链链要 O(n) 重放，这里是 O(log n)）。

## 算法（读者侧按此重建，逐字一致）

```
规范摘要 = SHA-256( 条目文本剔除 attestation / attested_at / anchor_* 行后的字节 )
叶       = SHA-256( 0x00 ‖ UTF-8( {"id":…,"digest":…} 的紧凑规范 JSON ) )
内部节点 = SHA-256( 0x01 ‖ 左 ‖ 右 )        # 折叠按 proof 的 side 逐层合并 → 应等于 root
```

## 怎么用

```bash
python scripts/nf.py library receipts --write          # 生成/刷新 library/RECEIPTS.json
python scripts/nf.py library receipts --entry NF-1     # 只验一条（本地折叠到根）
python scripts/nf_verify.py --entry NF-1               # 读者侧独立验证器（纯标准库，零 NF 依赖）
```

## 边界

- 回执证明「属于本馆且未被换」；**签名锚**（`anchor_*`）另证「谁签过」——两者互补。
- 落锚会改变锚字段，但**不改变规范摘要与全馆根**（锚字段排除在摘要之外，自指安全）。
- `nf library attest` 会自动刷新回执，避免"锚了新、回执还是旧"。

## 现状对照（2026-11-13 · 以 `nf library receipts` / `nf transparency` 实读为准）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 馆藏回执 | **3 条**（根 `6afa7b1a02e044ea…`） | `nf library receipts` 头行 |
| 协议回执 | **66 件**（`protocol/RECEIPTS.json: count`） | 同上 / 该文件 |
| 透明链 | **66 节**（链头**不钉值**：每次 `receipts --write` 后都变） | `nf transparency` |
| 算法 | 叶 = SHA-256(0x00‖JSON) · 内部 = SHA-256(0x01‖L‖R) · 根 = 折叠终值 | 本页「算法」段 |
| 读者侧验证 | `nf_verify.py` 三项：inclusion / content / anchor | `--entry NF-1` |
| 不可抵赖性 | **不提供**（单人治理、无第二署名方；生成物 `boundary` 字段必在） | `nf transparency` 尾行 |

> 本表只作「当时 → 现行」导航；根与条数以 `nf library receipts` / `nf transparency` 实读为准。

## 复现与引用口径

```bash
python scripts/nf.py library receipts          # 校验每条折叠到根 + 根与重算一致
python scripts/nf_verify.py --entry NF-1       # 读者侧独立验证（零 NF 依赖）
python scripts/nf.py transparency              # 链自洽 + 与回执一致 + 在盘生成物一致
```

- 引用本文时：「回执证属于本馆且未被换；签名锚另证谁签过」= 长期口径；两者**互补不可互替**。
- 链条只证 append-only 顺序 + 防删改；**不要**把它写成「不可抵赖」——那需要第三方见证。

## 透明日志（哈希链 · 2026-09-21 收口）

回执单根只证明「**此刻的集合**」；顺序与历史由 `nf transparency` 补上：

```bash
python scripts/nf.py transparency            # 校验链（自洽 + 与回执一致 + 在盘生成物）
python scripts/nf.py transparency --write    # 刷新 protocol/generated/receipt_chain.json
python scripts/nf.py interop --kind intoto   # 同源导出：in-toto Statement（外部校验器可读）
```

链式：`leaf = H(path ‖ digest)`、`chain[i] = H(chain[i-1] ‖ leaf[i])`（域分隔前缀见
`core/transparency_log.py`），由 `protocol/RECEIPTS.json` **确定性派生**。

**边界（不夸大）**：链条可证 **append-only 顺序 + 防删改**；**不提供不可抵赖性**——
那需要第三方见证或远程日志（Rekor/SCITT），本仓单人治理、无第二署名方，故该声明写在
生成物的 `boundary` 字段里，门禁判它必须在场。
