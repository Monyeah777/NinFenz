# 客户 brief（样例输入）

> 场景：客户要把「AI 系统」这一域接入自己的内容生产线（写方案、写选型说明、写上线材料），但客户的合规与技术评审要求：**每份材料都要能说清依据、能被复核、能交给第三方照做**。
> 本文件是 FDE 侧收到的原始需求，也是本样例的输入之一（不参与门禁判据，只解释交付物为什么长这样）。
> **最后更新：2026-11-13（复核）**：四条诉求 → 五项可判定项的映射**复核不变**；补「每项落点怎么复核」的
> 机读口径（见「§现状对照」），并明确两件事：① `evidence/manifest.json` 的 `inputs` **不含本文件**——
> brief 只解释交付物形状、不进门禁；② 交付物 §5 写「四道门 + 中游层核验」= **G1–G4 + G5（中游出口）**
> 共五门，与 README「五道门」同一件事，不是两种口径。

## 一、客户诉求（原话转写）

1. 我要一套「AI 系统」的领域规范：概念之间谁先谁后要写清楚，不能各写各的。
2. 每份交付材料要能回答三件事：**依据什么**（标准/来源）、**怎么验收**（判据）、**谁验过**（证据）。
3. 我方内部评审会抽检：随便挑一件产物，要能当场复跑出结论。
4. 换模型/换平台不能推翻这套规范——我们明年可能换供应商。

## 二、FDE 侧的交付判定（把诉求翻译成可判定项）

| 客户诉求 | 可判定项 | 本样例的落点 |
|---|---|---|
| 概念先后写清 | 概念前置图健康 + 闭包/装载序可复算 | G3 + `evidence/deliverable.md` §2 |
| 依据什么 | 每条细分绑定在册标准（主锚 + 辅锚） | `protocol/standards_binding.json` · `docs/standards/index.md` |
| 怎么验收 | 单入口门禁 + 逐门判据 | G1–G5 + `evidence/gates.txt` |
| 谁验过 | 回执单根 + 产物 sha256 + 可第三方复跑 | `evidence/manifest.json` · `docs/interop-thirdparty.md` |
| 换供应商不推翻 | 模型无关声明 + 协议不绑引擎 | `evidence/deliverable.md` §1（系统卡字段 `model_agnostic`） |

## 现状对照（2026-11-13 · 以落点实读为准）

| 诉求 | 落点 | 复核方式（本行可执行） |
|---|---|---|
| 概念先后写清 | `evidence/deliverable.md` §2 · `gates.txt` G3 | 48 节点 / 拓扑序 47 / 问题 0 |
| 依据什么 | `protocol/standards_binding.json`（1200 记录 / 2400 锚位）· `docs/standards/index.md` | `nf standards --stats` 与 `manifest.facts.standards=370` |
| 怎么验收 | `evidence/gates.txt`（G1–G5 逐门 PASS） | 每门一行 `[PASS]`；缺一行即样例腐烂 |
| 谁验过 | `evidence/manifest.json`（产物 sha256 + 输入 sha256）· `docs/interop-thirdparty.md` | `fde_sample_run.py --check` 逐字节比对 |
| 换供应商不推翻 | 系统卡 `model_agnostic=true`（`SYSTEM_CARD.json: system.model_agnostic`）· 交付物 §1「模型无关：True」 | 读字段 + 交付物行 |
| 输入边界 | brief **不进** `manifest.inputs` | `manifest.inputs` 五条全是域包件，无 brief |

> 本表只作「需求 → 落点」索引，不替代 `--check` 实跑。

## 复现与引用口径

```bash
python scripts/fde_sample_run.py --check   # brief 的落点是否仍然成立（逐字节比对证据）
python scripts/nf.py standards --stats     # 标准锚规模（370）
```

- 引用本文时：「brief 只解释形状、不进门禁」= 长期口径；任何一个落点失效，先跑 `--check`，再回 README §五门定位。
- 本文件**不是**判据输入：改 brief 不会让证据失效，但改落点会。

## 三、边界（本样例不承诺的事）

- 不承诺**内容质量本身**（客户评审自己判断业务正确性）；NF 只保证「可产、可检、可复现、零编造、白盒」。
- 不承诺**在线服务**（样例全程离线；MCP/A2A 面见互操作导出与他证通道）。
- 不替客户做**合规结论**；NF 提供可引用的标准锚与证据，结论由客户合规方出具。
