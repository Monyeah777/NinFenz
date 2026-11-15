# `nf-app-core` CLI / FFI 面（A0 冻结 v1）

> ⛔ 操作指令：本件与 `CONTRACT.md` 同属冻结层。**新增/改名 op 或改请求/响应字段 = 破坏性变更**：先改本件 + `app/core/src/cli.rs` + `app/tests/`，再改 Python/Android/Desktop 消费面。所有 op 名与错误码见 `app/schema/error_codes.json`。

## 1. 进程约定

```
nf-app-core --abi-version            # → {"abi":"nf-app-core/1","version":"<semver>"}
nf-app-core <op> --in <req.json|->   # → stdout: 单行 JSON（响应信封）；exit 按 §4
```

- `--in -` 或省略 = 读 stdin（一次读完，UTF-8）。
- `--json` 可省：默认就只输出 JSON（无人类可读噪声）；诊断信息走 stderr。
- 元数据形状：装配元数据 = `nf-assemble-result/1`；导出清单 = `nf-export-manifest/1`；备份 = `nf-backup/1`（三者均有 schema 文件）。
- **不写盘**的唯一例外：`assemble` / `export` / `pack-merge` / `overlay-apply` 需要在请求里显式给 `out_dir`，且必须已存在（核心不建用户目录树，除 out_dir 内子目录）。
- 确定性：同请求同字节输出；**禁**时间戳/随机/环境（`created_at` 等由请求显式给，测试用固定值）。

## 2. 响应信封

```json
{"ok": true, "exit": 0, "result": { ... }, "error": null}
{"ok": false, "exit": 3, "result": null, "error": {"code": "NF-SEC-001", "message": "...", "fix": "...", "path": "$.path"}}
```

- `error` 必带 `code`/`message`/`fix`；有定位时带 `path`（RFC 6901 JSON Pointer 或 schema 路径）。
- 校验失败（exit 1）时 `result` = `nf-validate-report/1`（不是 null）；`ok=false`。
- `ok=true` 严格等价 `exit == 0`。

## 3. Op 表（A0 冻结）

| op | 请求字段 | result | exit 语义 |
|---|---|---|---|
| `canonical` | `value`: 任意 JSON | `{canonical: str, digest: sha256}` | float/NaN/非字符串键 → NF-E-006 (1) |
| `pack-hash` | `root`: dir | `{items: [{path,kind,sha256,size}], hashes:{tree,count}}` | 路径不安全 → NF-PCK-003 (3) |
| `pack-verify` | `root`: dir | `nf-validate-report/1`（target=manifest） | 不符 → 1 |
| `import-sniff` | `name`, `mime?`, `file?/bytes_path?` | `{format, confidence, candidates:[{format,confidence}]}` | 未知 → NF-IMP-001 (3)；未实现格式 → NF-IMP-004 (3) |
| `import` | `file`, `source:{kind,name,mime?,size?,sha256?}` | `nf-import/1` | 低置信 → NF-IMP-002 (warn, exit 0)；未实现格式/超限 → 3 |
| `map-suggest` | `import`: nf-import/1, `spec?`: nf-md-spec/1 | `nf-import/1`（`suggested` 已填） | 无候选 → NF-MAP-001 (warn) |
| `protocol-validate` | `pack`: nf-protocol-pack/1 | `nf-validate-report/1` | 结构/引用 → 1 |
| `protocol-render` | `pack`, `values`: {field_id: value} | `{clauses:[{id, text}], warnings:[...]}` | 缺必填 → NF-PRT-003 (1)；未知占位符 → NF-PRT-004 (1)；规则不满足 → NF-PRT-005 语义（1） |
| `graph-validate` | `graph`: nf-pipeline-graph/1 | `nf-validate-report/1`（L0+L1） | 失败 → 1 |
| `graph-compile` | `graph`, `spec?`（用于 slots 推导） | `nf-assembly-plan/1` | 校验失败 → 1 |
| `spec-validate` | `spec`: nf-md-spec/1 | `nf-validate-report/1` | 失败 → 1 |
| `assemble` | `plan`, `spec`, `inputs`: {slot: str}, `stage?`, `block?`, `base_markdown?`（给 block 时必填）, `out_dir?` | `{markdown: str, meta: nf-assemble-result/1}`（`out_dir` 时写 `result.md` + `result.meta.json`） | 必填缺失 → NF-ASM-002 (1)；digest 不匹配 → NF-ASM-001 (1) |
| `validate` | `markdown`, `spec`, `plan`, `level`: L0/L1/L2 | `nf-validate-report/1` | fail → 1；L2 不可用 → NF-VAL-005 (4) |
| `export` | `markdown`/`result`, `plan_digest?`, `spec_digest?`, `project_id?`, `title?`, `format`: md/zip/json/**docx**/**skill**（pdf=平台打印）, `out_dir`, `manifest?: bool` | `nf-export-manifest/1` | 越界 → NF-EXP-002 (3)；重名 → NF-EXP-003 (1)；pdf → NF-EXP-004 (4，平台打印) |
| `pack-diff` | `old_root`, `new_root`, `projects?: [nf-project/1]` | `nf-pack-update/1` | 清单不符 → 1 |
| `pack-merge` | `update`, `base_root`, `new_root`, `overlay?`, `decisions?: {conflict_id: option}`, `out_dir` | `{applied: bool, conflicts:[...], result_tree: sha256}` | 冲突未裁决 → NF-PCK-006 (1)；摘要不符 → NF-PCK-004 (3) |
| `overlay-apply` | `base_root`, `overlay`, `out_dir` | `{tree: sha256, base: ref}` | base 不符 → NF-PCK-002 (1) |
| `ccos-build-task` | `project`, `task_id`（调用方生成，确定性）, `created_at`（显式）, `budget`, `variables?` | `ccos-task/1` | 项目未 validated → NF-CCOS-001 (1)；含密钥形状 → NF-CCOS-003 (3) |
| `ccos-import-result` | `task`, `result` | `{status, review:{state}, issues}` | digest 不符 → NF-CCOS-002 (1)；缺人审 → NF-CCOS-004 (warn) |
| `project-validate` | `project` | `nf-validate-report/1` | 引用失配/状态非法 → 1 |

## 4. 退出码

0 成功；1 校验失败（报告仍输出）；2 用法/IO；3 拒绝（安全/未知/超限/版本）；4 环境缺失。见 `CONTRACT.md` §4。

## 5. FFI（JSON over C ABI）

Android/Desktop 通过 JNA/cinterop 调用同一套 op：

```c
const char* nf_app_core_abi_version(void);          // 静态字符串 "nf-app-core/1"
char*       nf_app_core_call(const char* req_json); // 返回堆 JSON（响应信封 + op 字段），失败返回 NULL
void        nf_app_core_free(char* ptr);            // 释放 call 返回值
```

- `req_json` 形如 `{"op":"graph-validate","in":{...}}`；响应 = §2 信封 **+ 顶层 `op` 字段**（FFI 面回带 op 便于端壳多路复用；CLI 面不带，二者仅此一处差异）。
- `NULL` 只在 **panic 兜底** 时返回（stderr 必须留诊断）；正常错误一律走信封。
- 线程：必须可重入（不共享可变全局；`limits` 只读加载）。
- **为什么不是 UniFFI**：本机离线工具链无法获取 uniffi 依赖；APP Final §5.1 明确 Core Bridge = `UniFFI / JSON`，选 JSON-C ABI 是同一条契约的等价实现（ADR-APP-011 记录偏差与回切条件：获取到 uniffi 依赖后可在不破 ABI 的前提下加 UDL 生成绑定）。

## 6. 一致性判据

- `app/tests/test_cli_contract.py`：每个 op 的请求/响应字段与退出码逐条断言（含负例）。
- `app/tests/test_golden.py`：golden 夹具逐 op 逐字节比对（Rust 生成，Python 复核）。
- Kotlin 侧 `app/android/.../CoreBridgeTest.kt`（设备/单测）与 Desktop 同名测试：同一请求 → 同一响应字节。