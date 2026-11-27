"""output_forms 私有子模块 _meter：机验率计量：逐包机器可验面统计、基线比对与重签（只读/显式写）。

门面 core.output_forms 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import json

from core import atomic_write
from core import conformance_scan as _csc

from ._const import BASELINE_REL, INDEX_REL
from ._registry import _pack_dirs, _read_json, _rel



def _count(rows: Sequence[Dict[str, Any]], key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in rows:
        out[str(r.get(key))] = out.get(str(r.get(key)), 0) + 1
    return dict(sorted(out.items()))



# ---------------------------------------------------------------- 机验率计量

def meter(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """机验率与功能面计量（不改盘；基线比对见 baseline_verify）。"""
    stats: Dict[str, Any] = {"packages": {}, "totals": {}}
    # 资产档面一次枚举（共享枚举器：走查/子树清单复用），替代「每个包各一次 glob」——
    # 实测本仓 111 个包各 glob 一次 `assets/*.md`（106 次落盘遍历），而这一面本来就要被
    # asset_density / 指纹走一遍。
    prose_by_pkg: Dict[str, List[str]] = {}
    for rel in _csc.iter_files(root, "community/*/assets/*.md"):
        parts = rel.split("/")
        if len(parts) == 4 and parts[3] != "README.md":
            prose_by_pkg.setdefault(parts[1], []).append(parts[3])
    for pkg in _pack_dirs(root):
        idx, _err = _read_json(_rel(root, "community/%s/%s" % (pkg, INDEX_REL)))
        entries = (idx or {}).get("outputs") or []
        mv = [e for e in entries if e.get("tier") in ("T2", "T3", "T4")]
        fn_faces = [e for e in entries if e.get("tier") == "T4"]
        prose = prose_by_pkg.get(pkg, [])
        denom = len(mv) + len(prose)
        stats["packages"][pkg] = {
            "machine_verifiable": len(mv),
            "functional": len(fn_faces),
            "prose_assets": len(prose),
            "machine_verifiable_ratio": round(len(mv) / denom, 4) if denom else 0.0,
            "roles": _count([{"r": e.get("role")} for e in entries], "r"),
            "tiers": _count([{"t": e.get("tier")} for e in entries], "t"),
        }
    pkgs = stats["packages"]
    if pkgs:
        stats["totals"] = {
            "machine_verifiable": sum(p["machine_verifiable"] for p in pkgs.values()),
            "functional": sum(p["functional"] for p in pkgs.values()),
            "prose_assets": sum(p["prose_assets"] for p in pkgs.values()),
            "machine_verifiable_ratio": round(
                sum(p["machine_verifiable"] for p in pkgs.values())
                / max(1,
 sum(p["machine_verifiable"] + p["prose_assets"] for p in pkgs.values())),
 4),
        }
    return [], stats



def baseline_verify(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """机验率基线（可重签）：低于基线即 FAIL——防「新增产出又退回散文」。"""
    issues: List[str] = []
    base, err = _read_json(_rel(root, BASELINE_REL))
    _, stats = meter(root)
    if err:
        return ["%s 缺失或不可解析（%s；重签：nf output meter --write）" % (BASELINE_REL,
 err)], stats
    prev = (base.get("packages") or {})
    for pkg, cur in stats["packages"].items():
        old = prev.get(pkg)
        if old is None:
            continue
        if cur["machine_verifiable"] < int(old.get("machine_verifiable", 0)):
            issues.append("%s 机验产出面回退：%d → %d（基线 %s）"
                          % (pkg, int(old.get("machine_verifiable", 0)),
                             cur["machine_verifiable"], BASELINE_REL))
        if cur["functional"] < int(old.get("functional", 0)):
            issues.append("%s 功能面（T4 可复算）回退：%d → %d"
                          % (pkg, int(old.get("functional", 0)), cur["functional"]))
    return issues, {"baseline": bool(base), **stats}



def write_baseline(root: str = ".") -> Dict[str, Any]:
    _, stats = meter(root)
    doc = {
        "schema": "nf-output-forms-baseline/1",
        "note": "机验率/功能面基线（可重签工件）。低于基线即 check32 失败——"
                "产出形态不得从数据/契约退回散文。重签：nf output meter --write",
        "packages": {k: {"machine_verifiable": v["machine_verifiable"],
                         "functional": v["functional"],
                         "prose_assets": v["prose_assets"],
                         "machine_verifiable_ratio": v["machine_verifiable_ratio"]}
                     for k, v in stats["packages"].items()},
        "totals": stats["totals"],
    }
    dest = _rel(root, BASELINE_REL)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # 原子写（2026-09-30 收口）：产出形态基线是在仓产物（check32 的比对对象）。
    atomic_write.write_text(dest, json.dumps(doc, ensure_ascii=False,
                                             indent=2, sort_keys=True) + "\n")
    return doc
