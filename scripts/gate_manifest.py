#!/usr/bin/env python3
# nf-io: inputs=verify.sh,desktop/src/core/gate_engine.py outputs=protocol/gates.json
"""门禁清单（gate manifest）抽取器 —— Wave 2 T2.3 第一步：**只登记、不改判据**。

为什么有这件（T1.3 审计结论）
------------------------------
`verify.sh` 是 42 条 check 的 bash 主执行体（3213 行、26 段内嵌 Python）；门禁引擎
`core.gate_engine` 只迁入 22 条，且 check41/42 在 REGISTRY/PENDING 两边都不在——
"覆盖缺口"不是判据问题，而是**没有一份机读登记面**能回答「42 条各自在哪」。
本件产出 `protocol/gates.json`（schema `nf-gates/1`），把每条 check 的静态投影机械
抽取成 12 字段；判据本体一字未动（`--check` 只做差分，**不执行任何 check**）。

两条纪律
--------
1. **真源唯一**：id/title/segment/kind 全部从 `verify.sh` 与 `core.gate_engine` 现读现抽，
   不手抄（手抄必然漂移——`gate_labels` 的教训同源：手抄文案第一版就与真源不符）。
2. **只增不减**：`IDS` 是 id 登记表；新增 gate 只追加，既有条目不得改绑或删除
   （`--check` 与 `desktop/tests/test_gate_manifest.py` 各守一道）。

不确定的字段一律 `null`（inputs/depends/budget_ms：读面靠观测、依赖与预算靠实测，
第二步补；本步不假声明）。见 `null_fields`。

用法
----
    python scripts/gate_manifest.py --extract   # 重算并写 protocol/gates.json
    python scripts/gate_manifest.py --check     # 与 verify.sh/引擎差分；不一致 exit 1
    python scripts/gate_manifest.py --check --json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import atomic_write, json_doc  # noqa: E402  - 先用后置（scripts 面统一写法）

MANIFEST_REL = "protocol/gates.json"
SCHEMA = "nf-gates/1"
CHECK_JSON_SCHEMA = "nf-gate-manifest-check/1"

#: 12 字段（顺序即写盘顺序；多一个少一个都算形状漂移）。
FIELDS = (
    "id", "legacy_check", "title", "segment", "kind", "impl",
    "inputs", "assert", "output", "depends", "budget_ms", "tier",
)

#: 本步刻意不声明的字段（第二步：inputs=gate_faces 观测面；depends=产物图；
#: budget_ms=历史耗时 p95）。填 null 是**如实**，不是没做完的占位。
NULL_FIELDS = ("inputs", "depends", "budget_ms")

#: id 登记表 —— **只增不减**。新增 check 只在末尾追加；既有编号不得改绑、不得删除。
#: 命名规则：[a-z0-9] 起头、kebab-case、语义化（不绑段位/序号——序号会随历史分段漂移）。
IDS: dict[int, str] = {
    1: "core-dirs",
    2: "dup-ids-official",
    3: "invariant-anchors",
    4: "visibility-boundary",
    5: "quality-gate-action",
    6: "entry-navigation",
    7: "community-pack-structure",
    8: "community-asset-baseline",
    9: "module-asset-addressable",
    10: "ext-closure-redlines",
    11: "asset-three-way-reconcile",
    12: "desktop-unittest-compileall",
    13: "protocol-version-migration",
    14: "community-protocol-registration",
    15: "composition-references",
    16: "contract-arbitration",
    17: "quality-governance",
    18: "export-contract",
    19: "export-schema-shape",
    20: "doc-completeness",
    21: "registry-reference-graph",
    22: "export-spec-hygiene",
    23: "asset-supply-chain",
    24: "module-lifecycle",
    25: "knowledge-signature",
    26: "semantic-conflict",
    27: "architecture-purity",
    28: "idl-schema",
    29: "conformance-grading",
    30: "extension-bump-migration",
    31: "golden-generation",
    32: "quality-depth",
    33: "new-faces-summary",
    34: "library-face",
    35: "deepening-face",
    36: "governance-face",
    37: "knowledge-layer",
    38: "output-automation",
    39: "terminal-surface",
    40: "asset-contracts",
    41: "build-isolation",
    42: "provenance-nonfalsifiable",
}

#: kind 形状（八类执行体；第一列是 manifest 值，第二列是 assert 机制）。
KINDS = {
    "declarative": "decl-rows",        # verify.sh::_decl_check 的数据表
    "bash": "bash-exit0",              # 纯 bash 判定，退出码即结论
    "delegated": "python-issues-empty",  # 委托 core.*，issues 非空即红
    "inproc": "python-exit0",          # 进程内跑 heredoc 原文
    "script": "script-exit0",          # 独立脚本，转发退出码
    "unittest": "unittest-green",      # 单测模块全绿
}

DECLARATIVE = (1, 3, 4, 5, 6)          # 共用 _decl_check（verify.sh:242 附近）
BASH = (2, 7, 9, 10, 11)               # 纯 bash（find/grep/awk 循环）
UNITTEST = (12, 17, 18, 19, 21, 22)    # 起 unittest / verify_tests.py
TESTS_TIER = (12,)                     # 唯一把"全量测试"当本体执行的 gate

_CHECK_HEAD = re.compile(r"^check(\d+)\(\)\{")
_INVOKE = re.compile(r"^\s*((?:check\d+\s*;\s*)*check\d+)\s*;?\s*$")
_SECTION = re.compile(r"echo '—— 段 ([ABCD])")
_BANNER = re.compile(r"^\s*echo '(== \[[^']*)'")
_BANNER_SEG = re.compile(r"\[(\d+)/(?:[^\]·]*·([ABCD])|段([ABCD]))\]")
_LOG = re.compile(r'"\$NFL_TMP"/(nf_check[^"\s]+\.log)')
_VERSION = re.compile(r"版本\s*:\s*(v[\d.]+)")
_DELEGATED = re.compile(r'\(\s*(\d+)\s*,\s*"(\w+)"\s*,\s*"(\w+)"\s*\)')
_MAIN_BODY = re.compile(r"# ================= 主执行体")
_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


# ---------------------------------------------------------------- verify.sh 解析

def check_bodies(text: str) -> dict[int, list[str]]:
    """→ {check 号: 行列表}；按 `checkN(){` 起点、下一条起点或 EOF 收尾。"""
    lines = text.splitlines()
    marks = [(int(m.group(1)), i) for i, ln in enumerate(lines)
             for m in [_CHECK_HEAD.match(ln)] if m]
    out: dict[int, list[str]] = {}
    for k, (num, start) in enumerate(marks):
        end = marks[k + 1][1] if k + 1 < len(marks) else len(lines)
        out[num] = lines[start:end]
    return out


def banner(body: list[str]) -> str | None:
    for ln in body:
        m = _BANNER.search(ln)
        if m:
            return m.group(1)
    return None


def segments(text: str) -> dict[int, str]:
    """从**主执行体**抽「段位 → check 号」：banner 缺字母的（如 check12 `[12/代码层]`）
    只有这里能定段。"""
    out: dict[int, str] = {}
    cur = ""
    in_main = False
    for ln in text.splitlines():
        if _MAIN_BODY.search(ln):
            in_main = True
            continue
        if not in_main:
            continue
        m = _SECTION.search(ln)
        if m:
            cur = m.group(1)
            continue
        hit = _INVOKE.match(ln)
        if hit and cur:
            for num in re.findall(r"check(\d+)", hit.group(1)):
                out[int(num)] = cur
    return out


def banner_segment(title: str | None) -> str | None:
    if not title:
        return None
    m = _BANNER_SEG.search(title)
    if not m:
        return None
    return m.group(2) or m.group(3)


def verify_version(text: str) -> str | None:
    m = _VERSION.search(text)
    return m.group(1) if m else None


# ---------------------------------------------------------------- 引擎登记面

def engine_facts(root: Path | None = None) -> dict[str, object]:
    """从 `core.gate_engine` 读登记面（**只 build_registry，不跑任何 check**）。

    → {"kinds": {n: kind}, "impls": {n: str}, "migrated": set, "pending": set}
    """
    from core import gate_engine as ge  # 延迟导入：--help/纯解析路径不付引擎导入税

    ge.build_registry()
    kinds: dict[int, str] = {n: spec.kind for n, spec in ge.REGISTRY.items()}
    for _rel, num in ge.SCRIPT_CHECKS:      # 独立脚本型：引擎 kind 记为 inproc，这里纠正
        kinds[num] = "script"
    impls: dict[int, str] = {}
    try:
        src = (Path(ge.__file__)).read_text(encoding="utf-8")
    except OSError:
        src = ""
    for num, module, func in _DELEGATED.findall(src):
        impls[int(num)] = "core.%s::%s" % (module, func)
    return {
        "kinds": kinds,
        "impls": impls,
        "migrated": set(ge.REGISTRY),
        "pending": set(ge.PENDING),
    }


# ---------------------------------------------------------------- 抽取

def _gate_kind(num: int, facts: dict, has_heredoc: bool) -> str:
    if num in UNITTEST:
        return "unittest"
    if num in DECLARATIVE:
        return "declarative"
    if num in BASH:
        return "bash"
    kind = str((facts["kinds"] or {}).get(num) or "")
    if kind in ("delegated", "inproc", "script"):
        return kind
    if num in (facts["pending"] or set()):
        return "inproc" if has_heredoc else "bash"
    return "bash"


def _gate_impl(num: int, kind: str, facts: dict, has_heredoc: bool) -> str | None:
    if kind == "declarative":
        return "verify.sh::_decl_check"
    if kind == "bash":
        return "verify.sh::check%d" % num
    if kind == "delegated":
        return str((facts["impls"] or {}).get(num) or "") or None
    if kind == "inproc":
        # 已迁入 = 引擎进程内执行 heredoc 原文；未迁入 = 仍留在 bash（impl 如实为 null）
        return "core.gate_engine::inproc" if num in (facts["migrated"] or set()) else None
    if kind == "script":
        return "scripts/check37_knowledge.py"
    return None


def _repo_stats(root: Path) -> dict:
    try:
        return json_doc.load(root / "protocol" / "repo_stats.json", dict,
                             what="protocol/repo_stats.json")
    except ValueError:
        return {}


def _coverage(gates: list[dict], facts: dict) -> dict:
    checks = sorted(int(g["legacy_check"]) for g in gates)
    migrated = sorted(facts["migrated"] or set())
    pending = sorted(facts["pending"] or set())
    return {
        "gates": len(checks),
        "migrated": migrated,
        "pending": pending,
        "gaps": sorted(set(checks) - (set(migrated) | set(pending))),
        "orphans": sorted((set(migrated) | set(pending)) - set(checks)),
    }


def build(root: Path | None = None) -> dict:
    """→ manifest 文档（纯函数：同输入同字节；不含时间戳等不确定面）。"""
    root = Path(root or ROOT)
    text = (root / "verify.sh").read_text(encoding="utf-8")
    bodies = check_bodies(text)
    seg_map = segments(text)
    facts = engine_facts(root)
    stats = _repo_stats(root)
    gates: list[dict] = []
    for num in sorted(bodies):
        body = "\n".join(bodies[num])
        title = banner(bodies[num])
        has_heredoc = "<<'PYEOF'" in body
        kind = _gate_kind(num, facts, has_heredoc)
        log = _LOG.search(body)
        gates.append({
            "id": IDS.get(num),
            "legacy_check": num,
            "title": title,
            "segment": banner_segment(title) or seg_map.get(num),
            "kind": kind,
            "impl": _gate_impl(num, kind, facts, has_heredoc),
            "inputs": None,
            "assert": [{"type": KINDS[kind], "spec": None}],
            "output": {
                "log": log.group(1) if log else None,
                "verdict_lines": "[PASS]/[FAIL]/[WARN]",
                "machine": None,
            },
            "depends": None,
            "budget_ms": None,
            "tier": "tests" if num in TESTS_TIER else "static",
        })
    return {
        "schema": SCHEMA,
        "source": {
            "file": "verify.sh",
            "sha256": hashlib.sha256((root / "verify.sh").read_bytes()).hexdigest(),
            "verify_version": verify_version(text),
            "check_count": len(gates),
            "baseline_checks": stats.get("baseline_checks", stats.get("verify_checks")),
            "baseline_pass": stats.get("baseline_pass"),
        },
        "null_fields": list(NULL_FIELDS),
        "notes": [
            "第一步（T2.3）：只登记静态投影，不改任何判据；--check 不执行 check。",
            "id 登记表只增不减：新增 gate 追加 IDS；既有编号不得改绑/删除。",
            "inputs 留 null：读面应由 gate_faces 观测派生（声明面曾全空=假声明，见 subcheck_cache），第二步补。",
            "depends/budget_ms 留 null：依赖图与历史耗时 p95 属实测面，第二步补。",
            "impl=null 表示该 gate 在 gate_engine 里尚未迁入（PENDING），不假装有实现。",
        ],
        "coverage": _coverage(gates, facts),
        "gates": gates,
    }


# ---------------------------------------------------------------- 差分

def _shape_diffs(doc: object) -> list[str]:
    if not isinstance(doc, dict):
        return ["manifest 顶层不是对象：%r" % type(doc).__name__]
    out: list[str] = []
    if doc.get("schema") != SCHEMA:
        out.append("schema 须为 %r，实为 %r" % (SCHEMA, doc.get("schema")))
    gates = doc.get("gates")
    if not isinstance(gates, list):
        return out + ["gates 须为数组，实为 %r" % type(gates).__name__]
    for i, g in enumerate(gates):
        if not isinstance(g, dict):
            out.append("gates[%d] 不是对象" % i)
            continue
        got = set(g)
        want = set(FIELDS)
        if got != want:
            out.append("gates[%d] 字段集不符：多 %s / 缺 %s"
                       % (i, sorted(got - want), sorted(want - got)))
    return out


def check(root: Path | None = None) -> list[str]:
    """静态差分 → 差异列表（空 = 一致）。只读，不写盘、不跑 check。"""
    root = Path(root or ROOT)
    try:
        got = json_doc.load(root / MANIFEST_REL, dict, what=MANIFEST_REL)
    except ValueError as exc:
        return [str(exc)]
    diffs = _shape_diffs(got)
    want = build(root)
    got_gates = got.get("gates") if isinstance(got.get("gates"), list) else []
    got_by: dict[int, dict] = {}
    for g in got_gates:
        if not isinstance(g, dict):
            continue
        num = g.get("legacy_check")
        if not isinstance(num, int):
            diffs.append("legacy_check 不是整数：%r（id=%r）" % (num, g.get("id")))
            continue
        if num in got_by:
            diffs.append("legacy_check 重复：%d" % num)
        got_by[num] = g
    want_by = {int(g["legacy_check"]): g for g in want["gates"]}
    missing = sorted(set(want_by) - set(got_by))
    extra = sorted(set(got_by) - set(want_by))
    if missing:
        diffs.append("manifest 缺少 check：%s" % missing)
    if extra:
        diffs.append("manifest 多出 verify.sh 不存在的 check：%s" % extra)
    for num in sorted(set(want_by) & set(got_by)):
        for field in ("id", "title", "segment", "kind"):
            if got_by[num].get(field) != want_by[num].get(field):
                diffs.append("check%d.%s：manifest=%r ≠ verify.sh=%r"
                             % (num, field, got_by[num].get(field), want_by[num].get(field)))
    got_ids = [g.get("id") for g in got_gates if isinstance(g, dict)]
    dup_ids = sorted({i for i in got_ids if got_ids.count(i) > 1})
    if dup_ids:
        diffs.append("id 重复：%s" % dup_ids)
    for i in got_ids:
        if not isinstance(i, str) or not _ID_RE.match(i):
            diffs.append("id 不合规（kebab-case）：%r" % i)
    want_cov = want["coverage"]
    if want_cov["gaps"]:
        diffs.append("引擎覆盖缺口（REGISTRY∪PENDING 未覆盖）：%s" % want_cov["gaps"])
    if want_cov["orphans"]:
        diffs.append("引擎登记了 verify.sh 不存在的 check：%s" % want_cov["orphans"])
    return diffs


def _manifest(root: Path | None = None) -> dict:
    root = Path(root or ROOT)
    return json_doc.load(root / MANIFEST_REL, dict, what=MANIFEST_REL)


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="gate manifest 抽取/差分（零行为变更：不改判据、不执行 check）")
    act = ap.add_mutually_exclusive_group(required=True)
    act.add_argument("--extract", action="store_true", help="重算并写 %s" % MANIFEST_REL)
    act.add_argument("--check", action="store_true", help="与 verify.sh/引擎差分（不一致 exit 1）")
    ap.add_argument("--json", action="store_true", help="机器面（仅 --check）")
    args = ap.parse_args(argv)

    if args.extract:
        doc = build(ROOT)
        atomic_write.write_text(ROOT / MANIFEST_REL,
                                json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
        cov = doc["coverage"]
        print("已抽取 %d 条 gate → %s" % (len(doc["gates"]), MANIFEST_REL))
        print("覆盖：migrated %d + pending %d = %d；缺口 %s"
              % (len(cov["migrated"]), len(cov["pending"]),
                 len(cov["migrated"]) + len(cov["pending"]), cov["gaps"] or "无"))
        return 1 if cov["gaps"] else 0

    diffs = check(ROOT)
    cov = build(ROOT)["coverage"]
    if args.json:
        print(json.dumps({
            "schema": CHECK_JSON_SCHEMA,
            "ok": not diffs,
            "diffs": diffs,
            "coverage": {k: len(v) if isinstance(v, list) else v for k, v in cov.items()},
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 1 if diffs else 0
    if diffs:
        for d in diffs:
            print("  [FAIL] %s" % d, file=sys.stderr)
        print("manifest 与 verify.sh/引擎不一致（%d 处）" % len(diffs), file=sys.stderr)
        return 1
    print("== gate manifest 差分通过 ==")
    print("  schema=%s · gates=%d · migrated=%d · pending=%d · 缺口=无"
          % (SCHEMA, len(build(ROOT)["gates"]), len(cov["migrated"]), len(cov["pending"])))
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
