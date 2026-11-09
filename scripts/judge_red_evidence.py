#!/usr/bin/env python3
"""判据红证据登记（`nf-judge-red-evidence/1`）：每个测试模块「被证明过能红吗」。

为什么（第 149/151/152 轮）：389 个测试模块里，只有少数能拿出「它会红」的证据；
其余靠印象。本件把证据分三档并落成可增可减的数：

| 档 | 判据 |
|---|---|
| `negative_case` | 在 `results/ccos/gate_negative_tests.json` 里被记为有拒绝型用例（硬证据） |
| `mutation` | 被变异探针收录的判据所在模块（硬证据，显式名单） |
| `naming` | 测试名含否定关键词——**代理指标，只算 suspect，不算证据** |
| `none` | 以上都没有 |

棘轮口径（按第 152 轮的十问自查修正）：**允许新增模块暂时落进 none**（否则等于禁止新增测试），
但 `without_evidence` 的总数**只减不增**。

用法：python scripts/judge_red_evidence.py [--write|--check] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))
OUT_REL = "results/ccos/judge_red_evidence.json"
GATES_REL = "results/ccos/gate_negative_tests.json"
SCHEMA = "nf-judge-red-evidence/1"

#: 被变异探针收录的判据 → 其测试模块（显式名单：改这里要同步探针）
MUTATION_MODULES = ("test_judge_mutation_probe.py", "test_gate_probe.py")

#: 否定型测试名的关键词（代理指标，不计入硬证据）
NEGATIVE_KEYS = ("kill", "mutation", "reject", "rejects", "fail", "fails", "invalid",
                 "tamper", "detect", "detects", "wrong", "broken", "bad",
                 "escape", "guard", "must")


def _gate_modules(root: Path) -> set:
    path = root / GATES_REL
    if not path.is_file():
        raise ValueError("缺 " + GATES_REL
                         + "（修复指引：先跑 python scripts/gate_probe.py --write）")
    doc = json.loads(path.read_text(encoding="utf-8"))
    names = set()
    for row in doc.get("rows") or []:
        if row.get("has_negative") and str(row.get("module") or ""):
            names.add(str(row["module"]).split(".")[-1] + ".py")
    return names


def _has_negative_name(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    names = re.findall(r"def (test_[a-z0-9_]+)\(", text)
    return any(key in name for name in names for key in NEGATIVE_KEYS)


def collect(root: str | Path = ".") -> dict[str, Any]:
    base = Path(root)
    gate_mods = _gate_modules(base)
    modules = sorted(p.name for p in (base / "desktop" / "tests").glob("test_*.py"))
    if not modules:
        raise ValueError("没扫到测试模块（修复指引：确认 --root 指向仓库根）")
    entries = []
    hard = suspect = 0
    for name in modules:
        if name in gate_mods:
            entries.append({"module": name, "source": "negative_case"})
            hard += 1
        elif name in MUTATION_MODULES:
            entries.append({"module": name, "source": "mutation"})
            hard += 1
        elif _has_negative_name(base / "desktop" / "tests" / name):
            entries.append({"module": name, "source": "naming"})
            suspect += 1
        else:
            entries.append({"module": name, "source": "none"})
    return {"schema": SCHEMA, "modules": len(modules),
            "with_evidence": hard, "suspect": suspect,
            "without_evidence": len(modules) - hard - suspect,
            "entries": entries,
            "note": "hard = negative_case + mutation；naming 只是代理指标"}


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="judge_red_evidence",
                                 description="判据红证据登记：每个测试模块被证明过能红吗")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        doc = collect(ROOT)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.write:
        from core import atomic_write

        dest = ROOT / OUT_REL
        dest.parent.mkdir(parents=True, exist_ok=True)
        atomic_write.write_text(dest, render(doc))
        print("OK 已写入 " + OUT_REL + "（硬证据 " + str(doc["with_evidence"]) + " / 疑似 "
              + str(doc["suspect"]) + " / 无 " + str(doc["without_evidence"]) + "）")
        return 0
    if args.check:
        from core import json_doc

        dest = ROOT / OUT_REL
        if not dest.is_file():
            print("缺 " + OUT_REL + "（先跑 --write）", file=sys.stderr)
            return 1
        if render(json_doc.load(dest, dict, what=OUT_REL)) != render(doc):
            print("红证据登记已陈旧——重跑 --write", file=sys.stderr)
            return 1
        print("OK 红证据登记与现场一致")
        return 0
    if args.json:
        print(render(doc), end="")
        return 0
    print("模块 " + str(doc["modules"]) + " · 硬证据 " + str(doc["with_evidence"])
          + " · 疑似 " + str(doc["suspect"]) + " · 无 " + str(doc["without_evidence"]))
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
