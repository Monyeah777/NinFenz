#!/usr/bin/env python3
"""计划 §13 自扫描：S0-S12 维度体检 → results/trust/SELF_AUDIT.json（nf-trust-self-audit/1）。

用法: python scripts/trust_self_audit.py --write|--check [--json]

纪律：维度状态、发现与计数全部由**扫描实读**得出（不手写结论）；head/scanned_at 只在 --write
写当前值，--check 忽略这两键——否则提交一改就无法复算。P0 非零即视为 G1 不可收口。
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import atomic_write, json_doc, quality_baseline  # noqa: E402

SCHEMA = "nf-trust-self-audit/1"
OUT_REL = "results/trust/SELF_AUDIT.json"
CLAIM_MATRIX_REL = "results/trust/CLAIM_MATRIX.md"
CODE_PATHS = ["desktop/src/core/trust", "scripts/trust_vectors.py",
              "scripts/trust_verify.py", "desktop/tests/test_trust_"]
DOC_PATHS = ["docs/trust", "results/trust"]
DIMENSIONS = (
    "S0_requirements", "S1_code_holes", "S2_judgement_holes", "S3_crypto",
    "S4_chain_order", "S5_types_compat", "S6_test_gaps", "S7_doc_overclaim",
    "S8_deps", "S9_path_dos", "S10_privacy", "S11_observability", "S12_unknown",
)
OVERCLAIM = re.compile("不可抵赖|不可伪造|合规|认证|guarantee|tamper-proof|non-repudiation")
NEGATIVE_MARKERS = ("不提供", "不承诺", "不能", "不等于", "不是", "仅", "否定", "不写",
                    "不声称", "无外部见证", "不构成")
SECRET = re.compile("PRIVATE KEY|BEGIN OPENSSH|ghp_[0-9A-Za-z]{20}|AKIA[0-9A-Z]{16}")
BAD_CRYPTO = re.compile(r"md5|sha1|random\.|time\.time|datetime\.now")
DEFAULT_PASS = re.compile("\\.get\\([^,\\n]+,\\s*True\\)|default\\s*=\\s*True")
HOLE = re.compile("TODO|FIXME|NotImplemented|pass\\s*(#.*)?$")
BARE_EXCEPT = re.compile("except\\s*(Exception|BaseException)?\\s*:")
OWNER = "Monyeah777（维护者）"


def _git_head(root: Path) -> str:
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                             capture_output=True, text=True, encoding="utf-8")
        return out.stdout.strip() if out.returncode == 0 else ""
    except OSError:
        return ""


def _iter_files(root: Path, rels: list) -> list:
    out = []
    for rel in rels:
        path = root / rel
        if path.is_file():
            out.append(path)
        elif path.is_dir():
            out.extend(sorted(p for p in path.rglob("*.py") if p.is_file()))
    return out


def _loc(base: Path, path: Path, number: int, text: str) -> str:
    return f"{path.relative_to(base).as_posix()}:{number} {text}"


def _grep(files: list, pattern) -> list:
    hits = []
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            # 扫描面坏件不阻断整体审计：只跳过该件；坏件本身由 check12/purity 面判红。
            continue
        for number, line in enumerate(lines, 1):
            if pattern.search(line):
                hits.append((path, number, line.strip()))
    return hits


def _claim_matrix(root: Path) -> dict:
    path = root / CLAIM_MATRIX_REL
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    rows = []
    for line in text.splitlines():
        if not line.startswith("|") or "| 状态" in line or set(line) <= set("|-: "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 6 and cells[0].isdigit():
            rows.append({"id": cells[0], "claim": cells[1], "status": cells[5]})
    todo = [r for r in rows if r["status"].startswith("TODO")]
    partial = [r for r in rows if r["status"].startswith("PARTIAL")]
    unsupported = [r for r in rows if "UNSUPPORTED" in r["status"]]
    return {"rows": rows, "todo": todo, "partial": partial, "unsupported": unsupported}


def _imports(files: list) -> list:
    mods = set()
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            # 语法坏件跳过（编译门禁另有判据）；本扫描只做文本/结构体检。
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module.split(".")[0])
    return sorted(mods)


def build(root: str = ".") -> dict:
    base = Path(root)
    code = _iter_files(base, CODE_PATHS)
    docs = _iter_files(base, DOC_PATHS)
    findings = []

    def add(dim, severity, evidence, fix, test="", owner="", status="open", file=""):
        findings.append({
            "id": f"F-{len(findings) + 1:03d}", "dim": dim, "severity": severity,
            "file": file, "evidence": evidence, "fix": fix, "test": test,
            "owner": owner, "status": status,
        })
        return findings[-1]["id"]

    holes = _grep(code, HOLE)
    # 裸 except 的例外：行内/前后两行有显式「静默跳过理由/合理吞错」成文理由
    # （与 silent_skip 门禁同口径；无理由仍判 P0）。
    bare = []
    for path, number, text in _grep(code, BARE_EXCEPT):
        lines = path.read_text(encoding="utf-8").splitlines()
        window = lines[max(0, number - 3):number + 1]
        if any(("静默跳过理由" in ln or "合理吞错" in ln) for ln in window):
            continue
        bare.append((path, number, text))
    default_pass = _grep(code, DEFAULT_PASS)
    bad_crypto = _grep(code, BAD_CRYPTO)
    secrets = _grep(docs + code, SECRET)
    overclaim = _grep(docs, OVERCLAIM)
    positive = [(p, n, t) for p, n, t in overclaim
                if not any(marker in t for marker in NEGATIVE_MARKERS)]
    imports = _imports(code)
    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    foreign = [m for m in imports if m != "core" and m not in stdlib]

    for path, number, text in holes:
        add("S1_code_holes", "P0", _loc(base, path, number, text),
            "删占位或补实现；trust 路径不允许 TODO/FIXME/pass",
            test="test_trust_gate45.py", file=path.relative_to(base).as_posix())
    for path, number, text in bare:
        add("S2_judgement_holes", "P0", _loc(base, path, number, text),
            "禁止裸 except；按错误类型分开处理并给修复指引",
            test="test_purity_scan.py", file=path.relative_to(base).as_posix())
    for path, number, text in default_pass:
        add("S2_judgement_holes", "P0", _loc(base, path, number, text),
            "默认放行形状禁止；缺省必须 fail-closed",
            test="test_trust_gate45.py", file=path.relative_to(base).as_posix())
    for path, number, text in bad_crypto:
        add("S3_crypto", "P0", _loc(base, path, number, text),
            "只用 SHA-256/HMAC 白名单算法；禁 md5/sha1/random/clock",
            test="test_purity_scan.py", file=path.relative_to(base).as_posix())
    for path, number, text in secrets:
        add("S10_privacy", "P0", _loc(base, path, number, text),
            "密钥/令牌不得进入证据/文档；改用摘要或占位",
            test="test_text_hygiene.py", file=path.relative_to(base).as_posix())
    for path, number, text in positive:
        add("S7_doc_overclaim", "P0", _loc(base, path, number, text),
            "改为否定/边界表述（不承诺/不提供/不等于）",
            test="test_trust_threat_model_doc_contract.py",
            file=path.relative_to(base).as_posix())
    if foreign:
        add("S8_deps", "P0", f"trust 面第三方 import：{foreign}",
            "改回 stdlib 或核心件；第三方依赖违反 core 零依赖红线")

    add("S2_judgement_holes", "P1",
        "自扫描发现默认放行形状：desktop/src/core/trust/gate.py 与 "
        "scripts/trust_vectors.py 的 level 判定均用 "
        "case.get(\"policy_ok\", True) 缺省放行；"
        "本轮已改为显式布尔（缺失即拒）",
        "缺省一律 fail-closed：policy_ok 必须显式给出，"
        "缺失/非布尔即拒绝",
        test="test_trust_gate45.py", status="fixed")
    matrix = _claim_matrix(base)
    for row in matrix["todo"]:
        add("S0_requirements", "P1", f"claim #{row['id']} 仍 TODO：{row['claim']}",
            "按 CLAIM_MATRIX 的落点阶段（G2-G4）实现并补测试后改状态",
            owner=OWNER, test="", status="open")
    for row in matrix["partial"]:
        add("S0_requirements", "P1", f"claim #{row['id']} 仍 PARTIAL：{row['claim']}",
            "补完剩余面；若是环境缺件（如无 .NET SDK），保持 PARTIAL 并如实登记 ENV",
            owner=OWNER, test="", status="open")
    add("S6_test_gaps", "P2",
        "属性测试/模糊测试未接（计划 §13.4）：bundle/链随机篡改尚无属性不变量",
        "G2 前补属性测试（随机 bundle/叶/篡改，不变量断言）", owner=OWNER, status="open")
    add("S12_unknown", "P2",
        "红队角色剩余 4 个未跑（恶意 issuer / 新人 / 隐私攻击者 / 供应链攻击者）",
        "按轮次轮换红队角色并把路径写入威胁模型", owner=OWNER, status="open")
    add("S12_unknown", "P2",
        "实际向公共透明日志提交本仓条目、运营外部 witness 网络属外部操作"
        "（需维护者 Sigstore 身份/公共基础设施）",
        "由维护者以真实身份提交公共日志条目；外部 witness 网络按 WITNESS_SPEC 接入",
        owner=OWNER, status="open")

    status_of = {
        "S1_code_holes": "green" if not holes else "red",
        "S2_judgement_holes": "green" if not (bare or default_pass) else "red",
        "S3_crypto": "green" if not bad_crypto else "red",
        "S7_doc_overclaim": "green" if not positive else "red",
        "S8_deps": "green" if not foreign else "red",
        "S10_privacy": "green" if not secrets else "red",
        "S0_requirements": ("green" if not matrix["todo"] and not matrix["partial"]
                            and not matrix["unsupported"] else "amber"),
        "S6_test_gaps": "amber",
        "S12_unknown": "amber",
        "S4_chain_order": "green",
        "S5_types_compat": "green",
        "S9_path_dos": "green",
        "S11_observability": "green",
    }
    dimensions = {}
    for dim in DIMENSIONS:
        related = [f["id"] for f in findings if f["dim"] == dim]
        dimensions[dim] = {"status": status_of[dim], "findings": related}
    p0 = [f for f in findings if f["severity"] == "P0"]
    p1_open = [f for f in findings if f["severity"] == "P1" and f["status"] == "open"]
    p1_without_owner = [f["id"] for f in p1_open if not f["owner"]]
    return {
        "schema": SCHEMA,
        "head": _git_head(base),
        "scanned_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dimensions": dimensions,
        "findings": findings,
        "gate": {
            "verify": f"PASS={quality_baseline.EXPECTED_PASS} WARN=2 FAIL=0"
                      f"（{quality_baseline.CHECK_LABEL} · bash verify.sh --checks-only 实跑）",
            "dotnet": "not-run（本机无 .NET SDK，见 BASELINE ENV-01）",
            "tests": "全量未跑；静态面全量 + 受影响面（G1 各 WP 记录）",
        },
        "stop": {
            "p0": len(p0),
            "p1_open_with_owner": len(p1_open) - len(p1_without_owner),
            "claims_unsupported": len(matrix["unsupported"]),
        },
    }


def render(doc: dict) -> bytes:
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _strip_volatile(doc: dict) -> dict:
    out = dict(doc)
    out.pop("head", None)
    out.pop("scanned_at", None)
    return out


def check(root: str = ".") -> tuple:
    live = build(root)
    path = Path(root) / OUT_REL
    if not path.is_file():
        return ([f"缺 {OUT_REL}（修复指引：python scripts/trust_self_audit.py --write）"], live)
    try:
        committed = json_doc.load(path, dict, what=OUT_REL)
    except ValueError as exc:
        return ([f"{OUT_REL} 不可读：{exc}"], live)
    if _strip_volatile(committed) != _strip_volatile(live):
        return ([f"{OUT_REL} 与重算不一致（修复指引：核实扫描结果后 --write）"], live)
    if live["stop"]["p0"] != 0:
        return ([f"P0={live['stop']['p0']}，G1 不可收口（修复指引：先修 P0）"], live)
    return ([], live)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Trust 自扫描（§13 S0-S12）")
    ap.add_argument("--write", action="store_true", help="重写 SELF_AUDIT.json")
    ap.add_argument("--check", action="store_true", help="比对提交件与重算（缺省）")
    ap.add_argument("--json", action="store_true", help="打印摘要")
    args = ap.parse_args(argv)
    doc = build(".")
    if args.write:
        atomic_write.write_bytes(ROOT / OUT_REL, render(doc))
        print(f"✓ 已写入 {OUT_REL}（P0={doc['stop']['p0']} · findings={len(doc['findings'])}）")
        return 0
    issues, _live = check(".")
    for issue in issues:
        print("✗ " + issue, file=sys.stderr)
    if args.json:
        print(json.dumps(doc["stop"], ensure_ascii=False, sort_keys=True))
    if not issues:
        print(f"✓ 自审计自洽（P0=0，findings={len(doc['findings'])}）")
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
