"""terminal · _forms（自 terminal.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

from ._parse import (
    split_args,
)
from ._tables import (
    FORMS,
)
from ._ui import (
    _row,
    style,
    term_width,
)


def form_action_dict(form) -> dict:
    """一张写盘表单 → 动作字典（argv 模板与参数槽逐字取自表单真源，不加第二套语义）。

    参数槽的 `kind` 由步骤自带的 `kind` 决定（`path` = 仓库内路径，视图侧须过包含性判据）；
    步骤没写 `kind` 就是自由文本。`required=False` 的步骤在视图侧对应「留空则连同其旗标一起丢」。
    """
    params = [{"name": str(st["key"]), "label": str(st.get("prompt") or st["key"]),
               "kind": str(st.get("kind") or "text"),
               "required": bool(st.get("required"))}
              for st in form.get("steps") or ()]
    return {"key": str(form["id"]), "title": str(form["title"]),
            "argv": [str(t) for t in form.get("argv") or ()],
            "params": params, "note": str(form.get("summary") or "")}




def zone_action_dicts(zone) -> list:
    """某区的**有效动作表**：显式 `actions`，或（`forms: True` 的区）由 `FORMS` 投影而来。

    单一出处：真源侧自检、投影件与全屏视图都走这里——「表单 → 动作」的映射不许抄第二遍，
    否则表单改了而视图没跟上，正是本波要根除的那类漂移。
    """
    if zone.get("forms"):
        return [form_action_dict(f) for f in FORMS]
    return [dict(a) for a in zone.get("actions") or ()]




def form_table() -> tuple:
    """表单真源（终端渲染、`--form`、check39 共用同一份）。"""
    return FORMS




def form_by_id(fid: str):
    """按 id 取表单；未命中返回 None（调用方给可用清单，不抛栈）。"""
    for f in FORMS:
        if str(f["id"]) == str(fid).strip():
            return f
    return None




def form_missing(form, answers) -> list:
    """还差哪些**必填** step（未填或空白都算缺）。"""
    out = []
    for st in form.get("steps") or []:
        if st.get("required") and not str((answers or {}).get(st["key"], "")).strip():
            out.append(st["key"])
    return out




def form_pending(form, answers) -> list:
    """还没**settle**的 step（未出现在 answers 里；空串 = 已明确跳过）——表单逐项追问用它。"""
    return [st["key"] for st in form.get("steps") or []
            if st["key"] not in (answers or {})]




def build_argv(form, answers) -> list:
    """表单 + 回答 → CLI argv（空值连同其旗标一起丢弃；必填缺失即报并给指引）。"""
    answers = answers or {}
    missing = form_missing(form, answers)
    if missing:
        raise ValueError("表单 %s 还缺必填项：%s（修复指引：用 /form %s 补齐或 --answer %s=…）"
                         % (form.get("id"), "、".join(missing), form.get("id"),
                            missing[0]))
    toks = list(form.get("argv") or [])
    out = []
    i = 0
    while i < len(toks):
        tok = toks[i]
        nxt = toks[i + 1] if i + 1 < len(toks) else None
        if tok.startswith("{") and tok.endswith("}"):
            val = str(answers.get(tok[1:-1], "")).strip()
            if val:
                out.extend(split_args(val))
            i += 1
            continue
        if nxt and nxt.startswith("{") and nxt.endswith("}"):
            val = str(answers.get(nxt[1:-1], "")).strip()
            if val:
                out.append(tok)
                out.extend(split_args(val))
            i += 2                    # 空值：旗标与值一起丢，不留悬空旗标
            continue
        out.append(tok)
        i += 1
    return out




def render_forms(filt: str = "", width=None, color: bool = False) -> str:
    """列出全部写盘表单（可按 id/标题过滤）。"""
    f = str(filt or "").strip().lower()
    w = term_width(width)
    lines = [style("== 写盘表单（%d 张 · 逐项追问 → 组装命令 → 二次确认）==" % len(FORMS),
                   "head", color)]
    for form in FORMS:
        if f and f not in str(form["id"]).lower() and f not in str(form["title"]).lower():
            continue
        lines.append(_row("/form " + str(form["id"]),
                          "%s —— %s" % (form["title"], form["summary"]), w, color))
    lines.append("  用法：/form <id> 开始追问；/cancel 中止；参数真源见 protocol/LAYERS.json 同级的"
        " CLI 面")
    return "\n".join(lines)




def render_form(form, answers=None, color: bool = False) -> str:
    """渲染一张表单：已填/待填进度 + 下一个问题。"""
    answers = answers or {}
    lines = [style("== 表单：%s（%s）==" % (form["title"], form["id"]), "head", color),
             "  %s" % form["summary"], ""]
    for st in form.get("steps") or []:
        key = st["key"]
        val = str(answers.get(key, "")).strip()
        mark = "✔" if val else ("✱" if st.get("required") else "·")
        shown = ("　%s=%s" % (key, val)) if val else ""
        lines.append("  [%s] %s（%s）%s%s"
                     % (mark, key, st["prompt"], shown,
                        ("  提示：%s" % st["hint"]) if st.get("hint") and not val else ""))
    missing = form_missing(form, answers)
    pending = form_pending(form, answers)
    if pending:
        nxt = [st for st in form["steps"] if st["key"] == pending[0]][0]
        tail = "空行 = 跳过（可选项）" if not nxt.get("required") else "必填"
        lines += ["", "  请回答 %s（%s）：直接输入值（%s）；`/cancel` 中止"
                  % (nxt["key"], nxt["prompt"], tail)]
    elif missing:
        lines += ["", "  [FAIL] 必填项为空：%s" % "、".join(missing)]
    else:
        try:
            argv = build_argv(form, answers)
            lines += ["", "  组装命令：nf %s" % " ".join(argv),
                      "  确认执行？(yes/no)"]
        except ValueError as exc:
            lines += ["", "  [FAIL] %s" % exc]
    return "\n".join(lines)
