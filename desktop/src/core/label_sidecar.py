"""标注 sidecar v0：cc_label 的**回退载体**（嵌入载体做不到时，标识放进旁车文件）。

为什么是 sidecar 而不是水印（2026-11-05）：本仓没有标识写入子系统，任何「已写入水印/已嵌入元数据」
的宣称都不可证。ABI 的 cc_label 输出里本来就有 embedded 字段与「embedded=false（回退 sidecar）」
的语义——本模块把那半边做实，并且**永远 embedded=false**：它证明的是「这份声明与这份对象对得上」，
不是「对象里真的带标识」。

纪律：
- 旁车路径 = 对象路径 + .label.json（同一目录），写盘走 atomic_write（半截件会让读者读到假声明）；
- 旁车绑定对象摘要：读的时候对象变了就判 stale（不静默放行）；
- 纯函数式读取（只读旁车 + 对象摘要），不联网、不猜；
- 判据词表与证据线一致：ok / invalid（stale 归 invalid 并说清是「对象变了」）。
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from core import atomic_write, json_doc, label_ir

SIDECAR_SCHEMA = "nf-label-sidecar/1"
SUFFIX = ".label.json"
GUIDE = "修复指引："
EMBEDDED = False


def sidecar_path(object_path: str) -> str:
    """对象 → 旁车路径（同目录、后缀固定）。"""
    return str(object_path) + SUFFIX


def object_digest(path: str) -> str:
    """对象字节的 sha256（sidecar 绑定的就是它）。"""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write(object_path: str, ir: dict[str, Any], out: str = "") -> tuple[str, dict[str, Any]]:
    """把 IR 写成旁车（绑定对象摘要）→ (旁车路径, 摘要信息)。IR 不合法就带指引拒绝。"""
    src = str(object_path)
    if not os.path.isfile(src):
        raise ValueError(f"对象不是文件：{src}（{GUIDE}请先 ls 定位；目录请逐件处理）")
    issues = label_ir.validate(ir)["issues"]
    if issues:
        raise ValueError("标注 IR 不合法：" + "；".join(issues[:3])
                         + f"（{GUIDE}先 nf label validate 修好再写旁车）")
    obj = ir.get("object") or {}
    digest = object_digest(src)
    if str(obj.get("digest") or "") != digest:
        got = str(obj.get("digest"))[:12]
        raise ValueError(f"IR 里的 object.digest 与对象实际摘要不符（IR {got}"
                         f" / 实际 {digest[:12]}）（{GUIDE}请用 nf label ir 重编 IR）")
    doc = {
        "schema": SIDECAR_SCHEMA,
        "object": {"path": src, "digest": digest},
        "label": ir,
        "embedded": EMBEDDED,
        "boundary": ("旁车只声明「该对象该带哪些标识」并与对象摘要绑定；"
                     "不证明载体里写入了任何标识（载体写入未实装）"),
    }
    dest = out or sidecar_path(src)
    atomic_write.write_text(dest, json.dumps(doc, ensure_ascii=False, indent=2,
                                             sort_keys=True) + "\n")
    return dest, {"object": src, "digest": digest, "sidecar": dest,
                  "embedded": EMBEDDED}


def read(object_path: str, path: str = "") -> dict[str, Any]:
    """读旁车并与对象摘要对账 → {ok, verdict, label, embedded, issues}。"""
    res: dict[str, Any] = {"ok": False, "verdict": "invalid", "label": None,
                           "embedded": EMBEDDED, "object": str(object_path),
                           "issues": []}
    dest = path or sidecar_path(str(object_path))
    if not os.path.isfile(dest):
        res["issues"].append(f"缺旁车 {dest}（{GUIDE}先 nf label write 生成；"
                             "或者这说明该对象从未被标注过）")
        return res
    try:
        doc = json_doc.load(dest, dict, what=dest)
    except (OSError, ValueError) as exc:
        res["issues"].append(str(exc))
        return res
    if doc.get("schema") != SIDECAR_SCHEMA:
        res["issues"].append(f"旁车 schema 不匹配（实得 {doc.get('schema')!r}）（{GUIDE}期望 "
                             f"{SIDECAR_SCHEMA}）")
        return res
    obj = doc.get("object")
    if not isinstance(obj, dict):
        res["issues"].append("旁车缺 object 段（" + GUIDE + "需要 {path, digest}）")
        return res
    label = doc.get("label")
    issues = label_ir.validate(label)["issues"]
    if issues:
        res["issues"].append("旁车里的标注 IR 不合法：" + "；".join(issues[:3]))
        return res
    try:
        live = object_digest(str(object_path))
    except OSError as exc:
        res["issues"].append(f"对象不可读：{exc}（{GUIDE}对象被删/权限不足，旁车无从对账）")
        return res
    if str(obj.get("digest") or "") != live:
        res["issues"].append(f"对象已被改动：旁车绑定 {str(obj.get('digest'))[:12]} / 实际 "
                             f"{live[:12]}（{GUIDE}标签声明已过期——重新标注，别沿用旧声明）")
        return res
    res["label"] = label
    res["ok"] = True
    res["verdict"] = "ok"
    return res


def discover(root: str = ".") -> list:
    """在仓内找全部旁车 → [(sidecar, object, embedded)]（供审计/清点；只读）。"""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", ".worktrees", "node_modules",
                                                        "__pycache__")]
        for name in filenames:
            if name.endswith(SUFFIX):
                full = os.path.join(dirpath, name)
                target = full[: -len(SUFFIX)]
                out.append((os.path.relpath(full, root), os.path.relpath(target, root),
                            EMBEDDED))
    return sorted(out)

