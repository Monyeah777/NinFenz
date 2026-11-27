"""terminal · _parse（自 terminal.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import shlex

from ._catalog import (
    zone_by_key,
)
from ._const import (
    CONFIRM_FLAG_PAIRS,
    CONFIRM_FLAGS,
    CONFIRM_VERBS,
    QUIT_WORDS,
    SLASH_WORDS,
    Intent,
)


def _slash_intent(body: str, raw: str):
    """解析斜杠命令体 → Intent；非斜杠命令词返回 None（调用方决定怎么归类）。"""
    head, _, tail = body.partition(" ")
    head = head.lower()
    if head in ("quit", "exit", "q"):
        return Intent("quit", "", raw)
    if head in ("help", "?"):
        return Intent("help", tail.strip(), raw)
    if head in ("menu", "菜单"):
        return Intent("menu", "", raw)
    if head in ("zone", "z", "区"):
        return Intent("zone", tail.strip(), raw)
    if head in ("doctor", "自检"):
        return Intent("run", ["doctor"], raw)
    if head in ("version", "ver", "版本"):
        return Intent("run", ["--version"], raw)
    if head in ("find", "search", "找", "查"):
        return Intent("search", tail.strip(), raw)
    if head in ("commands", "cmd", "cmds", "命令"):
        return Intent("commands", tail.strip(), raw)
    if head in ("map", "families", "族", "地图"):
        return Intent("map", tail.strip(), raw)
    if head in ("history", "hist", "历史"):
        return Intent("history", tail.strip(), raw)
    if head in ("complete", "补全"):
        return Intent("complete", tail.strip(), raw)
    if head in ("set", "settings", "设置"):
        return Intent("set", tail.strip(), raw)
    if head in ("form", "forms", "表单"):
        return Intent("form", tail.strip(), raw)
    if head in ("cancel", "取消"):
        return Intent("cancel", tail.strip(), raw)
    if head in ("replay", "重放"):
        # `/replay`（无参数）= 列清单；`/replay n` / `/replay 前缀` = 重放
        return Intent("replay-list" if not tail.strip() else "replay", tail.strip(), raw)
    return None




def split_args(text: str) -> list:
    """把一行命令拆成 argv；兼容带引号的需求文本。拆分失败退回朴素空白切分。"""
    try:
        return shlex.split(text, posix=True)
    except ValueError:
        return text.split()




def _strip_nf(argv: list) -> list:
    """剥掉可选的 `nf` / `nf.py` 前缀——终端里两种写法都吃。"""
    if argv and argv[0] in ("nf", "nf.py"):
        return argv[1:]
    return argv




def _strip_comment(line: str) -> str:
    """剥掉行内注释：`#` 位于**词首**（行首或前一字符为空白）且不在引号内时起始注释。

    与 shell 同语义（`echo a # x` 的 `#` 起注释，`echo "a # x"` 的不算）——脚本文件面
    因此可以自注释，而带 `#` 的引号参数（如装配需求文本）不会被吃掉。
    """
    out, quote, prev = [], None, " "
    for ch in str(line):
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            prev = ch
            continue
        if ch == "#" and prev.isspace():
            break
        out.append(ch)
        prev = ch
    return "".join(out)




def parse(line: str) -> Intent:
    """解析一行输入 → Intent。

    支持四类：`/` 命令（/help /menu /quit /zone <k>）、裸菜单键（0-7）、
    `nf <args...>` 直通、纯 quit 词。其余为 unknown（由调用方给指引）。
    行内注释（词首 `#`）与行尾续行由调用方先行处理；此处只做语句解析。
    """
    raw = _strip_comment(line).strip()
    if not raw:
        return Intent("empty", "", raw)
    if raw.lower() in QUIT_WORDS:
        return Intent("quit", "", raw)
    if raw.startswith("!"):
        # `!!` = 上一条（剥掉全部前导 `!`）；`!n` = 第 n 条；`!前缀` = 最近一条前缀命中
        return Intent("replay", raw.lstrip("!").strip(), raw)
    if raw.startswith("/"):
        hit = _slash_intent(raw[1:].strip(), raw)
        return hit if hit is not None else Intent("unknown", raw, raw)
    if raw.isdigit() and zone_by_key(raw) is not None:
        return Intent("zone", raw, raw)
    argv = _strip_nf(split_args(raw))
    if not argv:
        return Intent("empty", "", raw)
    if argv[0] in ("quit", "exit"):
        return Intent("quit", "", raw)
    # MSYS/Git-Bash 兼容：`"/zone 4"` 这类以 `/` 开头的参数会被通行层当成 POSIX 路径
    # 转换成 `C:/…/zone 4`（单 token 的 `/menu` 不受影响）。若首 token 的**末段**是斜杠
    # 命令词，就还原成该命令——否则 Git Bash 用户会看到一条莫名其妙的 argparse 报错。
    head_path = argv[0].replace("\\", "/")
    if "/" in head_path:
        seg = head_path.rsplit("/", 1)[-1].lower()
        if seg in SLASH_WORDS:
            hit = _slash_intent(" ".join([seg] + [str(a) for a in argv[1:]]), raw)
            if hit is not None:
                return hit
    return Intent("run", argv, raw)




def needs_confirm(argv: list) -> bool:
    """判定一条命令是否属于写入/不可逆面（须显式确认才放行）。

    **闸门守的是「文本驱动」的面（2026-10-01 实测后写明）**：交互输入、`nf shell --exec`、
    `nf shell --file` —— 这三条都可能承载**粘贴/注入**进来的文本，机器不替人判断「这行该不该
    跑」。而**显式 argv** 的面不设这道闸：`nf <cmd> …` 直跑与 `nf daemon exec <argv>` 等价于
    操作者自己敲的命令（后者文档即写明「输出/退出码与直跑一致」）。实测对照：
    `nf shell --exec "nf stats --write"` → **exit 2（拒）**、`nf shell --file <含写命令的脚本>`
    → 同（两者加 `--yes` 即显式放行）；`nf daemon exec stats --write` → 照跑。

    **改口径要两边一起改**：谁要动这条边界（例如也给 `daemon exec` 加确认），必须同时更新本
    段说明与 CHANGELOG——不要只改一边，那会让「闸门到底守哪条面」重新变成无人可查的问题。
    """
    if any(tok in CONFIRM_FLAGS for tok in argv):
        return True
    if not argv:
        return False
    head = argv[0]
    sub = argv[1] if len(argv) > 1 and not argv[1].startswith("-") else ""
    if (head, sub) in CONFIRM_VERBS or (head, "") in CONFIRM_VERBS:
        return True
    return any((head, tok) in CONFIRM_FLAG_PAIRS for tok in argv)




def example_resolves(example: str, commands, root_flags) -> bool:
    """菜单示例是否指向**真实**命令面（commands/root_flags 由调用方从 argparse 面传）。

    单一判据：verify check39 与单测都调本函数——菜单不许指向死命令，判据只有一处实现。
    """
    intent = parse(example)
    if intent.kind != "run" or not intent.payload:
        return False
    head = intent.payload[0]
    return head in set(commands) or head in set(root_flags)




# ---------------------------------------------------------------- 命令面检索
# 「最全功能」的瓶颈不是命令少，而是**找不到**：CLI 有 60+ 顶层命令、70+ 二级子命令，
# 菜单只能覆盖入口。这一节提供确定性检索/列出/纠错，索引由 CLI 侧从 argparse 面派生
# （terminal 不 import scripts/nf.py，保持 core 不反向依赖）。

def _lev(a: str, b: str) -> int:
    """编辑距离（确定性；用于拼错建议）。"""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]




def did_you_mean(word: str, names, limit: int = 3) -> list:
    """最近的候选名（距离 ≤3），按（距离, 名称）排序——拼错时给建议而不是甩 usage。"""
    word = str(word or "").strip().lower()
    if not word:
        return []
    scored = [( _lev(word, str(n).lower()), str(n)) for n in names]
    hits = [(d, n) for d, n in scored if d <= 3 and d > 0]
    hits.sort()
    return [n for _d, n in hits[:limit]]




def search(index, query: str, limit: int = 8) -> list:
    """在命令面上检索 → [(score, entry)]（确定性：分数降序、路径升序）。

    打分档（不引入模糊权重谜团，全部可复算）：精确名 100 > 名前缀 80 > 名含 60 >
    摘要含 40 > 名称近似（编辑距离 ≤2）35-5·d。空查询 → 按路径列出前 limit 条。
    """
    q = str(query or "").strip().lower()
    entries = list(index or [])
    if not q:
        return [(0, e) for e in sorted(entries, key=lambda x: str(x.get("path")))[:limit]]
    out = []
    for e in entries:
        path = str(e.get("path") or "")
        low = path.lower()
        head = low.split(" ")[0]
        summary = str(e.get("summary") or "").lower()
        score = 0
        if low == q or head == q:
            score = 100
        elif low.startswith(q) or head.startswith(q):
            score = 80
        elif q in low:
            score = 60
        elif q in summary:
            score = 40
        else:
            d = min(_lev(q, head), _lev(q, low))
            if d <= 2:
                score = 35 - 5 * d
        if score:
            out.append((score, e))
    out.sort(key=lambda x: (-x[0], str(x[1].get("path"))))
    return out[:limit]
