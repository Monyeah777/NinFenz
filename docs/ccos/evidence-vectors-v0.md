# 证据判定向量集 v0（跨语言一致性的锚点）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-05
> **Status**: v0 已实装（scripts/evidence_vectors.py + results/ccos/evidence_verdict_vectors.json）

## 是什么

一份**与实现无关**的 JSON：18 条「证据包字节 → 期望判定 + 期望退出码」的固定用例。任何语言的
`cc_verify` 实现都能只读这一份文件自证对不对——不需要读本仓代码、不需要装 NF 工具链。

与攻击矩阵（`nf evidence bench`）的分工：矩阵证明「**本实现**抓得住攻击」；向量集证明
「**任何实现**都该给出这几个判定」。前者绑定代码，后者绑定契约。

## 产物形状（nf-evidence-vectors/1）

`json
{
  "schema": "nf-evidence-vectors/1",
  "pinned_at": "2026-01-01T00:00:00Z",
  "count": 15,
  "vectors": [
    {"id": "ok_digest_only", "desc": "完好包（digest_only）",
     "expected": {"verdict": "ok", "exit_code": 0},
     "bundle_b64": "<base64(zip)>", "bundle_sha256": "<hex>"},
    {"id": "revoked", "...": "...", "revocations": {"schema": "nf-revocation/1", "revoked": []}},
    {"id": "anchor_truncated", "...": "...", "anchor": {"count": 3, "head": "<hex>"}},
    {"id": "not_a_bundle", "...": "...", "special": "not_a_bundle",
     "expected": {"verdict": "invalid", "exit_code": 4}}
  ]
}
`

字段语义：`bundle_b64` 解码即证据包字节（`bundle_sha256` 是它的摘要）；`key_b64` 给出时按
hmac-sha256 级校验；`revocations` / `anchor` / `at` 就是 `nf evidence verify` 的对应参数。
`special="not_a_bundle"` 表示**输入不是证据包**：这是用法错（rc=4），实现必须拒绝，不许给判定。

## 18 条向量覆盖什么

| id | 攻击/变化 | 期望 |
|---|---|---|
| ok_digest_only / ok_hmac | 完好（两种强度） | ok / 0 |
| no_key_is_invalid / wrong_key_is_invalid | hmac 级缺密钥、错密钥 | invalid / 1 |
| payload_flip / root_flip | 改成员字节、改根 | invalid / 1 |
| chain_missing | 删掉 chain 段（顺序不可证） | invalid / 1 |
| anchor_ok / anchor_truncated | 锚点对得上 / 用更早的包冒充现在 | ok / invalid |
| revoked | 吊销表命中 | revoked / 2 |
| expired | 有效期已过 | expired / 3 |
| bad_revocations | 包内吊销表坏件（不是「无吊销」） | invalid / 1 |
| traversal_path | 成员路径含双点段（解包越界写的入口） | invalid / 1 |
| dup_members | 重名成员（zip 歧义：判定不可复算） | invalid / 1 |
| not_a_bundle | 输入不是证据包 | 用法错 / 4 |

## 第三方怎么用（以任何语言为例）

1. 读 JSON，对每条 `vectors[i]`；
2. `bytes = base64decode(bundle_b64)`，并校验 `sha256(bytes) == bundle_sha256`（防向量集被改）；
3. 用你的实现按 `evidence-bundle-v0.md` 的判定顺序判 `bytes`（需要时带上 `key_b64`、`revocations`、
   `anchor`、`at`）；
4. 比对 `verdict` 与退出码；**全部一致**才算实现对齐。任一条不一致，先查你的实现，别改期望值。

## 本仓怎么生成与复核

`bash
python scripts/evidence_vectors.py --write   # 重写向量集（确定性：钉死时间戳 + 固定密钥）
python scripts/evidence_vectors.py --check   # 提交件 == 重算（CI / gate 用）
python -m unittest desktop.tests.test_evidence_vectors   # 8 项：期望成立 + 双实现同判 + 可复现
# 注：向量集里的容器面两条（traversal_path / dup_members）是 2026-11-05 容器加固的锚点
`

确定性来自两处：`SOURCE_DATE_EPOCH` 钉到 `pinned_at`（信封时间戳固定）、zip 用固定时间戳 +
不压缩 + 成员名排序。`--write` 两次逐字节一致——否则「向量」会随生成时刻漂移。

## 边界

- 只覆盖**判定面**（verdict + 退出码），不覆盖人读文案、性能、并发。
- 密钥是**公开测试密钥**（写在生成器里），只用于可复现，不是生产材料。
- 向量集不含机器路径/用户名（有判据钉住），可直接对外分发。
