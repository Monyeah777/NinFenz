"""terminal · _tables（自 terminal.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

from typing import Any

#: 能力菜单（**单一真源**）：键 / 稳定 id / 标题 / 一句话 / 示例命令（可执行原文）/
#: 动作目录（argv 模板 + 参数槽，供全屏 TUI 物化成可回车执行的动作）。
#: 覆盖端壳退役前 GUI 七区的能力面（导入 / 校验 / 管线 / 生成 / 资产 / 预设 / 社区），
#: 但**只指向既有命令**——新增能力仍须先落 CLI，再登记进本表。
#: 多视图纪律（2026-10-03）：行模式 `nf shell` 渲染 examples / 能力族 / 表单，全屏
#: `tui/nf.py` 渲染 actions，`nf shell --surface --json` 出机器面——三者都是本表的**投影**，
#: 表本身只有这一份（TUI 不再手抄）。投影件 `tui/_surface.py` 由 `nf shell --surface-write`
#: 生成，check39 断言「重算结果与在场件逐字节一致」。
#: 动作字典形态：{"key", "title", "argv", "params", "note"}；参数形态：
#: {"name", "label", "kind": "text"|"path", "required"}——`kind=path` 的参数在 TUI 侧强制过
#: 路径包含性判据（与 core/paths.py 同口径）。
ZONES: tuple[dict[str, Any], ...] = (
    {"key": "0", "id": "doctor", "title": "环境自检",
     "family": "start",
     "summary": "只读体检：仓库件在场 / 解释器可用 / 基线自描述一致性",
     "examples": ("nf doctor",),
     "actions": (
         {"key": "doctor", "title": "只读体检", "argv": ("doctor",), "params": (), "note": ""},
         {"key": "doctor-json", "title": "体检（机器面）", "argv": ("doctor", "--json"),
          "params": (), "note": ""},
     )},
    {"key": "1", "id": "demo", "title": "一键演示世界",
     "family": "start",
     "summary": "P04 轻混全链跑一遍（retrieve→compose→gate→export）并产出 CCV3 卡",
     "examples": ("nf demo",),
     "actions": (
         {"key": "demo", "title": "跑一遍 P04 全链", "argv": ("demo",), "params": (), "note": ""},
     )},
    {"key": "2", "id": "assemble", "title": "需求 → 装配计划",
     "family": "forge",
     "summary": "一句话需求 → 命中预设包或转用户自定义流；--check 验收成品",
     "examples": ("nf assemble \"帮我组装一个西幻生存世界的完整版\"",
                  "nf assemble 西幻生存 --check sample.md"),
     "actions": (
         {"key": "assemble", "title": "一句话→装配计划", "argv": ("assemble", "{need}"),
          "params": ({"name": "need", "label": "需求（一句话）", "kind": "text",
                      "required": True},),
          "note": "产出装配计划文本，不落盘"},
         {"key": "assemble-check", "title": "校验成品文档",
          "argv": ("assemble", "{file}", "--check"),
          "params": ({"name": "file", "label": "成品 .md（仓内路径）", "kind": "path",
                      "required": True},),
          "note": ""},
     )},
    {"key": "3", "id": "run", "title": "全链生产",
     "family": "forge",
     "summary": "选管线与模块 → 装配 → 质量门 → 导出（--seed 装载官方核心 + 社区包）",
     "examples": ("nf run --pipeline community/校园西幻轻混组合包/pipelines/"
                  "P04_轻混装配流管线.md --modules 通用类:M00,轻混类:M91,"
                  "轻混类:M92,通用类:M80 --seed",),
     "actions": (
         {"key": "run", "title": "跑全链管线",
          "argv": ("run", "--pipeline", "{pipeline}", "--modules", "{modules}", "--seed"),
          "params": ({"name": "pipeline", "label": "管线 .md（仓内路径）", "kind": "path",
                      "required": True},
                     {"name": "modules", "label": "模块 full_id（逗号分隔）", "kind": "text",
                      "required": True}),
          "note": ""},
         {"key": "run-check", "title": "管线 dry-run", "argv": ("pipeline", "dryrun", "{pipeline}"),
          "params": ({"name": "pipeline", "label": "管线 .md（仓内路径）", "kind": "path",
                      "required": True},),
          "note": ""},
     )},
    {"key": "4", "id": "validate", "title": "校验与体检",
     "family": "verify",
     "summary": "正文 lint / 状态前置 / 一致性分级 / 模块引用门禁（端壳时代「校验区」）",
     "examples": ("nf lint sample.md", "nf conformance", "nf module verify"),
     "actions": (
         {"key": "conformance", "title": "契约一致性", "argv": ("conformance",), "params": (),
          "note": ""},
         {"key": "layers", "title": "抽象阶梯核验", "argv": ("layers", "--verify"), "params": (),
          "note": ""},
         {"key": "lint", "title": "文档语义体检", "argv": ("lint", "{file}"),
          "params": ({"name": "file", "label": "文档 .md（仓内路径）", "kind": "path",
                      "required": True},),
          "note": ""},
         {"key": "module-verify", "title": "模块门禁", "argv": ("module", "verify"),
          "params": (), "note": ""},
     )},
    {"key": "5", "id": "market", "title": "货架与资产",
     "family": "shelf",
     "summary": "市场浏览（--list）/ 单包详情 / 资产货架 / 供应链台账盘点",
     "examples": ("nf market --list", "nf asset ls", "nf asset inventory"),
     "actions": (
         {"key": "market", "title": "市场货架", "argv": ("market", "--list"), "params": (),
          "note": ""},
         {"key": "asset-ls",
 "title": "资产清单",
 "argv": ("asset",
 "ls"),
 "params": (),
 "note": ""},
         {"key": "asset-density", "title": "资产密度", "argv": ("asset", "density"), "params": (),
          "note": ""},
         {"key": "library-search", "title": "馆藏检索", "argv": ("library", "search", "{query}"),
          "params": ({"name": "query", "label": "关键词", "kind": "text", "required": True},),
          "note": ""},
     )},
    {"key": "6", "id": "pipeline", "title": "管线与模块",
     "family": "shelf",
     "summary": "管线派生（new）/ 抽象执行（dryrun）/ 模块状态位与边界签名",
     "examples": ("nf pipeline new --id P07 --name 演示领域管线", "nf module ls"),
     "actions": (
         {"key": "module-ls", "title": "模块清单", "argv": ("module", "ls"), "params": (),
          "note": ""},
         {"key": "patterns-ls", "title": "模式清单", "argv": ("patterns", "ls"), "params": (),
          "note": ""},
         {"key": "stats", "title": "自述数字核对", "argv": ("stats", "--check"), "params": (),
          "note": ""},
         {"key": "stats-write", "title": "自述数字：重写生成区（写盘）",
          "argv": ("stats", "--write"), "params": (),
          "note": "会改仓库文件，须键入 yes 确认"},
     )},
    {"key": "7", "id": "help", "title": "帮助与命令面",
     "family": "meta",
     "summary": "全命令总览与任意子命令帮助（终端内输入 /help 同效）",
     "examples": ("nf --help", "nf help assemble"),
     "actions": (
         {"key": "help", "title": "命令总览", "argv": ("--help",), "params": (), "note": ""},
         {"key": "help-cmd", "title": "看某命令帮助", "argv": ("help", "{cmd}"),
          "params": ({"name": "cmd", "label": "子命令名", "kind": "text", "required": True},),
          "note": ""},
     )},
    # 表单区：**不留动作字面量**——`forms: True` 表示本区的动作由 `FORMS` 投影而来
    # （`zone_action_dicts`），于是「写盘表单」这张真源只有一个（改表即改视图）。
    # 行模式用 `/form <id>` 逐项追问，全屏视图把它物化成可回车动作。
    {"key": "8", "id": "forms", "title": "写盘表单",
     "family": "meta",
     "summary": "会改仓库的动作逐项追问：表单真源 FORMS 的每一张都是一个可执行动作",
     "examples": (),
     "actions": (),
     "forms": True},
)



#: 能力地图（**策展真源**）：把 CLI 的每个顶层命令恰好归入一个能力族。
#: 菜单（0-8）是新手路径；本表是「全功能可见」的完整分面——两者分工不重叠。
#: check39 与 `nf shell --verify` 共用同一判据：族分区必须恰好覆盖命令集（不缺不重不虚）。
FAMILIES: tuple[dict[str, Any], ...] = (
    {"id": "start", "name": "上手与自检",
     "summary": "第一次进 NF：体检、一键演示、自述数字、抽象阶梯",
     "commands": ("doctor", "demo", "stats", "layers")},
    {"id": "forge", "name": "装配与生产",
     "summary": "从需求到产物：装配、全链管道、渲染、登记、元认知驾驶与离线盲评",
     "commands": ("assemble", "preset", "run", "render", "spec", "register", "import",
                  "cockpit", "cockpit-ab", "agent")},
    {"id": "shelf", "name": "资产与货架",
     "summary": "市场、资产台账、模块生命周期、管线派生、组合引擎、域包工厂、产出形态",
     "commands": ("market", "asset", "module", "pipeline", "combine", "domain",
                  "output", "rename", "resolve")},
    {"id": "verify", "name": "质检与验证",
     "summary": "门禁单进程引擎、正文 lint、一致性报告、断言表、知识签名、评分、差异、解释、状态前置、"
         "发布体检与变更日志生成、许可证、遥测、装配语言 guard 检查/编译",
     "commands": ("verify", "check", "lint", "conformance", "assertions", "sig", "score", "diff",
                  "explain", "st-validate", "release", "changelog", "license", "telemetry",
                  "nfal")},
    {"id": "library", "name": "图书馆与知识",
     "summary": "馆藏存取、双源知识、行话术语、实践包、协议件版本史、引用关系与影响面",
     "commands": ("library", "knowledge", "cognition", "patterns", "rfc",
                  "related", "who-refers", "impact", "wiki", "keywords")},
    {"id": "govern", "name": "治理与决策",
     "summary": "决策记录（ADR）、审计、背书、回执、交接、复盘、决策层、评审、构建回路、批准、透明"
         "日志、证据包（打包/第三方复验）、标注 IR（声明与校验，不写载体）、设计审计、"
         "语言面（本地化与责任方）",
     "commands": ("decisions", "audit", "attest", "receipts", "handover",
                  "postmortem", "decide", "model", "review", "workloop",
                  "approve", "transparency", "evidence", "label", "design", "locales",
                  "cog")},
    {"id": "integrate", "name": "服务与集成",
     "summary": "MCP 服务面、编辑器面、跑分台、端点契约、互操作导出、指令档路由、事件背书、状态前置"
         "、世界模型、模块工具面",
     "commands": ("serve", "lsp", "bench", "endpoint", "interop", "driver",
                  "events", "state-front", "worldmodel", "toolface")},
    {"id": "meta", "name": "命令面与终端",
     "summary": "帮助、补全脚本、终端自身（本命令即在此族）",
     "commands": ("help", "completion", "shell", "terminal", "daemon")},
)




# ---------------------------------------------------------------- 写盘表单
# 「会改仓库」的动作不该要求用户一口气敲全参数、再补一个 `--yes`。表单族把它拆成**逐项追问**：
# 参数真源 = 表单模板（argv 模板里的 `{key}` 由 step 填），执行仍走同一条写盘闸门。
#
# 纪律：每张表的模板只能指向**真实存在的 CLI 动词**（check39 断言 argv[0] 在命令面内）；
# 表单本身不改任何东西——它只把参数问齐，然后交给 CLI 与闸门。

FORMS: tuple[dict[str, Any], ...] = (
    {"id": "deprecate-module", "title": "弃用模块",
     "summary": "把某个模块文件标记为 deprecated（写文件头状态位）",
     "steps": ({"key": "file", "prompt": "模块 md 路径", "required": True, "kind": "path",
                "hint": "如 community/<包>/modules/M97_术语管理.md"},
               {"key": "reason", "prompt": "弃用原因（可空）", "required": False}),
     "argv": ("module", "deprecate", "{file}", "--reason", "{reason}")},
    {"id": "restore-module", "title": "恢复模块",
     "summary": "把 deprecated / retired 的模块恢复为 active",
     "steps": ({"key": "file", "prompt": "模块 md 路径", "required": True, "kind": "path"},),
     "argv": ("module", "restore", "{file}")},
    {"id": "types-write", "title": "补 I/O 类型面",
     "summary": "给有机读契约的模块补 io_types（确定性推导，未命中写 untyped）",
     "steps": (), "argv": ("module", "types", "--write")},
    {"id": "stats-write", "title": "重写自述数字生成区",
     "summary": "按实算重写 README / README.en / llms.txt 统计块与 protocol/repo_stats.json",
     "steps": (), "argv": ("stats", "--write")},
    {"id": "asset-add", "title": "资产入库",
     "summary": "资产文件头写 nf-asset 头 + 台账 append（溯源键表自动生成）",
     "steps": ({"key": "file", "prompt": "资产文件路径（相对 --root）", "required": True,
                "kind": "path"},
               {"key": "key", "prompt": "溯源键（台账内唯一）", "required": True},
               {"key": "source", "prompt": "溯源说明（源文件/区间/登记日期）", "required": True},
               {"key": "root", "prompt": "资产根目录", "required": True, "kind": "path",
                "hint": "如 05_资产库"},
               {"key": "module", "prompt": "消费模块 id（可空）", "required": False},
               {"key": "version", "prompt": "版本位（可空 = 1.0）", "required": False},
               {"key": "tier", "prompt": "货架分级 official/community/experimental（可空）",
                "required": False}),
     "argv": ("asset", "add", "{file}", "--key", "{key}", "--source", "{source}",
              "--root", "{root}", "--module", "{module}", "--version", "{version}",
              "--tier", "{tier}")},
    {"id": "register-apply", "title": "本地登记写回",
     "summary": "protocol.yaml → registry protocols[]（校验全过后只增不删合并写）",
     "steps": ({"key": "pkg_dir", "prompt": "包目录", "required": True, "kind": "path",
                "hint": "如 community/校园西幻轻混组合包"},),
     "argv": ("register", "{pkg_dir}", "--apply")},
    {"id": "rename-apply", "title": "模块改名重链",
     "summary": "批量更新 references 中对该模块的引用后写回",
     "steps": ({"key": "old_id", "prompt": "旧模块 id", "required": True},
               {"key": "new_id", "prompt": "新模块 id", "required": True}),
     "argv": ("rename", "{old_id}", "{new_id}", "--apply")},
    {"id": "receipts-write", "title": "重签协议层回执",
     "summary": "内容改动后重新冻结 protocol/RECEIPTS.json（随后通常重跑 conformance / 批准）",
     "steps": (), "argv": ("receipts", "--scope", "protocol", "--write")},
    # ---- 第二批（2026-10-01）：把「已入闸但没表」的常用写面补成组装式命令 ----
    # 依据：闸门表（CONFIRM_VERBS / CONFIRM_FLAGS / CONFIRM_FLAG_PAIRS）是写面的**穷举真源**，
    # 而表单此前只覆盖其中 8 张 ⇒ 其余写面在终端里只能手敲全参数。本批先补 agent 高频的四类，
    # 其余逐条登记在 `FORM_EXEMPT`（写明「为什么不为它建表」），由判据保证「写面必有去处」。
    {"id": "preset-save",
 "title": "保存预设",
 "summary": "把一条装配清单存成本机预设（落在 NF_HOME，非仓库）",
     "steps": ({"key": "name", "prompt": "预设名", "required": True, "hint": "如 西幻生存-最小"},
               {"key": "pipeline",
 "prompt": "管线 id（可空）",
 "required": False,
 "hint": "如 P04"},
               {"key": "modules", "prompt": "模块 full_id，逗号分隔（可空）", "required": False,
                "hint": "如 通用类:M00,轻混类:M91"},
               {"key": "assets", "prompt": "资产包名（可空）", "required": False},
               {"key": "force",
 "prompt": "要覆盖同名预设就填 --force，否则留空",
 "required": False}),
     "argv": ("preset", "save", "{name}", "--pipeline", "{pipeline}", "--modules", "{modules}",
              "--assets", "{assets}", "{force}")},
    {"id": "library-deprecate", "title": "馆藏条目弃用",
     "summary": "生命周期流转 → deprecated（不再推荐、仍可读）",
     "steps": ({"key": "entry", "prompt": "馆藏编号", "required": True, "hint": "如 NF-1"},),
     "argv": ("library", "deprecate", "{entry}")},
    {"id": "library-restore", "title": "馆藏条目回退",
     "summary": "生命周期回退 → active",
 "steps": ({"key": "entry",
 "prompt": "馆藏编号",
 "required": True},
),
     "argv": ("library", "restore", "{entry}")},
    {"id": "pipeline-new", "title": "派生新管线",
     "summary": "自 P00 骨架派生新管线（改 id/name/领域标签；登记 02 与填层名挂载按 README 三步）",
     "steps": ({"key": "id", "prompt": "新管线 id", "required": True, "hint": "如 P07"},
               {"key": "name", "prompt": "显示名", "required": True, "hint": "如 演示领域管线"},
               {"key": "from", "prompt": "模板管线 md（可空 = 03_管线库/P00…）", "required": False,
                "kind": "path"},
               {"key": "domain", "prompt": "领域标签（可空）", "required": False},
               {"key": "dest", "prompt": "输出路径（可空 = 官方管线位）", "required": False,
                "kind": "path"}),
     "argv": ("pipeline", "new", "--id", "{id}", "--name", "{name}", "--from", "{from}",
              "--domain", "{domain}", "--dest", "{dest}")},
    {"id": "approve-subject", "title": "批准内容绑定",
     "summary": "给被批准对象落一条批准记录（protocol/approvals/*.json）",
     "steps": ({"key": "subject", "prompt": "被批准对象路径（仓库相对）", "required": True,
                "kind": "path"},
               {"key": "by", "prompt": "批准人标识（可空）", "required": False},
               {"key": "note", "prompt": "批准说明（可空）", "required": False}),
     "argv": ("approve", "{subject}", "--by", "{by}", "--note", "{note}")},
)




#: 已入闸但**刻意不建表**的写面 → 理由（逐条点名）。判据：闸门表里的每一项要么有表、要么在这里
#: 有理由，否则红——这样新写面不会「悄悄没有组装式入口」（2026-10-01：表单只覆盖 8/30 个写面，
#: 而没有任何判据盯着这个比例）。
FORM_EXEMPT = {
    "--build": "输出类：`assemble --build` 的产物形态随需求变，一表装不下（闸门仍拦）",
    "--certify": "输出类：`combine plan --certify` 与组合证书绑定，参数由组合面推导",
    "--dest": "输出类：落点随命令而异，手敲路径比填表更快",
    "--fix": "机械修复：`lint --fix` 就地改源件，先跑 `lint` 看清单再决定",
    "--harvest": "登记类：`module types --harvest` 与 I/O 类型面绑定，属批量维护",
    "--out": "输出类：`interop --out` / `attest --out` 等落点由用例决定",
    "--register": "登记类：`import --register` 载荷来自外部件，先落盘再登记",
    "--save": "输出类：`assemble --save` 写用户命名的档案文件",
    "--write-advisory": "输出类：`pipeline dryrun --write-advisory` 写 advisory 台账",
    "--write-baseline": "基线类：`score --write-baseline` 重签回归基线，签发是评审动作",
    "asset deprecate": "货架维护：条目少、动作一次性，`nf asset ls` 后手敲更直接",
    "asset restore": "货架维护：同上（恢复路径带原层级，表单装不下）",
    "asset rm": "货架维护：删除类动作刻意不给一键表（留一步手敲）",
    "decisions reindex": "维护类：全量重建索引，一次一条命令即可",
    "import": "入库类：载荷是外部 SKILL.md / chara.json，路径与来源逐次不同",
    "knowledge transform": "维护类：`knowledge transform` 写 protocol/transform_log.json",
    "library attest": "签名类：要 `--key-file` / `--ssh-key`，密钥路径不该进表单回放",
    "library reindex": "维护类：全量重建索引（改 frontmatter 后跑一次）",
    "library supersede": "生命周期：取代链要指向新条目，取舍由作者判断",
    "module signature": "签名类：`module signature` 要密钥/身份件，同上",
    "patterns reindex": "维护类：实践包索引全量重建",
    "preset import": "本机态：导入要外部文件路径，`,` 与 `--store` 由使用场景决定",
    "preset rm": "本机态：与 `preset ls` 成对，手敲一眼确认删的是哪条",
    "release": "发布类：动词 `release` 改模块发布位，属评审动作",
    "interop --all": "导出类：`interop --all` 一条命令落全量 12 面，无需参数组装",
    "assemble --trace": "遥测类：trace 文件由上一次 `--trace` 产出，路径逐次不同",
    "assemble --session": "会话类：`--session` 要绝对路径且不得落仓库内（硬闸），表单帮不上",
    "--surface-write": "生成器类：`nf shell --surface-write` 把终端面真源投影成生成件，"
                        "落点只有一项且内容由真源确定性重算（`nf shell --surface` 可先看结果），"
                        "逐项追问给不出额外安全边际",
}
