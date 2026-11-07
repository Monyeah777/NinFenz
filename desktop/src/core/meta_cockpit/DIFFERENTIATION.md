# 核心与差异化（可借鉴，但不可丢）

| 先例 | 借鉴 | 必须守住的差异 |
|---|---|---|
| Tree of Thoughts | 分支与自我检验 | 不做运行时全树搜索；每轮按 need 组小簇，搜索在设计时/原子层完成 |
| Graph of Thoughts | 图结构推理 | 图是类型化原子 DAG，不是自由文本思维节点；每条边有契约 |
| MoE / MoA | 路由与专家 | 专家是模型无关的方法原子，不是模型权重；不绑定任何厂商 |
| 提示词库 | 可复用文本 | 原子有触发/产出/失败模式/组合约束，不是静态 prompt |
| Agent 工作流 | 步骤编排 | 驾驶舱不排固定全程计划；need 变就改道，下一轮重读 state |
| 认知架构（SOAR/ACT-R） | object-level / meta-level | LLM 原生的原子菜单 + 单轮 JSON 协议 + NF 内容契约 |
| 有类型函数调用 / 提示签名 | 输入输出契约 | 契约由认知欠账实时编译，模型思想增量经义务闭包、事务与 journal 重放 |
| 任务分类器 / prompt router | 任务类型识别 | 画像只提供非排他 cognitive facets 与证据角色，不评分、不锁死方法，未知任务显式 general |
| RAG / context selector | 找出相关内容 | 额外报告证据角色就绪度与信任级别；scope/advisory 不得冒充可用内容证据 |
| Role-aware retrieval | 按意图补上下文 | 角色只重排已命中任务锚点的本地摘录，不凭泛词制造证据；matched_roles 与 trust 分离 |
| Candidate provenance | 候选重排 | 每个方法牌记录 anchor、repair、preference、function、resolved 与 kind；审计系统依据，不记录模型内心理由 |
| 候选重排 / reranking | 给候选排序 | 只用任务 facets、preferred atoms、状态增量和可靠性扩面；不生成质量分，不用 prompt 固定全程 |
| Agent scratchpad / memory | 记住过往步骤 | 只记已提交方法轨迹和认知状态签名；不存模型理由/CoT，状态环直接 fail-closed |
| Task-aware completeness | 按任务检查交付 | facets 映射到 artifact witness，缺 criteria/checks/example 等则继续编排，不以通用结构完成冒充任务完成 |
| Validation / schema gate | 检查字段合法 | 额外校验跨字段一致性：裁决链、选择来源、计划覆盖与证据绑定；不做质量排名 |
| Workflow output adapters | 为任务定制输出模板 | projection 直接取自已闭合的 witness/state，按任务形态输出机器与人可读结构，不改写内容 |
| Error / abstention handling | 返回失败或重试 | 区分布局预算、Deadline、策略阻塞、证据不足、可修复 facet/coherence、人工复核，并绑定 repair keys |
| Secret guard | 日志脱敏 | 对 prompt、注入、模型响应、thought_patch、state/handoff 递归检测高置信凭据；只报路径，不回显密文 |
| Offline blind A/B | 模型对比 | 同 prompt/model/seed 严格配对，评审包隐藏 arm/model/seed，报告配对胜率 CI、符号检验与 insufficient/inconclusive |
| Experiment bundle | 保存实验文件 | experiment/plan/packet/ballot/analysis 内容寻址联合封装，局部替换会被语义重算抓住 |
| 上下文工程 | 喂什么、何时喂 | 本层管「怎么想」；上下文工程管「喂什么」，互补 |
| 传统评测 | 质量门 | 评分/审计在外部，不驾驶思考；驾驶舱内无 score |

## 四十六条不可让渡的核心

1. 方法即契约：原子/节点必须可检查、可组合、可移植，不是提示词。
2. 活体重组：每轮按当前 need 选 1–3 原子，不做固定全程编排。
3. 义务而非评分：驾驶舱按 witness 是否闭合推进，不计算质量分。
4. NF 落地：输出必须能落到真实模块/资产/管线/质检，不是通用聊天。
5. 有界元认知：M0–M4、33 原子、自用深度 1、holdout 冻结、复杂度/证据比封顶。
6. 模型执行方法：模型不只选原子簇，还在所选契约内提交受限思想增量；系统
   只提交通过类型、范围、义务与重放校验的回合。
7. 任务形态可画像但不可殖民：比较、诊断、设计等画像只增加 facets 和证据
   角色；未知任务可 abstain，任何画像都不能替代通用义务或绑定特定域。
8. 证据角色有信任边界：角色就绪必须能落到真实来源、摘录 digest 或图边；
   scope、derived、external-advisory 与 local-content 不得混同。
9. 候选面服务认知而非排名：画像可改变当前可看到的通用方法候选，但不能
   锁定后续路径、暴露覆盖分或绕过原子契约与可靠性地板。
10. 方法记忆服务反振荡：历史只承载可核验的已提交方法与状态签名，不保存
    模型理由；重复认知状态不得再次提交或伪装成新一轮思考。
11. 任务完成必须有任务 witness：通用六 need 完成不等于比较、审计、解释等
    任务完成；关键 facets 未闭合时必须继续安全编排或显式留下缺口。
12. Facet witness 必须有形状：criteria 要有可判定字段，checks 要形成完整裁决
    链，风险要可复述；字段非空或空 audit 不能单独关闭任务义务。
13. 最终状态必须跨字段自洽：裁决与检查、选择与选项、计划与部件、验证与证据
    不允许互相矛盾；一致性通过不等于内容优秀。
14. 一致性必须是控制信号：会引入新冲突的候选与 patch 在提交前被过滤，
    不能把矛盾状态写入 journal 后再依赖最终检查补救。
15. 生产交接必须任务原生：比较矩阵、审计裁决、决策选项等不能在下游退化为
    同一份通用拆解模板；projection 只搬运已成立 witness，不二次编造内容。
16. 角色检索不得造证据：角色词只能在已命中任务锚点的候选行中调整优先级，
    不能用“风险/示例”等泛词凭空引入 grounding。
17. 停止与拒绝必须结构化：预算、Deadline、阻塞、证据、facet、coherence 与
    人工复核不能压成一个失败字符串；下游必须拿到 repair keys 和动作归属。
18. 凭据不得进入状态或日志：输入、模型响应、patch 与 handoff 的高置信凭据
    必须在对应边界 fail-closed，显式占位符除外。
19. 候选必须可解释：系统须记录每张牌为何出现及搜索边界，但不记录模型理由、
    不生成覆盖分；可解释性服务于审计，不变成新的评分通道。
20. 质量增量必须可证：引导组与基线组要同 prompt/model/seed 配对、盲化评审，
    并区分 significant / inconclusive / insufficient，不能靠单次样例自嗨。
21. 聚合不能掩盖分层：A/B 必须报告 per-model 结果与 judge agreement，重复
    ballot 拒绝；总体平均不得掩盖某模型退步或评审分裂。
22. 实验效度先于结果：配对两臂必须同 prompt、同 generation、同资源预算，
    截断/失败样本不得进入盲评；实验参数漂移一律拒绝。
23. 统计可信度也是门：judge 数量、评审一致率和每模型样本量不足时，只能返回
    insufficient-evidence 或 judge-disagreement。
24. 分析计划必须预注册：阈值与 prompt/model/seed 集合在盲评前绑定，禁止
    看到结果后改 alpha、effect floor 或样本门槛。
25. 样本量应按目标效应与 power 预估：声明 power 后 required pairs 成为硬门槛，
    underpowered 实验只能 insufficient-evidence。
26. 实验证据必须成包：计划、盲包、ballot 与分析用联合 digest 绑定，任一层
    局部替换都不能被当成同一实验继续使用。
27. 实验库必须内容寻址且读取重验：文件名绑定 bundle digest，重复保存幂等，
    损坏/篡改 bundle 不得进入索引。
28. 停止规则必须固定：planned_pairs 与实际配对数量一致，禁止看到显著性后
    提前停止或临时扩充样本。
29. 实验必须有稳定操作入口：preregister/packets/analyze/save/verify/index
    可脚本化、原子写、结构化错误，不要求操作者手写 Python。
30. 搜索性能必须可见且有界：候选 beam 的 expansions/generated/frontier 峰值
    进入 payload，超预算 fail-closed，不能靠“目前还快”维持延迟假设。
31. 核心配置必须 schema + cross-reference 双验：profile 的 facet、witness、
    meta atom 引用任何漂移都在加载期失败。
32. 恢复存储必须有资源上限：journal/store 读取与写出有字节/事件上限，超大或
    深层 JSON 在分配/重放前 fail-closed。
33. 实验输入也属于敏感边界：A/B prompt 在盲包与 bundle/store 之前必须通过
    secret guard，不能只保护模型输出。
34. 12 层架构反模式必须持续可测：运行模块无隐藏网络/模型调用、工具门在代码、
    历史有界、预算硬门、输出为来源投影，不靠人工记忆判断。
35. 版本绑定必须覆盖配置数据、加载代码与 schema：只改其中一层也必须使旧
    journal 恢复失效，不能出现数据旧、校验新或反之。
36. 文档常量必须与代码同测：候选、context、history、search、storage 和 A/B
    参数漂移必须让文档契约检查失败。
37. 配置语义引用必须闭合：context roles 必须存在于 role catalog，strong/weak
    triggers 不得重叠，未知角色或歧义触发在加载期失败。
38. Judge ballot 也必须强类型：只允许 pair/judge/winner/rationale，额外评分、
    非法 ID 或未知字段在分析前失败。
39. Ballot rationale 也是敏感输入：评审说明在分析和落盘前必须经过 secret
    guard，错误不得回显凭据。
40. 实验库审计不能静默漏项：损坏 bundle 必须出现在 invalid 报告及对应原因中，
    有效索引与异常清单同时可观测。
41. 发布必须可一次验证：machine/runtime/profile/contract、关键 schema、硬上限、
    能力与 HR 状态须收束为 content-addressed manifest。
42. 元策略需随机属性验证：profile/facet/coherence/projection 在随机合法与残缺
    状态下必须确定、可序列化、无评分且 section 契约稳定。
43. 静态质量覆盖必须完整：所有非 spike Python 模块进入 Ruff/Mypy，不能只测
    新模块而遗漏 runtime、元认知入口和辅助生成器。
44. 控制面复杂度必须受门：Ruff C901≤25，超限需拆分或对单一事务状态机写明确
    豁免理由；行为回归仍由所有协议测试兜底。
45. 复杂度必须多工具交叉：Ruff C901 通过不等于 Radon 低复杂度；纯逻辑热点
    仍须拆分并由随机属性/突变测试验证。
46. 复杂度豁免必须显式可审计：仅白名单中的事务/夹具热点可超 Radon 25，
    新增热点或陈旧豁免都会失败。
