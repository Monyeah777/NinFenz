# 单对象策略体检 v0（check policy）

状态：**已实装**（判据：`desktop/tests/test_check_policy.py` 19 项；CLI：`nf check --policy`）。
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-04
> **Status**: v0 已实装（nf check）· **上位**: docs/ccos/abi-v0.md §2 cc_check

## 是什么

给定**一个对象**与**一份策略**，出可复算的 verdict。内部差距（2026-11-04 实证）：仓里的判定
全是仓库级的（nf verify / nf conformance / nf lint 都扫整个仓库或整类文件），缺「这个文件
符不符合这条要求」的最小单元——而合规体检的最小单元正是它。

**纪律**：只做**封闭词表**的确定性判定，不自造 DSL（与 protocol/assertions.json 同一条纪律：
新增规则 = 加一条数据，不扩表达力）；业务语义断言仍留在 check 代码里。

## 策略形状（nf-check-policy/1）

```json
{
  "schema": "nf-check-policy/1",
  "id": "ai-disclosure",
  "rules": [
    {"id": "must-disclose", "kind": "regex_present", "pattern": "AI\\s*生成",
     "severity": "fail", "fix": "在文首加一行披露：「本内容由 AI 生成」"},
    {"id": "no-tab", "kind": "regex_absent", "pattern": "\\t", "severity": "fail",
     "fix": "把制表符换成空格"},
    {"id": "min-lines", "kind": "count_at_least", "field": "lines", "n": 2,
     "severity": "warn", "fix": "补足内容长度（≥2 行）"},
    {"id": "utf8-only", "kind": "utf8", "severity": "fail", "fix": "另存为 UTF-8"}
  ]
}
```

| 字段 | 必填 | 判据 |
|---|---|---|
| schema | 是 | 必须等于 nf-check-policy/1 |
| rules[].id | 是 | 唯一（重复 id 让结论无法定位） |
| rules[].kind | 是 | 封闭词表：utf8 / regex_present / regex_absent / count_at_least / digest_pin |
| rules[].severity | 否 | fail（缺省）/ warn；**warn 只提示，不改 verdict** |
| rules[].fix | 是 | 非空（判失败却不说怎么改，等于把问题丢回读者） |
| rules[].pattern | 正则类必填 | 必须是合法正则 |
| rules[].field / n | count_at_least 必填 | field ∈ bytes / lines / chars；n 为非负整数 |
| rules[].sha256 | digest_pin 必填 | 64 位十六进制 |

坏策略一律**带指引拒绝**，不静默跳过——判据不合法时给出结论本身就是假结论。

## 意图编译器 v0（nf-check-intent/1 → nf-check-policy/1）

自动把**法规文本**翻成规则不在本仓能力内；能做的诚实中间层是：**人写结构化意图 → 编译器映射到
封闭词表**，并把「表达不了」逐条列出来（不静默丢要求）。

```json
{
  "schema": "nf-check-intent/1",
  "object": "docs/ccos/abi-v0.md",
  "policy_id": "AIGC-basic",
  "requirements": [
    {"rule": "explicit_notice", "text": "AI 生成", "where": "start"},
    {"rule": "forbidden_tokens", "patterns": ["TODO", "待补"]},
    {"rule": "min_bytes", "n": 120},
    {"rule": "require_metadata", "key": "AIGC", "value": "1"},
    {"rule": "semantic_claim"}
  ]
}
```

```bash
nf check --list-rules                                  # 可编译规则 + 明确不可表达规则
nf check --compile intent.json --out policy.json       # 0=全编 ｜ 3=有不可表达 ｜ 2=意图不合法
nf check 对象.md --policy policy.json                  # 拿编出来的策略去判
```

| 意图规则 | 编译成 | 说明 |
|---|---|---|
| `explicit_notice`(text, where) | regex_present（^ / $ / 任意） | 显式提示文字 |
| `forbidden_tokens`(patterns) | 每条一个 regex_absent | 不得出现的内容 |
| `min_bytes`(n) | count_at_least(bytes) | 最小体量 |
| `require_metadata`(key[, value]) | regex_present（key[:=]value） | 元数据声明（**只到"文本里有这个形态"**） |
| `digest_pinned`(sha256) | digest_pin | 钉摘要 |
| `utf8` | utf8（并恒为第一条前置） | 编码合法 |

**明确不可表达**（会进 `unsupported` 并写清缺什么）：`semantic_claim`（要不要模型判内容）、
`carrier_watermark`（要载体读写）、`visual_notice`（要媒体渲染）、`time_window`（要可信时间）、
`owner_signature`（要身份/CA）。编译出的策略带 `compiled_from.digest`——判据版本随结论走。

## 判定

- 逐条规则出 finding（ok / fail / warn），**顺序 = 规则顺序**（确定性，可 diff）。
- verdict 只有两个词：`ok`（无 fail 级违规）/ `invalid`（有 fail 级违规）。
- `policy_digest = sha256(canonical(policy))` 随结论一起返回：**判据版本随结论走**，
  判据版本不随结论，结论就不可复算。
- 退出码：ok=0 / invalid=1 / 用法错（策略或对象不可读、策略不合法）=2。

## 怎么用

```bash
# 单对象体检（对象 = 单个文件；目录请逐件跑）
python scripts/nf.py check 01_核心协议.md --policy <策略.json>
python scripts/nf.py check 01_核心协议.md --policy <策略.json> --json
```

## 判据（可证）

```bash
# 单测：两态可达 + warn 不改判定 + 坏策略全拒 + 摘要稳定
python -m unittest desktop.tests.test_check_policy          # 19 项全绿
```

## 边界

- **不是**政策编译器：不做法规**文本**的自动翻译（那要模型），也不做跨法域语义。做的是
  「人写结构化意图 → 封闭词表规则」的映射，且把表达不了的逐条挂账（见上面的意图编译器）。
- **不是**内容质量判定：它只判「你说的要求，这份对象满足了吗」，不判内容好不好。
- 单对象：跨文件的一致性（引用闭包、集合对账）不归这里，那类判据在 repository 级门禁。
