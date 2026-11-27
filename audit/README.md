# NF 审计体系（0.3.6 基线 / 0.3.7 落地）

> 来源：内部方案件《NF 0.3.7 Part 2：全方位审计体系》落地。
> 目标：量得出、复得现、改得动、拦得住。审计对象 = 0.3.6 冻结基线（commit aeae36b11，worktree D:/d/tmp/nf-036）。

## 目录

| 路径 | 内容 |
|---|---|
| audit/rules.json | 规则库（单文件，166 条；A–N 十四维；机读 + 人读） |
| audit/scoring.json | 维度权重（A–N）、单规则扣分上限、可复现容差 |
| audit/runner.py | 离线执行器（纯 stdlib）：跑 script 规则 → issues/meta/report → 评分 |
| audit/evidence/aeae36b11/ | 基线证据包：issues.json / meta.json / report.md |
| audit/evidence/aeae36b11-rerun/ | 同 commit 第二次重跑副本，用于逐字节确定性证明 |
| audit/remediation.md | 整改台账（初始 P0/P1 表 + P2/P3 汇总） |
| audit/ci/gate.sh | 一键门禁：跑 runner + 阈值检查，未过则非零退出 |
| audit/ci/thresholds.json | 门禁阈值（总分/维度/ P0/异常/no_targets） |
| audit/tools/ | detekt.yml、ktlint.editorconfig、konsist 骨架、SBOM 说明与工具清单 |

## 规则形状

    {
      "id": "C-001",
      "dimension": "C",
      "iso": "maintainability.analysability",
      "severity": "P2",
      "statement": "单文件 ≤400 行（生产源码）",
      "check": "script",
      "version": 1,
      "script": "file_line_limit",
      "params": { "globs": ["app/android/app/src/main/java/**/*.kt"], "limit": 400 },
      "penalty": 3,
      "source": "CISQ"
    }

字段口径：
- check = script：本仓 runner 离线执行，每个 script 名在 audit/runner.py 的 CHECKS 注册表里有唯一实现；
- check = tool：需外部工具，离线记 not-run（不扣分、不写成 pass、报告单列），必须带 tool 与 note；
- check = manual：人工抽样/双人复核，同样记 not-run，必须能追溯到方法与抽样面；
- 每条规则必须有 id、dimension、iso、severity(P0–P3)、statement、check、penalty、source、version；
- script 检查器抛异常记 error（门禁视为失败），未知 script 名也记 error，禁止静默跳过。

## 评分口径

- 维度分 = 100 − Σ min(单规则命中数, 该规则 penalty)，下限 0；
- 总分 = Σ(维度分 × 权重)，权重见 scoring.json（A–N 合计 1.00）；
- 命中数按规则实际条数统计（issues.json 单规则最多保留 200 条用于防超大文件，截断不影响评分/门禁，完整数字见 meta.json 的 rule_status.hits）；
- tool / manual / no_targets / error 均不计扣分，也不写成通过；error 与 no_targets 由门禁单独拦。

| `audit/report.md` | 汇总报告（由 `audit/ci/consolidate_report.py` 从最新证据包生成） |
| `audit/ci/` | 门禁脚本 gate.sh + 阈值 + 汇总报告生成器 |
| `.github/workflows/audit.yml` | CI：跑审计 + 门禁 + 上传证据包（actions 钉 commit SHA） |

## 跑法

    python audit/runner.py --root D:/d/tmp/nf-036 --commit aeae36b11 --out audit/evidence/aeae36b11

输出：
- issues.json：逐条命中（id = 规则::路径:行），附 not_run / no_targets / errors 清单；
- meta.json：commit、python 版本、规则数（script/tool/manual）、各维度分、总分、severity_counts、status_counts、rule_status（逐规则状态/命中/候选/错误）、runner 与规则库 sha256；
- report.md：评分表、规则执行状态、P0/P1 清单、未执行项、复现命令。

## 确定性

- 文件遍历排序、命中排序、输出无墙钟时间；同 commit + 同 runner/rules 重跑，issues.json / meta.json / report.md 逐字节一致（基线已验证：aeae36b11 与 aeae36b11-rerun 三文件 sha256 两两相同）；
- 不允许随机抽样进入分数；抽样类规则必须 manual/not-run。

## 门禁

    # 跑 runner + 阈值检查（默认 root=仓库根、commit=当前 HEAD）
    bash audit/ci/gate.sh --root D:/d/tmp/nf-036 --commit aeae36b11

    # 复用已有证据
    bash audit/ci/gate.sh --evidence audit/evidence/aeae36b11

当前阈值（audit/ci/thresholds.json）：总分 ≥95、单维度 ≥80、P0=0、规则执行异常=0、no_targets=0。
基线（aeae36b11）实测总分 92.1，C=77、E=79、总分低于阈值 → 门禁按设计返回 1（红）；这是整改起点，不是脚本故障。
tool/manual 未执行 31 条不计分，也不作为"通过"。

## 基线结果摘要（commit aeae36b11）

- 规则 166 条：script 135 / tool 14 / manual 17；
- script 执行：pass 83 / fail 52 / error 0 / no_targets 0；tool+manual not-run 31；
- 总分 92.1；维度分：A90 B91 C77 D94 E79 F94 G100 H97 I97 J97 K100 L96 M97 N98；
- 命中（按规则实际）：P0=0 / P1=84 / P2=1371 / P3=255，合计 1710；P0 两项（H-001/H-002）离线检查通过；
- 明细与未执行项见 audit/evidence/aeae36b11/report.md；整改见 audit/remediation.md。

## 纪律

- 没跑的工具/规则写 not-run 或"未接入"，不许写成通过；报告数字必须来自实际运行；
- 规则只增不减；放宽阈值或豁免规则必须附证据与 owner，写入 remediation.md；
- 整改关闭只看同 commit 重跑该规则 hits=0 + 门禁通过，不允许口头关闭。


## 当前状态（2026-11-27）

- 最新证据：audit/evidence/p2-batch7/（同 commit 连跑两次 issues/report 逐字节一致、meta 全等）。
- 总分 **97.64**；维度 A100 B97 C80 D99 E100 F98 G–N 全 100；P0=0 / P1=0 / P2=1233 / P3=220。
- 门禁：bash audit/ci/gate.sh --evidence audit/evidence/p2-batch7 → PASS。
- 测试面：Android 全量单测 green；engine/rust 全量 249/249 green；Python 资产契约/报告模块等关键套件 green。
- 残留债务（见 remediation.md 与 calibration.md，均有 owner/到期）：B-004（UI→data 直连 200 处，属单模块架构取舍，待 0.4 领域层拆分）、C 维度结构项（大文件/函数/圈复杂度）、D-005（测试样板重复）、F-003（C# sync-over-async，本机无 .NET SDK 无法构建校验）。
- 外部阻断（不在本仓能力内）：Play 上传、真机 macrobenchmark（AGP 测试模块规则通道）、on-demand OCR 触发（URI 授权）。
