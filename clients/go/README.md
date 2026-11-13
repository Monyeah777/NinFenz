# CCOS Go 客户端（`nfverify`）

CCOS 七个 ABI 调用的 **Go 侧第二实现**（判定面）。不 import 本仓任何 Python 代码，也不联网。

> **复核（2026-11-14）**：七调覆盖面 / 三条边界 / 退出码口径**复核不变**；补可核现状，并把「构建与测试需要 Go 工具链」写成显式前提——本机**未装 Go**，故本轮只做静态对账（向量文件逐个数、CLI 子命令逐条核），**不声称已跑过 `go test`**。见「§现状对照」。

## 覆盖面

| ABI 调用 | Go 侧状态 | 判据（跨语言向量） |
|---|---|---|
| `cc_verify` | **完整**：bundle / receipts / attest 三形态同判 | 28 例 |
| `cc_check` | **完整**：封闭词表五类（utf8/regex_present/regex_absent/count_at_least/digest_pin） | 6 例 |
| `cc_label` | **声明层**：IR 校验（档位/缺项/形状） | 7 例 |
| `cc_attest` | **完整**：信封生成（digest_only / hmac-sha256）+ 验证 | 3 例 |
| `cc_replay` | **完整**：逐成员摘要 → 叶 → 折叠 → 链头轨迹 | 1 例 |
| `cc_diff` | **JSON 契约**：字段级差异 + 兼容判定（bump/additive/editorial） | 6 例 |
| `cc_resolve` | **完整**：对象 → 认领契约集（含 closure_closed/unclaimed 显式面） | 4 例 |

**边界（不假装）**：

- `cc_label` 只移植**声明层**（IR 校验）；载体读写（PNG iTXt / JPEG APP15 / WebP / MP4 / PDF、
  像素水印）是另一件工程，Go 侧**未移植**——要验载体请用 Python 侧 `nf label extract`。
- `cc_diff` 只移植 **JSON 契约**那一路；Markdown 契约签名（knowledge_sig）未移植。
- `cc_resolve` 用 `git ls-files` 取受跟踪件（与真源同口径）；无 git 时回退文件系统 glob。

## 现状对照（2026-11-14 · 静态对账；Go 工具链本机缺位）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 七调向量总数 | **55** | `results/ccos/*_vectors.json` 逐文件 `len(vectors)` 相加 |
| 证据 `cc_verify` | **28** | `evidence_verdict_vectors.json` |
| 策略 `cc_check` | **6** | `check_verdict_vectors.json` |
| 标注 `cc_label` | **7** | `label_verdict_vectors.json` |
| 信封 `cc_attest` | **3** | `attest_envelope_vectors.json` |
| 轨迹 `cc_replay` | **1** | `replay_trace_vectors.json` |
| 差异 `cc_diff` | **6** | `diff_delta_vectors.json` |
| 契约 `cc_resolve` | **4** | `resolve_contract_vectors.json` |
| CLI 子命令 | **7**：`verify` / `check` / `label` / `attest` / `replay` / `diff` / `resolve` | `cmd/nfverify/main.go` 的分派 |
| 工具链前提 | **Go ≥ 1.24**（`go.mod`）；本机**未装 Go** → `go test` **本轮未跑** | `go.mod` + 环境 |
| 退出码 | `0 ok / 1 invalid / 2 revoked / 3 expired / 4 用法错` | 与仓内 Python 侧一致 |

> 本表只作「当时 → 现行」导航；向量数以 JSON 实读为准，Go 侧行为须在装有 Go 的环境跑 `go test ./...` 才算实测。

## 判据（自证）

```bash
cd clients/go && go build ./... && go test ./...
```

共 **55 例跨语言向量**：证据 28 + 策略 6 + 标注 7 + 信封 3 + 轨迹 1 + 差异 6 + 契约 4。
向量文件在 `results/ccos/`*_vectors.json`，Python 侧生成器见 `scripts/{evidence_vectors,check_vectors,abi_call_vectors}.py`。

## 用法

```bash
nfverify verify  --bundle 证据.zip [--key-file K] [--revocations R] [--anchor A] [--at T]
nfverify check   --object 文件 --policy 策略.json
nfverify label   --ir IR.json
nfverify attest  --subject 文件 [--key-file K] [--producer P]
nfverify replay  --bundle 证据.zip
nfverify diff    --a a.json --b b.json
nfverify resolve --root <仓库> --object <相对路径> [--decl 声明件]
```

退出码与仓内一致：`0 ok` · `1 invalid` · `2 revoked` · `3 expired` · `4 用法错`

## 只承诺什么

- **承诺**：以上七调的**判定面**与真源同口径（向量逐例对账）；容器/策略/IR/契约面 fail-closed。
- **不承诺**：载体写入读出、Markdown 契约签名、内容质量与真实性。
