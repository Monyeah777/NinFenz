# nf-app-core（NF APP 共享核心 · Rust 参考实现）

A0–A5 契约的 Rust 参考实现：canonical/摘要、schema 语义校验、导入/映射、协议、管线图、MD spec、装配/校验、导出、Pack 更新、CCOS 交接、项目校验；另出 C ABI 给 Android(JNA)/Desktop 复用。

- 契约真源：`app/docs/CONTRACT.md`、`app/docs/CLI.md`、`app/schema/*.json`（全部编译期内嵌，运行时不在盘上读 schema/limits/error_codes）。
- 提交物：`Cargo.toml` + `Cargo.lock` + 源码 + tests + golden 夹具；CLI 表 20 个 op 全部实现，无 TODO 桩。
- 测试：`cargo test` 20 个测试二进制、165 条断言：每 op 正例 + 定位负例；canonical 与 Python 参考向量逐字节对拍；zip slip/bomb/symlink/重名/嵌套；YAML 别名；JSON 深度；同输入两遍一致；golden 逐字节回归；FFI。

## 构建与依赖

依赖精确 pin：`serde_json` / `sha2` / `zip`（default-features=false, deflate）/ `regex`。不用 `walkdir`（Windows GNU 工具链缺 dlltool 时 windows-sys 构建失败，改为 std 递归；硬链检测用 Win32 `GetFileInformationByHandle`，stdlib 的 `number_of_links` 仍是 unstable）。

~~~bash
cd app/core
# 本机（crates.io 直连被失效代理挡住时）：先复制镜像配置（config.toml 不入仓）
cp .cargo/config.toml.example .cargo/config.toml
CARGO_HTTP_PROXY= HTTPS_PROXY= HTTP_PROXY= ALL_PROXY= cargo build --offline
CARGO_HTTP_PROXY= HTTPS_PROXY= HTTP_PROXY= ALL_PROXY= cargo build --release --offline
CARGO_HTTP_PROXY= HTTPS_PROXY= HTTP_PROXY= ALL_PROXY= cargo test --offline
~~~

CI / 默认 crates.io：`.cargo/config.toml` 是本机离线镜像（source replacement），**已 gitignore、不入仓**；仓库只提交 `.cargo/config.toml.example`。CI 可直连 crates.io 时无需该文件，直接用默认源构建；`Cargo.lock` 已提交、依赖版本钉死。要求 rustc ≥ 1.85，edition 2021。

产物：`target/release/nf-app-core.exe`（CLI）；`target/release/nf_app_core.dll`（Windows，平台对应 .so/.dylib；C ABI `nf_app_core_abi_version` / `nf_app_core_call` / `nf_app_core_free`）。

## CLI 面（CLI.md `1/`2）

- `nf-app-core --abi-version` → `{"abi":"nf-app-core/1","version":"0.1.0"}`；`--help` / `--version` 为人读输出。
- `nf-app-core <op> [--in <file>|-] [--json]`：stdin 一次读完请求体（op 表字段本体，不包 op 层）；stdout 单行 JSON 信封（canonical 键序：error,exit,ok,result 字母序）+ LF；诊断走 stderr。
- 退出码：0 成功；1 校验失败（result 必为 nf-validate-report/1）；2 用法/IO；3 拒绝（安全/未知/超限/版本）；4 环境缺失。
- warn 类语义走 exit 0，warning 在 result.warnings / result.issues 内：NF-IMP-002（低置信 <60）、NF-MAP-001（无映射候选）、NF-PCK-005（依赖未在本机）、NF-CCOS-004（人审 pending）。
- 请求级未知字段忽略；产物级未知字段按 schema additionalProperties:false 拒收（x- 扩展只有 schema 显式声明处接受，见 CONTRACT `3）。
- FFI 响应比 CLI 多一个 op 字段（CLI.md `5）；正常错误也返回信封，只有 panic 兜底返回 NULL 并留 stderr；ABI 可重入（无共享可变全局）。

## op 状态（全部实现）

| op | 语义要点 |
|---|---|
| canonical | 与 Python json.dumps(ensure_ascii=False, sort_keys=True, separators=(",",":"), allow_nan=False) 逐字节一致；禁 float（NF-E-006）；控制字符 \u00xx 小写、\b\f\n\r\t 短转义、U+2028/U+2029 与 DEL 不转义；键按 Unicode 码点序 |
| pack-hash | 递归普通文件（拒 symlink/junction/硬链/设备）；items 按 path 码点序；tree = sha256(canonical([{path,sha256,size}]))；排除 root 的 nf-pack.json、nf-pack.json.sig、root 下 *.sig |
| pack-verify | manifest schema → 逐 item sha/size → tree/count → requires（本机 root.parent()/<id>/<version> 探测；缺失=warn NF-PCK-005，越界=error）→ compat.min_app_version |
| import-sniff | 魔数 → MIME/扩展 → 内容特征；置信度整数百分比 0–100；未实现适配器（html/docx/pdf/ocr）→ NF-IMP-004 exit3；无候选 → NF-IMP-001 |
| import | 首版适配器 text/markdown/json/yaml/zip/nftpl/nfpack；结构抽取（标题/段落/代码块/表格）与原文保留；低置信 warn NF-IMP-002；超限 NF-IMP-003 |
| map-suggest | 标题→section（精确标题 90 / 顺序 60 / 无 spec 50）、段落→slot（55/40）、代码块→example（70）、表格→structured（65）；无候选 warn NF-MAP-001 |
| protocol-validate | schema → id 唯一 → 引用完整性 → 占位符声明 → compat/migrations → 规则 DSL 静态检查（未知 op NF-PRT-005） |
| protocol-render | {{F-###}} 替换（必填缺失 NF-PRT-003 / 未声明 NF-PRT-004 / 类型错 NF-PRT-005）；规则求值（and/or/not/eq/ne/gt/gte/lt/lte/in/matches/exists/len）；compat 越界拒 NF-PRT-006 exit3 |
| graph-validate | L0：schema/id 唯一/边端点与端口/kind↔必填/权重（仅 stage/module 0..100）/simple 模式限制；L1：无环（Kahn）、入口（无入边 stage）与出口可达、branch 出度≥2、merge 入度≥2、required_stages |
| graph-compile | Kahn 拓扑序（就绪集合按 node id 码点升序）；每个 module 一个 step（S01 连续）；**stage=沿入边反向 BFS 的最近上游 stage 节点 id**（同层取码点最小；无上游 stage → NF-GRF-005 exit1）；inputs=入边 from_port 去重排序；plan.digest = sha256(canonical(plan 去 digest)) |
| spec-validate | section/slot id 唯一、order 从 1 连续、双向一致、acceptance 唯一与引用、约束合法（min≤max、pattern 可编译）、references 去重；**顶层 budget 可选**：给了 max_total_chars/max_total_tokens 才判 Σ slot 预算超出 → NF-SPC-004，未给不判 |
| assemble | section.order 渲染；heading_level（默认 2）；槽位 kind=text/list/table/code/json；必填缺失 NF-ASM-002；plan digest 不符 NF-ASM-001；block 模式按 §base_markdown§ 只替换该节、其余字节保留（缺 base_markdown/节不存在 → NF-ASM-004）；meta 按 nf-assemble-result/1（slots 全槽位 [{id,section,chars}]，chars=本次写入字符数，未填 0）；out_dir 写 result.md + result.meta.json（canonical 字节） |
| validate | L0 结构/标题在场；L1 约束逐条求值（path=result.sections[i].slots[j]）+ acceptance info；L2 需 NF_APP_L2_CMD，缺 → NF-VAL-005 exit4 |
| export | md/zip/json；清单按 nf-export-manifest/1（files[{name,sha256,bytes}] + source{plan_digest,spec_digest,markdown_digest}）；来源摘要依次取请求显式 plan_digest/spec_digest → sources[{kind,ref,digest}] → result.meta → sha256(空串) 占位；zip entry 按 path 码点序、mtime 1980-01-01、权限 0644、无 extra field、deflate；重名 NF-EXP-003、越界 NF-EXP-002；docx/pdf → NF-EXP-004 exit4 |
| pack-diff | added/removed/modified（path 排序）+ impact（breaking/projects/overlay_keys）+ merge.actions + policy；conflicts 恒空（需要 overlay 内容，见 pack-merge） |
| pack-merge | 校验 update 与 base/new tree；三类冲突（delete/rename/schema，id CFL-##，默认 defer）；未裁决 NF-PCK-006；按决策写出并重算清单（items/hashes 按写出实况）；result_tree 与 pack-hash 一致 |
| overlay-apply | 校验 base 引用（tree/id/version）→ 复制 base → 应用 clauses.*.enabled（含 text_sha256 钉）→ 写 overlay/nf-overlay.json → 复制并校 custom_assets → 返回 tree（不含清单文件） |
| ccos-build-task | 项目须 validated/exported/reviewed；pipeline 取 refs.assembly 的 id/version/digest，md_spec 取 refs.spec；禁密钥形状键/值、禁绝对路径（NF-CCOS-003） |
| ccos-import-result | task_digest 回钉（NF-CCOS-002）、artifact 相对路径、密钥扫描；人审未 approved → warn NF-CCOS-004 exit0 |
| project-validate | schema、artifactRef 五字段、状态机（assembled+ 需 assembly；exported 需 history op=export；reviewed 需 history op=review 且 review.state=approved）、评审绑定字段、history 不计 digest |
| project-validate | schema、refs 形状（artifactRef 五字段）、状态机（assembled+ 需 assembly）、评审绑定（approved 需 reviewer/note/subject_digest）、history 不计入 digest |

## 确定性（NFR-DET）

- 所有 canonical 产物禁时间戳/随机/绝对路径/环境信息；同一请求两次运行输出逐字节一致（tests/determinism.rs 钉死 14 个 op + export zip 字节）。
- 唯一显式时间字段：ccos-task.created_at / ccos-result.provenance.*_at，由请求/结果显式携带；project.history[].at 不计 digest（剔除 history）。
- 列表/键一律码点升序；不依赖 locale。

## 安全硬化（CONTRACT `3/`6）

- 全部上限读 app/schema/limits.json（编译期内嵌，不散落字面量）：JSON 深度 64/字节 64MiB、YAML 深度、zip 条目 5000/总解压 512MiB/单文件 64MiB/压缩比 100:1/嵌套 1 层、pack 同上、import 标题/代码块/表格上限、文本 20M 字符。
- zip：拒绝绝对/../盘符/保留设备名/控制字符（NF-SEC-001）、symlink/junction（NF-SEC-002）、加密/未知压缩（NF-E-002）、超限与 bomb（NF-SEC-003）、嵌套（NF-SEC-003）、重名（NF-PCK-003；zip crate 会静默去重，故先在 raw 中央目录层扫）。解包只到内存，不落临时盘。
- 文件系统：symlink/junction/设备/硬链一律 NF-SEC-002；路径判据同时用于 pack item、zip entry、export 文件（NF-EXP-002）与 CCOS artifact。
- YAML：只做最小子集解析（块式 mapping/sequence/引号/裸标量/整行注释）；别名/锚点/merge key 一律拒绝（NF-SEC-004），不实现别名展开（比“限制展开”更强 fail-closed）。
- XML：本版本不解析 XML（docx/pdf 未实现 → NF-EXP-004/NF-IMP-004），实体/DTD 攻击面无入口。

## 三个新 schema 的写出/校验

- **nf-assemble-result/1**：assemble 的 `meta`（= result.meta.json）逐字段按 schema 生成并在返回前自检；`slots` 覆盖 spec 全部槽位 `[{id,section,chars}]`（chars=本次写入的字符数，未填 0），`missing` 为本次选中节里的可选缺槽位。
- **nf-export-manifest/1**：export 返回/写出的清单逐字段按 schema 生成并自检；`files` 只列导出件（result.md/result.zip/result.json），`source` 三摘要按上表来源规则解析。
- **nf-backup/1**：`src/backup.rs` 提供 `build(root, created_at?)` / `validate` / `write(root, out_path, created_at?)`；tree 口径 = pack-hash tree（排除 manifest/签名），files 列全部文件（含 nf-pack.json）便于恢复；`created_at` 由调用方显式给（可缺）。CLI op 表无 backup op（备份属 APP 数据目录/控制面职责），故以库 API + 单测（tests/backup.rs）交付。

## golden 夹具

- 生成：`cd app/core && cargo run --release -- golden-gen --out ../fixtures/golden`（或仓库根 `./app/core/target/release/nf-app-core.exe golden-gen --out app/fixtures/golden`）。
- 复核：`cargo test --test golden` —— 逐 case 用二进制跑请求，stdout 必须与 expected.json 逐字节一致；并把 golden-gen 重新生成结果与已提交夹具全量比对（防漂移）。不做 --bless 自动覆盖：重生成即改写，须人工确认后提交。
- 布局：`app/fixtures/golden/{fixtures,golden/<case>/{meta,request,expected}.json}`；27 个 case（含 4 个负例：canonical-float、pack-verify-tampered、import-unsupported、graph-validate-cycle）。
- request.json 是请求体原样 JSON（负例含 float，故不按 canonical 写）；expected.json 是 CLI 响应信封 canonical 字节 + LF。
- 写盘 op 的 out_dir 在 golden 生成/测试时都是临时目录，期望字节不含路径。

## 扩展口（计划 `17）

src/ext.rs 提供 8 个最小接口 + 默认实现（tests/ext.rs 9 条单测）：

| 接口 | 默认实现 / 行为 |
|---|---|
| Adapter | 7 个内置格式适配器包装 import 抽取；未知格式 extract → NF-IMP-004 |
| Provider | UnconfiguredProvider 仅声明（不做网络）；execute → NF-E-005 exit4 |
| PackPublisher | LocalDirPublisher 本地目录发布并返回 tree/items |
| FeatureGate | AllEnabled（计划 `2.3 要求空实现默认全开） |
| TraceRecorder | NoopTraceRecorder / InMemoryTraceRecorder（记录 step/elapsed，默认不落盘） |
| DslParser | 规则表达式白名单校验；未知 op/非法操作数 → NF-PRT-005 fail-closed |
| BatchRunner | 批量输入逐项结果，错误聚合不中断 |
| PluginAdapter | PluginRegistry；未注册插件 call → NF-E-002 exit3 |

## 环境约束（本机验证）

- ENV-01（Lead 判定，非核心代码问题）：本机 DSH 宿主工具沙箱按可执行文件路径生效——仓库内的 nf-app-core.exe 只能写工作区内路径，写 D:/tmp 等外部目录报 os error 5。因此：cargo 测试临时目录用 app/core/target/nf-test-tmp/（工作区内）；golden 写工作区内；E2E 若需写工作区外，请把 exe 复制到工作区外运行或把 out_dir 指向工作区内。核心写盘逻辑就是 std::fs::write，无私占/独占逻辑。

## OPEN（未做到/需契约方决策，附 owner）

1. **assemble --stage 的 section 可达性**：plan.steps 与 spec.sections 之间无映射字段，实现为“按 stage 过滤 plan steps；若 step.params.slots 声明则过滤 section，否则退回全部 section”。—— owner: A2 契约。
2. **pack-merge 的三方合并策略**：内容级 merge 未实现（modified 默认 take_new，merge action 仅记录意图；keep_mine 取 base 文件）；三类冲突（delete/rename/schema）按稳定 ID 检测，不静默丢。—— owner: A4。
3. **docx/pdf 导出**（NF-EXP-004 exit4）与 **html/docx/pdf/ocr 导入**（NF-IMP-004 exit3）：按契约首版未实现，不冒充成功。—— owner: A5/A3。
4. **L2 校验**：需环境变量 NF_APP_L2_CMD 指向适配器（stdin 收 {op,level,markdown,spec,plan}、stdout 回 {issues:[...]}）；未配置 → NF-VAL-005 exit4。默认 nf CLI 适配器未接线。—— owner: A2/A5。
5. **回滚（rollback）不是 CLI op**：核心提供确定性重算/覆盖写；apply→逆 update 再 pack-merge 已验证能回到 base tree（tests/ops_update.rs）；备份清单由 nf-backup/1 API 提供，备份目录指针（backups/<ts>）属 APP 数据目录职责。—— owner: APP 控制面。
6. **加密 zip**：无专用错误码，按 NF-E-002（未知/不支持）拒绝。—— owner: Lead（如需专用码改 error_codes.json）。
7. **导出 source 缺省**：markdown-only 导出且请求/结果都没给 plan/spec 摘要时，source 用 sha256(空串) 占位以满足 schema 必填；调用方应显式传 plan_digest/spec_digest 或 result.meta。—— owner: CLI/消费面约定。
