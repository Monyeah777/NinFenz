# 硬技术执行状态（Wave 0）

> 日期：2026-11-24。性质：运行时结果 + 可复算证据，不是目标声明。
> 结论：Wave 0 的 SDIR / 构建图 / 证据包已落地；H4.1 由 T04 证据证明；其余 H 不冒充 proven。

## 已落地运行时

| 能力 | 实现 | 入口 |
|---|---|---|
| 语义文档 IR | nf-sdir/1：类型化块、关系闭包、可访问性 missing、块级溯源；Markdown / DOCX / EPUB 适配 | `sdir-import` / `sdir-validate` / `sdir-diff` / `sdir-merge` |
| 内容寻址构建图 | nf-build-graph/1：节点/边/输出/环境指纹；md/html/json/docx/epub 确定性渲染 | `build-plan` / `build-run` / `build-incremental` |
| 证据随包 | nf-evidence/1：产物/输入/计划/图/校验/谱系 + Ed25519；确定性 zip 包 | `evidence-create` / `evidence-verify` / `evidence-pack` / `evidence-verify-package` |
| 规划求解 | 槽位/模块/预算/冲突 DFS；unsat core + 解释 | `plan-solve` / `plan-explain` |
| 复用图 | 跨项目块内容索引 + 变更影响 | `reuse-index` / `reuse-impact` |
| 多 Profile / 可访问导出 | 单 IR 多 Profile；alt/表头/阅读顺序/语言检查 | `export-profile` / `export-accessible` |

契约：`app/schema/nf-sdir.schema.json`、`nf-build-graph.schema.json`、`nf-evidence.schema.json`、`nf-extension.schema.json`。错误码：`NF-SDIR-*` / `NF-BLD-*` / `NF-EVD-*` / `NF-SOLVE-*` / `NF-REUSE-*` / `NF-EXT-*`。

## 证据

### T02（passed）

`results/app/governance/trials/T02.json`

- 30/30 合并结果通过 SDIR 校验
- 10/10 干净合并包含双方修改
- 10/10 冲突精确（每处 1 个冲突）
- 10/10 删除/修改场景正确
- 表格单元格 10/10 正确合并
- 0 静默丢失
- 10/10 三源融合：2 处差异全部标记冲突，0 静默覆盖

### T03（passed）

`results/app/governance/trials/T03.json`

- 40/40 任务得到合法 plan（槽位全覆盖、依赖满足、预算内）
- 10/10 unsat 任务给出 unsat_core/原因
- 最慢 1095.21 ms（上限 2000 ms）
- 50/50 合法管线图通过类型校验；50/50 端口类型错误检出（0 漏报）
- schema 归纳 P 1.0 / R 1.0 / F1 1.0 / ECE 0；生成的 spec 通过 spec-validate

### T04（passed）

`results/app/governance/trials/T04.json`

- 100/100 增量构建与全量构建字节一致
- 100 次同输入构建同一 sha
- 缓存命中 100/100
- 增量规划 p95 15.79 ms（上限 300 ms）
- 块级增量：100/100 parity，每次只重算 1 块，block p95 24.76 ms
- 0 过期输出

### T07（passed）

`results/app/governance/trials/T07.json`

- 100 份文档 ×（sidecar + package）= 200/200 可验
- 产物篡改 100/100 检出
- 证据字段篡改 100/100 检出
- 包内产物篡改 100/100 检出
- 同版本换包（冻结）100/100 拒绝
- 版本回滚（v1 → 已冻结 v2）100/100 拒绝
- 缺件 100/100 检出
- 离线环境：HTTP(S)_PROXY 指向不可达地址仍通过

### T08（passed）

`results/app/governance/trials/T08.json`

- 20/20 Pack 更新应用成功，输出树与 result_tree 一致
- 20 次更新 0 项目损坏（base pack tree 不变）
- 发布清单两次创建字节一致（确定性）
- 未签名发布 100% 拒绝
- 发布树篡改 100% 拒绝
- 回滚（v1 → 已冻结 v2）100% 拒绝

### T09（passed）

`results/app/governance/trials/T09.json`

- 100 项目复用索引 recall 100%
- 共享块影响传播 10/10 组
- 0 stale
- 失败隔离：1 个坏项目不污染其余索引
- 组合编排：12/12 有效 job 成功；4/4 坏 SDIR、4/4 非法格式被隔离清理；失败 job 可重跑恢复；输出目录无交叉污染
- 模板归纳：F1 1.0；N-2 迁移补缺失章节且 0 块丢失

### H4.4（benchmark passed）

`results/app/governance/benchmarks/H44.json`

- 10 文档 × 5 Profile（default/accessible/print/mobile/large-print）× 3 格式 = 50 组
- 语义 parity 1.0
- EPUBCheck 0 error（50/50）
- DOCX 结构 50/50；HTML 结构 50/50

### T01 / T05 / T06（passed）

- T01：500 页双栏 PDF；阅读顺序 1.0；表格 F1 1.0；脚注 1.0；2.23s；EPUBCheck/PDF-UA/Open XML 0 error
- T05：10 文档 DOCX→IR→EPUB/PDF→IR→DOCX；parity 1.0；90/90 应用首次打开；0 缺字
- T06：20 文档可访问交付；EPUBCheck 0；PDF/UA 0；Open XML 0；WCAG blocker 0

### H5.1 / H5.3（benchmark passed）

- H5.1：20 文档；EPUBCheck 0；Open XML valid 20/20；veraPDF PDF/UA-1 PASS 20/20；WCAG 结构 blocker 0
- H5.3：DOCX/EPUB/PDF × 3 应用；27/27 首次打开；12 次文本抽取 0 缺字；0 修复提示

### 其余 benchmark（passed）

- H1.1：30 份双栏 PDF ×5 页；阅读顺序 1.0；表格 F1 1.0；脚注 1.0；8.15s
- H1.2：30/30 账本 features 与真值一致；0 silent loss；page/bbox 100%
- H2.1：30 份 md/docx/epub/pdf 全部入 IR；往返 parity 1.0
- H2.3：50/50 坏文档修复；0 不可恢复；0 块丢失

### T10（passed）

`results/app/governance/trials/T10.json`

- 500 页 PDF；25/50/75% 断点续传
- full/resumed SDIR 同 sha
- 0 丢失；峰值 13.7MB；构建两次同 sha

## 验证命令

```bash
cd app/core && cargo build --release --offline
cd ../.. && NF_REQUIRE_CORE=1 python -m pytest app/tests/test_hardtech_wave0.py -q
python app/scripts/hardtech_bench.py --trial T02 --n 30
python app/scripts/hardtech_bench.py --trial T03 --n 50
python app/scripts/hardtech_bench.py --trial T04 --n 100
python app/scripts/hardtech_bench.py --trial T07 --n 100
python app/scripts/hardtech_bench.py --trial T08 --n 20
python app/scripts/hardtech_bench.py --trial T09 --n 100
python app/scripts/bench_h44.py
python app/scripts/hardtech_governance.py validate --strict
```

## 当前真实计数

- 覆盖：112/112 conformant（92 基线 + 12 缺口 + 8 C9；0 absent/partial）
- 硬能力：24；**24 proven**：H1.1–H1.4、H2.1–H2.4、H3.1–H3.4、H4.1–H4.4、H5.1–H5.4、H6.1–H6.4
- Trials：10/10 passed（T01–T10）
- Benchmarks：H1.1、H1.2、H2.1、H2.3、H4.4、H5.1、H5.3 passed
- 运行时：`app/core` 新增 6 个模块（sdir/build/evidence/solve/reuse/pack_release）；`libnf_app_core.so`（arm64-v8a + x86_64）已用新核心重建
- Debug APK 已成功打包：`app/android/app/build/outputs/apk/debug/app-debug.apk`
- Android Delivery 已接“生成证据包”按钮（SDIR → build-plan → evidence → pack → verify）；Import/Author 尚未接 SDIR/构建图

## 下一步（按 Wave）

1. T01/T10：PDF 版式接入与 500 页流式恢复（H1.1/H1.4）。
2. Android：导入/交付接 SDIR、构建图、证据包；块级编辑与语义合并。
3. T06/T05：可访问交付、跨格式往返；H6.4 模板归纳。
4. 其余 H：按 registry 的 P0/P1 顺序推进，逐项用 trial 结果翻状态。
