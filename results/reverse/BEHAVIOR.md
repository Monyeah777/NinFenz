# 行为重建（BEHAVIOR，§4A R2）

> ⛔ 操作指令：本件是 §4A R2（行为重建）人读结果；机读真源 `results/reverse/behavior.json`（`nf-reverse-behavior/1`），判据 `desktop/tests/test_reverse_behavior.py`。每条流必须指到入口/生成物/校验链/失败语义；未实现流显式 `status=gap`。
> 状态：v1（2026-11-14 · G0 §4A R2）· 前置：`CONTRACT_MAP.md`（R1）
> 方法：按 R1 消费方列从入口读调用链；阶段名来自实现 docstring/参数；失败语义来自代码 return/exit 分支。

## 1. 行为流（11 条：9 documented + 2 gap）

| 编号 | 名称 | 入口 | 阶段 | 生成物（例） | 校验 | 失败语义 |
|---|---|---|---|---|---|---|
| F-01 | 生产全链 run | `scripts/nf.py` | retrieve→compose→gate→export | output_forms / interop cid | check12/18 | gate 不过 exit 1；未知 fmt exit 2 |
| F-02 | 需求自组装 assemble | `scripts/nf.py` | plan→build→check | assembly schema | check16 | 需求坏 exit 2；成品未过验收 exit 1 |
| F-03 | 冻结链 | `docs/release.md` | conformance→approve→receipts | 报告/批准/回执 | check35 | 顺序错/对象改动 exit 1 |
| F-04 | 门禁 verify | `verify.sh` | checks-only→tests→report | verification_report | check12/38 | FAIL exit 1；缺脚本 exit 2 |
| F-05 | 证据包 evidence | `scripts/nf.py` | build→self-verify→third-party | SELF_AUDIT / 向量 | check45/48 | 缺锚 exit 2；篡改 exit 1 |
| F-06 | 信任等级判定 | `scripts/trust_verify.py` | load→decide | verify schema | check46 | 0/1/2 三态（缺锚=2、结构=1） |
| F-07 | 发布体检/冻结 | `scripts/nf.py` | gate→changes→freeze→verify→audit | 批准/回执链 | check38 | 体检未过 exit 1 |
| F-08 | 语言面重签 | `scripts/nf.py` | scan→mirror→resign | locales.json | check34 | 缺件/未声明 exit 1 |
| F-09 | Spec Registry 查询 | `scripts/nf.py` | load→list | registry.json | — | registry 不可读 exit 2 |
| F-10 | Wiki 编译（未实现） | `scripts/nf.py` | compile→index→graph | wiki-page schema | check43 | gap（G1 WP-10） |
| F-11 | Spec 编译（未实现） | `scripts/nf.py` | intent→spec→task | spec schema | check44 | gap（G1 WP-11） |

## 2. 状态机

| 编号 | 状态机 | 状态 | 规则 | 证据 |
|---|---|---|---|---|
| S-01 | 冻结链 | content-final→conformance→approval→receipts | 单向前进；回退=重做内容整链重跑 | `protocol/release_policy.json` |
| S-02 | 信任等级 | T0→T1→T2→T3→T4 | achieved≥required；缺项 exit 2 不冒充 | `core/trust/verify.py` |
| S-03 | 契约生命周期 | draft→active→deprecated→retired | deprecated/retired 不得被引用（check24 同源） | `protocol/production/contract.schema.json` |

## 3. 失败语义要点

- **exit 三态**：0=通过 / 1=判定为否（结构/签名/篡改/未过验收）/ 2=不可判定（缺输入、缺锚、策略非法）。报告必须写缺什么与修复指引。
- **门不过 ≠ 产物可交付**：`PipeResult.ok` 与 export 分离；下游可看坏产物，但不得当合格。
- **顺序不可颠倒**：冻结链、发布体检、TSA/锚组合都有顺序依赖；错序即红，不能靠重跑掩盖。
- **未实现流**（Wiki/spec 编译）显式 `gap`，不写成「已具备」。

## 4. 复核命令

```bash
python -m pytest desktop/tests/test_reverse_behavior.py -q
python -c "import json;d=json.load(open('results/reverse/behavior.json',encoding='utf-8'));print(len(d['flows']),len(d['state_machines']))"
```

## 5. 交接（R3–R6）

- R3 耦合/重复：从 F-01/F-04 的入口闭包与 `contracts` 引用交叉。
- R4 失败考古：用本件失败语义对照 git log 历史失败/回滚/热修。
- R5 同行对照：只作机制借鉴（STRATEGY §3）。
- R6 不变量：把状态机（S-01…S-03）与 exit 三态转成机检不变量与反例。
