# 耦合与重复实现（COUPLING，§4A R3）

> ⛔ 操作指令：本件是 §4A R3 耦合/重复实现的人读结果；机读真源 `results/reverse/coupling.json`（`nf-reverse-coupling/1`），判据 `desktop/tests/test_reverse_coupling.py`（**实时重算模块图并与本件比对**，图变即红）。不把「模块化」写成已解耦；重复裁定须给证据。
> 状态：v1（2026-11-14 · G0 §4A R3）· 前置：`CONTRACT_MAP.md`（R1）、`BEHAVIOR.md`（R2）

## 1. 模块图事实（`core.coupling_metrics` 实时重算，2026-11-14）

| 指标 | 值 |
|---|---|
| 模块数 | 300 |
| 依赖边 | 540 |
| 环 | 0 |
| SDP 违规（被依赖方依赖依赖方） | 9（已进 `results/coupling.json` 基线，只许收敛） |

SDP 违规清单：`conformance_scan→disk_cache/import_graph`、`gate_faces→effect_rows`、`import_graph→disk_cache`、`mcp_runtime→knowledge/repo_index`、`pack_combo→domain_pack`、`prose_lint→mcp_runtime`、`purity_scan→layer_model`。基线登记不等于「可接受」，逐条理由归 R6（C-02）。

## 2. 耦合热点

| 方向 | 模块（fan-in/fan-out） | 解读 |
|---|---|---|
| 高 fan-in | `json_doc`(89) · `atomic_write`(57) · `conformance_scan`(38) · `paths`(9) | 共享原语，接口必须窄；改动成本最高 |
| 高 fan-out | `capability_battery`(48) · `conformance_report`(29) · `quality_depth_scan`(15) | 聚合层，允许厚；不得被反向依赖 |

## 3. 重复实现裁定（7 项）

| 编号 | 主题 | 裁定 | 候选（例） | 动作 |
|---|---|---|---|---|
| D-01 | canonical JSON 族 | **compat-duplicate** | trust/canonical + attest + evidence + scripts/jcs | R6 不变量：冻结向量/域分隔；改口径=重签 |
| D-02 | sha256 原语 | shared-primitive | atoms/hash 等 104 文件 | 不合并；新代码走 atoms/hash 或显式 digest |
| D-03 | 路径包含性 | **duplicate-suspected** | paths + daemon/gate_observe/lsp/mcp_runtime/repo_trust/verify_report | R6 收口到 validate_path 或登记例外（mcp_runtime 已文档化例外） |
| D-04 | 覆盖率三件 | distinct-role | requirement/judgement/coverage_summary | 只共享输出口径 |
| D-05 | JSON 读写 | shared-primitive | json_doc / canonical / pipeline_loader | json_doc 管加载，canonical 管字节口径 |
| D-06 | 原子写 | shared-primitive | atomic_write + 2 调用方 | 单点保持；禁裸 open 写证据 |
| D-07 | 注册表加载 | distinct-role | registry_loader / registry_sync | 不合并；写路径只在 sync |

判定词表：`compat-duplicate` / `distinct-spec` / `distinct-role` / `shared-primitive` / `duplicate-suspected` / `documented-exception`。

## 4. 缺口（进 R6）

- C-01 路径包含性 5 处变体未统一（D-03）。
- C-02 SDP 违规 9 条未逐条写「为何可接受」。
- C-03 重复实现判定缺机器判据（当前靠人读证据；CQ3 可补）。

## 5. 复核命令

```bash
python -m pytest desktop/tests/test_reverse_coupling.py -q
python -c "import sys;sys.path.insert(0,'desktop/src');from core import coupling_metrics as c;d,m=c.graph('.');print(len(d),sum(len(v) for v in d.values()),len(c.cycles(d)),len(c.sdp_violations(d,m)))"
```

## 6. 交接（R4–R6）

- R4 失败考古：用热点模块（json_doc/canonical/paths）对照 git log 历史失败/回滚。
- R5 同行对照：只作机制借鉴（STRATEGY §3）。
- R6 不变量：D-01 冻结向量、D-03 包含性单点、SDP 不增加 → 转成机检不变量与反例（回填 C-01…C-03）。
