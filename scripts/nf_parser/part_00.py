"""命令面切片 part_00（自 nf.py::_make_parser 抽出；勿改顺序）。"""
from __future__ import annotations


def add_00(sub, ctx):
    st = sub.add_parser("stats",
 help="自述数字实算与生成（README/README.en/llms.txt 的 marker 区）",
                        description="出口自动化：README/README.en/llms.txt 的数字由产物实算生成，禁"
                            "止手改")
    st.add_argument("--write", action="store_true", help="重写生成区并落 protocol/repo_stats.json")
    st.add_argument("--check", action="store_true", help="只校验（生成区 == 实算）")
    st.add_argument("--json", action="store_true", help="打印机读结果")


def add_01(sub, ctx):
    fx = sub.add_parser("facts",
                        help="事实真源：生成/校验 protocol/facts.json（版本/许可/质量/规模/npm）",
                        description="SSOT：唯一机读事实产物 protocol/facts.json；--check 做逐字节比对"
                                    " + 跨源不变量 + 字面量禁区断言（历史 MIT 句单独放行）")
    fx.add_argument("--write", action="store_true", help="重写 facts.json 与受管事实面")
    fx.add_argument("--check", action="store_true", help="只校验（默认）")
    fx.add_argument("--json", action="store_true", help="打印机读结果")


def add_02(sub, ctx):
    run = sub.add_parser("run",
 help="跑全链管道：模块选择→装配→质检→导出",
 description="跑全链管道：模块选择→装配→质检→导出")
    run.add_argument("--pipeline", required=True,
                     help="管线 md 文件路径（如 community/校园西幻轻混组合包/pipelines/P04_轻混装配"
                         "流管线.md）")
    run.add_argument("--modules", required=True,
                     help="参与装配的模块 full_id，逗号分隔（如 通用类:M00,轻混类:M91）")
    run.add_argument("--store", default=None,
                     help="Store 工作区目录（缺省=临时，配合 --seed）")
    run.add_argument("--seed", action="store_true",
                     help="把 04_模块库官方核心 + community 组合包装载进 store（演示/自测）")
    run.add_argument("--fmt", default="md",
                     choices=["md", "ccv3", "skill", "agents", "claude", "mcp", "mvu"],
                     help="导出格式（缺省 md = 原生 Markdown 交付物；"
                          "ccv3/skill/agents/claude/mcp/mvu 按需显式选择）")
    run.add_argument("--doc-semantics", default=None,
                     choices=["project_rules", "skill"],
                     help="显式声明装配产物语义（v2.3.0 A3：project_rules → AGENTS/CLAUDE 出口；ski"
                         "ll → SKILL）——不传则回退 classify 启发式")
    run.add_argument("--dest", default=None, help="导出目录（缺省=store 根）")
    run.add_argument("--variant-add", default="",
                     help="变体增量模块 full_id（逗号分隔，v2.3.0 B2：经 apply_variant 并入 selecte"
                         "d）")
    run.add_argument("--variant-remove", default="",
                     help="变体移除模块 full_id（逗号分隔，从 selected 剔除；与 --variant-add 同用"
                         "时 remove 优先）")
    run.add_argument("--no-include-refs", action="store_true",
                     help="不并入 E3 references 跨包模块（默认并入）")
    run.add_argument("--force-export", action="store_true",
                     help="质量门 FAIL 也导出（诊断用；ok 仍 False）")


def add_03(sub, ctx):
    reg = sub.add_parser("register",
                         help="协议登记本地助手（B3-B：protocol.yaml → registry protocols[]）",
 description="协议登记本地助手（B3-B：protocol.yaml → registry protocols[]）")
    reg.add_argument("pkg_dir", help="包目录（如 community/校园西幻轻混组合包）")
    reg.add_argument("--check", dest="mode", action="store_const", const="check",
                     help="只校验三要件 + 打印投影 diff（缺省，不写盘）")
    reg.add_argument("--apply", dest="mode", action="store_const", const="apply",
                     help="校验全过后合并写 registry.json protocols[]（只增不删）")
    reg.add_argument("--registry", default=None,
                     help="registry.json 路径（缺省 = desktop/src/core/registry.json）")
    reg.set_defaults(mode="check")


def add_04(sub, ctx):
    rgi = sub.add_parser("registry",
                         help="契约注册表内容寻址（CID）：registry_index.json 生成/校验（T8.2）",
 description="契约注册表内容寻址（T8.2）：每包 canonical manifest 的 SHA-256（CID）+ 顶层 root；"
             "只读扫描、不改各包；本版不含签名（sig 留空，只做内容寻址与篡改检测）")
    rgis = rgi.add_subparsers(dest="registry_cmd", required=True)
    rgx = rgis.add_parser("index",
                          help="生成/校验 protocol/registry_index.json（schema nf-registry-index/1）",
 description="--write 生成索引；--check 与实时重算比对（文件级差异：索引行号 + 包内路径）；"
             "--json 机读（kind=registry-index）")
    rgx.add_argument("--write", action="store_true", help="重写 protocol/registry_index.json")
    rgx.add_argument("--check", action="store_true", help="只校验（默认）")
    rgx.add_argument("--json", action="store_true", help="打印机读结果")


def add_05(sub, ctx):
    mkt = sub.add_parser("market",
                         help="市场协议查询（B4：依赖闭包 + 挂载冲突预检；list 目录视图）",
 description="市场协议查询（B4：依赖闭包 + 挂载冲突预检；list 目录视图）")
    mkt.add_argument("pkg_dir", nargs="?", default=None,
                     help="包目录（如 community/校园西幻轻混组合包）；缺省 + --list 列目录")
    mkt.add_argument("--list", action="store_true",
                     help="列市场目录（官方核心 + 社区包，各带分级徽章）")
    mkt.add_argument("--json", action="store_true",
                     help="输出结构化 JSON（目录 / 包视图）")
    mkt.add_argument("--tier", default=None,
                     choices=["official", "community", "experimental"],
                     help="按分级筛选（v2.5.0 Wave3：官方/社区/实验）")
    mkt.add_argument("--registry", default=None,
                     help="registry.json 路径（缺省 = desktop/src/core/registry.json）")


def add_06(sub, ctx):
    spc = sub.add_parser("spec",
                         help="Spec Registry 查询（v2.5.0 Wave3）+ 契约语义可判定（T7.1/T10.1）",
 description="Spec Registry 查询（v2.5.0 Wave3：版本化 spec 查询）；T7.1 契约语义核心："
             "`nf spec check --core [--json]`（五概念模型 + W1/W2/W3）与 "
             "`nf spec canonical [--json]`（registry 子集规范形 SHA256，幂等）；"
             "T10.1 形式化模型检查：`nf spec modelcheck [--json] [--max-states N]`"
             "（world_model 相位图 BFS：可达性/确定性/不变式/死锁/槽位）")
    spc.add_argument("action", nargs="?", default="ls",
                     choices=["ls", "check", "canonical", "modelcheck"],
                     help="动作：ls 列 spec 版本清单 / check 契约语义三规则 / canonical 规范形摘要 / "
                          "modelcheck world_model 有限状态检查")
    spc.add_argument("--core", action="store_true",
                     help="check 的语义核心范围 = 官方核心 + 包登记面（本轮仅实现 --core）")
    spc.add_argument("--json", action="store_true", help="结构化 JSON 输出")
    spc.add_argument("--max-states", dest="max_states", type=int, default=None,
                     metavar="N",
                     help="modelcheck 的 BFS 状态上限（缺省 256；超限 exit 2 不假装通过）")
    spc.add_argument("--registry", default=None,
                     help="registry.json 路径（缺省 = desktop/src/core/registry.json）")


def add_07(sub, ctx):
    rnd = sub.add_parser("render",
                         help="协议多出口渲染（A3：protocol.yaml → agents/claude/skill rules）",
 description="协议多出口渲染（A3：protocol.yaml → agents/claude/skill rules）")
    rnd.add_argument("pkg_dir", help="包目录（如 community/技术文档域包）")
    rnd.add_argument("--fmt", default="agents", choices=["agents", "claude", "skill"],
                     help="目标格式（agents/claude/skill）")
    rnd.add_argument("--dest", default=None, help="输出目录（缺省=当前目录）")


def add_08(sub, ctx):
    srv = sub.add_parser("serve",
                         help="MCP 运行时服务（C1：mcp.json 快照或实时仓库面 → stdio JSON-RPC，供 M"
                             "CP client 拉起）",
 description="MCP 运行时服务（C1：mcp.json 快照或实时仓库面 → stdio JSON-RPC，供 MCP client 拉起）")
    srv.add_argument("snapshot", nargs="?", default=None,
                     help="mcp.json 快照路径（如 nf run --fmt mcp 产物）；"
                          "缺省 = 实时仓库面（无需先产快照，默认路径直起）")


def add_09(sub, ctx):
    dsn = sub.add_parser("design",
                         help="决策辅助工具族（v2.6-A：可选装载——钢人论证工作单）",
 description="决策辅助工具族（v2.6-A：可选装载——钢人论证工作单）")
    dsub = dsn.add_subparsers(dest="design_cmd", required=True)
    stl = dsub.add_parser("steelman",
                          help="钢人论证工作单：init/--check/ls（默认缺席，按需自检）",
 description="钢人论证工作单：init/--check/ls（默认缺席，按需自检）")
    stl.add_argument("action", nargs="?", default="ls",
                     choices=["init", "ls"],
                     help="动作（init 生成工作单 / ls 列决策档案索引；缺省 ls）")
    stl.add_argument("question", nargs="?",
                     help="init：问题描述（引号包裹，如 \"是否立项？\"）")
    stl.add_argument("--context", default="",
                     help="init：context 字段（方案号/域包名/触发场景）")
    stl.add_argument("--decider", default="",
                     help="init：decider 字段（决策人，缺省留空待填）")
    stl.add_argument("--out", default=None,
                     help="init：输出路径（缺省 = 当前目录 steelman.md）")
    stl.add_argument("--check", dest="check_file", metavar="FILE",
                     help="check：结构自检指定 steelman.md（输出缺项 warn）")
    stl.add_argument("--root", default=".",
                     help="ls：扫描目录（缺省 = 当前目录）")
    aud = dsub.add_parser("audit",
                          help="协议设计审计（M_AUDIT：决策过程质量——钢人/blindspot/full）",
 description="协议设计审计（M_AUDIT：决策过程质量——钢人/blindspot/full）")
    aud.add_argument("action", nargs="?", default="ls",
                     choices=["init", "ls"],
                     help="动作（init 生成 audit.md / ls 列审计索引；缺省 ls）")
    aud.add_argument("question", nargs="?",
                     help="init：审计问题描述（引号包裹）")
    aud.add_argument("--target", default="",
                     help="init：被审计对象（方案/决策/协议设计引用）")
    aud.add_argument("--mode", default="full",
                     choices=["steelman", "blindspot", "full"],
                     help="审计模式（默认 full：钢人 + 双盲区 + 结论 + 行动）")
    aud.add_argument("--context", default="",
                     help="init：related 字段（关联方案文档）")
    aud.add_argument("--out", default=None,
                     help="init：输出路径（缺省 = 当前目录 audit.md）")
    aud.add_argument("--check", dest="check_file", metavar="FILE",
                     help="check：结构自检指定 audit.md（缺文件返回提示非红）")
    aud.add_argument("--root", default=".",
                     help="ls：扫描目录（缺省 = 当前目录）")


def add_10(sub, ctx):
    whr = sub.add_parser("who-refers",
                         help="引用反查（A2：谁引用了某模块，遍历 registry references）",
 description="引用反查（A2：谁引用了某模块，遍历 registry references）")
    whr.add_argument("module_id", help="模块 id（如 M91 或 情感:M55）")
    whr.add_argument("--registry", default=None,
                     help="registry.json 路径（缺省 = desktop/src/core/registry.json）")


def add_11(sub, ctx):
    imp = sub.add_parser("impact",
                         help="变更影响面预检（A4 前置：拟删除 module/protocol 前查破坏性影响）",
 description="变更影响面预检（A4 前置：拟删除 module/protocol 前查破坏性影响）")
    imp.add_argument("target",
 help="目标（protocol id 如 校园情感领域包，或 module id 如 M55 / 情感:M55）")
    imp.add_argument("--check", dest="mode", action="store_const", const="check",
                     help="门禁模式：破坏性变更（有引用方/官方在册）exit 1，无破坏 exit 0")
    imp.add_argument("--registry", default=None,
                     help="registry.json 路径（缺省 = desktop/src/core/registry.json）")


def add_12(sub, ctx):
    ren = sub.add_parser("rename",
                         help="模块改名引用重链（A5：references 中引用该模块的条目批量更新）",
 description="模块改名引用重链（A5：references 中引用该模块的条目批量更新）")
    ren.add_argument("old_id", help="旧模块 id（如 M55 或 情感:M55）")
    ren.add_argument("new_id", help="新模块 id（如 M99 或 情感:M99）")
    ren.add_argument("--check", dest="mode", action="store_const", const="check",
                     help="只列受影响引用清单不写盘（缺省）")
    ren.add_argument("--apply", dest="mode", action="store_const", const="apply",
                     help="批量重链 references 后合并写 registry protocols[]（只改引用不改其它）")
    ren.add_argument("--registry", default=None,
                     help="registry.json 路径（缺省 = desktop/src/core/registry.json）")


def add_13(sub, ctx):
    imp2 = sub.add_parser("import",
                          help="读入外部产物（SKILL.md/chara.json；docx/dita → 内容 IR）→ parse"
                               " + 可选内容库登记（A4 遗留闭环；T9.2 导入面）",
                          description="读入外部产物：`nf import <SKILL.md|chara.json>`（旧面）；"
                                      "`nf import docx <file> [--json/--out]`、`nf import dita "
                                      "<file> [--json/--out]`（T9.2：DOCX/DITA → 内容 IR）")
    imp2.add_argument("file", nargs="+",
                      help="外部产物文件；或 `docx|dita <file>`（T9.2 导入器）")
    imp2.add_argument("--register", action="store_true",
                      help="解析出的 IR 模块幂等装载进 Store 内容库（save_module 覆盖式幂等；"
                           "仅旧面 SKILL/chara 支持）")
    imp2.add_argument("--store", default=None,
                      help="Store 工作区目录（缺省=临时）")
    imp2.add_argument("--json", action="store_true",
                      help="机器面：导入结果 JSON（docx/dita 含 stats/warnings；旧面含模块数）")
    imp2.add_argument("--out", default="",
                      help="把导入产物写成规范形 Markdown 到该路径（docx/dita；相对路径按仓库根）")


def add_14(sub, ctx):
    glp = sub.add_parser("glossary",
                         help="英文术语层（Terminology layer：zh/en 双语定义 + 真实协议锚点）",
                         description="英文术语层（T12.2）：protocol/glossary.json 的 entries "
                                     "逐条给出 zh/en/双语定义/category 与**真实锚点**"
                                     "（file + section/keyword，禁假行号）；check 校验 schema/"
                                     "唯一性/锚点/必含清单；render 生成 docs/protocol/"
                                     "glossary.en.md（同源、确定性，非全文翻译）")
    glsub = glp.add_subparsers(dest="glossary_cmd")
    gl_ck = glsub.add_parser("check", help="术语层校验（失败非零）",
                             description="校验 schema/术语唯一/锚点真实/必含术语清单齐全；"
                                         "任一不过即非零退出")
    gl_ck.add_argument("--json", action="store_true", help="输出结构化 JSON 报告")
    gl_rd = glsub.add_parser("render", help="从同一数据渲染英文术语表（人读件）",
                             description="按 category 分组渲染 docs/protocol/glossary.en.md"
                                         "（同输入同字节；禁止手改生成件）")
    gl_rd.add_argument("--out", default="docs/protocol/glossary.en.md",
                       help="落点（缺省 docs/protocol/glossary.en.md；相对路径按仓库根）")


def add_15(sub, ctx):
    ROOT = ctx.root
    ast = sub.add_parser("asset",
                         help="资产供应链台账（S2：add 入库 / verify 闭合 / inventory 盘点 / ls 浏"
                             "览 / rm 摘除 / deprecate·restore 流转）",
 description="资产供应链台账（S2：add 入库 / verify 闭合 / inventory 盘点 / ls 浏览 / rm 摘除 / dep"
     "recate·restore 流转）")
    asub = ast.add_subparsers(dest="asset_cmd", required=True)
    a_add = asub.add_parser("add",
                            help="入库资产：资产文件头写 nf-asset 头 + 台账 append（溯源键表自动生"
                                "成）",
 description="入库资产：资产文件头写 nf-asset 头 + 台账 append（溯源键表自动生成）")
    a_add.add_argument("file", help="资产文件路径（相对 --root，如 用户自定义/TECH_RULES.md）")
    a_add.add_argument("--key", required=True, help="溯源键（台账内唯一，键无孤儿前提）")
    a_add.add_argument("--source", required=True,
                       help="溯源说明（源文件/区间/登记日期——每资产必须可溯源）")
    a_add.add_argument("--root", default=None,
                       help="资产根目录 = 台账所在目录（如 05_资产库；add 必填）")
    a_add.add_argument("--module", default="", help="消费模块 id（如 M90/M93/M96，可空）")
    a_add.add_argument("--version", default="1.0", help="资产版本位（默认 1.0）")
    a_add.add_argument("--status", default="active",
                       choices=("active", "deprecated", "retired"))
    a_add.add_argument("--tier", default=None,
                       choices=("official", "community", "experimental"),
                       help="货架分级（首次建档落台账级；缺省 official）")
    a_add.add_argument("--package", default="", help="归属包名（台账级，如 官方核心资产集）")
    a_vrf = asub.add_parser("verify",
 help="台账闭合校验（与 verify.sh check23 同语义）",
 description="台账闭合校验（与 verify.sh check23 同语义）")
    a_vrf.add_argument("--root", default=ROOT, help="扫描根（缺省=仓库根）")
    a_bl = asub.add_parser("baseline",
                           help="社区资产行数基线（可重签工件；漂移即 FAIL 直到显式重签）",
                           description="社区资产行数基线（机制对齐 module signature：外形冻结、内容"
                               "演进须显式重签）")
    a_bl.add_argument("--write", action="store_true", help="重新冻结基线（评审后显式重签）")
    a_bl.add_argument("--root", default=ROOT, help="扫描根（缺省=仓库根）")
    a_inv = asub.add_parser("inventory",
 help="库存盘点（台账摘要 + 未托管/孤儿统计）",
 description="库存盘点（台账摘要 + 未托管/孤儿统计）")
    a_inv.add_argument("--root", default=ROOT, help="扫描根（缺省=仓库根）")
    a_inv.add_argument("--json", action="store_true",
                       help="输出结构化 JSON（盘点行）")
    a_ls = asub.add_parser("ls",
 help="货架浏览（--pkg / --tier / --status 过滤）",
 description="货架浏览（--pkg / --tier / --status 过滤）")
    a_ls.add_argument("--root", default=ROOT, help="扫描根（缺省=仓库根）")
    a_ls.add_argument("--json", action="store_true",
                      help="输出结构化 JSON（货架条目）")
    a_dns = asub.add_parser("density",
                            help="资产键语义密度体检（45：键数/字符/无键与空档统计）",
 description="资产键语义密度体检（45：键数/字符/无键与空档统计）")
    a_dns.add_argument("--root", default=ROOT, help="扫描根（缺省=仓库根）")
    a_dns.add_argument("--json", action="store_true",
                       help="输出结构化 JSON（密度统计）")
    a_use = asub.add_parser("usage",
                            help="资产引用度体检（45：键在 04/community/docs 全语料引用次数/零引用"
                                "清单）",
 description="资产引用度体检（45：键在 04/community/docs 全语料引用次数/零引用清单）")
    a_use.add_argument("--root", default=ROOT, help="扫描根（缺省=仓库根）")
    a_use.add_argument("--json", action="store_true",
                       help="输出结构化 JSON（引用度统计）")
    a_use.add_argument("--strict", action="store_true",
                       help="零引用键存在即 exit 1（键消费证明进门禁）")
    a_thk = asub.add_parser("thickness",
                            help="资产语义厚度体检（45：字符/键/小节/表格 + 低信息档候选）",
 description="资产语义厚度体检（45：字符/键/小节/表格 + 低信息档候选）")
    a_thk.add_argument("--root", default=ROOT, help="扫描根（缺省=仓库根）")
    a_thk.add_argument("--json", action="store_true",
                       help="输出结构化 JSON（厚度统计）")
    a_led = asub.add_parser("ledger",
                            help="资产键表机读投影（45：protocol/community_asset_ledger.json；--ref"
                                "resh 重生成）",
 description="资产键表机读投影（45：protocol/community_asset_ledger.json；--refresh 重生成）")
    a_led.add_argument("--root", default=ROOT, help="扫描根（缺省=仓库根）")
    a_led.add_argument("--refresh", action="store_true",
                       help="重生成 ledger 文件（随资产变更提交）")
    a_led.add_argument("--json", action="store_true",
                       help="输出结构化 JSON（校验统计）")
    a_ctr = asub.add_parser("contract",
                            help="数字资产契约四面校验（数据/代码/脚本/包清单：格式+字段完整性+"
                                "防篡改+AST 规范+可证空指针+脚本 I/O 对齐+包自述对账）",
                            description="数字资产契约四面校验（真源 protocol/asset_contracts.json；"
                                "与 verify check40 同源）")
    a_ctr.add_argument("--root", default=ROOT, help="扫描根（缺省=仓库根）")
    a_ctr.add_argument("--face", default="", choices=("", "data", "code", "script", "index"),
                       help="只跑某面（缺省=四面全跑：数据/代码/脚本/包清单）")
    a_ctr.add_argument("--export", action="store_true",
                       help="导出 Frictionless Data Package（protocol/generated/asset_contract.frictionless.json）")
    a_ctr.add_argument("--freeze", action="store_true",
                       help="按当前内容重冻声明的 sha256（显式棘轮，不由扫描器偷偷写）")
    a_ctr.add_argument("--run-tests", action="store_true",
                       help="跑声明的测试件（显式开启；默认门禁不执行被声明代码）")
    a_ctr.add_argument("--json", action="store_true", help="输出结构化 JSON")
    a_ls.add_argument("--pkg", default="", help="台账 package 过滤")
    a_ls.add_argument("--tier", default="",
                      choices=("official", "community", "experimental"))
    a_ls.add_argument("--status", default="",
                      choices=("active", "deprecated", "retired"))
    for _name, _desc in (("rm", "从台账摘除条目（不删资产文件，残留头由 check23 报孤儿）"),
                         ("deprecate", "状态流转 → deprecated"),
                         ("restore", "状态流转 → active（deprecated 回退）")):
        _sp = asub.add_parser(_name, help=_desc)
        _sp.description = _desc
        _sp.add_argument("--ledger", required=True,
                         help="provenance.json 路径（如 05_资产库/provenance.json）")
        _sp.add_argument("--key", required=True, help="溯源键")


def add_16(sub, ctx):
    pln = sub.add_parser("pipeline",
                         help="管线脚手架（v2.8 波B S4：pipeline new——自 P00 骨架派生新管线）",
 description="管线脚手架（v2.8 波B S4：pipeline new——自 P00 骨架派生新管线）")
    psub = pln.add_subparsers(dest="pipeline_cmd", required=True)
    p_new = psub.add_parser("new",
 help="派生新管线：复制模板 → 改 id/name/领域标签（登记 02 / 填层名挂载按 README 三步）",
 description="派生新管线：复制模板 → 改 id/name/领域标签（登记 02 / 填层名挂载按 README 三步）")
    p_dry = psub.add_parser("dryrun",
                            help="管线抽象执行（不调模型跑一遍声明 → 执行图；hard 缺陷 + advisory "
                                "分列）",
                            description="管线抽象执行（内部差距：静态 check 只能答『声明自洽吗』，"
                                "答不了『跑得通吗』）")
    p_dry.add_argument("--pipeline", default="", help="管线 md 路径（缺省 + --all 时全仓扫）")
    p_dry.add_argument("--all", action="store_true", help="全仓管线扫一遍并汇总")
    p_dry.add_argument("--json", action="store_true", help="输出执行图 JSON")
    p_dry.add_argument("--write-advisory", action="store_true",
                       help="配合 --all：把 advisory 分类台账写入 protocol/pipeline_advisory.json")
    p_new.add_argument("--id", required=True, help="新管线 id（如 P07）")
    p_new.add_argument("--name", required=True, help="新管线显示名（如 演示领域管线）")
    p_new.add_argument("--from", dest="template", default=None,
                       help="模板管线 md（缺省 = 03_管线库/P00_通用文档生成管线.md）")
    p_new.add_argument("--domain", default="",
                       help="领域标签（如 悬疑 → tags 追加「悬疑领域」）")
    p_new.add_argument("--dest", default="",
                       help="输出 md 路径（缺省 = 03_管线库/<id>_<name>.md 官方管线位）")


def add_17(sub, ctx):
    ROOT = ctx.root
    mds = sub.add_parser("module",
                         help="模块生命周期（v2.8 波B S5：status 位 + deprecate/restore + 引用门禁 "
                             "verify）",
 description="模块生命周期（v2.8 波B S5：status 位 + deprecate/restore + 引用门禁 verify）")
    msub = mds.add_subparsers(dest="module_cmd", required=True)
    m_ls = msub.add_parser("ls",
 help="浏览模块状态（--status 过滤；缺省全量）",
 description="浏览模块状态（--status 过滤；缺省全量）")
    m_ls.add_argument("--status", default="", choices=("active", "deprecated", "retired"))
    m_ls.add_argument("--root", default=ROOT, help="扫描根（缺省 = 仓库根）")
    m_ls.add_argument("--json", action="store_true",
                      help="输出结构化 JSON（模块状态清单）")
    m_st = msub.add_parser("status",
 help="查看单个模块文件状态位",
 description="查看单个模块文件状态位")
    m_st.add_argument("file", help="模块 md 路径（如 community/<包>/modules/Mxx_….md）")
    m_dp = msub.add_parser("deprecate",
 help="状态流转 → deprecated（写文件元信息行状态位）",
 description="状态流转 → deprecated（写文件元信息行状态位）")
    m_dp.add_argument("file", help="模块 md 路径")
    m_dp.add_argument("--reason", default="", help="弃用原因（写入状态位）")
    m_rs = msub.add_parser("restore",
 help="状态流转 → active（deprecated/retired 回退）",
 description="状态流转 → active（deprecated/retired 回退）")
    m_rs.add_argument("file", help="模块 md 路径")
    m_vf = msub.add_parser("verify",
 help="引用门禁扫描（与 verify.sh check24 同语义）",
 description="引用门禁扫描（与 verify.sh check24 同语义）")
    m_sg = msub.add_parser("signature",
                           help="模块边界签名基线（边界写一次；漂移即 FAIL 直到重签）",
                           description="模块边界签名基线（机制借鉴 Pipelex signature_for：边界冻结"
                               "、实现可替）")
    m_sg.add_argument("--write", action="store_true",
                      help="重新冻结边界基线（评审后显式重签）")
    m_sg.add_argument("--json", action="store_true", help="输出结构化 JSON")
    m_ty = msub.add_parser("types",
                           help="I/O 类型面（io_types）：覆盖率 + 可证不匹配；--write 补标",
                           description="I/O 类型面（机制借鉴 Pipelex typed concepts，01 §7 V1 字段"
                               "级新增）")
    m_ty.add_argument("--write", action="store_true",
                      help="给全部有机读契约的模块补 io_types（确定性推导，未命中写 untyped）")
    m_ty.add_argument("--json", action="store_true", help="输出结构化 JSON")
    m_ty.add_argument("--harvest", action="store_true",
                      help="从模块正文事件契约收割载荷字段（并入 event_registry）")
    m_ty.add_argument("--backlog", action="store_true",
                      help="生成/校验类型积压台账（不可推断的 untyped 显式化）")
    m_ct = msub.add_parser("contract",
                           help="L0 → L1 机读块 retro-fit（从人读引用块/正文投影，不编造）",
                           description="L0 → L1 机读块 retro-fit（机制借鉴 Pipelex：机读块 = 人读契"
                               "约的结构化投影）")
    m_ct.add_argument("--write", action="store_true", help="写入机读块（幂等；已有机读块则跳过）")
    m_ct.add_argument("--json", action="store_true", help="输出结构化 JSON")
    m_vf.add_argument("--root", default=ROOT, help="扫描根（缺省 = 仓库根）")


def add_18(sub, ctx):
    dm = sub.add_parser("demo",
                        help="一键交付物演示（默认 P06 技术文档全链 → Markdown；"
                             "`demo narrative` = P04 轻混 → CCV3 导出）",
 description="一键交付物演示（T3.1：默认 P06 技术文档全链 → 可交付 Markdown；"
             "叙事域用 `nf demo narrative` = P04 轻混 → CCV3）")
    dm.add_argument("mode", nargs="?", choices=("techdoc", "narrative"), default="techdoc",
                    help="演示域（缺省 techdoc = 技术文档 P06→Markdown；narrative = 叙事 P04→CCV3）")
    dm.add_argument("--dest", default="", help="导出目录（缺省 = 系统临时目录并打印路径）")


def add_19(sub, ctx):
    sg = sub.add_parser("sig",
                        help="协议知识签名（41 波C C1：01-36 文档/管线/模块 → 结构化签名，知识指纹"
                            "）",
 description="协议知识签名（41 波C C1：01-36 文档/管线/模块 → 结构化签名，知识指纹）")
    sg.add_argument("target", nargs="*", default=None,
                    help="目标 md 或目录；缺省 = 全量 01-36 编号方案文档")
    sg.add_argument("--json", action="store_true", help="输出完整 canonical JSON 记录")
    sg.add_argument("--verify", action="store_true",
                    help="check25 同语义：两遍生成一致性校验（可复现门禁）")


def add_20(sub, ctx):
    at = sub.add_parser("attest",
                        help="内容 attestation（三级信任：digest_only / hmac-sha256 / sigstore 外挂"
                            "锚）",
                        description="内容 attestation（内部差距：知识签名只自证可复现，无对外可验证"
                            "的篡改证据）。"
                                    "签发时间戳取墙钟（`issued_at`），可用 `SOURCE_DATE_EPOCH`（可"
                                        "复现构建惯例）"
                                    "钉成固定值——机器面据此逐字节可复现。")
    at.add_argument("target", nargs="?", default="",
                    help="目标 md（缺省 = 01/02/06/07 四件集合）")
    at.add_argument("--out", default="", help="写出 attestation JSON 的路径（缺省 = 不写盘）")
    at.add_argument("--issuer", default="", help="签发方标识（写入 producer.issuer）")
    at.add_argument("--key-file", default="",
                    help="HMAC 密钥文件 → 签发/校验 hmac-sha256 级 attestation")
    at.add_argument("--verify", default="",
                    help="校验既有 attestation JSON（缺省 = 生成模式）")
    at.add_argument("--selfcheck", action="store_true",
                    help="体检「外部验签」机制：独立子进程验签 + 篡改必红（check42 的用户侧入口）")
    at.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_21(sub, ctx):
    sc = sub.add_parser("score",
                        help="基线相对回归评分（Codecov 式：当前 vs 基线，no silent worsening）",
                        description="基线相对回归评分（内部差距：现有门禁全为绝对门，无 delta/回归"
                            "判据）")
    sc.add_argument("--baseline", default="",
                    help="基线 JSON（缺省 = protocol/score_baseline.json）")
    sc.add_argument("--write-baseline", action="store_true",
                    help="把当前分值写入基线（审计注记随写入）")
    sc.add_argument("--tolerance", type=float, default=0.0,
                    help="整体分允许下降幅度（缺省 0 = 不允许下降）")
    sc.add_argument("--exceptions", default="",
                    help="审计例外 JSON（[{signal,reason}]，例外只标注理由不隐藏回归）")
    sc.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_22(sub, ctx):
    ln = sub.add_parser("lint",
                        help="机械检查/修复（doc_hygiene 同源判据 + 可选正文 lint；--fix 只改机械面"
                            "）",
                        description="机械检查/修复（内部差距：既有扫描器只报告不修，仓库无 auto-fix"
                            "）")
    ln.add_argument("target", nargs="*", default=None,
                    help="目标 md/目录（缺省 = doc_hygiene 关键/指令档清单）")
    ln.add_argument("--fix", action="store_true",
                    help="应用机械修复（缺省 = 只报告，发现即 exit 1）")
    ln.add_argument("--dry-run", action="store_true",
                    help="配合 --fix：只报将改什么，不写盘")
    ln.add_argument("--prose", action="store_true",
                    help="额外跑正文 lint（去 AI 味规则集；**咨询面**：发现即 exit 1，"
                         "但仓库门禁不拦它——正文质量不由机器判死刑）")
    ln.add_argument("--kinds", action="store_true",
                    help="只跑四型写法判据（信息类型化：类型不只是标签）")
    ln.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_23(sub, ctx):
    asrt = sub.add_parser("assertions",
                          help="数据化断言表（Schematron 式：patterns→rules→assertions）",
                          description="数据化断言表（机制借鉴 Schematron；kind 为封闭集）")
    asrt.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_24(sub, ctx):
    mdl = sub.add_parser("model",
                         help="内容建模三件（词表登记册 / 规范与说明件 / 数据契约登记）",
                         description="内容建模三件（机制借鉴 SKOS 概念方案 / 规范-说明件二分 / 数据"
                             "契约要素）")
    mdl.add_argument("part", nargs="?", default="",
                     choices=["", "vocab", "normative", "contracts"],
                     help="只看一件（缺省 = 三件全跑）")
    mdl.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_25(sub, ctx):
    dec = sub.add_parser("decisions",
                         help="决策记录（ADR：一条一编号；采纳后不改不删，只可被取代）",
                         description="决策记录（机制借鉴 ADR：supersede-only + 不可改）")
    dsub = dec.add_subparsers(dest="decisions_cmd")
    d_sh = dsub.add_parser("show",
 help="看单条决策（frontmatter + 正文）",
 description="看单条决策")
    d_sh.add_argument("id", help="编号（如 ADR-0001）")
    for _d in (dsub.add_parser("verify", help="机检决策记录", description="机检决策记录"),
               dsub.add_parser("reindex", help="重建 INDEX 投影", description="重建 INDEX 投影"),
               d_sh):
        _d.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_26(sub, ctx):
    ho = sub.add_parser("handover",
                        help="接力协议（SBAR：情境/背景/评估/建议 + 未决项带判据）",
                        description="接力协议（机制借鉴 SBAR；空未决即不合格交接）")
    hosub = ho.add_subparsers(dest="handover_cmd")
    ho_ls = hosub.add_parser("ls", help="列全部交接件", description="列全部交接件")
    ho_ck = hosub.add_parser("check", help="机检单件交接", description="机检单件交接")
    ho_ck.add_argument("path", help="交接件路径（仓库相对）")
    for _h in (ho_ls, ho_ck, hosub.add_parser("verify", help="机检声明 + 全部交接件",
                                              description="机检声明 + 全部交接件")):
        _h.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_27(sub, ctx):
    pm = sub.add_parser("postmortem", help="复盘（无指责 + 根因指向机制 + 行动项闭环）",
                        description="复盘（机制借鉴 SRE postmortem）")
    pmsub = pm.add_subparsers(dest="postmortem_cmd")
    pm_ck = pmsub.add_parser("check", help="机检单件复盘", description="机检单件复盘")
    pm_ck.add_argument("path", help="复盘件路径（仓库相对）")
    for _p in (pmsub.add_parser("ls", help="列全部复盘", description="列全部复盘"), pm_ck,
               pmsub.add_parser("verify", help="机检声明 + 全部复盘件", description="机检")):
        _p.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_28(sub, ctx):
    au = sub.add_parser("audit", help="审计/验收（列表 / 单件机检 / 全量机检 / 重审重绑）",
                        description="审计/验收（机制借鉴 Audit Report + Acceptance/Sign-off）")
    ausub = au.add_subparsers(dest="audit_cmd")
    au_ck = ausub.add_parser("check", help="机检单件审计", description="机检单件审计")
    au_ck.add_argument("path", help="审计件路径（仓库相对）")
    for _a in (ausub.add_parser("ls", help="列全部审计件", description="列全部审计件"), au_ck,
               ausub.add_parser("verify", help="机检声明 + 全部审计件", description="机检")):
        _a.add_argument("--json", action="store_true", help="输出结构化 JSON")
    au_rb = ausub.add_parser("rebind", help="重审并更新 digest（对象改动后机械重绑 + 落重审理由）",
                             description="重审并更新 digest：只逐行替换 subjects 的 sha256（不重排"
                                         "frontmatter），并把重审理由落成正文首行；同一理由不重复追加。"
                                         "理由必填——无理由的重绑就是洗数据。顺序：改代码 → "
                                         "code_metrics --write → audit rebind → receipts（先重绑会又被"
                                         "基线重冻打回——实测踩过）。")
    au_rb.add_argument("--note", required=True, help="重审理由（写进审计件的重审行）")
    au_rb.add_argument("--dry-run", action="store_true", help="只列将重绑的条目，不写盘")
    au_rb.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_29(sub, ctx):
    cog = sub.add_parser("cognition", help="认知族（行话术语表 + 执行分档 Runbook/Playbook）",
                         description="认知族（机制借鉴 Glossary + SOP/Runbook/Playbook 分档）")
    cog.add_argument("part", nargs="?", default="", choices=["", "glossary", "modes"],
                     help="只看一件（缺省 = 全跑）")
    cog.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_30(sub, ctx):
    stv = sub.add_parser("st-validate",
                         help="ST 制卡校验器原型（卡 / 世界书 / MVU 变量 → 报告；A-S3）",
                         description="ST 制卡校验器原型 v0（任务书 A-S3：R1 结构 / R3 世界书 / R4 "
                             "变量）")
    stv.add_argument("path", help="被校验对象（JSON；卡 / 世界书 / MVU 变量产物）")
    stv.add_argument("--out", default="", help="把 markdown 报告写入该路径")
    stv.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_31(sub, ctx):
    sfp = sub.add_parser("state-front",
                         help="条件先行排布（状态块前置/后置/省略；T3 刺激件生成器）",
                         description="条件先行排布（灵感来源 arXiv:2609.02702 的 condition-first；N"
                             "F 只做排布纪律）")
    sfp.add_argument("path", help="产物 md 路径（仓库相对或绝对）")
    sfp.add_argument("--mode", default="front", choices=["front", "back", "none"],
                     help="排布方式（缺省 front = 条件先行）")
    sfp.add_argument("--out", default="", help="写出排布结果")
    sfp.add_argument("--check", action="store_true", help="只判「状态块是否已前置」")
    sfp.add_argument("--ab", action="store_true", help="输出 A/B/C 三刺激件清单（T3 装置）")
    sfp.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_32(sub, ctx):
    lp = sub.add_parser("lsp",
                        help="LSP 服务器（stdio：诊断/补全/悬停/跳定义/大纲/quickfix；不写盘）",
                        description="LSP 服务器（stdio Content-Length 分帧；诊断与 nf lint 同源，"
                                    "领域符号表来自 core/nf_language；--print-config 出编辑器配置）"
                                        "")
    lp.add_argument("--root", default="", help="仓库根（缺省 = 本仓库）")
    from core.lsp_client import CLIENT_EDITORS as _lsp_editors   # 单一真相：lsp_client.render_client_config
    lp.add_argument("--print-config", default="", choices=["", *_lsp_editors],
                    help="只打印目标编辑器的现成配置（不启动服务）")


def add_33(sub, ctx):
    lc = sub.add_parser("license",
                        help="图书馆许可证门（登记表「许可」列 + 条目内联声明双源校验）",
                        description="图书馆许可证门（内部差距：登记表无许可列，入库产物不承载共享条"
                            "款）")
    lc.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_34(sub, ctx):
    tl = sub.add_parser("telemetry",
                        help="遥测 semconv 映射（trace 记录 → OTel GenAI 属性 / OTLP 形状）",
                        description="遥测 semconv 映射（内部差距：trace 为自定 JSON，对外界不可消费"
                            "）")
    tl.add_argument("trace", help="trace JSON（单条记录或 {records:[...]}）")
    tl.add_argument("--otlp", action="store_true",
                    help="输出 OTLP 形状 JSON（resourceSpans → scopeSpans → spans）")


def add_35(sub, ctx):
    conf = sub.add_parser("conformance",
                         help="一致性报告工件（全部契约 → Merkle 根 + verdict；可归档可比对）",
                          description="一致性报告工件（机制借鉴 MCOP runConformanceSuite：make it c"
                              "heckable instead of trusted）")
    conf.add_argument("--write", action="store_true",
                      help="把当前报告写入 protocol/conformance_report.json")
    conf.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_36(sub, ctx):
    ev = sub.add_parser("events",
                        help="全仓事件背书核对（订阅必有发布方；跨包事件可见；外部通道须挂账）",
                        description="全仓事件背书核对（补 check16/26 之外：社区域包订阅是否真有发布"
                            "方）")
    ev.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_37(sub, ctx):
    rc2 = sub.add_parser("receipts",
                         help="协议层回执单根（01–07/schema/baseline 等机读产物各带 inclusion proof"
                             "）",
                         description="协议层回执单根（把回执覆盖面从馆藏扩到协议层机读产物）")
    rc2.add_argument("--scope", default="protocol", choices=["protocol"],
                     help="回执范围（当前支持 protocol）")
    rc2.add_argument("--write", action="store_true", help="写入 protocol/RECEIPTS.json")
    rc2.add_argument("--entry", default="", help="只验一条（按相对路径）")
    rc2.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_38(sub, ctx):
    drv = sub.add_parser("driver",
                         help="指令档机器面路由（有 MCP 走 MCP；派发失败即停、不回退文本步骤）",
                         description="指令档机器面路由（机制借鉴 ACP driver override）")
    drv.add_argument("workflow", nargs="?", default="",
                     help="工作流名（缺省 = 列全部工作流）")
    drv.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_39(sub, ctx):
    rfc = sub.add_parser("rfc",
                         help="协议件 RFC 索引（编号/Category/Date/Status + supersede 链）",
                         description="协议件 RFC 索引（机制借鉴 HMP：把协议版本史做成可机读头）")
    rfc.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_40(sub, ctx):
    ptn = sub.add_parser("patterns",
                         help="实践包：可发布/可消费/可移植的最佳实践（ls/show/for/verify/reindex）",
                         description="实践包品类（机制借鉴 ACP patterns：与内容域包并列的实践规范包"
                             "）")
    p2 = ptn.add_subparsers(dest="patterns_cmd")
    pa_ls = p2.add_parser("ls", help="列出全部 pattern", description="列出全部 pattern")
    pa_sh = p2.add_parser("show", help="看单条 pattern（frontmatter + 正文）",
                          description="看单条 pattern（frontmatter + 正文）")
    pa_sh.add_argument("id", help="pattern id（目录名）")
    pa_fp = p2.add_parser("for", help="反向查：某文件适用哪些 pattern",
                          description="反向查：某文件适用哪些 pattern")
    pa_fp.add_argument("target", help="文件路径（仓库相对或绝对）")
    pa_vf = p2.add_parser("verify", help="机检 pattern（格式 + 可证性）",
                          description="机检 pattern（格式 + 可证性）")
    pa_ri = p2.add_parser("reindex", help="重建 patterns/INDEX 投影",
                          description="重建 patterns/INDEX 投影")
    for _p2 in (pa_ls, pa_sh, pa_fp, pa_vf, pa_ri):
        _p2.add_argument("--json", action="store_true", help="输出结构化 JSON")


