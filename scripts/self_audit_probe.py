#!/usr/bin/env python3
"""自省探针：把「当前验证器摘要」记进结果件，供判据核对（自省层对象）。

为什么（第 96 轮）：发布结论只绑定 HEAD，不绑定「谁判的」。本探针把判定面脚本的内容摘要
（`core.verifier_version`）写进 `results/ccos/self_audit.json`；判据断言：结果件里的摘要必须
等于当前重算值——**工具改了而没重跑，就是红**。

边界：摘要只覆盖判定面脚本，不覆盖被测代码；它证明「结论由这套逻辑产出」，
不证明「这套逻辑是对的」。

用法：python scripts/self_audit_probe.py [--write] [--check] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))
OUT_REL = "results/ccos/self_audit.json"
SCHEMA = "nf-self-audit/1"


def _core(name: str):
    src = str(ROOT / "desktop" / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    import importlib

    return importlib.import_module("core." + name)


def build() -> dict[str, Any]:
    from core import verifier_version  # 显式导入：模块须被静态引用（防被死代码判据判成墓碑）

    vv = verifier_version.digest(ROOT)
    return {"schema": SCHEMA, "files": vv["files"],
            "verifier_digest": vv["verifier_digest"],
            "note": "判定面脚本的内容摘要；与当前重算不一致即说明工具变了结论未重跑"}


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="self_audit_probe",
                                 description="自省探针：记录当前验证器摘要（判定面脚本内容摘要）")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        doc = build()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.write:
        dest = ROOT / OUT_REL
        dest.parent.mkdir(parents=True, exist_ok=True)
        _core("atomic_write").write_text(dest, render(doc))
        print("OK 已写入 " + OUT_REL + "（验证器 " + doc["verifier_digest"][:16] + "）")
        return 0
    if args.check:
        dest = ROOT / OUT_REL
        if not dest.is_file():
            print("缺 " + OUT_REL + "（先跑 --write）", file=sys.stderr)
            return 1
        if dest.read_text(encoding="utf-8") != render(doc):
            print("验证器摘要已变（判定面脚本改了）——重跑 --write 并复核旧结论", file=sys.stderr)
            return 1
        print("OK 验证器摘要与重算一致")
        return 0
    print(render(doc), end="")
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
