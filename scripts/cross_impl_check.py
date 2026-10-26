#!/usr/bin/env python3
# nf-io: inputs=engine/js/nf_canonical.js,desktop/src/core/registry.json outputs=-
"""跨实现差分：Python canonical ⇄ Node canonical（`nf-sem-canon/1`）逐组对拍。

目的
----
`desktop/src/core/contract_semantics.py` 的 canonical 是**协议语义**，不是「某个 Python
脚本的内部格式」。本件用固定种子生成 ≥20 组 registry 子集（外加 6 组 canonical 边缘用例），
分别跑 Python 真源与 Node 第二实现（`engine/js/nf_canonical.js`），逐组比较：

- `digest`：sha256("nf-sem-canon/1\\n" + 规范 JSON + "\\n") —— 语义身份；
- `bytes_sha256`：sha256(规范 JSON + "\\n") —— 字节级校验；
- `bytes`：规范字节长度。

边界（**不夸大**）
------------------
第二实现只覆盖 **canonical 规范形**（键排序 / 集合排序去重 / 数字规范化 / 路径 POSIX /
紧凑分隔符 / 版本行）。W1-W3 契约规则（层序闭包 / 域隔离 / 门全性）仍只有 Python 单实现，
本件不复制、也不声称覆盖。Node 不可用时**明确 skip**（rc=0 + skip 标记），不假装通过。

用法
----
    python scripts/cross_impl_check.py                 # 人读摘要（20 组 registry + 6 组边缘）
    python scripts/cross_impl_check.py --json          # 机器面报告
    python scripts/cross_impl_check.py --groups 30 --seed 20261026
    python scripts/cross_impl_check.py --node-script <替代 JS>   # 负例/变异用
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import contract_semantics as cs  # noqa: E402
from core import json_doc  # noqa: E402

REPORT_SCHEMA = "nf-cross-impl-check/1"
NODE_SCRIPT = ROOT / "engine" / "js" / "nf_canonical.js"
REGISTRY_REL = "desktop/src/core/registry.json"
SEED = 20261026                      # 固定种子：同种子同子集（可复现）
MIN_GROUPS = 20
_UNSET = object()                    # 区分「未传 node_bin」与「显式给 None（=不可用）」

BOUNDARY = ("第二实现只覆盖 canonical 规范形与 registry 子集载荷装配（键排序/集合排序去重/"
            "数字规范化/路径 POSIX/紧凑分隔符/版本行；modules[:n] / protocols[:n//4+1] 与 "
            "Python canonical_payload 同口径）；W1-W3 契约规则（层序闭包/域隔离/门全性）"
            "仍只有 Python 单实现，本台架不复制、不声称覆盖。")

#: canonical 边缘用例（payload 模式）：把单实现里容易「看起来一样」的规则各打一处。
EDGE_FIXTURES: List[Dict[str, Any]] = [
    # 1 键排序 + 标量集合（去重/排序）+ 路径 POSIX
    {"z": 1, "a": {"y": 2, "x": [3, 1, 2, 2]}, "m": "中文\\路径/混合"},
    # 2 标量集合：Python set 相等语义（True==1）+ (type, str) 排序 + 空容器
    {"nums": [1, 1.0, 2, 2.5, True, False, None, "b", "a", "a"], "empty": {}, "arr": []},
    # 3 对象列表排序（规范 JSON 文本定序）+ 嵌套列表
    {"objects": [{"b": 1, "a": "x"}, {"a": "x", "b": 1}, {"a": "y"}],
     "nested": [[1, 2], [2, 1]]},
    # 4 路径归一 + 控制字符转义 + 非 ASCII 原样
    {"paths": ["a\\b", "a/b", "c\\d\\e"], "unicode": "内容契约层", "control": "a\tb\nc"},
    # 5 整数值浮点折叠 + 混合标量
    {"float_int": [1.0, 2.0, -3.0], "mixed": [1, "1", True, None, 1.5]},
    # 6 深层键序 + 对象列表里键序不同也同 digest
    {"deep": {"c": {"b": {"a": 1}}}, "list_of_dicts": [{"k": "v2"}, {"k": "v1"}]},
]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _registry() -> Dict[str, Any]:
    return json_doc.load(ROOT / REGISTRY_REL, dict, what=REGISTRY_REL)


def generate_groups(seed: int = SEED, count: int = MIN_GROUPS) -> List[Dict[str, Any]]:
    """固定种子生成 registry 子集 + 边缘用例（纯函数；同种子同输出）。"""
    reg = _registry()
    module_ids = sorted(str(m.get("id") or "") for m in (reg.get("modules") or [])
                        if isinstance(m, dict) and str(m.get("id") or ""))
    groups: List[Dict[str, Any]] = []
    for i in range(max(1, int(count))):
        rng = random.Random(seed + i)
        k = rng.randint(1, len(module_ids))
        groups.append({"id": "registry-%02d" % i, "kind": "registry",
                       "subset": rng.sample(module_ids, k)})
    # 全量 registry 载荷（canonical_payload(model) 的默认口径）也纳入对拍：
    # 子集只覆盖切片分支，全量覆盖「不切片」分支。
    groups.append({"id": "registry-full", "kind": "registry", "subset": list(module_ids)})
    for i, fixture in enumerate(EDGE_FIXTURES, 1):
        groups.append({"id": "edge-%02d" % i, "kind": "edge", "subset": fixture})
    return groups


def python_expected(group: Dict[str, Any]) -> Dict[str, Any]:
    """Python 真源：registry 子集 → canonical_payload；边缘 → canonicalize。"""
    model = {"root": str(ROOT)}      # canonical_payload 只消费 model["root"]（真源读 registry）
    if group["kind"] == "registry":
        payload = cs.canonical_payload(model, group["subset"])
    else:
        payload = cs.canonicalize(group["subset"])
    data = cs.canonical_bytes(payload)
    prefix = (cs.CANON_VERSION + "\n").encode("utf-8")
    body = data[len(prefix):]
    return {"digest": "sha256:" + _sha256(data),
            "bytes_sha256": _sha256(body), "bytes": len(data)}


def run_node(group: Dict[str, Any], node_cmd: List[str], timeout: int = 120) -> Dict[str, Any]:
    """跑 Node 第二实现 → 它自报的 {schema,digest,bytes_sha256,bytes}。"""
    request = {"schema": cs.CANON_VERSION, "subset": group["subset"]}
    proc = subprocess.run(  # nosec B603 - argv 列表、无 shell；只跑仓库内实现
        node_cmd, cwd=str(ROOT),
        input=json.dumps(request, ensure_ascii=False).encode("utf-8"),
        capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError("node 退出码 %d：%s"
                           % (proc.returncode,
                              (proc.stderr or b"").decode("utf-8", "replace")[-300:]))
    try:
        doc = json.loads((proc.stdout or b"").decode("utf-8"))
    except ValueError as exc:
        raise RuntimeError("node 输出不是 JSON：%s" % exc) from exc
    for key in ("digest", "bytes_sha256", "bytes"):
        if key not in doc:
            raise RuntimeError("node 输出缺字段 %s：%r" % (key, doc))
    return doc


def run_checks(seed: int = SEED, count: int = MIN_GROUPS,
               node_script: Optional[str] = None,
               node_bin: Any = _UNSET) -> Dict[str, Any]:
    """→ 报告 dict（status = ok / skip / fail；确定性：无时间戳）。"""
    script = Path(node_script) if node_script else NODE_SCRIPT
    if node_bin is _UNSET:
        # 环境变量是给「CLI 子进程里模拟无 node」用的（沙箱/CI 排查；值为 none 即显式不可用）
        node_bin = os.environ.get("NF_NODE_BIN", _UNSET)
    if node_bin == "none":
        node = None
    else:
        node = shutil.which("node") if node_bin is _UNSET else node_bin
    report: Dict[str, Any] = {
        "schema": REPORT_SCHEMA, "seed": int(seed), "registry_groups": int(count),
        "edge_groups": len(EDGE_FIXTURES), "boundary": BOUNDARY,
        "node_script": str(script), "groups": [], "mismatches": [], "errors": [],
    }
    if not node:
        report.update(status="skip", skip_reason="node 不可用（未假装通过）",
                      checked=0, matched=0)
        return report
    if not script.is_file():
        report.update(status="fail", checked=0, matched=0,
                      errors=["Node 实现缺失：%s" % script])
        return report
    node_cmd = [str(node), str(script)]
    groups = generate_groups(seed, count)
    matched = 0
    for group in groups:
        try:
            expected = python_expected(group)
            got = run_node(group, node_cmd)
        except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
            report["errors"].append("%s：%s" % (group["id"], exc))
            continue
        ok = (got.get("digest") == expected["digest"]
              and got.get("bytes_sha256") == expected["bytes_sha256"]
              and int(got.get("bytes", -1)) == expected["bytes"])
        row = {"id": group["id"], "kind": group["kind"], "match": bool(ok),
               "python_digest": expected["digest"], "node_digest": got.get("digest"),
               "python_bytes_sha256": expected["bytes_sha256"],
               "node_bytes_sha256": got.get("bytes_sha256"),
               "bytes": expected["bytes"]}
        report["groups"].append(row)
        if ok:
            matched += 1
        else:
            report["mismatches"].append(group["id"])
    checked = len(report["groups"])
    status = "ok" if (checked and matched == checked and not report["errors"]) else "fail"
    report.update(status=status, checked=checked, matched=matched)
    return report


def _summary(report: Dict[str, Any]) -> str:
    status = report["status"]
    if status == "skip":
        return ("== 跨实现差分：SKIP ==\n  %s\n  （未跑任何组；这不是通过）"
                % report.get("skip_reason", ""))
    lines = ["== 跨实现差分（Python ⇄ Node canonical）==",
             "  状态：%s · 种子 %d · registry 子集 %d 组 + 边缘用例 %d 组"
             % (status.upper(), report["seed"], report["registry_groups"],
                report["edge_groups"]),
             "  逐组全等：%d/%d" % (report["matched"], report["checked"])]
    if report["mismatches"]:
        lines.append("  [FAIL] 不一致组：%s" % "、".join(report["mismatches"][:6]))
    if report["errors"]:
        lines.append("  [FAIL] 执行错误：%s" % report["errors"][:3])
    lines.append("  边界：%s" % report["boundary"])
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="跨实现差分：Python contract_semantics canonical ⇄ Node 零依赖第二实现")
    ap.add_argument("--json", action="store_true", help="机器面报告")
    ap.add_argument("--groups", type=int, default=MIN_GROUPS,
                    help="registry 子集组数（默认 %d，任务要求 ≥%d）" % (MIN_GROUPS, MIN_GROUPS))
    ap.add_argument("--seed", type=int, default=SEED, help="固定随机种子（默认 %d）" % SEED)
    ap.add_argument("--node-script", default="", help="替代 Node 实现路径（负例/变异用）")
    args = ap.parse_args(argv)
    report = run_checks(seed=args.seed, count=args.groups,
                        node_script=args.node_script or None)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
          if args.json else _summary(report))
    if report["status"] == "fail":
        return 1
    return 0                     # skip 也 rc=0：明确标注，不假装通过


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
