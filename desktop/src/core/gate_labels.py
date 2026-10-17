#!/usr/bin/env python3
"""从 `verify.sh` **结构化抽取**各 check 的逐字文案与「成功路径」。

为什么要单独成层（2026-10-15 实测）
------------------------------------
门禁引擎（`core/gate_engine.py`）要与 `verify.sh` **逐字等价**，就不能手抄文案——手抄必然漂移。
第一版手抄时 check27 等几条立刻与真源不符，差分测试当场抓出。故文案改为**现读现抽**：
本模块把「banner / 成功文案 / 失败前缀」从 bash 源码里解析出来。

而解析 bash 的分支语义**比看起来难**，实测踩过的坑都记在下面，故它值得独立成件：

1. `then` 分支可能是空壳 `:`（check20）⇒ 成功面只有收尾那一条 ok，不能无条件发两条；
2. `ok` 的单/双引号都有人用（check13 用双引号）⇒ 只认单引号会**整条丢**；
3. `then ok '…'` 在按 `;` 切词时是**一个分段** ⇒ 不把 `then` 切成独立词就**永远看不到那条 ok**；
4. 换行续行 `\\` + `\\"` 转义（check13）⇒ 不处理会把文案截在反斜杠上；
5. 按行数而不是按词认 `if` ⇒ 单行 `if … fi` 把深度算负，**吞掉后面所有 ok**；
6. heredoc 里嵌的 Python `if` 不是 shell 分支 ⇒ 必须先挖掉 heredoc 段再扫分支。

纪律：本模块只**读**；不执行、不写盘；同输入同输出。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


def check_body(text: str, num: int) -> str:
    """机械切出 `checkN(){ … }` 的函数体（第 0 列的独占 `}` 收尾）。

    不用花括号计数：heredoc 里的 Python 字典字面量会让计数失真。
    """
    lines = text.splitlines()
    head = "check%d(){" % num
    i = next((k for k, ln in enumerate(lines) if ln == head), None)
    if i is None:
        return ""
    for j in range(i + 1, len(lines)):
        if lines[j] == "}":
            return "\n".join(lines[i:j + 1])
    return ""


_BANNER_RE = re.compile(r"""echo\s+'(== \[[^']*)'""")


def banner(text: str, num: int) -> str:
    """banner 文本也从 verify.sh 抽（与门禁输出逐字对齐，供差分比对）。"""
    m = _BANNER_RE.search(check_body(text, num))
    return m.group(1) if m else "== [%d/?] (未取到 banner) ==" % num


#: 一条 check 的**逐字**文案。
@dataclass
class Labels:
    ok: list[str]              # body 里全部 `ok '…'` 字面量（取证用）
    then_ok: str               # 成功路径第一条（= pass_lines[0]）
    final_ok: str              # 成功路径最后一条（多用于收尾统计行）
    fail_prefix: str           # `no "…$` 的前缀
    pass_lines: list[str] = field(default_factory=list)   # 成功时逐条打出的 PASS 文案

    @property
    def success(self) -> str:
        return self.then_ok or self.final_ok or (self.ok[0] if self.ok else "")


def _join_continuations(text: str) -> str:
    """把 bash 的 `\\<换行>` 续行折叠成一行（**必须**，否则文案被截断）。"""
    return text.replace("\\\n", " ")


def _ok_literals(text: str) -> list[str]:
    """抽出全体 `ok` 文案（单/双引号都认）。

    本仓两种引号都在用——check13 的版本一致性是 `ok "协议版本两处一致…"`；
    早期只认单引号，那条 PASS 被整条丢掉，差分测试当场抓住。
    """
    return [(m.group(1) or m.group(2) or "")
            for m in _OK_RE.finditer(_join_continuations(text))]


#: `ok '…'` 或 `ok "…"`；引号内的 `\"` 是**转义**、不是结束（check13 写的就是 `\"$v02\"`，
#: 早期正则在这里提前收尾，文案被截成 `…registry.json = \`）。
_OK_RE = re.compile(r'''ok\s+(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")''')


def _heredoc_ranges(lines: list[str]) -> list[tuple[int, int]]:
    """所有 heredoc 的 (起始行, 结束行) —— 用于把「shell 结构行」与「嵌入代码」分开。

    为什么要分开：嵌入的 Python 里也有 `if/else`，若不排除，按词扫分支会张冠李戴。
    """
    spans: list[tuple[int, int]] = []
    i = 0
    while i < len(lines):
        m = _HEREDOC_START_LINE.search(lines[i])
        if not m:
            i += 1
            continue
        marker = m.group(1)
        for j in range(i + 1, len(lines)):
            if lines[j].strip() == marker:
                spans.append((i, j))
                i = j + 1
                break
        else:
            i += 1
    return spans


#: heredoc 起始行：**不要写成 `^\s*.*"…"`**——`\s*` 与 `.*` 匹配集重叠，不命中时指数级
#: 重分配起点（65536 字符实测 1598 ms > 本仓 redos_scan 的 1500 ms 预算，被判红）。
_HEREDOC_START_LINE = re.compile(r'^.*"\$PY3"\s+-\s+<<\'(\w+)\'')


def _reachable_oks(lines: list[str], spans: list[tuple[int, int]]) -> list[str]:
    """按 bash 的**分支语义**算出「成功路径上会执行的 ok」，按文档顺序。

    实现：先挖掉 heredoc 段（嵌入代码里的 `if/else` 不是 shell 分支），再把 shell 行
    切成**词**，用一个 `if/then/elif/else/fi` 状态机判定当前位置是否在成功路径上。

    规则（本仓 verify.sh 的实际形状）：
      - `if …; then <A>; elif …; then <B>; else <C>; fi`：**只有 then 分支**是成功路径；
      - `cond || ok '…'`：失败路径上的 ok（条件为假才走），**不算成功文案**。

    踩坑史（都被差分测试抓过，故这里写得啰嗦但要写对）：
      - 按行数而不是按词认 `if` ⇒ 单行 `if … fi` 把深度算负，**吞掉后面所有 ok**；
      - 把 `; else` 当成行首 `else` ⇒ 跳不过 else 分支；
      - heredoc 内的 Python `if` 被当 shell 分支 ⇒ 张冠李戴。
    """
    in_heredoc: set = set()
    for a, b in spans:
        in_heredoc.update(range(a, b + 1))
    tokens = _shell_tokens(lines, in_heredoc)
    return _oks_on_success_path(tokens)


def _shell_tokens(lines: list[str], in_heredoc: set) -> list[str]:
    """把 shell 行切成词：先折续行，再按 bash 分隔符与**独立关键词**切。

    为什么要按独立关键词切：`if [ "$err" -eq 0 ]; then ok '…'` 里 `then ok '…'` 按 `;`
    切出来是**一个**分段；不把 `then` 再切出来，就永远看不到紧随其后的 `ok`
    （实测把收尾结论整条吞掉）。
    """
    tokens: list[str] = []
    i = 0
    while i < len(lines):
        # 续行折叠：把以 `\` 结尾的物理行与后续行合成**一条逻辑行**
        # （`ok "… = \` + `    \"$v02\""` 必须合并，否则文案被截在 `\` 上）。
        logical = ""
        while i < len(lines) and i not in in_heredoc:
            logical += lines[i].rstrip()
            if lines[i].rstrip().endswith("\\"):
                logical = logical[:-1] + " "
                i += 1
                continue
            break
        i += 1
        if not logical:
            continue
        for raw in re.split(r"(;|\|\||&&|\{|\})", logical):
            for part in re.split(r"\b(if|then|elif|else|fi)\b", raw):
                t = part.strip()
                if t:
                    tokens.append(t)
    return tokens


def _oks_on_success_path(tokens: list[str]) -> list[str]:
    """`if/then/elif/else/fi` 状态机：只收集**成功（then）路径**上的 `ok` 文案。

    踩坑史（都被差分测试抓过，故这里写得啰嗦但要写对）：
      - 按行数而不是按词认 `if` ⇒ 单行 `if … fi` 把深度算负，**吞掉后面所有 ok**；
      - 把 `; else` 当成行首 `else` ⇒ 跳不过 else 分支；
      - heredoc 内的 Python `if` 被当 shell 分支 ⇒ 张冠李戴（故调用方先挖掉 heredoc 段）。
    """
    out: list[str] = []
    active: list[bool] = []          # 每层 if：当前是否位于 then（成功）分支
    pending_if = False
    for tok in tokens:
        if tok == "if":
            pending_if = True
            continue
        if tok == "then":
            if pending_if:
                active.append(True)
                pending_if = False
            continue
        if tok in ("elif", "else"):
            if active:
                active[-1] = False      # elif / else 分支都不是成功路径
            continue
        if tok == "fi":
            if active:
                active.pop()
            continue
        if "||" in tok:
            continue
        if tok.startswith(("ok ", "ok'", 'ok"')) and all(active):
            m = _OK_RE.search(tok)
            if m:
                out.append(m.group(1) or m.group(2) or "")
    return out


_NO_RE = re.compile(r'''no\s+"([^"]*?)\$(?:\(|\{)''')


def parse_labels(text: str, num: int) -> Labels:
    """从 verify.sh 的 checkN 体里抽出成功/失败文案（**结构化**，不做正则碰运气）。

    必须区分「then 分支的 ok」与「收尾 `if [ "$err" -eq 0 ]; then ok`」：
    两者**不一定都在**（check20 的 `then` 分支是 `:`，只有收尾那条）。
    """
    body = check_body(text, num)
    if not body:
        return Labels([], "", "", "")
    lines = body.splitlines()
    spans = _heredoc_ranges(lines)
    oks_all = _ok_literals(body)
    pass_lines = _reachable_oks(lines, spans)
    m_no = _NO_RE.search(body)
    prefix = (m_no.group(1) if m_no else "").strip()
    then_ok = pass_lines[0] if pass_lines else ""
    final_ok = pass_lines[-1] if len(pass_lines) > 1 else ""
    return Labels(oks_all, then_ok, final_ok, prefix, pass_lines)


def resolve_shell_vars(text: str, root: Any, read_json: Any = None) -> str:
    """把文案里**已知的** shell 变量展开成真值，让引擎文案与 bash 输出同形。

    为什么需要：`ok "… = \\"$v02\\""` 里 `v02` 是从 registry.json 取的
    `registry_schema_version`；bash 打印的是展开后的 `"2"`，引擎若打印模板 `"$v02"`
    就与门禁输出不同形（差分测试据此判不一致）。

    只支持**本仓实际用到的那个变量**——不做通用 shell 展开器：遇到没见过的变量就原样保留
    （**宁可暴露差异，也不猜**），差分测试会把它抓出来。
    """
    if "$v02" not in text or read_json is None:
        return text
    try:
        js = read_json(root)
        v02 = str(js.get("registry_schema_version", ""))
    except (OSError, ValueError):
        return text
    if not v02:
        return text
    return text.replace("\\", "").replace("$v02", v02)


__all__ = ["Labels", "banner", "check_body", "parse_labels", "resolve_shell_vars"]
