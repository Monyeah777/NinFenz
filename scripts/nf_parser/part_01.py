"""命令面切片 part_01（自 nf.py::_make_parser 抽出；勿改顺序）。"""
from __future__ import annotations


def add_41(sub, ctx):
    pre = sub.add_parser("preset",
                         help="预设配置：一份存档 = 管线+模块+资产包的**一次组装**"
                              "（ls/show/apply/save/rm/export/import）",
                         description="预设配置（指令集 F：端壳退役后按「端壳能力一律落 CLI」"
                                     "把预设接成命令；落点 = NF_HOME，非仓库）")
    pr2 = pre.add_subparsers(dest="preset_cmd")
    pr_ls = pr2.add_parser("ls", help="列出本机预设", description="列出本机预设")
    pr_sh = pr2.add_parser("show", help="看一条预设", description="看一条预设")
    pr_sh.add_argument("name", help="预设名")
    pr_ap = pr2.add_parser("apply", help="应用预设：解析成装配清单（管线+模块+资产包）",
                           description="应用预设：解析成装配清单（本地缺失模块如实进 warnings）")
    pr_ap.add_argument("name", help="预设名")
    pr_sv = pr2.add_parser("save", help="保存预设（同名已存在须加 --force 覆盖）",
                           description="保存预设（同名已存在须加 --force 覆盖）")
    pr_sv.add_argument("name", help="预设名")
    pr_sv.add_argument("--pipeline", default="P01", help="管线 id（如 P04）")
    pr_sv.add_argument("--modules",
 default="",
 help="模块 full_id，逗号分隔（如 通用类:M00,轻混类:M91）")
    pr_sv.add_argument("--assets", default="", help="资产包名（如 校园情感领域包）")
    pr_sv.add_argument("--force", action="store_true", help="同名预设已存在时覆盖")
    pr_rm = pr2.add_parser("rm", help="删除本机预设", description="删除本机预设")
    pr_rm.add_argument("name", help="预设名")
    pr_ex = pr2.add_parser("export", help="导出预设到文件（跨机迁移）",
                           description="导出预设到文件（跨机迁移）")
    pr_ex.add_argument("name", help="预设名")
    pr_ex.add_argument("--out", required=True, help="导出文件路径（JSON）")
    pr_im = pr2.add_parser("import", help="从文件导入预设到本机",
                           description="从文件导入预设到本机")
    pr_im.add_argument("file", help="预设 JSON 文件（`nf preset export` 的产物）")
    pr_im.add_argument("--name", default="", help="改名导入（缺省用文件里的名字）")
    for _p3 in (pr_ls, pr_sh, pr_ap, pr_sv, pr_rm, pr_ex, pr_im):
        _p3.add_argument("--store", default="", metavar="NF_HOME",
                         help="预设库根（缺省 = NF_HOME，即 ~/.NinFenz 或 NARRATIVE_FORGE_HOME）")
        _p3.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_42(sub, ctx):
    bn = sub.add_parser("bench",
                        help="执行结果跑分台（对 agent 产物五维确定性评分；多跑可比对）",
                        description="执行结果跑分台（机制借鉴 ACP benchmark suite：外部实测的容器）")
    b2 = bn.add_subparsers(dest="bench_cmd", required=True)
    b_run = b2.add_parser("run", help="跑一个用例 → run 记录（可 --out 存档）",
                          description="跑一个用例 → run 记录（可 --out 存档）")
    b_run.add_argument("--case", required=True, help="用例目录（含 case.json）")
    b_run.add_argument("--artifact", default="", help="被评产物 md（缺省=用例 default_artifact）")
    b_run.add_argument("--model", default="", help="跑次来源标识（模型/客户端名）")
    b_run.add_argument("--out", default="", help="把 run 记录写入该 JSON（缺省=打印）")
    b_cmp = b2.add_parser("compare", help="多跑比对（逐维均值/极差/相对最佳回落）",
                          description="多跑比对（逐维均值/极差/相对最佳回落）")
    b_cmp.add_argument("runs", help="run 记录 JSON（单个对象或数组）")
    b_rep = b2.add_parser("report", help="人读跑分报告（markdown）",
                          description="人读跑分报告（markdown）")
    b_rep.add_argument("runs", help="run 记录 JSON（单个对象或数组）")
    for _b2 in (b_run, b_cmp, b_rep):
        _b2.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_43(sub, ctx):
    rtp = sub.add_parser("runtime",
                         help="参考运行时（确定性 harness：装配计划 → trace；MockModel + record/replay）",
                         description="参考运行时（T7.3）：载入装配计划与状态，按管线层序执行并产 trace；"
                                     "MockModel 按 contract_digest+step 确定性派生响应（无随机/无网络）；"
                                     "record/replay 复现同一 trace 与产物 digest，fixture 缺失/篡改即 FAIL。")
    rtp2 = rtp.add_subparsers(dest="rt_cmd", required=True)
    rtr = rtp2.add_parser("run", help="跑一次：--plan/--trace（可 --record/--replay）",
                          description="跑一次参考运行时：计划 → trace；可录制/回放 fixture。")
    rtr.add_argument("--plan", required=True,
                     help="装配计划 JSON 路径（assemble_plan.plan 产出）")
    rtr.add_argument("--trace", required=True, help="trace 输出 JSON 路径")
    rtr.add_argument("--state", default="",
                     help="状态 JSON 路径（缺省=protocol/world_slots.json）")
    rtr.add_argument("--record", default="", help="录制 fixture JSON 路径（模型调用序列）")
    rtr.add_argument("--replay", default="", help="回放 fixture JSON 路径（复现同一 digest）")
    rtr.add_argument("--json", action="store_true", help="输出结构化 JSON 摘要")


def add_44(sub, ctx):
    ep = sub.add_parser("endpoint",
                        help="服务端点契约（proposed：把已实现能力声明成 HTTP 面 + 指向真实性门禁）",
                        description="服务端点契约（机制借鉴 microsoft/ai-chat-protocol）")
    ep.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_45(sub, ctx):
    iop = sub.add_parser("interop",
                         help="互操作导出（OpenAPI 3.1 / AsyncAPI 3.0 / in-toto Statement / SPDX SB"
                             "OM——纯派生）",
                         description="互操作导出面：把既有声明件实时派生为外部标准工具可读的文档"
                                     "（不新增真源；同一输入两次导出逐字节一致）")
    try:
        from core import interop_export as _ie_kinds
        _kinds = sorted(_ie_kinds.KINDS)
    except Exception:  # pragma: no cover - 声明件不可读时退回最小面
        _kinds = ["openapi"]
    iop.add_argument("--kind", default="openapi", choices=_kinds,
                     help="导出种类（缺省 openapi；可选值派生自 interop_export.KINDS）")
    iop.add_argument("--all", action="store_true",
                     help="导出全部面（配合 --out 落盘为目录；单面时 --out 为文件）")
    iop.add_argument("--list", action="store_true", help="列出可导出种类与其消费方")
    iop.add_argument("--check", action="store_true",
                     help="只跑导出面门禁（覆盖完整 + 形状合法 + 确定性）")
    iop.add_argument("--out", default="", help="写入文件（缺省打印到 stdout）")
    iop.add_argument("--json", action="store_true", help="--check 时输出结构化 JSON")


def add_46(sub, ctx):
    tr = sub.add_parser("transparency",
                        help="透明日志（哈希链）：append-only 顺序 + 防删改（不可抵赖另说）",
                        description="透明日志：由 protocol/RECEIPTS.json 确定性派生哈希链"
                                    "（RFC 6962 风格域分隔），并校验在盘生成物")
    tr.add_argument("--write", action="store_true",
                    help="写入 protocol/generated/receipt_chain.json")
    tr.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_47(sub, ctx):
    of = sub.add_parser("output",
                        help="产出形态面（数据/图表/图结构/契约：形态清单 + 机验档位 + 可复算）",
                        description="产出形态面：把「产出一律是散文」的缺口机制化——"
                                    "形态清单（protocol/output_forms.json）、包级产出面"
                                    "（community/<包>/outputs/INDEX.json）、T0–T4 档位判定、"
                                    "T4 可复算面重算比对、机验率基线")
    ofsub = of.add_subparsers(dest="output_cmd", required=True)
    of_ls = ofsub.add_parser("list", help="列形态清单（可按状态/类别/档位过滤）",
                             description="列产出形态清单：每条给类别 / 档位 / 状态 / 规范入口，"
                                         "并打印覆盖统计（可达数与档位/状态分布）")
    of_ls.add_argument("--status", default="", help="按状态过滤（supported/absorbed/planned/…）")
    of_ls.add_argument("--category", default="", help="按类别过滤")
    of_ls.add_argument("--tier", default="", help="按档位过滤（T0–T4）")
    of_ls.add_argument("--json", action="store_true", help="输出结构化 JSON")
    of_ck = ofsub.add_parser("check", help="判单件（多件）产出面的形态与档位并校验",
                             description="判件：按扩展名 + 内容嗅探判形态与上限档位，"
                                         "跑该形态的校验器（JSON 重复键 / CSV 行长 / Vega-Lite 通道"
                                             "绑定 / "
                                         "GraphML 悬空边 / 口径注册表的 engine 真实性…）")
    of_ck.add_argument("paths", nargs="+", help="待判文件路径（仓库相对或绝对）")
    of_ck.add_argument("--json", action="store_true", help="输出结构化 JSON")
    of_vf = ofsub.add_parser("verify", help="全量机检（与 verify check32 output_forms 同语义）",
                             description="全量机检：形态清单自洽 + 包级产出面逐件校验（形态/档位/sc"
                                 "hema/"
                                         "双源一致/T4 复算）+ 机验率基线不回落；退出码即门禁语义")
    of_vf.add_argument("--json", action="store_true", help="输出结构化 JSON")
    of_rn = ofsub.add_parser("render", help="按包清单渲染产出面（数据/图表/图结构）",
                             description="渲染：按 community/<包>/outputs/INDEX.json 调生成器重算/"
                                 "重绘产出面；"
                                         "缺省只报告差异，--write 才落盘（EOL 契约 = LF）")
    of_rn.add_argument("--package", default="", help="只渲染某包（缺省全部）")
    of_rn.add_argument("--write", action="store_true", help="落盘（缺省只报告差异，不写）")
    of_rn.add_argument("--json", action="store_true", help="输出结构化 JSON")
    of_mt = ofsub.add_parser("meter", help="机验率 / 功能面计量（--write 重签基线）",
                             description="计量：逐包算机验面 / 功能面（T4）/ 散文资产与机验率；"
                                         "--write 重签 protocol/output_forms_baseline.json（回退即 "
                                             "FAIL）")
    of_mt.add_argument("--write", action="store_true",
                       help="重签 protocol/output_forms_baseline.json")
    of_mt.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_48(sub, ctx):
    ROOT = ctx.root
    sec = sub.add_parser("security",
                         help="内容供应链安全（域包/投稿正文的外来内容形态扫描：注入/可执行/凭据/结构）",
                         description="内容供应链安全扫描：把 community/ 与 library/ 的正文当**外来"
                                     "内容**做只读形态扫描（不联网、不执行、不改写）——指令注入标记"
                                     "（单源 core.trust_boundary）、可执行/主动内容、明文凭据（只回"
                                     "掩码）、隐藏/控制字符、超长单行、base64 大块、可疑外链。退出码"
                                     "：0 干净 / 1 有 critical / 2 不可判定")
    secsub = sec.add_subparsers(dest="security_cmd", required=True)
    sec_sc = secsub.add_parser("scan", help="扫描路径（缺省 community/ 与 library/）",
                               description="扫描：缺省扫 community/ 与 library/；显式测试样本"
                                           "（desktop/tests/fixtures/security/ 等白名单前缀）默认跳过"
                                           "并登记，显式传参时仍逐条报出但不计入退出码")
    sec_sc.add_argument("paths", nargs="*", default=None,
                        help="待扫路径（文件或目录；缺省 = community/ 与 library/）")
    sec_sc.add_argument("--root", default=ROOT, help="扫描根（缺省=仓库根）")
    sec_sc.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_49(sub, ctx):
    ops = sub.add_parser("ops",
                         help="内容 SRE：只用真实产物算 SLI/SLO（缺数据即 UNKNOWN）",
                         description="内容 SRE 观测面（T11.1）：从既有真实产物（门禁缺陷 bench / "
                                     "一致性报告 / 回执 / 审计 / verify 判据面 / benchmark 榜单 / "
                                     "M2 执行记录 / 索引 root）+ 既有只读扫描器（安全扫描 / "
                                     "modelcheck / 知识图 check）采集 SLI，逐条给 value/unit/"
                                     "source/freshness/status∈OK|WARN|UNKNOWN；不编造、不判绿")
    opssub = ops.add_subparsers(dest="ops_cmd", required=True)
    ops_rep = opssub.add_parser("report", help="采集并打印 SLI/SLO 报告",
                                description="报告：汇总 nf-ops-report/1；缺源/已知无数据如实标 "
                                            "UNKNOWN（--no-live 跳过现场只读扫描）")
    ops_rep.add_argument("--json", action="store_true", help="输出结构化 JSON")
    ops_rep.add_argument("--no-live", action="store_true",
                         help="跳过现场只读扫描（安全/modelcheck/知识图 check → UNKNOWN）")
    ops_chk = opssub.add_parser("check", help="校验各源在场可解析（缺源 fail-closed）",
                                description="校验：缺源/不可解析/值非法 → 非零退出；已知无数据"
                                            "（真实模型 0 行、M2 0 条）的 UNKNOWN 不算失败")
    ops_chk.add_argument("--json", action="store_true", help="输出结构化 JSON")
    ops_chk.add_argument("--no-live", action="store_true", help="跳过现场只读扫描")


def add_50(sub, ctx):
    ROOT = ctx.root
    prv = sub.add_parser("privacy",
                         help="隐私与 air-gap 静态审计（PII/本机路径/凭据 + core·scripts 网络站点）",
                         description="隐私与 air-gap 静态审计：`scan` 扫内容面（PII / 本机路径 / "
                                     "凭据，掩码输出）；`check` 用 AST 静态审计 desktop/src/core 与 "
                                     "scripts 的网络站点（requests/urllib.request/socket/… 与 "
                                     "subprocess curl|wget|nc）。只读、离线、不执行被扫内容；"
                                     "不宣称绝对离线（未覆盖项见 docs/security/airgap-and-privacy.md）")
    prvsub = prv.add_subparsers(dest="privacy_cmd", required=True)
    prv_sc = prvsub.add_parser("scan", help="内容面扫描（缺省 docs/ site/ protocol/ community/ library/）",
                               description="内容面扫描：缺省扫 docs/ site/ protocol/ community/ "
                                           "library/；合成测试样本（desktop/tests/fixtures/privacy/）"
                                           "默认跳过并登记，显式传参时仍逐条报出但不计入退出码。"
                                           "退出码：0 干净 / 1 有 critical / 2 不可判定")
    prv_sc.add_argument("paths", nargs="*", default=None,
                        help="待扫路径（文件或目录；缺省 = docs/ site/ protocol/ community/ library/）")
    prv_sc.add_argument("--root", default=ROOT, help="扫描根（缺省=仓库根）")
    prv_sc.add_argument("--json", action="store_true", help="输出结构化 JSON")
    prv_ck = prvsub.add_parser("check", help="air-gap 静态审计（core/ 与 scripts/ 的网络站点）",
                               description="静态审计：AST 扫描 core/ 与 scripts/ 的 import/调用网络面，"
                                           "合法站点须在白名单登记理由；无命中即红（名单不得变黑洞）")
    prv_ck.add_argument("--root", default=ROOT, help="扫描根（缺省=仓库根）")
    prv_ck.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_51(sub, ctx):
    dm = sub.add_parser("domain",
                        help="域包工厂（AI 品类清单工程：从一个域规格生成整套过门禁的域包）",
                        description="域包工厂：读内部域规格（.rivet/private_archive/ai_packs/specs/"
                                    "<code>.json）生成 protocol.yaml / README / 模块×2 / 管线 / "
                                    "资产×3（含 provenance 台账）/ 机验产出面×9，并登记 02 §8 与 "
                                    "verify.sh DOMAIN 列表；幂等（重跑逐字节一致）")
    dmsub = dm.add_subparsers(dest="domain_cmd", required=True)
    dm_b = dmsub.add_parser("build", help="按规格生成/更新一个域包（--write 才落盘）",
                            description="生成域包：缺省只报差异（dry-run），--write 落盘并登记；"
                                        "--render/--no-render 控制是否顺带重渲染产出面")
    dm_b.add_argument("--spec", required=True, help="域码（如 A01）")
    dm_b.add_argument("--write", action="store_true", help="落盘（缺省 dry-run）")
    dm_b.add_argument("--no-render", action="store_true", help="不自动渲染产出面")
    dm_b.add_argument("--json", action="store_true", help="输出结构化 JSON")
    dm_v = dmsub.add_parser("verify", help="校验已生成域包与生成器逐字节一致 + 登记到位",
                            description="工厂自检：生成物 ≡ 计划（字节级）+ 02 §8 在册 + "
                                        "verify.sh DOMAIN 在册 + registry protocols[] 在册 + R2 类"
                                            "别不冲突")
    dm_v.add_argument("--spec", default="", help="只验某域码（缺省全部已建域包）")
    dm_v.add_argument("--json", action="store_true", help="输出结构化 JSON")
    dm_l = dmsub.add_parser("specs", help="列出内部域规格与其状态",
                            description="列域规格：域码 / 名称 / 度量族 / 是否已建包")
    dm_l.add_argument("--json", action="store_true", help="输出结构化 JSON")
    dm_m = dmsub.add_parser("maturity", help="域包成熟度 M0–M3（按证据计算；--write 落盘）",
                            description="域包成熟度：按证据逐级计算 M0 模板 / M1 机检 / M2 真实模型"
                                        "执行 / M3 用户签收；声明位 package.maturity 不参与计算，"
                                        "证据不足一律降级。--write 落 protocol/domain_maturity.json "
                                        "并投影 registry protocols[].maturity")
    dm_m.add_argument("--json", action="store_true", help="输出结构化 JSON")
    dm_m.add_argument("--write", action="store_true",
                      help="落盘 protocol/domain_maturity.json 与 registry protocols[].maturity")
    dm_s = dmsub.add_parser("shells", help="派生空壳台账（域口径表：可数 + 只减不增棘轮）",
                            description="清点社区域包 DOMAIN_SPEC 的框架占位条目：逐包空壳数 / "
                                        "已填包数 / 双源（md↔json）一致性 / 与冻结基线比对（只减不"
                                            "增）")
    dm_s.add_argument("--json", action="store_true", help="输出结构化 JSON")
    dm_r = dmsub.add_parser("record", help="真实模型执行记录校验/落盘（M2 证据 · nf-exec-record/1）",
                            description="M2 真实模型执行记录（protocol/schema/exec_record.schema.json）："
                                        "校验 artifact 在仓内且 sha256 可复算 / check_rc==0 / "
                                        "executor 是模型标识（非工具/装配器）/ date 合法 / package "
                                        "在册；--write 落盘 protocol/exec_records/<run_id>.json。"
                                        "无参 = 扫描 protocol/exec_records/。模板 _TEMPLATE.json 显式"
                                        "标记「未执行」，不构成 M2 证据。")
    dm_r.add_argument("--check", metavar="FILE", default=None,
                      help="校验一条执行记录（JSON）；PASS=0 / FAIL=1 / 模板=0（未执行状态）")
    dm_r.add_argument("--write", metavar="FILE", default=None,
                      help="校验通过后落盘 protocol/exec_records/<run_id>.json（原子写；同内容幂等）")
    dm_r.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_52(sub, ctx):
    cb = sub.add_parser("combine",
                        help="域包自由组合（任意 n 元 / 组件级；五不变量 + 可复算证书）",
                        description="组合引擎：任选若干域包（或直接点模块/资产）→ 层位堆叠 / 依赖闭"
                            "包 / "
                                    "事件闭包 / 资产借阅 / 合法性判定 → 可复算证书（T4）；"
                                    "`breadth` 对全部两两 + 抽样三元/四元/五元/六元跑同一套不变量证"
                                        "明广度；"
                                    "`materialize` 把组合落成可装载的组合包（派生协议/管线/借阅索引"
                                        "/机验产出面）。")
    cbsub = cb.add_subparsers(dest="combine_cmd", required=True)
    cb_p = cbsub.add_parser("plan", help="组合一个（打印/落证书）",
                            description="组合：--packs 逗号分隔包名；--modules/--assets 组件级取用"
                                "；"
                                        "--certify 写进 protocol/combo_certificates.json")
    cb_p.add_argument("--packs",
 default="",
 help="包名，逗号分隔（如 大语言模型域包,视觉模型域包）")
    cb_p.add_argument("--modules", default="", help="组件级：模块 id，逗号分隔（可跨包）")
    cb_p.add_argument("--assets", default="", help="组件级：资产，`包名:资产键`，逗号分隔")
    cb_p.add_argument("--label", default="", help="证书标签")
    cb_p.add_argument("--note", default="", help="证书说明")
    cb_p.add_argument("--certify", action="store_true", help="写入证书台账")
    cb_p.add_argument("--json", action="store_true", help="输出结构化 JSON")
    cb_b = cbsub.add_parser("breadth", help="广度证明（全部两两 + 抽样三元/四元/五元/六元）",
                            description="广度证明：对 C(N,2) 全部两两组合与定种子抽样的三元/四元组"
                                "合"
                                        "跑同一套不变量（依赖闭合 / 事件闭合 / 层栈 / 资产可寻址）")
    cb_b.add_argument("--triples", type=int, default=400, help="三元抽样数（缺省 400）")
    cb_b.add_argument("--quads", type=int, default=200, help="四元抽样数（缺省 200）")
    cb_b.add_argument("--quints", type=int, default=120, help="五元抽样数（缺省 120）")
    cb_b.add_argument("--sexts", type=int, default=60, help="六元抽样数（缺省 60）")
    cb_b.add_argument("--json", action="store_true", help="输出结构化 JSON")
    cb_v = cbsub.add_parser("verify", help="证书复算（T4：与在盘证书逐字段比对）",
                            description="证书复算：读 protocol/combo_certificates.json 逐条重算并比"
                                "对")
    cb_v.add_argument("--json", action="store_true", help="输出结构化 JSON")
    cb_m = cbsub.add_parser("materialize",
                            help="把组合落成可装载的组合包（派生协议/管线/借阅索引/机验产出面）",
                            description="组合包产物化：0 自有模块 + references 只读借阅 + available"
                                " 层栈 + "
                                        "派生 P00 管线 + 8 件机验产出面（含 T4 证书）；"
                                        "--write 落盘并按域包工厂同一套登记流程登记")
    cb_m.add_argument("--packs", required=True, help="包名，逗号分隔")
    cb_m.add_argument("--id", default="", help="组合包名（缺省 组合包-<前两包>）")
    cb_m.add_argument("--category", default="", help="独占类别（缺省 组合域-<名>）")
    cb_m.add_argument("--write", action="store_true", help="落盘并登记（缺省 dry-run）")
    cb_m.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_53(sub, ctx):
    dc = sub.add_parser("decide",
                        help="决策层（typed-decision 三原语 choice/noul/score：候选集上报概率 + arg"
                            "max）",
                        description="决策层端口：把选择写成类型化问题交给决策模型；"
                                    "模型在门禁之外，缺适配器/超时/输出不合 schema 一律 abstained")
    dc.add_argument("--state", default="", help="状态文本文件路径")
    dc.add_argument("--state-text", default="", help="状态文本（与 --state 二选一）")
    dc.add_argument("--questions", required=True, help="问题 JSON 文件路径")
    dc.add_argument("--adapter", default="stub",
                    help="适配器 id（stub 离线确定性 / systemone-http 本地服务 / openai-json）")
    dc.add_argument("--endpoint",
 default="",
 help="适配器端点（systemone-http / openai-json 必填）")
    dc.add_argument("--model", default="", help="openai-json 适配器的模型名")
    dc.add_argument("--timeout", type=float, default=30.0, help="适配器超时秒（缺省 30）")
    dc.add_argument("--dry-run", action="store_true",
                    help="只体检（声明面 + 请求形状 + stub 决定），不调用外部适配器")
    dc.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_54(sub, ctx):
    wl = sub.add_parser("workloop",
                        help="构建回路：决策模型挑活 → 生成式 worker 落笔 → NF 门禁验收",
                        description="构建回路：从公开待办真源（type_backlog / pipeline_advisory）"
                                    "组类型化问题问决策层，产出**工单**（含完成判据与验收命令）；"
                                    "决策模型只选择不落笔，工单只落内部档案")
    wl.add_argument("--adapter", default="stub", help="决策适配器（stub / systemone-http）")
    wl.add_argument("--top", type=int, default=5, help="候选工作项数（缺省 5）")
    wl.add_argument("--source", default="",
                    help="限定候选池来源：type-backlog / pipeline-advisory / capability-gaps"
                         "（缺省=全池；操作者定池、模型定选）")
    wl.add_argument("--endpoint", default="", help="systemone-http 端点")
    wl.add_argument("--timeout", type=float, default=30.0, help="适配器超时秒")
    wl.add_argument("--list", action="store_true", help="列出待办工作项（不提问）")
    wl.add_argument("--write", action="store_true",
                    help="把工单写入内部档案 .rivet/private_archive/work_orders/")
    wl.add_argument("--close", default="", help="收口：工单号（配合 --outcome/--gate/--note）")
    wl.add_argument("--outcome", default="", help="收口结果：landed / abandoned")
    wl.add_argument("--gate", default="", help="收口时的门禁结论（如 PASS=61）")
    wl.add_argument("--note", default="", help="收口说明")
    wl.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_55(sub, ctx):
    rv = sub.add_parser("review",
                        help="缺口逐行审查（决策模型逐行判 + 确定性证据复核，双轨）",
                        description="逐行审查：机械预筛候选行 → 决策模型逐行判（是否缺口/严重度）"
                                    "→ 确定性证据复核 → 只把**有证据**的放进修复清单")
    rv.add_argument("--adapter", default="stub", help="判定适配器（stub / systemone-http）")
    rv.add_argument("--endpoint", default="", help="systemone-http 端点")
    rv.add_argument("--scope", default="",
                    help="只扫某类（逗号分隔）：unharvestable-payload / payload-no-evidence / "
                         "silent-skip / missing-quality-rule")
    rv.add_argument("--limit", type=int, default=0, help="只审前 N 行候选（0=全量）")
    rv.add_argument("--batch", type=int, default=8, help="每批行数（缺省 8）")
    rv.add_argument("--timeout", type=float, default=120.0, help="适配器超时秒")
    rv.add_argument("--write", default="", help="把审查报告写入路径（不得写 protocol/）")
    rv.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_56(sub, ctx):
    kn = sub.add_parser("knowledge",
                        help="双源知识层（权威分层 / 消化可追溯 / 查询有序 / 时效 / 可见性）",
                        description="双源知识层（机制借鉴一句式：编译时机按数据域选择）")
    ksub = kn.add_subparsers(dest="knowledge_cmd")
    k_order = ksub.add_parser("order", help="解析查询顺序（合同级在前、参考级在后）",
                              description="解析查询顺序（合同级在前、参考级在后）")
    k_order.add_argument("--as", dest="clearance", default="",
                         choices=["", "public", "internal", "restricted"],
                         help="按可见性裁剪（缺省 = 不裁剪）")
    k_lint = ksub.add_parser("lint", help="知识层巡检（悬空 / 孤儿 / 时效 / 溯源 / 声明）",
                             description="知识层巡检（悬空 / 孤儿 / 时效 / 溯源 / 声明）")
    k_tr = ksub.add_parser("transform", help="列消化记录（外部 → 本地，digest 绑定）",
                           description="列消化记录（外部 → 本地，digest 绑定）")
    k_tr.add_argument("--json", action="store_true", help="输出结构化 JSON")
    _t = k_tr.add_subparsers(dest="transform_cmd")
    t_add = _t.add_parser("add", help="登记一条消化记录（复核双签，未转正）",
                          description="登记一条消化记录（复核双签，未转正）")
    t_add.add_argument("--from", dest="src", required=True, help="参考级源 id")
    t_add.add_argument("--to", dest="dst", required=True, help="本地产物（仓库相对路径）")
    t_add.add_argument("--by", default="", help="复核人")
    t_add.add_argument("--at", default="", help="复核时间 YYYY-MM-DD（缺省 = 今天）")
    t_add.add_argument("--json", action="store_true", help="输出结构化 JSON")
    t_prom = _t.add_parser("promote", help="转正（须齐三档证据 + 复核双签）",
                           description="转正（须齐三档证据 + 复核双签）")
    t_prom.add_argument("--from", dest="src", required=True, help="参考级源 id")
    t_prom.add_argument("--to", dest="dst", required=True, help="本地产物（仓库相对路径）")
    t_prom.add_argument("--by", default="", help="复核人（必填）")
    t_prom.add_argument("--at", default="", help="复核时间 YYYY-MM-DD（缺省 = 今天）")
    t_prom.add_argument("--evidence", default="",
                        help="证据档（逗号分隔，须齐 machine-checkable,reproducible,externally-atte"
                            "stable）")
    t_prom.add_argument("--json", action="store_true", help="输出结构化 JSON")
    k_freq = ksub.add_parser("frequency", help="从 trace 复算知识源使用频次（--write 落台账）",
                             description="从 trace 复算知识源使用频次（确定性；频次不可手写）")
    k_freq.add_argument("--trace", required=True, help="trace 文件（JSON / JSONL）")
    k_freq.add_argument("--write", action="store_true",
                        help="写入 protocol/knowledge_usage.json")
    k_vis = ksub.add_parser("visible", help="按可见性列出源（认知裁剪执行面）",
                            description="按可见性列出源（认知裁剪执行面）")
    k_vis.add_argument("--as", dest="clearance", default="public",
                       choices=["public", "internal", "restricted"],
                       help="消费方清除级（public ⊆ internal ⊆ restricted）")
    k_graph = ksub.add_parser(
        "graph",
        help="资产本体索引：合并全部域包 CONCEPT_GRAPH（nf-concept-index/1）",
        description="资产本体索引（T10.2）：扫描 community/*/assets/CONCEPT_GRAPH.md（缺件时回退"
                    " outputs/CONCEPT_DAG.graphml），同名概念跨域合并、边去重，产出唯一机读产物"
                    " protocol/concept_graph_index.json；只读扫描、不改各包资产")
    k_graph.add_argument("--write", action="store_true",
                         help="重写 protocol/concept_graph_index.json")
    k_graph.add_argument("--check", action="store_true", help="只校验（默认）")
    k_graph.add_argument("--json", action="store_true", help="打印机读结果")
    for _k in (k_order, k_lint, k_freq, k_vis):
        _k.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_57(sub, ctx):
    ap = sub.add_parser("approve",
                        help="内容绑定批准记录（被批准对象改动即失效）",
                        description="内容绑定批准记录（机制借鉴 MCOP approved-changeset gate）")
    ap.add_argument("subject", nargs="?", default="", help="被批准对象路径（仓库相对）")
    ap.add_argument("--by", default="", help="批准人标识")
    ap.add_argument("--note", default="", help="批准说明")
    ap.add_argument("--verify", action="store_true",
                    help="校验全部批准记录（缺省 = 生成模式）")
    ap.add_argument("--list", action="store_true", help="列出全部批准记录（含失效标记）")
    ap.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_58(sub, ctx):
    lib = sub.add_parser("library",
                         help="云端图书馆机器面（frontmatter 真源 / INDEX·ALIAS 投影 / 检索）",
                         description="云端图书馆机器面（内部差距：library 无 CLI 面、MCP 检索不覆盖"
                             "馆藏、元数据非一等公民）")
    lsub = lib.add_subparsers(dest="library_cmd")
    l_ls = lsub.add_parser("ls", help="列出馆藏条目（编号/状态/许可/标题）",
                           description="列出馆藏条目（编号/状态/许可/标题）")
    l_sh = lsub.add_parser("show", help="查看单条条目（frontmatter + 正文头）",
                           description="查看单条条目（frontmatter + 正文头）")
    l_sh.add_argument("entry", help="编号（如 NF-1）")
    l_ri = lsub.add_parser("reindex",
                           help="重生成 INDEX 生成区 + ALIAS（真源 = 条目 frontmatter）",
                           description="重生成 INDEX 生成区 + ALIAS（真源 = 条目 frontmatter）")
    l_vf = lsub.add_parser("verify", help="校验 frontmatter + 投影一致性（图书馆门同语义）",
                           description="校验 frontmatter + 投影一致性（图书馆门同语义）")
    l_vf.add_argument("--key-file", default="",
                      help="验签名锚用的 HMAC 密钥（缺省 = 只报「无法校验」，不判死）")
    l_vf.add_argument("--ssh-allowed-signers", default="",
                      help="ssh-sig 锚校验用的 allowed_signers 文件")
    l_vf.add_argument("--ssh-identity", default="",
                      help="ssh-sig 锚校验用的 principal")
    l_se = lsub.add_parser("search", help="关键词检索（标题/描述/标签/正文，中文子串可用）",
                           description="关键词检索（标题/描述/标签/正文，中文子串可用）")
    l_se.add_argument("query", help="检索串")
    l_dp = lsub.add_parser("deprecate", help="生命周期流转 → deprecated（不再推荐、仍可读）",
                           description="生命周期流转 → deprecated（不再推荐、仍可读）")
    l_dp.add_argument("entry", help="编号")
    l_rs = lsub.add_parser("restore", help="生命周期回退 → active",
                           description="生命周期回退 → active")
    l_rs.add_argument("entry", help="编号")
    l_sp = lsub.add_parser("supersede", help="取代链：旧条目 → superseded（指向新条目）",
                           description="取代链：旧条目 → superseded（指向新条目）")
    l_sp.add_argument("entry", help="被取代的旧编号")
    l_sp.add_argument("by", help="取代它的新编号")
    l_at = lsub.add_parser("attest", help="给条目挂 attestation（复用 nf attest 信封摘要）",
                           description="给条目挂 attestation（复用 nf attest 信封摘要，写入 frontma"
                               "tter）")
    l_at.add_argument("entry", help="编号")
    l_at.add_argument("--key-file", default="",
                      help="HMAC 密钥文件 → 一并落签名锚（不给则 digest_only 级）")
    l_at.add_argument("--ssh-key", default="",
                      help="SSH 私钥路径 → 落 ssh-sig 锚（真实非对称签名，读者用 ssh-keygen 即可验"
                          "）")
    l_at.add_argument("--ssh-identity", default="",
                      help="ssh-sig 的 principal（allowed_signers 里的身份）")
    l_rc = lsub.add_parser("receipts",
                           help="馆藏回执 + 单根（逐条 inclusion proof，读者可本地折叠验证）",
                           description="馆藏回执 + 单根（机制借鉴 MCOP MMR：O(log n) 审计路径代替 O"
                               "(n) 重放）")
    l_rc.add_argument("--write", action="store_true", help="写入 library/RECEIPTS.json")
    l_rc.add_argument("--entry", default="",
                      help="只验一条：按编号取回执并本地折叠到根（读者侧验证入口）")
    for _p in (l_ls, l_sh, l_ri, l_vf, l_se, l_dp, l_rs, l_sp, l_at, l_rc):
        _p.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_59(sub, ctx):
    df = sub.add_parser("diff",
                        help="版本差异检测（41 波C C2：两份签名/文档 → 字段级差异 + 兼容判定）",
 description="版本差异检测（41 波C C2：两份签名/文档 → 字段级差异 + 兼容判定）")
    df.add_argument("a", help="签名 A 的文档 md 路径")
    df.add_argument("b", help="签名 B 的文档 md 路径")
    df.add_argument("--json", action="store_true", help="输出结构化差异 JSON")


def add_60(sub, ctx):
    ex = sub.add_parser("explain",
                        help="check 修复指引（41 波C C5：缺什么/补什么/示例 三段式）",
 description="check 修复指引（41 波C C5：缺什么/补什么/示例 三段式）")
    ex.add_argument("check", help="check 编号（如 25；all = 全量清单）")


def add_61(sub, ctx):
    rel = sub.add_parser("related",
                        help="See-Also 关联查询（41 波C C4：market/图书馆条目人读引用链）",
 description="See-Also 关联查询（41 波C C4：market/图书馆条目人读引用链）")
    rel.add_argument("target",
                    help="目标 = 包 id（如 技术文档域包）或模块 id（如 M90 / 技术文档:M90）")
    rel.add_argument("--registry", default=None,
                     help="registry.json 路径（缺省 = desktop/src/core/registry.json）")
    rel.add_argument("--json", action="store_true",
                     help="输出结构化 JSON（See-Also 关联结果）")


def add_62(sub, ctx):
    hep = sub.add_parser("help",
                         help="显示 nf 或指定子命令的帮助",
 description="显示 nf 或指定子命令的帮助")
    hep.add_argument("command", nargs="?", metavar="COMMAND",
                     help="子命令名；缺省 = 显示 nf 总帮助")


def add_63(sub, ctx):
    doc = sub.add_parser("doctor",
                         help="环境自检（快速只读体检：关键文件/registry/schema/核心库——不开 verify"
                             " 慢跑）",
 description="环境自检（快速只读体检：关键文件/registry/schema/核心库——不开 verify 慢跑）")
    doc.add_argument("--json", action="store_true",
                     help="输出结构化 JSON 报告")


def add_64(sub, ctx):
    cmp = sub.add_parser("completion",
                         help="生成 shell 补全脚本（bash/zsh/fish；用法：nf completion bash >> ~/.b"
                             "ashrc）",
 description="生成 shell 补全脚本（bash/zsh/fish；用法：nf completion bash >> ~/.bashrc）")
    cmp.add_argument("shell", choices=("bash", "zsh", "fish"),
                     help="目标 shell")


def add_65(sub, ctx):
    asm = sub.add_parser("assemble",
                         help="需求 → 自组装编排（44：一句话需求 → 装配计划；--check 对成品机器验收"
                             "）",
 description="需求 → 自组装编排（44：一句话需求 → 装配计划；--check 对成品机器验收）")
    asm.add_argument("requirement",
                     help="用户需求一句话（如：帮我组装一个西幻生存世界的完整版）")
    asm.add_argument("--check", dest="check_md", metavar="OUT.md",
                     help="对成品完整版 md 做机器验收（骨架/编号/引用）")
    asm.add_argument("--save", dest="save_path", metavar="FILE.md",
                     help="把澄清/计划落成需求档案（八字段回填稿）")
    asm.add_argument("--trace", dest="trace_path", metavar="TRACE.json",
                     help="执行遥测落盘（计划/澄清/验收留痕，供真实转录/E3 补测底座）")
    asm.add_argument("--check-trace", dest="check_trace", metavar="TRACE.json",
                     help="读回 `--trace` 落盘的遥测件，重跑回合级 drill 并断言判定未漂移"
                          "（写→读回自证闭环；漂移即 exit 1）")
    asm.add_argument("--rounds", action="store_true",
                     help="回合级 drill：对成品转录按回合断言（引用/推进/编造，45 A2）")
    asm.add_argument("--loose", action="store_true",
                     help="放宽装配允许集：恢复旧行为 = 全库已登记模块（缺省 scoped：官方核心 13 + "
                          "命中管线 default/allowed + 组合包 references；跨域/自定义件才需要）")
    asm.add_argument("--answer", action="append", default=None,
                     metavar="问答",
                     help="澄清回填（可多次，如 --answer \"题材：西幻生存\" --answer \"主轴：生存"
                         "\"）")
    asm.add_argument("--session", dest="session_path", metavar="SESSION.json",
                     help="会话存储：多次调用间保留已回填澄清（多轮记忆落盘）")
    asm.add_argument("--build", action="store_true",
                     help="组装式命令：直接产出**引用式「完整版」单文件**（八段骨架 + "
                          "契约/出处/清单）并对产物自检（缺省只出装配计划）")
    asm.add_argument("--dest", dest="build_dest", metavar="DIR",
                     help="--build 的输出目录（缺省 = 当前目录）")
    asm.add_argument("--allow-protected-dest", dest="allow_protected_dest",
                     action="store_true",
                     help="显式允许把产物写进真源面目录（缺省 fail-closed："
                          "拒写 protocol/ 03_管线库/ 04_模块库/ 05_资产库/ community/ library/ 等）"
                              "")


def add_66(sub, ctx):
    argparse = __import__("argparse")
    rel = sub.add_parser("release",
                         help="发布前体检与编排（体检照旧；--plan 出有序发布计划；--freeze [--apply"
                             "] 按序走冻结链）",
                         description="发布前体检与编排：默认=体检（verify + 基线自描述 + e2e + 覆盖"
                             "率 + 报告新鲜度）；--plan=发布计划（只读）；--freeze [--apply]=冻结链"
                             "（conformance → approve → receipts）")
    rel.add_argument("--fast", action="store_true",
                     help="跳过 verify.sh 全量（快速自检：基线自描述 + doctor）")
    rel.add_argument("--plan", action="store_true",
                     help="打印有序发布计划（命令/产出/判据），不执行任何写面")
    rel.add_argument("--json", action="store_true",
                     help="机读输出（配合 --plan；或体检结论摘要）")
    rel.add_argument("--freeze", action="store_true",
                     help="冻结链：conformance --write → approve → receipts（缺省只打印；--apply 才"
                         "执行）")
    rel.add_argument("--apply", action="store_true",
                     help="冻结链：真正执行（缺省 dry-run；首例发布取证 2026-10-05：此前只登记了 --"
                         "freeze，--apply 被 argparse 拒收）")
    rel.add_argument("--by", metavar="NAME",
                     help="批准人（--freeze --apply 写进 protocol/approvals/*）")
    rel.add_argument("--note", metavar="TEXT",
                     help="批准说明（--freeze --apply；同批准人一并落档）")


def add_67(sub, ctx):
    cl = sub.add_parser("changelog",
                        help="变更日志生成（从变更条目 + 约定式提交生成版本节；默认预览，--write 落"
                            "盘并归档条目）",
                        description="变更日志生成：渲染确定（无墙钟，版本/日期由参数给）+ 逐条可溯"
                            "源（只分组、不改写）；"
                                    "--write 把版本节插入 CHANGELOG 顶部并把 changes/unreleased/* "
                                        "归档到 changes/<version>/")
    cl.add_argument("--version", metavar="X.Y.Z",
                    help="版本号（缺省 = CHANGELOG 最新节）")
    cl.add_argument("--date", metavar="YYYY-MM-DD",
                    help="发布日期（--write 必填；不臆造日期）")
    cl.add_argument("--json", action="store_true", help="机读输出（版本节 + 自检结论）")
    cl.add_argument("--write", action="store_true",
                    help="落盘：插 CHANGELOG 版本节 + 归档 changes/unreleased/*（幂等）")
    cl.add_argument("--no-commits", dest="no_commits", action="store_true",
                    help="只用变更条目，不并入 git 提交主题")


def add_68(sub, ctx):
    loc = sub.add_parser("locales",
                         help="语言面自检（--write 重签文档译件的源件摘要）",
                         description="语言面：注册表 ⇄ 文件在场双向对账（入口锚点/切换行/结构；文档"
                             "译件路径镜像 + source_sha256 防过期）")
    loc.add_argument("--json", action="store_true", help="机读输出（issues + stats）")
    loc.add_argument("--write", action="store_true",
                     help="重签文档译件的 source_sha256（写 protocol/locales.json）")


def add_69(sub, ctx):
    tf = sub.add_parser("toolface",
                        help="模块工具面浏览（45：machine_contract.tool_face 可选建议层，AI 裁量不"
                            "入门禁）",
 description="模块工具面浏览（45：machine_contract.tool_face 可选建议层，AI 裁量不入门禁）")
    tf.add_argument("--json", action="store_true",
                    help="输出结构化 JSON（工具面清单）")


def add_70(sub, ctx):
    wm = sub.add_parser("worldmodel",
                        help="world_model 浏览（JEPA-inspired 确定性抽象状态契约，check32 硬门）",
 description="world_model 浏览（JEPA-inspired 确定性抽象状态契约，check32 硬门）")
    wm.add_argument("--json", action="store_true",
                    help="输出结构化 JSON（world_model 清单）")
    wm.add_argument("--walk", action="store_true",
                    help="从 initial_phase 重放确定性相位迁移环")
    wm.add_argument("--run", action="store_true",
                    help="执行 WorldModelRuntime：状态校验 + 相位前进 + 轨迹重放")
    wm.add_argument("--state", dest="state_path", metavar="STATE.json",
                    help="具体 M00 状态 JSON；与 --run 联用时按 slot 绑定重放")


def add_71(sub, ctx):
    argparse = __import__("argparse")
    sh = sub.add_parser(
        "shell", aliases=["terminal"],
        help="NF 终端：交互式入口（能力菜单 + nf 命令直通；--exec 非交互回归面）",
        description="NF 终端（端壳退役后的人机交互入口）：把既有 CLI 命令面按能力菜单"
                    "组织成可交互会话（数字 0-7 看菜单 / 任意 nf 命令直通 / /help /quit）。"
                    "纯 stdlib、确定性；写入类命令须显式确认（--yes 或交互输入 yes）。"
                    "命令真源仍是本 CLI 的 argparse 面——菜单不许指向死命令（verify check39）。")
    sh.add_argument("--exec", dest="exec_script", default="", metavar="\"命令1; 命令2\"",
                    help="非交互执行一串命令（分号分隔）后退出——CI 与回归用（确定性）")
    sh.add_argument("--no-banner", action="store_true",
                    help="不开场横幅（管道/日志场景）")
    sh.add_argument("--yes", action="store_true",
                    help="显式放行写入类命令（终端默认拒跑 --write/--apply/--register 等）")
    sh.add_argument("--json", action="store_true",
                    help="配合 --exec：输出逐条记录的结构化 JSON")
    sh.add_argument("--file", dest="script_file", default="", metavar="SCRIPT",
                    help="脚本文件模式：逐行执行（`#` 注释与空行跳过，行内 `;` 再分隔）")
    sh.add_argument("--commands", nargs="?", const="", default=None, metavar="过滤词",
                    help="列出全部可达命令（顶层 + 二级，可按子串过滤）后退出——「最全功能」的可检视"
                        "面")
    sh.add_argument("--search", default="", metavar="词",
                    help="在命令面上检索（不进入终端）：命中打印命令与用途，未命中退出 2")
    sh.add_argument("--map", dest="family_map", nargs="?", const="", default=None,
                    metavar="族或片段",
                    help="打印能力地图（把全部顶层命令按能力族策展呈现），可按族名/片段过滤")
    sh.add_argument("--verify", action="store_true",
                    help="终端自检（索引覆盖 / 能力族分区 / 菜单示例可达），退出码即结论")
    sh.add_argument("--deep", action="store_true",
                    help="配合 --verify：活体档——真跑一条只读命令 + 探测历史/会话落点可写性")
    sh.add_argument("--baseline", action="store_true",
                    help="跑「顶尖 CLI 基线」：逐行执行证据命令并给判定（与 verify check39 同源）")
    sh.add_argument("--complete", dest="complete_prefix", default="", metavar="前缀",
                    help="补全候选（非交互）：给命令/子命令/旗标/斜杠命令/能力族前缀，未命中退出 2")
    sh.add_argument("--history", default="", metavar="文件",
                    help="跨会话历史文件（缺省 <NF_HOME>/shell_history；仅交互态写入）")
    sh.add_argument("--no-history", action="store_true",
                    help="不写历史（`--exec`/`--file` 本来就一律不写，以保证确定性）")
    sh.add_argument("--color", choices=("auto", "always", "never"), default=None,
                    help="着色模式（缺省 auto：真 TTY 且未设 NO_COLOR 才上色；非 TTY 恒无色）")
    sh.add_argument("--width", type=int, default=0, metavar="列宽",
                    help="渲染宽度（缺省取环境 COLUMNS，否则 100；CJK 按显示宽度对齐）")
    sh.add_argument("--limit", type=int, default=None, metavar="条数",
                    help="列表限长（0 = 全部；截断时给「还有 N 条」提示）")
    sh.add_argument("--session", dest="session_path", default="", metavar="文件",
                    help="会话状态文件（视图设置 + 上次分区；缺省不持久化）")
    sh.add_argument("--form", dest="form_id", nargs="?", const="", default=None,
                    metavar="表单id",
                    help="写盘表单：不带值列全部；带 id 组装命令（配合 --answer k=v；加 --yes 才执"
                        "行）")
    sh.add_argument("--answer", action="append", default=None, metavar="k=v",
                    help="表单回答（可多次；非交互模式下与 --form 配合）")
    sh.add_argument("--pager", choices=("auto", "never"), default="never",
                    help="分页（缺省 never：非交互面逐字节确定；auto 仅在真 TTY 且 less/more 在场时"
                        "接管）")
    sh.add_argument("--surface", action="store_true",
                    help="终端面投影（单真值源 → 多视图）：打印机器快照，配 --json 出 JSON")
    sh.add_argument("--surface-write", dest="surface_write", nargs="?", const="", default=None,
                    metavar="路径",
                    help="把终端面投影写成生成件（缺省 tui/_surface.py；改真源后必跑，check39 逐字"
                        "节对账）")


