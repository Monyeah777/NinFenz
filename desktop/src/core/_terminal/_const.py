"""terminal · _const（自 terminal.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

from collections import namedtuple

SHELL_VERSION = "1.0.0"



#: 会话提示符（单行、无颜色——重定向到文件时逐字节可读）
PROMPT = "nf> "


#: 退出词（大小写不敏感）
QUIT_WORDS = ("quit", "exit", "q", "退出", "再见")


#: 确认词（写入类命令的显式放行）
YES_WORDS = ("y", "yes", "ok", "是", "确认", "可以")



#: 需要显式确认的写入面标记（命令里出现任一即视为写盘/不可逆动作）
CONFIRM_FLAGS = ("--write", "--apply", "--register", "--force",
                 "--out", "--dest", "--build",
                 # 2026-10-01 补：**写盘但不叫 `--write`** 的三个旗标——按 help 清点「收文件/
                 # 写产物的旗标」时逐个核对 `needs_confirm` 抓到（此前 shell 里可无确认改仓库）：
                 #   `--write-baseline`（nf score 重签回归基线）、`--fix`（nf lint 机械修复
                 #   **就地改源件**）。
                 "--write-baseline", "--fix",
                 # 2026-10-01 三补（**机械枚举全部旗标**后逐条核对写 sink 抓到）：上一轮是
                 # 按「已知写旗标名」清的（`--write*` / `--re-sign` / `--fix`），漏掉了三个
                 # **不带任何 `--write` 语义**却直接改仓库的旗标：
                 #   `nf module types --harvest`  → 写 `protocol/event_registry.json`
                 #   `nf pipeline dryrun --write-advisory` → 写 `protocol/pipeline_advisory.json`
                 #   `nf combine plan --certify`  → 写 `protocol/combo_certificates.json`
                 # 外加一个「写你自己命名的文件」的旗标（与已入闸的 `--out` 同类）：
                 #   `nf assemble … --save <文件>`（可给仓库相对路径 ⇒ 在 shell 粘贴面里能落仓）。
                 "--harvest", "--write-advisory", "--certify", "--save",
                 # 2026-10-03 补（终端面单真值源波）：`nf shell --surface-write` 把终端面真源
                 # 投影成生成件 `tui/_surface.py`——**它写仓库**，故按同一口径登记为写面标记。
                 # 本旗标只属于 `shell` 自身，而 `shell` 在会话内被拒跑（`BLOCKED_IN_SHELL`），
                 # 所以它在闸门里的作用面正是 `needs_confirm` 写明的那条：**文本驱动面**
                 # （`--exec` / `--file` / 交互输入）里出现该旗标即须显式确认；显式 argv 直跑
                 # 与其余写面同待遇（不额外设闸）。表单侧不建追问表，理由见 `FORM_EXEMPT`。
                 "--surface-write")


#: 2026-10-01 清掉 5 个**死条目**（表里有、`nf` 的 argparse 面里没有）：`--tag` / `--push` /
# : `--delete` / `--rm` / `--re-sign`——都是更早版本的残影（`nf release` 如今是 `--fast` / `--plan` /
# `--freeze [--apply]`；
#: `nf asset baseline` 的重签旗标是 **`--write`**，已被上面那条覆盖，行为面并没有因此漏拦）。
#: 死条目的害处不是漏拦（它们匹配不到任何东西），而是**误导读者的口径**：文档写着「命中
#: `--re-sign` 才需要确认」，读者照着敲只会拿到用法错误。判据见 `test_write_flag_gate`：闸门
#: 三表的每一条都必须真在 argparse 面里（本类问题由它兜住）。
#: 需要显式确认的 (命令, 子命令) 组合（无标记位也写盘的动词）
CONFIRM_VERBS = (("asset", "add"), ("asset", "rm"), ("asset", "deprecate"),
                 ("module", "deprecate"), ("module", "restore"),
                 ("module", "signature"), ("register", ""), ("import", ""),
                 ("rename", ""), ("release", ""),
                 # 2026-09-30 补：这些动词**不带 `--write` 也直接改仓库件**（投影重建 / 生命周期
                 # 流转 / frontmatter 落锚 / 派生新件），此前只在 `CONFIRM_FLAGS` 里找标记位，
                 # 于是 `nf shell --exec "nf library deprecate <id>"` 这类**无标记写盘**漏过闸门。
                 ("pipeline", "new"), ("decisions", "reindex"), ("patterns", "reindex"),
                 ("library", "reindex"), ("library", "deprecate"), ("library", "restore"),
                 ("library", "supersede"), ("library", "attest"),
                 # 2026-10-01 补：`nf approve <对象> --by <人>` 会写**批准记录**
                 # （`protocol/approvals/*.json`）——那是治理/问责产物，且**不带任何写旗标**，
                 # 此前在 shell 里可无确认落一条批准。
                 ("approve", ""),
                 # 2026-10-01 再补（**机械枚举**变异类子命令后逐条核对 `needs_confirm` 抓到）：
                 #   `nf asset restore` 与 `nf asset deprecate` 同型（改台账 + 资产文件头），
                 #   但动词表里只登记了 deprecate ⇒ 恢复方向漏过闸门；
                 #   `nf knowledge transform add|promote` 会写 `protocol/transform_log.json`
                 #   （消化记录），同样不带旗标。
                 ("asset", "restore"), ("knowledge", "transform"),
                 # 2026-10-01 新增 `nf preset` 面时的同步登记：`save` / `rm` / `import` 会改
                 # **本机预设库**（`<NF_HOME>/presets/*.json`）——与 `library deprecate` 同型
                 # （无旗标、直接改状态），`ls` / `show` / `apply` 是只读解析面，不入闸。
                 ("preset", "save"), ("preset", "rm"), ("preset", "import"))


#: 「某命令 + 某旗标」才写盘的组合：同一旗标在别的命令上是只读（`pipeline --all` 只扫不改），
#: 故不能把 `--all` 放进 `CONFIRM_FLAGS`。
#: 「某命令 + 某旗标」才写盘的组合：同一旗标在别的命令上是只读，故不能放进 `CONFIRM_FLAGS`。
#: - `interop --all`：只扫不改（`--all` 在别处是只读全集），只有 interop 的面才是落盘全集；
#: - `assemble --trace` / `--session`：这两个旗标在 `nf knowledge frequency --trace` 与
#:   `nf shell --session` 上是**读/仓外受控**（shell 那条另有「必须绝对路径且不得落仓库内」的
#:   硬闸），只有 `nf assemble` 的这两条会**写你自己命名的文件**（可仓库相对 ⇒ 粘贴面能落仓）。
CONFIRM_FLAG_PAIRS = (("interop", "--all"),
                       ("assemble", "--trace"), ("assemble", "--session"),
                       # 2026-11-08：cog claim --sheet 写「证据作业单」文件（与 --out 同型
                       # 的落点），必须过确认闸；同旗标在 claim-check 上是读作业单，故用组合表
                       ("cog", "--sheet"))


#: 会话内不直接执行：长驻/递归/需独占终端的动词 → 给指引
BLOCKED_IN_SHELL = {
    "shell": "终端内不再开终端（避免递归会话）：请另开一个终端窗口运行 nf shell。",
    "serve": "serve 是长驻 MCP 服务（会占住当前终端）：请另开终端运行 "
             "nf serve <快照.json>，本终端可继续用只读命令面。",
    # 2026-10-01 补：`lsp` 与 `serve` **同型**——常驻 stdio 服务，`LspServer.serve()` 是
    # `while True: stdin.readline(...)`，交互会话里跑它会**静默占住终端**（实测：给空 stdin
    # 才立刻退；活终端会一直等帧）。此前只拦了 serve，本条按同一口径补齐。
    "lsp": "lsp 是常驻 stdio 服务（等编辑器发 Content-Length 帧，会占住当前终端）："
           "请由编辑器/IDE 直接拉起（nf lsp），本终端可继续用只读命令面。",
}


#: 别名单源：`nf terminal` 是 `nf shell` 的 argparse 别名（`add_parser("shell",
#: aliases=["terminal"])`）。此前只有 `_cmd_shell` 内部自己认这两个拼写，会话层的
#: `BLOCKED_IN_SHELL` 查不到 `terminal` ⇒ 会**先执行再被 handler 拒**（结果一样，但拦截点晚
#: 一拍）。这里补上别名键、消息仍只有一份（引用同一条），两种拼写都在**执行前**拦下。
BLOCKED_IN_SHELL["terminal"] = BLOCKED_IN_SHELL["shell"]



#: 一行输入的解析结果：kind ∈ empty/quit/help/menu/zone/run/unknown
Intent = namedtuple("Intent", "kind payload raw")



#: 斜杠命令词表（`/` 后首个词）：既是 `/x` 形态的判据，也是 MSYS 还原的判据
SLASH_WORDS: tuple[str, ...] = ("quit", "exit", "q", "help", "?", "menu", "菜单",
               "zone", "z", "区", "doctor", "自检", "version", "ver", "版本",
               "find", "search", "找", "查", "commands", "cmd", "cmds", "命令",
               "map", "families", "族", "地图",
               "history", "hist", "历史", "complete", "补全",
               "set", "settings", "设置",
               "form", "forms", "表单", "cancel", "取消")


SLASH_WORDS = SLASH_WORDS + ("replay", "重放")




# ---------------------------------------------------------------- 输出体验
# 顶尖 CLI 的观感三件：**列宽对齐**（CJK 按两个显示宽度算）、**长列表可收**（限长 + 提示）、
# **颜色克制**（默认只在真 TTY 上色，`NO_COLOR` 一票否决；非 TTY 逐字节确定——这是硬契约）。

#: East Asian Wide / Fullwidth 码位区间（UAX #11 的实用子集；emoji 走宽）
_WIDE_RANGES = (
    (0x1100, 0x115F), (0x2E80, 0x303E), (0x3041, 0x33FF), (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF), (0xA000, 0xA4CF), (0xAC00, 0xD7A3), (0xF900, 0xFAFF),
    (0xFE10, 0xFE19), (0xFE30, 0xFE6F), (0xFF00, 0xFF60), (0xFFE0, 0xFFE6),
    (0x1F300, 0x1F64F), (0x1F900, 0x1F9FF), (0x20000, 0x2FFFD), (0x30000, 0x3FFFD),
)


#: 结构着色（ANSI）：只在 color=True 时生效；语义固定、可复算
_STYLES = {"head": "\033[1m", "cmd": "\033[36m", "ok": "\033[32m",
           "warn": "\033[33m", "fail": "\033[31m", "dim": "\033[2m"}


_RESET = "\033[0m"




#: 会话状态文件 schema（`--session <file>`；仅显式给出时读写）
SESSION_SCHEMA = "nf-shell-session/1"




# ---------------------------------------------------------------- 顶尖 CLI 基线
# 「对标最顶尖 CLI」若只停在观感上，就没法判完成。这一节把它摊成**可复跑的证据表**：
# 每行 = 一项能力 + 一条证据命令（+ 必须出现/必须不出现的片段）；`nf shell --baseline` 逐行跑、
# verify check39 逐行断言——「顶尖」于是是逐条可核的事实。行只许用**仓库内真实存在**的入口
# （argv[0] 必须是 shell），且必须**只读**（不许带写盘旗标）。

#: 基线里的受控临时路径占位：展开为系统临时目录下的固定目录（**仓库之外**，不污染工作区）。
BASELINE_TMP = "{TMP}"



#: 每行证据的**默认延迟预算**（毫秒）：超时即判「效率退化」——把「极致效率」变成门禁。
#: 标定方法：单跑实测（机器空闲）后留 100× 以上余量——轻行实测 ~1-2 ms，预算 300 ms，
#: 既能容忍负载抖动，又能拦住**数量级回归**（例：解析器缓存失效会让轻行从 ~2 ms 涨到 ~300 ms
#: 量级；全命令扫描从 ~0.3 s 涨回 ~11 s，那一行另有 BASELINE_DEEP_MAX_MS 预算兜底）。
BASELINE_DEFAULT_MAX_MS = 300


#: 活体深检行的预算。**2026-09-29 实测重标 2000 → 6000**：该行主成本是**全仓抽象阶梯扫描**
#: （`nf layers --verify` 空闲 ~0.5–1.7 s / 本机满载 2.4–3.7 s），旧注「~320 ms × 6」的前提
#: 已不成立（2000 ms 实余 1.15×、同一棵树一次绿一次红）；6000 ≈ 3.5× 空闲余量，仍拦 ~11 s 级回归。
BASELINE_DEEP_MAX_MS = 6000



#: 基线的写盘禁令：证据行只许只读（出现这些旗标即视为基线自身违规）
BASELINE_FORBIDDEN_FLAGS = ("--write", "--apply", "--register", "--yes", "--force",
                            "--tag", "--rm", "--delete")




# ---------------------------------------------------------------- 补全与历史
# 顶尖 CLI 终端的体感差距主要在这两件：**打一半能补**、**翻得回上一轮**。
# 约束：core 零第三方依赖——`readline` 是 stdlib 但 Windows 无该模块，故补全判据本身
# 做成**纯函数**（任何平台都能用：`/complete <前缀>` 与行尾 Tab 都吃），readline 只在
# 可用时接管（POSIX），不可用则退化为候选列表。

#: 斜杠命令的展示词表（补全用）：只列拉丁规范词，中文别名仍可直接输入
SLASH_HELP = (
    ("menu", "能力菜单"), ("map", "能力地图（8 族）"), ("find", "检索命令面"),
    ("commands", "列出全部命令"), ("zone", "看某能力区示例"), ("help", "CLI 帮助面"),
    ("history", "看历史（可给条数）"), ("complete", "补全（可给前缀）"),
    ("doctor", "环境自检"), ("version", "版本"), ("quit", "退出"),
)




# ---------------------------------------------------------------- 终端面投影（单真值源 → 多视图）
# 单真值源 = 本模块的策展表（ZONES / FAMILIES / FORMS / 写盘闸门三表 / BLOCKED_IN_SHELL）
#            + `scripts/nf.py` 的 argparse 面（命令的**存在性**）。
# 多视图   = ① 行模式 `nf shell`：菜单示例 / 能力族 / 写盘表单
#            ② 全屏 `tui/nf.py`：动作目录（把 ZONES[].actions 物化成可回车执行的动作）
#            ③ 机器面 `nf shell --surface --json`：给 agent 与门禁的整面快照
#            ④ 生成件 `tui/_surface.py`：全屏视图在源码态与冻结态的**唯一输入**（零 core 依赖）
# 为什么要有这一节：全屏 TUI 冻结成单文件 exe，**不能 import core**，于是曾把命令白名单、
# 写盘闸门与动作目录**各手抄一份**。手抄件的代价当场可见——它漏了 `CONFIRM_FLAG_PAIRS`，
# 即 `nf interop --all` / `nf assemble --trace` 这类「命令 + 旗标才写盘」的面在全屏视图里
# **不确认就执行**；而两份表只在 TUI 自检时比对，平时可以静默漂移。
# 口径：视图只许**投影**真值，不许各自留表；漂移由 check39（生成件逐字节）+ 单测当场判红。

SURFACE_SCHEMA = "nf-terminal-surface/1"


#: 投影件规范落点（`nf shell --surface-write` 的缺省目标，check39 也按这里对账）
SURFACE_MODULE_PATH = "tui/_surface.py"


#: 投影源件（人读元信息；机器判据只认本模块的表 + argparse 面）
SURFACE_SOURCE = {
    "module": "desktop/src/core/terminal.py",
    "tables": ["ZONES", "FAMILIES", "FORMS", "CONFIRM_FLAGS", "CONFIRM_VERBS",
               "CONFIRM_FLAG_PAIRS", "BLOCKED_IN_SHELL"],
    "commands": "scripts/nf.py 的 argparse 面",
}




#: 生成件抬头（人读纪律写在件内，免得后人把它当手写表改）
SURFACE_MODULE_HEAD = '''"""NF 终端面投影（**生成件 · 请勿手改**）。

真源：desktop/src/core/terminal.py 的策展表（ZONES / FAMILIES / FORMS / 写盘闸门三表 /
      BLOCKED_IN_SHELL）+ scripts/nf.py 的 argparse 面（命令存在性）。
生成：python scripts/nf.py shell --surface-write tui/_surface.py
判据：verify check39「投影与真源同步」+ desktop/tests/test_nf_tui.py
——本件被手改、或真源改了没重生成，都会在判据里当场判红（重算后逐字节比对）。
"""'''
