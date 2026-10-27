"""命令面切片 part_02（自 nf.py::_make_parser 抽出；勿改顺序）。"""
from __future__ import annotations


def add_72(sub, ctx):
    ly = sub.add_parser(
        "layers",
        help="抽象阶梯（两轴 + 纵切）：四阶真源/接口面 + 资产五子级 + 入口面 + 验证纵切",
        description="NF 抽象阶梯（真源 = protocol/LAYERS.json，机制借鉴多视图描述 / 稳定依赖 / "
                    "适应度函数 / 单一真源+生成投影）：抽象轴四阶（契约→资产→引擎→出口）、"
                    "入口面（只登记角色，永不作为真源）、验证纵切（贯穿四阶的门禁与证据）。"
                    "判据与 verify check27 的 R7 同源；--write 刷新 docs/layers.md 的生成区。")
    ly.add_argument("--json", action="store_true", help="输出结构化 JSON（逐阶真源面/接口面/判据）")
    ly.add_argument("--verify", action="store_true",
                    help="跑阶梯体检（归属互斥/接口子集/依赖向下/入口非真源/生成区一致）")
    ly.add_argument("--write", action="store_true",
                    help="把渲染结果写回 docs/layers.md 生成区（改真源后必跑）")


def add_73(sub, ctx):
    os = ctx.os
    argparse = __import__("argparse")
    dnm = sub.add_parser(
        "daemon",
        help="执行层常驻守护（毫秒级响应）：start / stop / status / exec / bench",
        description="NF 执行层常驻守护：把「每条命令一次解释器启动」（实测 ~400 ms 固定成本）"
                    "换成「一次启动、长期热跑」，客户端只做一次套接字往返。只绑 127.0.0.1 + "
                    "一次性令牌；单线程串行；每次请求比对 core/scripts 源码指纹并清空按路径键的"
                    "进程缓存——「热进程」与「新起进程」结果一致（等价性由 test_daemon_parity 常驻："
                    "全部命令面的 `--help` 逐条 + 可无参运行的 `--json` 机器面逐字节比对；"
                    "长驻/自指命令在守护内拒跑，不走等价面）。")
    dsub = dnm.add_subparsers(dest="daemon_cmd", required=True)
    dst = dsub.add_parser("start", help="拉起守护（后台、脱离控制台）",
                          description="拉起执行层常驻守护：后台子进程、只绑 127.0.0.1 + 一次性令牌"
                              "，"
                                      "状态落在 <NF_HOME>/daemon.json。已在运行则幂等返回。")
    dst.add_argument("--idle", type=float,
                     default=float(os.environ.get("NF_DAEMON_IDLE", 3600.0)),
                     help="空闲多少秒后自动退出（0=不退出）")
    dst.add_argument("--watch", action="store_true",
                     help="启用目录监听 + 只读命令响应缓存（树没变即整条复用；平台不支持时自动降级"
                         "）")
    dsub.add_parser("stop", help="请守护自行退出（协议级 shutdown，不发信号）",
                    description="请守护自行退出：走协议级 shutdown 帧（不发信号、不删文件），"
                                "并把状态文件标记为停用——之后启动器自动回到 python 直跑。")
    dss = dsub.add_parser("status", help="守护状态（在线？端口 / pid / 往返时延）",
                          description="看守护是否在线、端口/pid/协议版本/仓库根与状态文件落点，"
                                      "并实测一次往返时延（--json 给机器面）。")
    dss.add_argument("--json", action="store_true", help="输出结构化 JSON")
    dex = dsub.add_parser("exec", help="把一条 nf 命令交给守护执行（输出/退出码与直跑一致）",
                          description="把一条 nf 命令交给守护执行：stdout/stderr/退出码与真子进程"
                                      "直跑逐字节一致（长驻/自指命令在守护内被拒跑）。")
    dex.add_argument("--no-start", action="store_true",
                     help="守护不在时直接失败（默认自动拉起）")
    dex.add_argument("argv", nargs=argparse.REMAINDER,
                     help="要执行的 nf 命令（如：nf daemon exec stats --check）")
    dbn = dsub.add_parser("bench", help="测量：直跑（含解释器启动）vs 守护往返",
                          description="复跑效率对照表：对同一批探测命令分别测「直跑（含解释器启动）"
                              "」"
                                      "与「守护往返」，各取 --runs 次最小值（--json 给机器面）。")
    dbn.add_argument("--runs", type=int, default=3, help="每场景取样次数（取最小值）")
    dbn.add_argument("--json", action="store_true", help="输出结构化 JSON")
    dsi = dsub.add_parser("shell-init", help="输出 shell 快路（零子进程客户端），供 eval 安装",
                          description="输出 shell 快路脚本：在交互 shell 里定义 nf() 函数，用 bash "
                              "内建"
                                      "（/dev/tcp + read -N）直连守护——零子进程，真毫秒级；用法 "
                                      "eval \"$(nf daemon shell-init bash)\"。")
    dsi.add_argument("shell", nargs="?", default="bash", choices=("bash",),
                     help="目标 shell（缺省 bash；需要 /dev/tcp 内建）")
    dsi.add_argument("--shell", dest="shell_opt", default=None, choices=("bash",),
                     help="目标 shell（目前只支持 bash：需要 /dev/tcp 内建）")


def add_74(sub, ctx):
    vfy = sub.add_parser(
        "verify",
        help="门禁单进程引擎（已迁入的 check 与 verify.sh 判据逐字等价）",
        description="门禁单进程引擎：把 verify.sh 的 check 收进**一个进程**跑，省掉每条一次的解释器"
                    "启动（实测全量门禁起 42 次 $PY3）。判据**一字不改**——已迁入的 check 与 "
                    "verify.sh 的输出逐字一致（由 tests/test_gate_engine_parity.py 逐 check 差分"
                    "常驻守着）。**注意**：全量门禁的权威入口仍是 `bash verify.sh`；本命令是引擎"
                    "入口，未迁入的 check 会如实报「未迁入」，不假装绿。")
    vfy.add_argument("--only", default="",
                     help="只跑指定 check 号（逗号分隔，如 1,3,23）；缺省跑全部已迁入的")
    vfy.add_argument("--json", action="store_true", help="输出结构化 JSON（机器面）")
    vfy.add_argument("--memo", action="store_true",
                     help="打开内容寻址 memo（重复跑时跳过未变读面；默认关，保证差分测的是真跑）")
    vfy.add_argument("--cached", action="store_true",
                     help="打开**跨进程子 check 缓存**：按上次观测到的真实读面复核，等价则"
                          "不跑判据本体直接回上次的判定（fail-closed：读面为空/含仓外/"
                          "输入变或缺 ⇒ 重跑）。默认关，保证差分测的是真跑")
    vfy.add_argument("--jobs", type=int, default=0,
                     help="并行跑各条 check 的进程数（0=串行，缺省）。每条 check 仍在"
                          "**独立子进程**里跑 `nf verify --only N --json`，判据一字不改；"
                          "合并按 check 号排序，输出与串行逐字节一致（实测 8 路 ≈3.2×）")
    vfy.add_argument("--trust-repo", dest="trust_repo", action="store_true",
                     help="显式信任目标仓库：允许引擎在**本进程内执行**其 verify.sh 内嵌代码"
                          "（H1/CWE-94 面）。默认只信任当前运行代码所在的安装根；"
                          "外来/不可信仓库不加本旗标一律拒绝执行（自担风险）")


def add_75(sub, ctx):
    argparse = __import__("argparse")
    nfl = sub.add_parser("nfal",
                         help="NFA-L 装配语言：guard 表达式 解析/检查/编译/求值（声明层借 YAML/IDL"
                             "）",
                         description="NFA-L：声明层借既有 YAML + JSON-Schema IDL，命令层是封闭 guar"
                             "d 表达式"
                                     "（无用户函数/循环/赋值/IO）；用法见 docs/nfal.md")
    nfl.add_argument("nfal_args", nargs=argparse.REMAINDER,
                     help="透传给 NFA-L 的参数；完整用法见 nf nfal help")


def add_76(sub, ctx):
    irp = sub.add_parser(
        "ir",
        help="内容 IR：产物 → 带类型节点图（parse/render；节点级检查）",
        description="内容 IR（T7.2）：document/section/paragraph/claim/citation/entity/slot_ref "
                    "节点图；每节点稳定 id（路径+内容哈希）；render 规范形逐字节确定性；"
                    "check 输出 section/claim/无归属引用/悬空实体，并以 IR 节点为执行面重跑 "
                    "techdoc-strict 的 3 条文本规则（标题句式/标题末尾标点/单空格）")
    irsub = irp.add_subparsers(dest="ir_cmd")
    ir_ck = irsub.add_parser(
        "check", help="节点级检查（section/claim/无归属引用/悬空实体/IR 文本规则）",
        description="节点级检查：parse 产物 → 统计 + 悬空引用/实体 + 3 条文本规则（IR 节点执行）")
    ir_ck.add_argument("file", help="待检 markdown 路径（仓库相对或绝对）")
    ir_ck.add_argument("--json", action="store_true", help="输出结构化 JSON 报告")


def add_77(sub, ctx):
    ag = sub.add_parser(
        "agent",
        help="多 agent 协作契约（角色=模块 / 交接=事件 / 验收=门）",
        description="多 agent 协作契约（T10.3）：writer/critic/fact_checker/editor 四角色契约与域链"
                    "（techdoc/regulatory）。角色引用既有模块/管线/gate profile，不新造能力；"
                    "`plan` 输出角色链（谁→谁、交接事件、每步门、runtime 衔接点）；"
                    "`check` 校验闭合（缺门/孤儿交接/无失败策略/引用不存在模块即 FAIL）。只读、不跑真实模型")
    agsub = ag.add_subparsers(dest="agent_cmd", required=True)
    ag_p = agsub.add_parser("plan", help="输出域角色链（角色→模块→门 + 交接边）",
                            description="角色链计划：按域取链，逐角色给模块/registry 模块/门/"
                                        "失败策略/交接事件，并给 runtime 衔接点（可注入 ModelClient 直接跑）")
    ag_p.add_argument("--domain", default="techdoc",
                      choices=("techdoc", "regulatory"),
                      help="域：techdoc（技术文档）或 regulatory（合规与监管）")
    ag_p.add_argument("--json", action="store_true", help="输出结构化 JSON")
    ag_c = agsub.add_parser("check", help="校验角色链闭合（缺门/孤儿交接/无失败策略/坏引用）",
                            description="闭合校验：角色字段齐全、相邻交接事件有发布/订阅方、"
                                        "每步门真实可达、引用模块/管线/gate profile 真实存在、"
                                        "无孤立角色；任一不过 rc=1")
    ag_c.add_argument("--json", action="store_true", help="输出结构化 JSON")


def add_78(sub, ctx):
    cm = sub.add_parser(
        "cli",
        help="CLI 信息架构：命令目录 / 族覆盖 / 机器面（生成 protocol/cli_map.json + docs/cli-map.md）",
        description="CLI IA 机读层（T11.3）：从 argparse 命令面 + terminal.FAMILIES 构建 "
                    "nf-cli-map/1（命令→族→用途→flags/has_json/相关文档），生成件 "
                    "protocol/cli_map.json 与人读件 docs/cli-map.md 同源渲染；"
                    "覆盖率判据：每命令恰好一族、每族非空、无重复归族/虚指。只读消费，不改命令行为")
    cms = cm.add_subparsers(dest="cli_cmd", required=True)
    cm_m = cms.add_parser(
        "map", help="构建/校验命令地图（--write 生成；--check 与实时重算对账）",
        description="命令地图：默认打印覆盖率摘要；--write 落 protocol/cli_map.json + "
                    "docs/cli-map.md；--check 与实时重算逐字节对账（源改了没重生成即红）；"
                    "--json 输出 nf-cli-map/1（配 --check 输出 nf-cli-map-check/1）")
    cm_m.add_argument("--write", action="store_true", help="生成并落盘机读件与人读件")
    cm_m.add_argument("--check", action="store_true", help="与实时重算对账（漂移 rc=1）")
    cm_m.add_argument("--json", action="store_true", help="输出结构化 JSON")


