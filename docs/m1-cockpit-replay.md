# M1 · 认知驾驶舱全链离线演练（P4，2026-11-02）

> 定义（记忆 133 §5）：M1 = 任务 → 驾驶舱 → 决策账本 → 契约门禁 → 回执 → 关闭 Action，
> 全链**可离线重放**且结论一致。
> 实现：`scripts/m1_e2e.py`（run / check 两模式）；门禁：`verify.sh` check45。

## 1. 链路与产物

```
prompt ──nf cockpit──► manifest.json + journal.json + event.json（nf-cognition-event/1）
                              │                     │
                              ▼                     ▼
                     artifact.md（AI 生成标记）   cognition event store
                              │                     │
                     nf labeling check（契约门禁 PASS）
                              │                     │
                              ▼                     ▼
                     evidence card（含 cognition 块） ◄── 事件 digest
                              │
                     cockpit ledger：decision（refs=event）→ close_action（evidence=cog-event:<digest>）
                              │
                     receipt.json（nf-m1-receipt/1：artifact_sha256/card_digest/event_digest/gate/action/digest）
                              │
                     report.json（nf-m1-report/1：6 项 checks + verdict，确定性）
```

## 2. 运行

```bash
# 一次完整演练（约 15–20 s，主要成本是 cockpit 4 turns）
python3 scripts/m1_e2e.py run --work /tmp/m1

# 离线重放复核（只读；同一 work 连续两次报告逐字节相同）
python3 scripts/m1_e2e.py check --work /tmp/m1
python3 scripts/m1_e2e.py check --work /tmp/m1
diff <(python3 scripts/m1_e2e.py check --work /tmp/m1) \
     <(python3 scripts/m1_e2e.py check --work /tmp/m1)
```

## 3. 判据（check45）

- `run` rc=0 且 report verdict=PASS；
- `check` 两次 rc=0 且两次 `report.json` **逐字节相同**（同一工作目录的重放确定性）；
- 任一环节被篡改（artifact/事件库/card/gate/ledger/receipt）→ check rc=1 并列出失败环节。

## 4. 实测（2026-11-02）

- run：cockpit 4 turns / status=pass；artifact 经 labeling sign+check PASS；事件 digest 写入事件库；
  证据卡 cognition 块可复算；ledger 关闭动作带 `cog-event:<digest>`；receipt/report 生成。
- check：连续两次输出与 report.json 逐字节一致；篡改 artifact → artifact/card/gate 三项 FAIL；
  删事件库 → event/card FAIL；缺 receipt / 坏 JSON / gate 不一致 / ledger 缺记录 → 对应 FAIL。
- 单测：`desktop/tests/test_m1_e2e.py` 9 例 OK。

## 5. 边界

- 依赖现有 CLI 契约（`nf cockpit`、`nf labeling`）；本机 cockpit 约 8 s/次。
- 跨工作目录的两次 run 不要求报告相同（journal 含时间戳，事件 digest 必然不同）；M1 的「可重放」
  指同一工作目录内从 manifest+journal 重算一致。
- 回执为**本地回执**（哈希自证），不含外部签名/时间戳；外部锚定属后续阶段。

## 6. 双会话 prev 链 + card digest 证据（扩展，2026-11-02）

### 6.1 双会话 prev 链

- 会话 A：`nf cockpit --prompt A` → `manifest_a/journal_a` → `eventA = build(...)`；
- 会话 B：`nf cockpit --prompt B` → `manifest_b/journal_b` → `eventB = build(...)`，
  **`eventB.prev = eventA.digest`**，随后「删 digest → 重算」得 `eventB.digest`
  （digest 覆盖含 prev 的 body，改写 prev 必须重算，否则链自证失败）；
- 两个事件都写入 cognition event store；`receipt.json` 记录
  `event_a_digest` / `event_b_digest` / `event_b_prev`；
- check 的 `event` / `chain` 两项复核：A/B 由 manifest+journal 重算一致、
  A/B 均在事件库、且 `event_b.prev == event_a.digest`（prev 链断裂即 FAIL）。

### 6.2 card digest 证据

- `card = evidence_card(artifact, cognition=eventB)`；
  `card_digest = sha256(canonical(card))`（与 `receipt.card_digest` 同口径）；
- ledger `decision` 的 evidence = `[artifact, cog-event:A, cog-event:B,
  card:<card_digest>]`；
- 关闭 action 的 evidence = `[cog-event:A, cog-event:B,
  card:<card_digest>]`；
- `evidence_mcp.close_action` 的证据形态校验（fail-closed）：
  - `cog-event:<64hex>`：必须能在事件库加载；
  - `card:<64hex>`：正则 `^card:[0-9a-f]{64}$`，非法即加入 bad 并拒绝；
  - 其它形态按仓内路径校验（越界/缺失即拒绝）。
  「**action 关闭必须带 card digest**」的语义由 `m1_e2e.py run` 与
  `verify.sh check45` 保证（工具面只做形态校验，不把卡绑定到具体路径）；
- check 的 `card` / `card_digest` / `ledger` 三项复核：卡 verify 通过且
  cognition 绑定 `eventB.digest`、`sha256(canonical(card)) == receipt.card_digest`、
  账本 action 已关闭且 evidence 覆盖 A/B/card 三条。

### 6.3 check45 判据与文案

- `m1_e2e.py run --work W` rc=0；随后 `check --work W` 跑**两次**均 rc=0，
  且**同一工作目录**两次 `report.json` 逐字节相同（跨工作目录不比，
  journal 时间戳必然不同）；
- 绿时 verify.sh 打印：「驾驶舱 M1 双会话链可重放（prev 链 + action 带
  card digest；cockpit→event→card→gate→ledger→receipt→replay 逐字节一致）」。

### 6.4 实测（2026-11-02）

- run：双会话 A/B + prev 链 + card digest；labeling gate PASS；
  ledger decision/action 均带 A/B/**card:<digest>** 三条证据；
  `check` 两次 rc=0 且 report 逐字节一致；report 8 项 checks：
  `receipt / event / chain / artifact / card / card_digest / gate / ledger`。
- 篡改：改 artifact / 断 prev 链 / 改 card / 删事件 / 改 receipt /
  删 ledger 关闭记录 → 对应 check FAIL（rc=1）。

## 7. 证据角色传播（event→card→receipt，2026-11-02 扩展）

### 7.1 角色语义（只许原样传播，不得升级）

| 角色 | 含义 | 允许用途 |
|---|---|---|
| `local-trusted` | 本地可信源（本仓协议/门禁/事件库摘要） | 可作为证据 |
| `derived` | 由可信输入派生（证据卡 digest / receipt 摘要等） | 可作为证据 |
| `external-advisory` | 外部建议（未经本地复算） | **只作咨询，不得当证据** |

- 传播链：cognition event（`evidence_roles`）→ evidence card 的
  `cognition.evidence_roles`（**同值透传**）→ receipt（impl 侧原样记录）；
- 硬约束：角色只能**原样传播**。把 `external-advisory` 改成 `derived`
  这类「咨询→证据」升级，`verify_card` 会报
  `cognition evidence_roles 不一致`（fail-closed）；
- 跨目录事件库：`m1_e2e.py run/check` 支持 `--event-store <dir>` 让事件库
  读写指向指定目录；roles 随事件一起迁移，不因目录变化而升/降级。

### 7.2 core 接口

- `cognition_event.build(manifest, journal=None, session_id="",
  evidence_roles=None)`：仅当 `evidence_roles` 为**非空 dict** 时写
  `event["evidence_roles"] = dict(evidence_roles)`；缺省/空/非 dict
  **不加键**（旧事件 digest 保持稳定）。roles 参与 digest，键序由
  `sort_keys` 规范化；
- `evidence_card(..., cognition=event)`：事件含 `evidence_roles` 时，
  card 的 cognition 块**透传同值**；
- `verify_card`：除既有 digest / manifest_digest / handoff_digest 校验外，
  **逐值比较** card 与事件库事件的 `evidence_roles`，不一致即 issues。

### 7.3 M1 的 A/B 角色示例

  角色映射的口径是「角色名 → 非负计数」，键必须来自白名单
  `local-trusted / derived / external-advisory`，未知键/负数/bool 即拒；
- 会话 A：`{"local-trusted": 3}`（manifest/journal/event 均本地可信）；
- 会话 B：`{"local-trusted": 1, "derived": 1, "external-advisory": 1}`
  （`derived` 对应 `prev`=A 的 digest 派生；外部笔记只作咨询）；
- 跨目录 --event-store 复核：事件/digest/roles 三者一起迁移；check 的
  `card` 项同时校验 digest 与 roles 一致，任一被改即 FAIL。

## 8. 事件库查询与 GC（2026-11-02 扩展）

### 8.1 查询面

- core：`list_sessions() -> [{session_id, events, prev_chain}]`（按 session_id
  排序；优先读 `events/index.json`，索引缺失/损坏时只扫描事件库现算，不写盘）；
  `query(session_id=None, status=None, digest=None, limit=50) -> [event...]`
  （按文件加载后过滤，按 digest 排序取前 limit；limit 1..500，越界 ValueError）；
- CLI：
  ```bash
  python scripts/evidence_cli.py cognition-query --json
  python scripts/evidence_cli.py cognition-query --session <sid> --status pass --limit 10 --json
  python scripts/evidence_cli.py cognition-query --digest <64hex> --json
  ```

### 8.2 GC（按会话整组保留 + 保留链）

- core：`gc(keep_last=20, keep_digests=(), dry_run=True) -> dict`
  - 会话按「会话内事件文件 mtime 最新」排序，保留最近 `keep_last` 个会话；
  - `keep_digests` 里的 digest 额外强制保留；
  - **自动保留被保留会话 `prev_chain` 引用的祖先**（跨会话祖先也会保留），
    不会把 B 的 `prev=A` 链断掉；
  - `dry_run` 默认 True（只算不删）；`--apply` 才删事件文件并原子重建索引；
  - `keep_last < 1` / digest 形态非法 → `ValueError`（附修复指引）；
    `keep_last >= 会话数` → no-op（全部保留）；
  - 返回 `{"kept":[digest...],"removed":[...],"sessions_kept":n,
    "sessions_removed":m,"dry_run":bool}`；
- CLI：
  ```bash
  # 先看会删什么（默认 dry-run）
  python scripts/evidence_cli.py cognition-gc --keep-last 1 --json
  # 真正执行：删后重建索引
  python scripts/evidence_cli.py cognition-gc --keep-last 1 --apply --json
  # 额外强制保留某个事件
  python scripts/evidence_cli.py cognition-gc --keep-last 5 --keep-digest <64hex> --json
  ```
- apply 之后 `verify_index()` 必须为空（索引与目录一致）。

### 8.3 check45 覆盖（第 6 段）

对事件库副本：`cognition-query --json` 必须能查到 A/B 两个 digest；
`cognition-gc --keep-last 1` dry-run rc=0 且事件文件数不变；
`--apply` rc=0 且随后 `verify_index()==[]`，并且保留会话 B 与其 prev 祖先 A
都仍在（保留链不断）。任一条失败即 check45 红。

## 9. M1 报告中的 query/gc 检查项（2026-11-02 扩展）

`scripts/m1_e2e.py check` 的 checks 从 12 项扩到 **15 项**，新增 `query`、
`gc_dry`、`gc_apply`，报告仍是确定性 JSON（无时间戳 / 无绝对路径 / `sort_keys`），
同一 work 连续两次 check 的 `report.json` 逐字节相同，退出码逻辑不变
（全 True → 0，否则 1）。

- `query`：在 `--event-store` 作用域内 `cognition_event.query(status="pass",
  limit=500)` 的结果 digest 集合必须包含 A/B；`list_sessions()` 必须包含 A、B
  两个 session_id（session_id 由事件重算得到，A/B 分别来自两次 cockpit 会话）。
  store 里删掉事件 A → `event`/`chain`/`query` 等项一起 FAIL。
- `gc_dry`：对**真实**事件库调 `gc(keep_last=1, dry_run=True)`：`dry_run` 必须为
  True、`kept ⊇ {A,B}`（保留会话 B 时按 prev 链自动保留祖先 A），且
  `<store>/events/*.json` 文件数前后不变（干跑绝不写盘）。
- `gc_apply`：把 `<store>/events` 用 `cp -a` 语义（`copytree(copy_function=
  copy2)`，保留 mtime——GC 按会话内事件文件 mtime 判新旧）复制到
  `<work>/gc-probe/events`，临时 `NF_COCKPIT_HOME=<work>/gc-probe` 调
  `gc(keep_last=1, dry_run=False)`；断言 `verify_index()==[]`、A/B 文件仍在
  （祖先保留）、`removed` 不含 A/B；结束后删除 probe 目录并恢复环境变量
  （check 不残留 `gc-probe`）。
- 失败面实测：store 里删事件 A → `event/chain/index/query/gc_dry/gc_apply`
  FAIL；索引被篡改/删除 → `index`（及 query 相关）FAIL；probe 只在 check
  内部生成和清理，不进 receipt/report。
- 边界：`gc_dry/gc_apply` 都用 `keep_last=1`，依赖「B 会话是最近会话、A 是 B
  的 prev 祖先」这一 M1 数据形态；`gc_apply` 只动副本，真实事件库只做 dry-run，
  因此 check 是只读的（除 `<work>/report.json` 与临时 probe）。

## 10. 保留策略配置（2026-11-02 扩展）

### 10.1 schema `nf-cognition-retention/1`

| 字段 | 类型 | 说明 |
|---|---|---|
| `keep_last` | int ≥ 1 | 按会话最近保留 N 个会话 |
| `keep_status` | list[str] | 命中的状态（如 `["fail"]`）→ 该会话**整组保留** |
| `max_events` | int ≥ 1（可选） | 只截断「按最近保留」部分的事件数 |
| `dry_run` | bool，默认 `true` | true=只算不删；apply 需 false |

`schema` 可省略；写了必须等于 `nf-cognition-retention/1`。未知字段/类型错/
负数一律 `ValueError`（CLI 返回 2），fail-closed。

### 10.2 优先级（字段级合并）

显式 `gc(...)` 参数 > 环境变量 `NF_COCKPIT_RETENTION`（JSON 字符串）>
`config`（dict/JSON 路径；CLI `--config FILE`）或 `<store>/retention.json` >
内置默认（`keep_last=20, keep_status=[], max_events=None, dry_run=true`）。

- 高层只覆盖「出现过的字段」，其余字段回落到下一层；
- `config` 参数/`--config` **替代**事件库里的 `retention.json`（同一 tier），
  环境变量仍优先于它；
- 非法 JSON / schema 不符 / 未知字段 / 类型错 / 负数 → `ValueError`
  （带修复指引），CLI rc=2。

### 10.3 语义

- `keep_status` 命中的会话整组保留，**不参与** `max_events` 截断；
- `max_events` 只截断「按最近保留」部分；`keep_digests` 与 prev 祖先仍保留
  （可能因此超过 max_events）；
- `dry_run` 默认 true（只算不删）；apply 后删事件文件并重建索引，
  `verify_index()` 必须为空；
- 返回结构含 `policy`（生效策略），便于审计/门禁用例断言。

### 10.4 CLI 示例

```bash
# 策略文件（dry-run 默认 true）
cat > /tmp/retention.json <<'JSON'
{"schema":"nf-cognition-retention/1","keep_last":2,"keep_status":["fail"]}
JSON
python scripts/evidence_cli.py cognition-gc --config /tmp/retention.json --json
# 真正执行
python scripts/evidence_cli.py cognition-gc --config /tmp/retention.json --apply
# 环境变量优先于文件（字段级覆盖）
NF_COCKPIT_RETENTION='{"keep_last":1,"dry_run":true}' \
  python scripts/evidence_cli.py cognition-gc --json
# 非法配置必须失败（fail-closed）
echo '{"keep_last": 0}' >/tmp/bad-retention.json
python scripts/evidence_cli.py cognition-gc --config /tmp/bad-retention.json  # rc=2
```

### 10.5 check45 覆盖（第 7 段）

对事件库副本：写临时策略文件（`keep_last=1, keep_status=["pass"]`）→
`cognition-gc --config ... --json` 断言 rc=0 且输出含 `"policy"`；
再写非法配置（`keep_last=0`）→ 断言 rc!=0。任一条失败即 check45 红。

## 11. 灰度/审计试运行（--audit / --canary，2026-11-02 扩展）

- `gc_audit(config=None, canary=False)`：
  - 按现行策略链算 kept/removed（dry-run 语义），生成**确定性**审计记录
    `nf-cognition-gc-audit/1`（字段：policy、policy_digest、kept、removed、sessions_kept、
    sessions_removed、store_digests、dry_run=true、digest；无时间戳），
    原子写 `<store>/audit/<digest>.json`；重复调用同输入 → 同 digest、不重复写。
  - `canary=True`：把 store 拷到 `<store>/canary/`（copy2 保 mtime），在**影子库**上真跑
    `gc(dry_run=False)` 并校验影子 `verify_index()==[]`；真实库不动；返回 `canary`
    块（applied/kept/removed/index_ok）。
- CLI：`python3 scripts/evidence_cli.py cognition-gc --audit [--json]`、
  `... --audit --canary [--json]`（默认 dry-run；`--apply` 仍只用于真库）。
- check45 **第 8 段**（在 store 副本 `$_msq` 上）：
  1) `--audit` 两次 → rc0、审计文件落盘且含 schema/policy_digest/removed、两次 digest 相同；
  2) `--audit --canary` → `canary.applied/index_ok` 均为 true；
  3) 前后事件文件数不变（审计/灰度不得动真实库）。
- 实测：审计两次 digest 相同、audit 目录 1 个文件；canary 后真实库文件数不变、影子索引一致。

## 12. 审计记录查询/汇总（2026-11-02 扩展）

### 12.1 API

- `list_audits() -> list[dict]`：读 `<store>/audit/*.json`，按 digest 排序；
  坏 JSON / schema 不符 / 文件名与 digest 不符 → `ValueError`（fail-closed，
  带修复指引）；
- `query_audits(policy_digest=None, has_removed=None, limit=50)`：按策略 digest
  与「是否有删除项」过滤，再按 digest 排序取前 limit（1..500，越界 ValueError）；
- `audit_summary() -> dict`（确定性、无时间戳）：
  ```json
  {"schema":"nf-cognition-audit-summary/1","total":n,
   "by_policy_digest":{"<policy_digest>":count,...},
   "total_removed":x,"total_kept":y,
   "max_removed":{"digest":"<audit digest>","removed":n}|null}
  ```
  空审计目录 → `total=0`、`by_policy_digest={}`、totals=0、`max_removed=null`。

### 12.2 CLI

```bash
python scripts/evidence_cli.py cognition-audits --json
python scripts/evidence_cli.py cognition-audits --policy-digest <64hex> --json
python scripts/evidence_cli.py cognition-audits --has-removed --limit 10 --json
python scripts/evidence_cli.py cognition-audit-summary --json
```

### 12.3 check45 覆盖（第 9 段）

store 副本上（第 8 段已产生审计；第 9 段再补一条不同策略的审计以凑 ≥2 条）：
`cognition-audits --json` rc0 且数组 ≥2 条；
`cognition-audit-summary --json` 跑两次 rc0 且两次输出 `cmp` 逐字节相同、
`total ≥2`。任一条失败即 check45 红。

## 13. 审计异常阈值告警（2026-11-02 扩展）

### 13.1 规则 `nf-cognition-audit-alerts/1`

| 字段 | 类型/默认 | 含义 |
|---|---|---|
| `max_removed` | int ≥0，默认 10 | 单条 audit 的 removed 数上限 |
| `max_removed_ratio` | float 0..1，默认 0.5 | 整体 removed/(removed+kept) 上限 |
| `max_policy_churn` | int ≥0，默认 5 | 审计里出现的策略 digest 种类上限 |
| `min_audits_for_ratio` | int ≥0，默认 1 | 计算 ratio 前要求的最少审计条数 |

- `config` 可为 dict 或 JSON 路径；缺省读 `<store>/alert_rules.json`（不存在则用默认）；
- 未知字段/schema 不符/类型错/负数/ratio 越界 → `ValueError`（fail-closed，带修复指引）。

### 13.2 输出 `audit_anomalies(config=None)`

确定性（无时间戳）：
```json
{"schema":"nf-cognition-audit-alert/1",
 "findings":[{"severity":"fail|warn","kind":"max_removed|removed_ratio|policy_churn",
              "detail":"...","audit":"<digest>|null"}],
 "clean":true|false,
 "digest":"<sha256(canonical)>"}
```
- `max_removed` 命中 → severity=`fail`，`audit` 为该条 digest；
- `removed_ratio` 命中 → severity=`warn`，`audit=null`（需 `total_audits >= min_audits_for_ratio`）；
- `policy_churn` 命中 → severity=`warn`，`audit=null`；
- findings 按 `(kind, audit)` 排序；空审计库 → `clean=true`、findings=[]。

### 13.3 CLI

```bash
# clean → rc0；有 findings → rc1
python scripts/evidence_cli.py cognition-audit-alerts --json
# 自定义规则（例：策略种类上限 0 → 必告警）
echo '{"schema":"nf-cognition-audit-alerts/1","max_policy_churn":0}' >/tmp/alerts.json
python scripts/evidence_cli.py cognition-audit-alerts --config /tmp/alerts.json --json  # rc1
```

### 13.4 check45 覆盖（第 10 段）

store 副本上：默认规则 `--json` rc0 且 `clean=true`、findings=[]；再跑一次输出
`cmp` 逐字节相同（确定性）；`--config` 设 `max_policy_churn=0` → rc1 且 findings
非空、含 `policy_churn`。任一条失败即 check45 红。

## 14. 告警历史/趋势（2026-11-02 扩展）

### 14.1 API

- `record_alert_report(config=None) -> dict`：调用 `audit_anomalies(config)` 生成
  `nf-cognition-audit-alert/1` 报告，**原子写** `<store>/alerts/<digest>.json`；
  同一 digest 已存在则**不重写**（幂等）；返回该报告。
- `audit_alert_history() -> list[dict]`：读 `<store>/alerts/*.json`，按 digest 排序；
  坏 JSON / schema 不符 / 文件名与 digest 不符 → `ValueError`（fail-closed，带修复指引）；
  空目录 → `[]`。
- `audit_alert_trend() -> dict`（确定性、无时间戳）：
  ```json
  {"schema":"nf-cognition-alert-trend/1","reports":n,"clean":x,"dirty":y,
   "by_kind":{"max_removed":c,...},"by_severity":{"fail":c,"warn":c},
   "latest":"<最后一条按 digest 排序的报告 digest>|null"}
  ```
  空历史 → `reports=0, clean=0, dirty=0, by_kind={}, by_severity={}, latest=null`。

### 14.2 CLI

```bash
# 生成并落盘告警历史（同 digest 只落一次；clean→rc0 / 告警→rc1）
python scripts/evidence_cli.py cognition-audit-alerts --record --json
python scripts/evidence_cli.py cognition-audit-alerts --record --config /tmp/alerts.json --json
# 查历史与趋势
python scripts/evidence_cli.py cognition-alert-history --json
python scripts/evidence_cli.py cognition-alert-trend --json
```

### 14.3 check45 覆盖（第 11 段）

store 副本 `$_msq` 上：`--record --json` 两次 → rc0 且 `<store>/alerts/` 恰 1 个
文件（同 digest 不重写）；`cognition-alert-history --json` rc0 且 ≥1 条、schema 正确；
`cognition-alert-trend --json` 两次 rc0 且输出 `cmp` 逐字节相同、`reports ≥1`。

## 15. 回执外部锚定（HMAC，2026-11-02 扩展）

- `m1_e2e.py run/check --anchor-key FILE`（可选；密钥文件必须在工作目录 **W 之外**，否则 exit 2）。
- run：先算回执 base body 的 `base_digest = sha256(canonical(body))`，用
  `core.attest.sign_digest_hmac(base_digest, key_bytes)` 生成
  `anchor={scheme:"hmac-sha256", key_id:sha256(key)[:16], mac, issuer:""}`，
  把 `anchor` 放进回执后再算回执自证 `digest`（anchor 参与自证）；确定性、无时间戳。
- check：回执有 anchor → 必须有同 key 且重算 mac/key_id/scheme 一致，否则 `anchor` FAIL；
  无 anchor → `anchor` PASS（detail `no-anchor`），兼容既有 15 项演练。
- report 现为 **16 项 checks**（`receipt → anchor → event → chain → … → gate → ledger`）。
- 失败面：篡改 anchor.mac（并重算回执 digest）→ 仅 anchor FAIL；有 anchor 但 check 不带 key →
  anchor FAIL；key 放 W 内 → run/check 均 exit 2；空 key 文件 → run exit 2 / check anchor FAIL。
- 实测：带 key run/check 16/16 PASS、anchor `hmac-sha256`；篡改 mac → rc=1。
- 边界：目前仅 HMAC（本地外锚）；sigstore/TSA 属后续（`core.attest` 已有 sigstore 外挂验证接口）。
