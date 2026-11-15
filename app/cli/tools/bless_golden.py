"""生成/复核 golden 夹具：app/fixtures/golden/<op>/case.json。

期望值**只由 Rust release 核心生成**（不是手写假期望）：
- 记录 expected envelope（解析后 JSON，供人读/复核）
- 记录 expected_sha256 = sha256(核心 stdout 原始字节)（逐字节钉住，含键序/unicode 转义）
- 记录核心 --abi-version，便于追溯生成版本

用法（仓库根）：
    python app/cli/tools/bless_golden.py --bless    # 核心有变化时人工审 diff 后执行
    python app/cli/tools/bless_golden.py --check    # 只核对，不写盘
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]  # app/cli/tools/bless_golden.py → 仓库根
sys.path.insert(0, str(REPO / "app" / "cli"))

from nf_app.canonical import sha256_hex  # noqa: E402
from nf_app.core import resolve_core  # noqa: E402

GOLDEN = REPO / "app" / "fixtures" / "golden" / "ops"  # 与 core golden-gen 的 fixtures/ 分目录，互不覆盖
FIXTURE_TOKEN = "$fixtures"


def _resolve(obj):
    """把请求里的 $fixtures/... 占位换成真实绝对路径（记录时保留占位）。"""
    if isinstance(obj, str) and obj.startswith(FIXTURE_TOKEN + "/"):
        return str(REPO / "app" / "fixtures" / obj[len(FIXTURE_TOKEN) + 1 :])
    if isinstance(obj, list):
        return [_resolve(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _resolve(value) for key, value in obj.items()}
    return obj


def _call(exe: Path, op: str, request: dict) -> tuple[int, bytes]:
    payload = json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    proc = subprocess.run([str(exe), op, "--in", "-"], input=payload, capture_output=True, timeout=300, check=False)
    return proc.returncode, proc.stdout


def _abi(exe: Path) -> dict:
    proc = subprocess.run([str(exe), "--abi-version"], capture_output=True, timeout=60, check=False)
    return json.loads(proc.stdout.decode("utf-8"))


def cases(exe: Path) -> list[dict]:
    pack = FIXTURE_TOKEN + "/sample-pack"
    pack_v2 = FIXTURE_TOKEN + "/sample-pack-v2"
    graph = json.loads((REPO / "app/fixtures/sample-pack/pipeline/main.nfg.json").read_text(encoding="utf-8"))
    spec = json.loads((REPO / "app/fixtures/sample-pack/spec/main.nfspec.json").read_text(encoding="utf-8"))
    protocol = json.loads((REPO / "app/fixtures/sample-pack/protocol/nf-protocol-pack.json").read_text(encoding="utf-8"))
    manifest = json.loads((REPO / "app/fixtures/sample-pack/nf-pack.json").read_text(encoding="utf-8"))
    _code, imported_raw = _call(
        exe,
        "import",
        {
            "file": _resolve(pack + "/docs/sample.md"),
            "source": {"kind": "file", "name": "sample.md"},
        },
    )
    imported = json.loads(imported_raw.decode("utf-8"))["result"]

    project = {
        "schema": "nf-project/1",
        "id": "golden-project",
        "title": "golden",
        "refs": {
            "base_pack": {"id": manifest["id"], "version": manifest["version"], "tree": manifest["hashes"]["tree"]},
            "graph": {
                "id": graph["id"],
                "version": graph["version"],
                "digest": __import__("nf_app.canonical", fromlist=["digest"]).digest(graph),
                "path": "pack/pipeline/main.nfg.json",
                "sha256": sha256_hex((REPO / "app/fixtures/sample-pack/pipeline/main.nfg.json").read_bytes()),
            },
            "spec": {
                "id": spec["id"],
                "version": spec["version"],
                "digest": __import__("nf_app.canonical", fromlist=["digest"]).digest(spec),
                "path": "pack/spec/main.nfspec.json",
                "sha256": sha256_hex((REPO / "app/fixtures/sample-pack/spec/main.nfspec.json").read_bytes()),
            },
        },
        "status": "draft",
        "review": {"state": "none"},
        "history": [],
    }
    cyclic = json.loads(json.dumps(graph))
    # 自环：端口都在声明集合内，只违反 L1 无环 → 才能稳定拿到 NF-GRF-004
    cyclic["edges"].append(
        {"id": "E99", "from": "N05", "to": "N05", "from_port": "checked", "to_port": "final", "type": "data"}
    )
    return [
        {"op": "canonical", "case": "nested-unicode", "expect": {"ok": True}, "request": {"value": {"b": 1, "a": [True, None, "ü"], "z": {"k": "v"}}}},
        {"op": "canonical", "case": "float-rejected", "expect": {"ok": False, "code": "NF-E-006"}, "request": {"value": {"x": 1.5}}},
        {"op": "canonical", "case": "control-chars", "expect": {"ok": True}, "request": {"value": {"ctrl": "a\nb\tc", "quote": 'say "hi"\\'}}},
        {"op": "pack-hash", "case": "sample-pack", "expect": {"ok": True}, "request": {"root": pack}},
        {"op": "pack-verify", "case": "sample-pack", "expect": {"ok": True}, "request": {"root": pack}},
        {"op": "pack-diff", "case": "sample-pack-to-v2", "expect": {"ok": True}, "request": {"old_root": pack, "new_root": pack_v2}},
        {"op": "import", "case": "sample-md", "expect": {"ok": True}, "request": {"file": pack + "/docs/sample.md", "source": {"kind": "file", "name": "sample.md"}}},
        {"op": "map-suggest", "case": "sample-md", "expect": {"ok": True}, "request": {"import": imported, "spec": spec}},
        {"op": "protocol-validate", "case": "sample", "expect": {"ok": True}, "request": {"pack": protocol}},
        {"op": "protocol-render", "case": "sample", "expect": {"ok": True}, "request": {"pack": protocol, "values": {"F-001": "灯灭之前别回头", "F-002": "冷静"}}},
        {"op": "graph-validate", "case": "sample", "expect": {"ok": True}, "request": {"graph": graph}},
        {"op": "graph-validate", "case": "cycle-rejected", "expect": {"ok": False, "code": "NF-GRF-004"}, "request": {"graph": cyclic}},
        {"op": "graph-compile", "case": "sample", "expect": {"ok": True}, "request": {"graph": graph, "spec": spec}},
        {"op": "spec-validate", "case": "sample", "expect": {"ok": True}, "request": {"spec": spec}},
        {"op": "project-validate", "case": "draft", "expect": {"ok": True}, "request": {"project": project}},
    ]


def build(exe: Path, *, write: bool) -> int:
    abi = _abi(exe)
    by_op: dict[str, list[dict]] = {}
    for case in cases(exe):
        by_op.setdefault(case["op"], []).append(case)
    problems = 0
    for op, entries in by_op.items():
        for entry in entries:
            request = _resolve(entry["request"])
            exit_code, raw = _call(exe, op, request)
            if not raw.strip():
                print(f"FAIL {op}/{entry['case']}: 核心无输出 exit={exit_code}")
                problems += 1
                continue
            expected = json.loads(raw.decode("utf-8"))
            expect = entry.get("expect") or {"ok": bool(expected.get("ok"))}
            if bool(expected.get("ok")) != bool(expect.get("ok")):
                print(
                    f"FAIL {op}/{entry['case']}: 期望 ok={expect.get('ok')}，核心返回 ok={expected.get('ok')} "
                    f"code={(expected.get('error') or {}).get('code')}"
                )
                problems += 1
                if write:
                    continue
            if expect.get("code") and (expected.get("error") or {}).get("code") != expect["code"]:
                print(f"FAIL {op}/{entry['case']}: 期望 code={expect['code']}，实际 {(expected.get('error') or {}).get('code')}")
                problems += 1
                if write:
                    continue
            record = {
                "schema": "nf-golden-case/1",
                "op": op,
                "case": entry["case"],
                "expect": expect,
                "note": "expected 由 app/core release 的 nf-app-core 生成（不是手写）；expected_sha256 钉核心 stdout 原始字节",
                "core": abi,
                "request": entry["request"],
                "expected_exit": exit_code,
                "expected": expected,
                "expected_sha256": sha256_hex(raw),
            }
            path = GOLDEN / op / f"{entry['case']}.json"
            if write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(
                    (json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
                )
                print(f"blessed {path.relative_to(REPO)} exit={exit_code}")
            else:
                if not path.is_file():
                    print(f"FAIL 缺少 golden: {path.relative_to(REPO)}")
                    problems += 1
                    continue
                saved = json.loads(path.read_text(encoding="utf-8"))
                if saved["expected_sha256"] != record["expected_sha256"]:
                    print(f"FAIL 字节摘要不一致: {path.relative_to(REPO)}")
                    problems += 1
                if saved["expected"] != expected:
                    print(f"FAIL 语义不一致: {path.relative_to(REPO)}")
                    problems += 1
    return 0 if problems == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="golden 夹具 bless/check（期望值只来自核心）")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--bless", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    exe = resolve_core()
    return build(exe, write=bool(args.bless))


if __name__ == "__main__":
    raise SystemExit(main())
