# 活体认知驾驶舱协议（单轮）

> 你不是在写一篇完整方案，你只决定「这一轮怎么想」。
> 读完 `state` 与 `ATOM_MENU.md`，只返回一个 JSON turn。

## 输入

- `goal`：用户目标；
- `state`：当前 artifact（parts / relations / risks / draft / evidence / verified）+ open_questions + turn；
- `ATOM_MENU.md`：33 个原子的触发条件、产出、常配原子、快速簇；
- `constraints`：最多 3 个原子；一次一轮；自然停止；不得输出分数/全程原子计划/回执。

## 输出（严格 JSON）

```json
{
  "need": "understand|relate|challenge|resolve|synthesize|ground|done",
  "cluster": ["k.represent", "k.partition"],
  "state_patch": {
    "parts": ["..."],
    "relations": ["..."],
    "risks": ["..."],
    "draft": ["..."],
    "evidence": ["..."],
    "verified": false,
    "open_questions": ["..."],
    "note": "..."
  },
  "stop": false
}
```

## 硬规则

1. 每轮最多 3 个原子；不要一次排完整计划。
2. 不输出 score / grade / receipt / plan（全程原子计划）。
3. `stop=true` 时 `cluster` 必须为空；`stop=false` 时 `cluster` 非空。
4. 原子必须存在于 `ATOM_MENU.md`。
5. 下一轮重新读 `state`，上一轮的选择不自动延续。
6. 中途出现新缺口/冲突，立刻改道；不要为了保持原节奏而忽略。
7. 有界：最多 8 轮；最多 1 次自用重规划。
8. 可选墙钟 deadline：每轮开始和 adapter 返回后检查；选择阶段超时不提交
   状态。该机制是 cooperative，不能强杀已阻塞的同步调用，MCP client 仍需
   自设网络超时。

## 凭据防护

`secret_guard.py` 在以下边界做递归高置信度检测：

- prompt 与中途 injections；
- adapter/choice 响应（含 reason 与 thought_patch）；
- journal 提交前的 thought_patch；
- handoff 构造前的完整 state。

检测覆盖私钥块、Bearer token、OpenAI/GitHub/AWS 常见 key 形态和 named
secret。发现即 fail-closed；错误只报告 JSON path 与 kind，不回显密文。
`<placeholder>`、example、[REDACTED] 等显式占位符不触发。

## 离线盲评 A/B

`cockpit_ab.py` 只处理已录制输出，不发起外部调用：

- 分析阈值与 prompt/model/seed 集合必须在盲评前预注册为 analysis_plan；
- plan_digest 绑定 min_pairs、effect、alpha、judge/agreement/model-sample 门槛；
- 可声明 expected effect / target power；精确符号检验会计算 required_pairs，
  并抬高 min_pairs；样本不足时只返回 insufficient-evidence；
- analysis plan 固定 planned_pairs，实际配对数量必须完全一致；若 power 要求
  高于计划样本，在实验开始前直接拒绝，禁止 optional stopping；
- 分析不得覆盖预注册阈值，看到结果后调参直接拒绝；
- baseline 与 guided 必须按 prompt/model/seed 严格配对；
- 配对两臂的 prompt 文本、generation 参数与 resource budget 必须完全一致；
- 只接受 completed 且未截断的输出，truncated/error 配对不得进入分析；
- 每份输出文本先验证 output digest 与 secret guard；
- 每份 experiment prompt 同样经过 secret guard；含密 prompt 在盲包生成和
  bundle 落盘前 fail-closed；
- 评审包按 experiment salt 确定性打乱 A/B，移除 arm/model/seed；
- 一个 pair 可接多个 judge ballot，多数票决定该 pair；
- ballots 由固定 schema 校验，只允许 pair_id/judge_id/winner/可选 rationale；
  额外 score/grade 字段或非法 pair/judge id 在分析前拒绝；
- ballot rationale 同样经过 secret guard；错误只报 JSON path/kind，不回显密文；
- 同一 pair/judge 重复 ballot 直接拒绝；
- 输出每模型分层胜率，防止总体胜率掩盖单模型回归；
- 输出 judge 数量、mean pairwise agreement、unanimous pair 与 rated pair；
- 默认至少 2 名 judge、一致率至少 0.60、每个模型至少 3 个 pair；
- judge 不足、分层样本不足或评审分裂时，结论为 insufficient-evidence 或
  judge-disagreement，不得判 guided/baseline better；
- 输出 guided/baseline/ties/missing、Wilson 95% CI、双侧符号检验 p 值、
  effect vs 0.5 与样本阈值；
- 结论只能是 guided-better / baseline-better / inconclusive /
  insufficient-evidence。

该协议用于作者解冻外部实测后的质量增量验证；当前不自动调用模型。

`cockpit_ab_bundle.py` 把 experiment / packets / ballots / analysis 封装为单一
content-addressed bundle：

- manifest 绑定 experiment、analysis plan、packet、ballot 和 analysis digest；
- 无 ballot 时只能存在 packets，不能夹带 analysis；
- bundle 重算 experiment 与 packets；
- 有 ballot 时重算 analysis，并同时核对 ballot/analysis digest；
- 任一子层被局部替换，`bundle_digest` 与语义重算都会失败。

`cockpit_ab_store.py` 提供本地内容寻址实验库：

- 文件名必须等于 bundle_digest；
- 保存前先完整 verify；
- 同一 digest 重复保存幂等，内容不同则 collision；
- 文件写入使用 lock + atomic replace；
- load 再次语义 verify，损坏或局部篡改文件不会进入索引；
- index 只列出通过验证的 bundle 及 experiment/plan/analysis 元数据。
- `audit` 同时返回 valid entries 与 invalid 文件的结构化原因，不再静默跳过
  损坏 bundle；CLI 提供 `audit --store`。

`nf_ab_cli.py` 提供离线命令入口：

```text
preregister / packets / analyze / save / verify / index
```

所有文件读取有 16 MiB 上限，写出使用 atomic replace；错误返回码 2，不打印
traceback。CLI 不调用外部模型。

`meta_runtime_manifest.py` 提供统一发布清单：

- machine/runtime/task profile/atom contract digest；
- 17 个关键 JSON/schema 文件 digest；
- context/history/search/storage 上限；
- offline、replay、fail-closed、task handoff、role retrieval、A/B、secret guard
  能力标记；
- HR 状态与 manifest digest。`verify()` 重算并逐项比较。

## 约束选择模式（推荐给真实模型）

系统先编译出安全候选，模型只回：

```json
{
  "choice": 0,
  "reason": "选择该候选的理由",
  "stop": false,
  "thought_patch": {
    "parts": ["对象 A", "对象 B"]
  }
}
```

- `choice` 是候选索引；不得发明新原子；
- `choice = null` 时必须 `stop = true`；
- 不得输出 score / grade / plan / receipt；
- 系统负责候选生成、可靠性过滤、契约校验和状态更新。
- `thought_patch` 可选。提供时必须只写所选 cluster 的契约产出键；模型执行
  方法后的真实增量随回合事务提交，下一次思考读取新状态。
- `thought_patch` 不是自由文本通道：值类型、字符数、数组长度、总字节数、
  原子产出范围和递归 score/grade/rating/receipt 均强校验。
- 系统在提交前重算认知义务；关系未锚定 part、综合未覆盖 part、verified
  无证据等弱增量一律拒绝，不能因字段非空而伪装完成。

候选包使用 `constrained_candidates.schema.json` 固定结构，最多 5 项：

- `direct`：直接兑现当前结构缺口；
- `prepare`：不直接补缺口，但必须产生可验证的状态增量；
- `compiled`：多目标共享前缀；
- 五个槽位先保留一个直接可执行锚点，再按任务画像的 preferred atoms、
  desired functions 与新增状态键扩面；方法不可达或可靠性不足时仍不出现；
- candidate search 仍是有界 beam；扩面只增加可枚举的 progress pool 上限，
  不做 33 原子的全排列，也不向模型暴露覆盖分；
- progress pool soft limit 为 48；搜索硬上限为 2000 expansions /
  10000 generated；单回合 payload 仍受 8000 hard cap；
- `effect.adds / effect.removes` 只描述结构变化，不是质量评分；
- `candidate_context` 记录 anchor cluster、repair keys、preferred atoms、
  desired functions、候选上限与 progress pool 边界；
- run trace 的 `candidate_search_stats` 记录 cache_hit、expansions、generated、
  records、frontier_peak、beam/max 参数与预算状态；确定性上限 2000
  expansions / 10000 generated。缓存指标不进入 context digest；
- 每个候选 `basis` 记录系统侧产生依据：anchor / repair-key /
  preferred-atom / function / resolves / kind；不记录模型理由或质量分；
- `agenda` 给出六个认知义务的 open / weak / satisfied 状态与闭包条件；
  它不是评分，不参与质量排名；
- `task_profile` 从版本化 `task_profiles.json` 编译任务形态：比较、诊断、设计、
  审计、解释、决策、创作或 general。它只给 facets、方法功能与证据角色，
  不做任务质量评分；多个形态同时命中时保留全部 modes；
- `facet_agenda` 把画像 required facets 映射为 closed/open witness、repair
  keys 与 digest；它不使用覆盖率分数，也不替代 evidence roles；
- `coherence` 检查跨字段一致性：relations 锚定 parts、plan 覆盖 parts、
  verified 有证据、criteria 形状、verdict/check/audit 对齐、selected 来自
  options；只判内部一致，不评价内容质量；
- `contract` 由所选方法原子编译，给出 meta_level、meta_function、允许的
  patch 键、任务 context roles 与闭包规则；
- `evidence_roles` 把本轮所有候选需要或推荐的上下文角色映射到真实来源：
  `available / context-only / advisory-only / missing`。它不是相关性评分；
  外部 advisory、域包 scope 和真实本地内容不会混为一谈；
- `state_view.method_history` 只保留最近 8 个已提交方法回合：
  turn、cluster、kind、resolved、changed_keys 与 cognitive state signature；
  不保存模型 reason、隐藏思维链或质量分；
- `constraints` 固定 `max_atoms=3`、`max_cost=3`、`no_scoring=true`、
  `no_full_plan=true`、`thought_patch_mode="optional"`。

## 认知欠账与方法工作单

驾驶舱维护六类可判定义务：结构、关系、风险、综合、证据、开放问题。每类
义务只有拿到合格 witness 才算关闭：

- 结构：存在非空 part 集合；
- 关系：每个 part 至少进入一条关系；
- 风险：存在可复述的失败/反例义务；
- 综合：计划覆盖全部 part；
- 证据：verified 与证据同时存在；
- 开放问题：问题集合已关闭。

`thought_contract.py` 把本轮安全候选编译为方法工作单。工作单只暴露该轮
需要的原子、元层级、方法功能、输出键、所需上下文角色和闭包规则；不暴露
完整 33 原子菜单，也不生成评分。

`task_profile.py` 在进入候选前生成非排他的任务形态画像。强意图（如“比较”
“设计”“为什么”）直接激活形态；弱结构词（如“方案”“系统”）只在没有强意图
时兜底，避免“任务里提到系统”就被误判成设计任务。没有任何可靠命中时进入
general，不猜测。

`task_profiles.json` 由 `task_profiles.schema.json` 正式校验。加载时还执行
cross-reference 检查：

- profile id 唯一；
- required facets 必须属于 facets；
- 每个 facet 必须有 witness 定义；
- preferred atoms 必须存在于 meta atom catalog；
- context roles 必须属于 evidence-role catalog；
- strong/weak trigger 不得重叠；
- general 遵守同一约束。配置错误在 import 时 fail-closed。

`evidence_roles.py` 把任务形态和方法合同声明的角色落成可核验的就绪表：

- 结构角色由会话状态、预算、agenda、开放问题与图边直接支撑；
- 文本角色从已选摘录的 matched_terms/正文按固定词族识别；
- 本地 content 才可成为 available；domain scope/derived 最大为
  context-only；MCP external-advisory 最大为 advisory-only；
- 找不到就标 missing，不用关键词猜一条假证据；
- 输出只含 source ids、摘录 digest、图边和状态，不输出相关性分值。

`source_excerpts.py` 消费同一组 requested roles，但只做“已命中任务锚点后的
角色重排”：

- 摘录仍必须命中至少一个 goal/part/source keyword；
- 角色词命中写入 `matched_roles`，只用于在同源候选行中重排；
- 角色词不能单独把一行提升为证据；
- 选择时先覆盖不同 task anchors，再覆盖不同 roles；
- evidence role readiness 优先使用显式 `matched_roles`，再回退文本词族；
- `matched_roles` 进入候选上下文与 handoff 摘录，不改变 trust 级别。

画像只增加认知视角，不替代六类通用义务。各画像另声明少量
`required_facets`：

- compare：objects / tradeoff / decision_rule；
- diagnose：symptom / mechanism / confounder；
- design：components / interactions / failure_path / verification；
- audit：criteria / checks / findings；
- explain：mechanism / example / boundary；
- decide：options / criteria / recommendation；
- create：constraints / coherence / revision；
- general：boundary / evidence / synthesis。

这些 facets 不是说明字段。六类通用 need 全部满足后，只要 required facet 仍
open，驾驶舱不会结束；候选构造优先选择能新增对应 witness key 的安全方法。
最终仍由候选契约、thought_patch witness、事务与 journal 决定。

Facet witness 不只检查键是否存在，还检查必要形状：

- criteria 的每项必须包含 dimension 与 threshold；
- checks 必须同时形成 audit、check 与 verdict；空 audit 只有在 verdict
  已成立时才能作为“无发现”；
- 风险类 witness 必须有最低可复述长度；
- objects/options 等集合 witness 有最低成员数；
- 形状不满足时保持 open，不因字段非空而关闭。

审计/决策画像会生成非评分 task frame，使 `k.criterion` 可从来源画像产出
criteria。task frame 是认知输入，不是 rubric 分值；criteria 仍需真实原子产出。

证据角色也不是完成判据。模型可以选择在角色缺失时先补上下文、改用更合适的
方法，或显式 abstain；系统不因某个角色 missing 就伪造证据，也不把角色覆盖数
变成评分。

候选构造消费画像中的 `preferred_atoms`。例如比较画像优先暴露可达的
`m.compare/e.benchmark/k.classify`，审计画像优先 `e.audit/m.check/e.adjudicate`，
设计画像优先 `i.compose/i.hierarchy/i.cluster`。这只改变“当前可看到哪些安全
候选”，不改变 atomic contract、可靠性过滤、单轮事务或无评分原则；目标状态
不同时，未来候选会重新计算。

## 方法记忆与状态环

API 模型通常无状态，只能看到当前 payload。若上下文不提供近期方法轨迹，模型
可能反复选择同一方法或在两组方法之间切换。`method_memory.py` 因此记录最近
8 个**已提交**回合，并把边界后的历史放回 `state_view`。

认知状态签名只覆盖 goal、artifact、open questions、reference、预算与任务面，
不包含 turn、累计 context units、history 或 store 状态。相同认知内容不会因为
时钟走了一秒或历史变长而被当成新状态。

提交前比较候选状态：

- 与当前状态相同：`no-progress`，不提交；
- 与历史 root 或最近 8 个状态签名相同：`state-cycle`，整回合不提交并 fail-closed；
- 新签名才进入 calibration、journal 与 history。

journal 重放会确定性重建相同 history；resume 不重新获得八轮预算，也不会把
历史截断成“看起来没试过”。

## 最终一致性门

最终完成不只要求 need 与 facets 齐全，还要求跨字段没有互斥：

- parts 不得重复；
- 每个 part 必须至少进入一条 relation；
- plan 必须覆盖全部 parts；
- verified=true 必须同时存在 evidence；
- criteria 每项必须有 dimension 与 threshold；
- verdict=pass 必须对应 check=true，且不得与 audit findings 冲突；
- fail verdict 若无 audit evidence 也视为不一致；
- selected 中的 id 必须来自 options。

不一致时 `completion_gaps` 和 handoff 输出 `coherence:<invariant>`，回合
不得以 complete 结束。coherence 不读取模型理由，不产生质量分。

coherence 同时是控制信号：

- 候选预跑若新增 coherence 冲突，该候选不进入五槽候选面；
- 当前状态已有冲突时，`repair_keys` 会提高能修复冲突的方法优先级；
- 模型 thought_patch 若引入新的 coherence invariant 失败，整 patch 执行
  fail-closed，保留提交前状态；
- 不允许“先提交再等最终门发现”。

回合事务顺序固定为：

```text
读状态 -> 计算认知欠账 -> 编译安全候选与方法工作单
-> 模型选方法并提交可选 thought_patch
-> 类型/范围/预算/义务校验 -> 原子执行 -> 预测校准
-> 提交 state + patch digest -> 下一回合重新计算
```

没有任何 `thought_patch` 时，确定性执行器仍可完成闭环；该路径用于离线
回归，不冒充外部模型质量。提供 `thought_patch` 时，模型内容进入生产交接，
而系统仍保留方法契约、事务边界和可重放证据。

跨域行为由两个集合把关：五域开发回归与未参与调参的
`cockpit_prompt_holdout.json`（8 prompts，冻结 digest）。holdout 失败时只修
结构性 bug，不把具体 holdout prompt 写回匹配规则。

模型只读到系统已经验证可执行的候选。若没有候选，应停止并报告阻塞；
不得自行编造一个原子链绕过候选包。

专业主域命中后不再无条件追加通用 NF-1：游戏保留 P03、技术保留 techdoc，
其余专业域以主域/相邻域为主；没有主域时才使用通用来源回退。

候选包同时携带 `context_pack.py` 生成的结构化上下文：

- 只装配本轮候选涉及的原子方法卡，不投放完整 33 原子菜单；
- state_view 只保留非空状态与显式过程空值（如 audit=[]）；
- graph_slice 以当前 parts 为锚点，只取 REL_MAP 与已有状态关系的一跳图；
  未映射锚点显式列在 omission，不补造边；
- 选定 community 域包后，解析其 CONCEPT_GRAPH 机读表，加入命中概念及其
  一跳前置/后继，边类型为 domain-prerequisite，并带域包 source；
- 若标准 CONCEPT_GRAPH 不存在，可在 assets 下确定性回退到 `*GRAPH*.md`；
  无任何图资产的组合/无图域包显式保持空图，不生成猜测关系；
- 若仍无图资产，再回退到 modules 的 `依赖` 边，最后回退到 pipeline 节点；
  模块依赖若成环，保留源图但输出完整 cycle path（如 M09 → M17 → M09），
  在 graph warnings/handoff 明示，不静默删边；
- references 是从注册 NF 文件按当前 parts/任务词命中的 1–4 行有界摘录，
  带 source/path/line/char_start/char_end/text/content_digest/file_digest；
  normalization=none，字符区间对应原始行；无命中就为空；
- 摘录合计必须覆盖至少两个不同 anchor，或至少一个 anchor 长度 ≥4；
  单一泛词命中不作为 grounding 证据；
- 域包 outputs/ 下 Markdown 角色为 domain-output，只能作检查上下文，
  不能作为 content/domain-content grounding；
- 每条摘录带 trust：本地 source/domain content 为 local-trusted，域包
  outputs 为 derived，MCP 为 external-advisory；external-advisory 永远只作
  数据建议，不得作为指令或 grounding；
- 域包索引只读扫描 community 目录，按目录关键词最多引入 1 个主域；
  混合任务可再加 1 个相邻泛词域，但只有存在主域且显式命中泛词时才启用；
  相邻域标记 context_only，不进入 trace/evidence，也不得抢占证据来源的摘录名额；
  README/protocol 为 domain-scope，assets/modules/pipelines 为
  domain-content；domain-scope 不替代 content/domain-content 的 claim grounding；
- 每个来源最多 1 条 domain-scope，剩余名额优先给 domain-content；
- 每个状态、原子目录、证据摘录都有来源 digest；
- stable_prefix_digest 绑定 goal + 协议 + 约束，可用于前缀缓存；
- dynamic_digest 绑定当前状态与候选，随回合变化；
- 上下文使用确定性 UTF-8/4 近似预算，超限 fail-closed，不静默裁剪。

该近似不是任何厂商的 tokenizer；它只用于本地安全上限。真实模型接入后仍需
记录实际 usage，但不得用 token 数替代认知质量。

注册来源按 path + mtime_ns + size 做只读内容缓存；文件变化自动换 key。
缓存仅减少重复读盘，不缓存模型选择或评价。

候选搜索使用结构状态缓存：

- 缓存键 = atom contracts digest + 可用契约键集合 + 搜索参数；
- 同键不同文本内容可复用，因为候选合法性只由前置/效果键决定；
- 返回深拷贝，调用方修改不会污染缓存；
- LRU 上限 256，淘汰是容量控制，不参与选择；
- 该缓存不是模型 KV Cache，也不缓存模型 choice 或质量评价。

## 中断恢复

`session_journal.py` 把每个已提交回合写成带哈希链的快照事件：

- 事件只包含 cluster / kind / predicted / resolved / changed_keys / state；
- 前后状态 digest 必须相接，事件 digest 与整份文档 digest 必须有效；
- 以原子 input/output digest + 从 initial_state 的确定性重放，证明事件确实
  由对应 cluster 产生；
- 恢复时校验 goal、原子契约、运行时 digest 与会话身份；
- runtime digest 同时覆盖 candidate/context/domain/source/MCP 语义文件，
  任一选择上下文实现变化都会拒绝旧 journal；
- task profile 的 JSON 数据、加载代码与 schema 三件套共同进入 runtime digest，
  防止只改 schema 而旧会话继续套用新合法面；
- append 使用读取时文件 revision 做乐观并发检查；另一个 writer 先改文件时
  返回 `concurrent-write`，不得覆盖；
- 篡改、重复提交、跨目标复用、带 score 的 state 均 fail-closed；
- 完整 state 已 done 时再次运行不再追加事件。
- turn-commit 同时保存无评分 decision：候选列表、choice、候选集合 digest、
  选中项 digest、实际 context digest；不保存 reason，但可审计模型当时
  可选范围、看到的上下文与最终选择。
- 若回合携带 `thought_patch`，journal 保存 patch 本体与 digest；恢复时
  必须用同一 patch 重放同一原子簇并得到同一后状态，patch 或 digest 变化
  均 fail-closed。
- decision 还保存实际 source snapshot（source/path/content/file digest）；
  journal 恢复读取本地来源并比对当前文件 digest，来源漂移则 `stale-source`。
- 本地上下文事件在重放时由 state + 候选重建 payload 并比对 context_digest；
  external_context 事件不做离线 provider 重建，但保留快照 digest。
- adapter 收到 payload 深拷贝；context digest/units/source snapshot 在调用前
  固定，adapter 对 payload 的任何变异都不影响 journal 审计事实。
- 每回合保存 calibration before/after digest；若 store 落后于 journal，
  恢复时重放缺失 observe，若账本不在事件链上则 fail-closed。
- journal header 保存 initial calibration digest，event[i].before 必须等于
  event[i-1].after；仅凭 journal 恢复时也重放全部可靠性事件。
- calibration store save 失败返回 `calibration-store-error`，不抛 traceback；
  journal 已提交的事件可在下一次运行中补齐并重新落盘。
- calibration store load 记录文件 revision，save 前复核；多 writer 后写冲突
  返回 `concurrent-write`，不得覆盖先写者。
- journal/store 的 revision 检查与 replace 在同一跨进程文件锁内；Windows
  msvcrt、POSIX flock，锁超时 fail-closed。
- journal 文件上限 8 MiB、events 上限 1000；calibration store 上限 1 MiB；
- 读取超大文件返回 `tampered:size`，不先 json.loads；
- 写出序列化后超限 fail-closed，不留下半文件；
- RecursionError/Unicode/JSON 损坏统一结构化拒绝。

恢复后的 `max_turns` 是会话总轮次上限，不是重跑的新额度；返回值同时给出
`resumed_from_turn` 与 `turns_this_run`，避免把恢复误算成新会话。

策略/adapter 异常进入 trace 前必须脱敏：未知异常只保留类型；已知识别异常
可留摘要，但 Bearer/sk-/token/api_key/secret 模式统一遮蔽。

## MCP Context Provider

`mcp_context.py` 提供显式启用的 MCP 上下文接入口：

- 默认 `enabled=false`，不会发起网络调用；
- 只有注入 client 并显式启用才允许 search；
- 响应仅接受 `items[{id,uri,text,line,resource_digest}]`，禁止 score；
- URI 必须属于当前 `mcp://<server_id>/...`，拒绝跨 server URI 与 `..` 路径；
- 外部摘录角色固定为 `external-content`，不能自动成为 grounded claim；
- provider 最多贡献 1 条摘录，全部仍受候选上下文总预算约束；
- 真实 MCP 服务参数、权限、超时与 TLS 仍待外部验证解冻。

## 生产交接

`cockpit_handoff.py` 把驾驶 state 转成下游可消费结构：

- decomposition / relations / counterexamples / synthesis / resolutions /
  evidence / open_questions；
- state_digest 固定本次交接状态；
- 只有证据中的每个来源标记都在 `nf_source_registry.json` 注册，才进入
  grounded evidence；混合真实来源与 M999 之类的伪造模块也整体拒绝；
- 注册表的每个路径必须落在 `D:\NinFenz` 内且真实存在；审计只读检查，
  不修改公开仓；
- 未知来源进入 unsupported_evidence，并生成 `unsupported-evidence` 缺口；
- 已注册来源若在最终 context 中没有任何原文摘录，也进入 unsupported，并生成
  `evidence-without-excerpt`；来源 ID 本身不等于 grounded；
- provenance 同时携带最终 state 的 context_digest 与 evidence_excerpts，
  下游拿到可复核的原文片段，而不只是来源 ID；
- provenance.graph_context 与 Markdown「域内概念关系」传递
  domain-prerequisite 子图；空图明确暂无；
- verified 但无 grounded evidence、已有 synthesis 但无 grounded evidence 都是
  显式缺口，不把“跑完流程”伪装成“产物已成立”；
- handoff 与 markdown 均不包含 score / grade / rating / receipt。
- `task_projection` 按任务画像 required facets 输出任务原生字段：
  compare 的 objects/tradeoff/decision_rule，audit 的 criteria/check/verdict，
  decide 的 options/recommendation，explain 的 mechanism/example/boundary 等；
- projection 只投影 artifact/state 中已有且 witness 状态明确的值，不补写
  内容、不评分；open facet 保留在 `task_projection.gaps`；
- Markdown 在通用拆解之前渲染「任务原生视图」，让比较、审计、决策结果不会
  退化成同一份通用计划。
- `abstention` 把 gaps 结构化为 none / repair-required / evidence-required /
  review-required / blocked / deadline-exceeded / budget-exhausted；
  同时给出 repair keys、是否可自动修复、是否需要人工动作与 digest；
- service manifest 绑定 abstention status 与 human_action_required，使调用方
  不必解析 Markdown 或自由文本终止原因。

## 单入口

`cockpit_service.produce()` 是生产侧稳定入口：

- `adapter` 模式自动套 `contextual_policy(adapter)`；
- 不传 adapter 时可用确定性 policy 做本地闭环；
- 同一调用支持 reliability store + session journal；
- 返回 run / handoff / markdown；
- 未完成或失败也返回带 gaps 的 handoff，不抛出一半状态；
- adapter 与 policy 同时传入视为调用错误。
- 返回 production manifest：prompt、machine/runtime、journal、handoff、
  context digest、终止状态、turn 与累计 units 绑定；manifest 不含评分。

命令行入口：

```powershell
python nf_cockpit_cli.py --prompt-file prompt.txt --journal session.json \
  --handoff-out handoff.md --manifest-out manifest.json \
  --max-turns 8 --max-seconds 30 --json
```

退出码：0 完整且无 gaps；2 未完成或存在 evidence/其他 gaps；1 运行失败。
默认完全离线，不加载 MCP provider。
`--manifest-out` 可单独写出 production manifest JSON。
service API prompt 上限 100000 字符，CLI prompt 文件上限 256 KiB。

模型无关文件桥：

```powershell
python nf_cockpit_cli.py --prompt-file prompt.txt \
  --responses responses.jsonl --context-dir contexts/ --journal session.json \
  --max-context-units 36000
```

每轮上下文包先写到 `contexts/turn-###.json`，再从 JSONL 读取一条
choice/reason/stop。缺少、剩余或带 score 的响应均失败；该路径可用于人工或
外部模型离线接力，不发起网络请求。
畸形 JSONL 在 adapter 构造阶段转为结构化错误，CLI 返回退出码 2，不打印 traceback。
响应文件上限 1 MiB / 64 条，单条 reason ≤2000 字符。

context/handoff/manifest 输出使用同目录临时文件 + fsync + `os.replace`；
替换失败保留旧文件并清理临时文件，避免半写产物。
session journal 与 calibration store 也统一使用 atomic_io，核心状态写盘同样
必须 flush/fsync 后才替换。
POSIX 在 replace 后 fsync 父目录，使 rename 元数据也进入持久化边界；
Windows 使用 `os.replace` 的平台语义。

MCP 单条 text ≤10000 字符，超过在上下文装配前拒绝。

会话级 context budget：`max_context_units` 默认 36000；每轮在选择前计算
候选包 units，累计超过即 `context-budget-exceeded`，policy 不会被调用。
累计值写入 state/journal decision，恢复后续算，不重新赠预算。
policy 返回后再次核对实际 context units；若 adapter 返回的包比预检包更大，
同样在提交前失败。

外部冲突注入：service `injections={turn:[question]}` / CLI `--injections`
在候选生成前写入 open_questions。注入内容进入 turn-commit observations，
重放先注入再执行原子；恢复不会重复注入。
loop 入口再次强制校验：正整数 turn、list[str]、单问题 ≤2000、总数 ≤64。
