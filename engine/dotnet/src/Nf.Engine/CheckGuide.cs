namespace Nf.Engine;

/// <summary>
/// 复刻 <c>scripts/nf.py::CHECK_GUIDE</c>（41 波C C5）：check 编号 → 「缺什么 / 补什么」修复指引。
///
/// **本件是机械导出件，不是手抄**：由 <c>probes/_fixtures/_check_guide.json</c>（用 <c>ast.literal_eval</c>
/// 从 nf.py 直读，不做任何改写）生成，导出脚本与结果一并留档（同 <c>_doc_tables.cs.txt</c> 的口径）。
/// 表滞后于仓库的风险由**面级对账**兜住：<c>nf explain all</c> 一旦与 Python 不同就立刻显形——不自愈、不猜。
///
/// **为什么值得移植**：这是「门禁报红之后人该怎么办」的导航面（缺什么 / 补什么 / 示例），
/// 属只读判据面；引擎侧有它，第二道门报红时不必回头开 Python CLI 查指引。
/// </summary>
public static class CheckGuide
{
    private static readonly Dictionary<string, string> Guide = new(StringComparer.Ordinal)
    {
        ["1"] = "缺什么：官方核心目录结构件缺失（01/02/06/07/README/LICENSE + 官方管线 P00/P01/P90）。补什么：按 07 §7 项1 清单补齐根级文件与 03_管线库 官方管线。",
        ["10"] = "缺什么：EXT 闭合违约或社区红线未落地。补什么：EXT 实体闭合 + 红线条目对齐 07 §7 项2/8。",
        ["11"] = "缺什么：资产-模块三方对账不一致（02 §8.1 ↔ modules/ ↔ assets/README）。补什么：三方条目对齐（08 方案 T5 A5）。",
        ["12"] = "缺什么：desktop/src 或 scripts 语法/单测失败。补什么：跑 python -m unittest discover -s desktop/tests 修到全绿；示例：新模块未补测试→先写测试再实现。",
        ["13"] = "缺什么：02 头部与 registry.json 协议版本不一致或迁移记录不全。补什么：版本改动需 02 §9.3 四步（快照/bump/迁移说明/回读）。",
        ["14"] = "缺什么：社区协议登记缺 protocol.yaml/Schema 12 字段/登记三要件。补什么：01 §6.1 + 02 §8.3 补齐并保持 registry protocols[] 一致。",
        ["15"] = "缺什么：组合引用 references 违约（不在册/闭包未闭合/层冲突/schema 不兼容/双源不一致）。补什么：按 02 §8.4 五断言核对。",
        ["16"] = "缺什么：machine_contract 机读结构或装配 publish⊆subscribe 违约。补什么：01 §1.1 契约字段 + 运行时寻址授权一致。",
        ["17"] = "缺什么：质量门 unittest 失败。补什么：装配/锚点/资产悬空需过 quality_gate 语义。",
        ["18"] = "缺什么：导出契约 unittest 失败。补什么：ccv3_adapter/exporter 映射层检查锚点与条目。",
        ["19"] = "缺什么：导出产物 shape 与 schema 不符。补什么：对照 export_schema 5 格式自检。",
        ["2"] = "缺什么：重号 ID 未全限定（官方层裸号重复）。补什么：官方核心层模块引用一律全限定（通用:M10/事件:M22），07 §7 项5。",
        ["20"] = "缺什么：模块文档必填项缺失。补什么：按文档完整性清单补必填字段。",
        ["21"] = "缺什么：registry 引用图悬空/裸号重复。补什么：清理 source_package/module_id 引用。",
        ["22"] = "缺什么：导出物规范体检失败（spec_version/name/description 超限）。补什么：按 export_schema 硬约束修正。",
        ["23"] = "缺什么：资产供应链台账违约（不可溯源/不可发现/键孤儿）。补什么：05_资产库/provenance.json + 文件头双源一致。",
        ["24"] = "缺什么：模块状态位异常或 deprecated/retired 被引用。补什么：module deprecate/restore 流转或移除引用方。",
        ["25"] = "缺什么：01-36 编号方案文档签名不可复现/结构缺标题。补什么：文档须 UTF-8 且含 # 标题，同一内容重复生成须逐字节一致；示例：nf sig --verify。",
        ["26"] = "缺什么：语义矛盾（techdoc 链订阅事件无发布方 / 挂载点或类别漂移）。补什么：全库补发布方或修正漂移；示例：nf related 反查 + semantic_conflict.scan。",
        ["27"] = "缺什么：架构纯度违约（端壳残留/私货可变物/重复标题/raise 消息缺修复指引/第三方 import 未登记）。补什么：purity_scan 五规则逐条修；示例：R1 端壳关键词残留清理、R5 第三方 import 改软导入并在 SOFT_IMPORTS 登记理由。",
        ["28"] = "缺什么：协议层 IDL 违约（schema 定义缺失或协议件字段漂移）。补什么：protocol/schema 五定义在场 + 在场 machine_contract/管线/协议包/台账过 schema；示例：nf doctor 看 schema 在场。",
        ["29"] = "缺什么：Conformance 虚标或声明缺失（声明级别 > 可证级别）。补什么：按 01 §1.2 与 conformance_scan 提示降级或补证据。",
        ["3"] = "缺什么：五条不变式落点缺失或错位。补什么：核对 01 §5 ↔ 07 §7 项6 的逐条落点声明。",
        ["30"] = "缺什么：扩展判据缺失或版本字段 bump 无迁移记录。补什么：protocol/EXTENSION.md 判据 + bump 变更带 01 §7/02 §9.3 四步迁移记录。",
        ["31"] = "缺什么：生成物过期（protocol/generated 与当前 schema/协议件不一致）。补什么：重跑 protocol_golden.write_golden 并随变更一并提交。",
        ["32"] = "缺什么：质量纵深汇总违约（载荷注册表/资产 ledger/指令审计/资产密度·厚度·零引用/tool_face/world_model/world_slots 任一缺口）。补什么：跑 nf release 看细分失败项，修复后 verify 全绿；world_model 契约自查可用 nf worldmodel。",
        ["33"] = "缺什么：新面汇总任一子扫描红（MCP dual-era/stdio 帧纪律、attestation、基线回归评分、机械修复、正文 lint、编辑器面（能力/诊断定位/didClose/退出码/领域智能/配置生成）、许可证门、遥测 semconv、编码卫生、互操作导出与入仓面、文档命令面、决策层面、构建回路）。补什么：`nf doctor` 先定位，再按面跑 `nf interop --check` / `nf lint` / `nf score` / `nf telemetry` / `nf conformance`；编码卫生命中按 `docs/text-hygiene.md` 处置（隐形字符/行尾/重复键）。",
        ["34"] = "缺什么：云端图书馆面违约（frontmatter 真源缺字段、INDEX·ALIAS 投影漂移、生命周期状态越表、文档四型未覆盖、llms.txt 入口缺失、内容分级未声明）。补什么：`nf library verify` 看逐条失败；改条目 frontmatter 后 `nf library reindex` 重建投影（投影不是真源）。",
        ["35"] = "缺什么：深化面违约（管线抽象执行 GraphSpec、馆藏回执单根、模块边界冻结、内容绑定批准、一致性报告工件、无效语料）。补什么：按失败项分别跑 `nf pipeline dryrun --all` / `nf library receipts --write` / `nf module signature --write` / `nf approve --verify` / `nf conformance --write`。",
        ["36"] = "缺什么：治理面违约（一致性声明 CONFORMANCE、RFC 版本史、指令档机器面路由、实践包、跑分台、端点契约）。补什么：`nf conformance` 看契约面，并用 `nf rfc` / `nf driver` / `nf patterns verify` / `nf endpoint` 逐条对；改声明件后重跑。",
        ["37"] = "缺什么：双源知识层违约（权威分层、查询有序、时效、消化可追溯、认知裁剪越权）。补什么：`nf knowledge lint` 逐条看巡检结论（`nf knowledge order|visible` 可复核顺序与可见性；本子命令**没有** `--check`）；补 `protocol/knowledge_sources.json` 声明或消化记录后重跑（越权源不得进入任何 clearance 的查询顺序）。",
        ["38"] = "缺什么：出口自动化违约（自述数字与实算不一致、他证通道缺回填、GEO 出口过期、FDE 样例不过）。补什么：`nf stats --write` 重写生成区；`docs/standards/index.md` 与 `protocol/geo_export.json` 重渲染；FDE 样例跑 `python scripts/fde_sample_run.py` 看失败项。",
        ["39"] = "缺什么：端壳残留回潮 / 终端三件缺失 / 菜单指向死命令 / 命令面未策展 / 输出不确定。补什么：按 `docs/L3_FROZEN.md` 裁决删除残留件；`nf shell --verify` 看终端自检逐项失败；新增命令要登记进 `core/terminal.py` 的能力族。",
        ["40"] = "缺什么：数字资产契约违约（数据格式/字段完整性/输入输出一致性/防篡改；代码 AST 规范、可证空指针、测试用例在场；脚本 nf-io 头与声明双源不一致、链上 A 输出不匹配 B 输入）。补什么：`nf asset contract` 逐条看；数据件改声明或补字段；脚本补 `# nf-io: inputs=… outputs=…` 头并与 protocol/asset_contracts.json 对齐；sha256 漂移确认后用 `nf asset contract --freeze` 重冻。",
        ["41"] = "缺什么：构建隔离违约（构建入口出现取网/取包命令；Dockerfile 基座未按 @sha256 钉或写了 :latest；engines.node / engine/rust/Cargo.lock 缺位；CI 的 setup-python / setup-node 未给具体版本号）。补什么：先跑 core.build_isolation.scan 看逐条；构建入口改读仓内既有件、基座换成 name:tag@sha256:*、工具链把版本写死（不浮动 major）。",
        ["42"] = "缺什么：provenance 校验不过（回执单根形状坏 / 独立子进程验签失败 / 篡改未被检出）。补什么：nf receipts --scope protocol --write 重建单根；确认 nf attest --key-file 与 core.attest.verify 的口径一致；篡改必须被判否——否则这份证据是摆设。",
        ["4"] = "缺什么：认知边界断链（06 §4 管线 ↔ M23 认知域不一致）。补什么：对齐执行协议与 M23 的裁剪/过滤口径。",
        ["5"] = "缺什么：质检门流水线违约（M80 gate_action ↔ 06 §5）。补什么：核对输出生成器的 gate_action 三态与执行协议一致。",
        ["6"] = "缺什么：入口导航断链（README → 07 → 协议链/官方目录）。补什么：按 07 §7 项6 修 README 路由。",
        ["7"] = "缺什么：社区两包结构完整度违约。补什么：校园/西幻包 modules/pipelines/protocol.yaml/README 与 02 §8 在册数一致。",
        ["8"] = "缺什么：社区资产外形与基线不一致（文件数 / 行数 / 逐文件摘要）。补什么：核对内容后显式重签 `nf asset baseline --write`（07 §7 项3）。",
        ["9"] = "缺什么：模块-资产引用不可寻址或社区 README 重号未限定。补什么：资产键真实可寻址 + 社区重号限定引用。",
    };

    /// <summary>Python <c>CHECK_GUIDE.get(key)</c>（缺键 → null）。</summary>
    public static string? Get(string key) => Guide.TryGetValue(key, out var v) ? v : null;

    /// <summary>Python <c>sorted(CHECK_GUIDE)</c> 的键序（码点序，故 "10" 排在 "2" 之前）。</summary>
    public static List<string> SortedKeys() => Guide.Keys.OrderBy(k => k, StringComparer.Ordinal).ToList();

    /// <summary>条目数（供自检对账 nf.py 的表长）。</summary>
    public static int Count => Guide.Count;
}
