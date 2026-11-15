"""Oracle 对账：Python 独立实现（app/tests/oracle.py）vs Rust 核心 vs 已入仓夹具。

本文件分两层：
1) 本地层（不需要核心）：oracle 自身向量、与 nf_app 实现互证、与 sample-pack 清单对齐；
2) 对账层（需要可用核心）：canonical / pack tree / 拓扑序 / verdict 逐项对账。
   核心未接通时通过 core fixture 显式报告阻塞（owner: rust-core），接通后自动真跑。
"""

from __future__ import annotations

import json
from pathlib import Path

import oracle
import pytest

from nf_app import canonical as nf_canonical
from nf_app.pack import compute_items, tree_digest
from conftest import run_core_raw

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "app" / "fixtures"
SAMPLE_PACK = FIXTURES / "sample-pack"

CORPUS = [
    {},
    [],
    {"b": 1, "a": "ü"},
    {"nested": {"z": [1, 2, 3], "a": {"k": None}}},
    {"ctrl": "a\nb\tc\r\x01", "quote": 'say "hi"\\', "unicode": "中文🙂"},
    {"ints": [0, -1, 9007199254740993], "bools": [True, False, None]},
]

LOCAL_CORPUS = CORPUS + [
    {"b": 1, "a": [True, None, "ü"], "z": {"k": "v"}},
]


# ---------------------------------------------------------------- 本地层：oracle 自身

def test_oracle_canonical_known_vectors() -> None:
    assert oracle.canonical({"b": 1, "a": "ü"}) == '{"a":"ü","b":1}'.encode("utf-8")
    assert oracle.canonical([True, False, None]) == b"[true,false,null]"
    assert oracle.canonical("a\nb") == b'"a\\nb"'
    assert oracle.canonical("\x01") == b'"\\u0001"'
    assert oracle.canonical({"z": {}, "a": []}) == b'{"a":[],"z":{}}'
    assert oracle.digest({"a": 1}) == __import__("hashlib").sha256(b'{"a":1}').hexdigest()


def test_oracle_and_impl_agree_on_corpus() -> None:
    """两套独立实现互证（任一漂移都说明有 bug）。"""
    for value in LOCAL_CORPUS:
        assert oracle.canonical(value) == nf_canonical.canonical_bytes(value), value
        assert oracle.digest(value) == nf_canonical.digest(value), value


def test_oracle_rejects_float() -> None:
    with pytest.raises(TypeError):
        oracle.canonical({"x": 1.5})
    with pytest.raises(nf_canonical.CanonicalError):
        nf_canonical.canonical_bytes({"x": 1.5})


def test_oracle_pack_tree_matches_manifest() -> None:
    manifest = json.loads((SAMPLE_PACK / "nf-pack.json").read_text(encoding="utf-8"))
    items = oracle.scan_pack(SAMPLE_PACK)
    assert [row["path"] for row in items] == [row["path"] for row in manifest["items"]]
    assert items == [
        {"path": row["path"], "sha256": row["sha256"], "size": row["size"]} for row in manifest["items"]
    ]
    assert oracle.tree_digest(items) == manifest["hashes"]["tree"]
    assert manifest["hashes"]["count"] == len(items)
    # 与 nf_app.pack 交叉验证（两种独立扫描实现，同一 tree 口径）
    assert tree_digest(compute_items(SAMPLE_PACK)) == oracle.tree_digest(items)


def test_oracle_topo_order_and_module_steps() -> None:
    graph = json.loads((SAMPLE_PACK / "pipeline" / "main.nfg.json").read_text(encoding="utf-8"))
    assert oracle.topo_order(graph) == ["N01", "N02", "N03", "N04", "N05"]
    assert oracle.module_step_nodes(graph) == ["N02", "N04"]
    # 口径（核心/lead 确认）：stage = 最近上游 stage（反向 BFS 同层取 id 最小）
    assert oracle.stage_of(graph, "N02") == "N01"
    assert oracle.stage_of(graph, "N04") == "N03"
    assert oracle.step_inputs(graph, "N02") == ["text"]
    assert oracle.step_inputs(graph, "N04") == ["draft"]


def test_oracle_topo_cycle_rejected() -> None:
    graph = {
        "nodes": [{"id": "N01"}, {"id": "N02"}],
        "edges": [
            {"from": "N01", "to": "N02"},
            {"from": "N02", "to": "N01"},
        ],
    }
    with pytest.raises(ValueError):
        oracle.topo_order(graph)


def test_oracle_verdict() -> None:
    assert oracle.verdict([]) == "pass"
    assert oracle.verdict([{"severity": "info"}]) == "pass"
    assert oracle.verdict([{"severity": "warn"}]) == "warn"
    assert oracle.verdict([{"severity": "warn"}, {"severity": "error"}]) == "fail"
    issues = [{"severity": "warn"}, {"severity": "error"}]
    assert oracle.summary(issues) == {"error": 1, "warn": 1, "info": 0}


# ---------------------------------------------------------------- 对账层：vs Rust 核心

def _envelope(core: Path, op: str, request: dict) -> dict:
    code, stdout, stderr = run_core_raw(core, op, request)
    assert stdout.strip(), f"核心 {op} 无输出（exit={code}, stderr={stderr[:500]!r}）"
    envelope = json.loads(stdout.decode("utf-8"))
    assert envelope["exit"] == code, (envelope, code)
    return envelope


def test_core_canonical_matches_oracle(core: Path) -> None:
    for value in CORPUS:
        envelope = _envelope(core, "canonical", {"value": value})
        assert envelope["ok"] is True, envelope
        result = envelope["result"]
        assert result["canonical"] == oracle.canonical(value).decode("utf-8"), value
        assert result["digest"] == oracle.digest(value), value


def test_core_canonical_rejects_float(core: Path) -> None:
    envelope = _envelope(core, "canonical", {"value": {"x": 1.5}})
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "NF-E-006"
    assert envelope["exit"] == 1


def test_core_pack_hash_matches_oracle(core: Path) -> None:
    envelope = _envelope(core, "pack-hash", {"root": str(SAMPLE_PACK)})
    assert envelope["ok"] is True, envelope
    result = envelope["result"]
    expected = oracle.scan_pack(SAMPLE_PACK)
    assert [row["path"] for row in result["items"]] == [row["path"] for row in expected]
    assert [
        {"path": row["path"], "sha256": row["sha256"], "size": row["size"]} for row in result["items"]
    ] == expected
    assert result["hashes"]["tree"] == oracle.tree_digest(expected)
    assert result["hashes"]["count"] == len(expected)


def test_core_pack_verify_report_matches_oracle_verdict(core: Path) -> None:
    envelope = _envelope(core, "pack-verify", {"root": str(SAMPLE_PACK)})
    assert envelope["ok"] is True, envelope
    report = envelope["result"]
    assert report["verdict"] == oracle.verdict(report["issues"])
    assert report["summary"] == oracle.summary(report["issues"])
    manifest = json.loads((SAMPLE_PACK / "nf-pack.json").read_text(encoding="utf-8"))
    # 报告 target.digest = 被校验对象（清单）的 canonical digest，不是 tree
    assert report["target"]["digest"] == oracle.digest(manifest)
    assert report["target"]["ref"] == manifest["id"]


def test_core_graph_compile_matches_oracle(core: Path) -> None:
    graph = json.loads((SAMPLE_PACK / "pipeline" / "main.nfg.json").read_text(encoding="utf-8"))
    spec = json.loads((SAMPLE_PACK / "spec" / "main.nfspec.json").read_text(encoding="utf-8"))
    envelope = _envelope(core, "graph-compile", {"graph": graph, "spec": spec})
    assert envelope["ok"] is True, envelope
    plan = envelope["result"]
    steps = plan["steps"]
    assert [step["node"] for step in steps] == oracle.module_step_nodes(graph)
    assert [step["id"] for step in steps] == [f"S{i:02d}" for i in range(1, len(steps) + 1)]
    expected_stage = {node_id: oracle.stage_of(graph, node_id) for node_id in oracle.module_step_nodes(graph)}
    expected_inputs = {node_id: oracle.step_inputs(graph, node_id) for node_id in oracle.module_step_nodes(graph)}
    weights = graph["weights"]
    for step in steps:
        node_id = step["node"]
        assert step["stage"] == expected_stage[node_id]
        assert step["inputs"] == expected_inputs[node_id]
        assert step["weight"] == weights.get(node_id, 0)
    assert plan["digest"] == oracle.digest_excluding(plan, ["digest"])
    assert plan["pipeline"]["digest"] == oracle.digest(graph)


def test_core_graph_validate_report_matches_oracle(core: Path) -> None:
    graph = json.loads((SAMPLE_PACK / "pipeline" / "main.nfg.json").read_text(encoding="utf-8"))
    envelope = _envelope(core, "graph-validate", {"graph": graph})
    assert envelope["ok"] is True, envelope
    report = envelope["result"]
    assert report["verdict"] == oracle.verdict(report["issues"])
    assert report["summary"] == oracle.summary(report["issues"])
    assert report["target"]["digest"] == oracle.digest(graph)
    code2, stdout2, _ = run_core_raw(core, "graph-validate", {"graph": graph})
    assert code2 == 0
    assert json.loads(stdout2.decode("utf-8"))["result"] == report, "同输入两次报告必须逐字节一致"


def test_core_spec_validate_target_digest(core: Path) -> None:
    spec = json.loads((SAMPLE_PACK / "spec" / "main.nfspec.json").read_text(encoding="utf-8"))
    envelope = _envelope(core, "spec-validate", {"spec": spec})
    assert envelope["ok"] is True, envelope
    report = envelope["result"]
    assert report["target"]["digest"] == oracle.digest(spec)
    assert report["verdict"] == oracle.verdict(report["issues"])


def test_core_negative_verdict_matches_oracle(core: Path, tmp_path: Path) -> None:
    """构造带环图：核心必须 fail 且 verdict 与 oracle 由 issues 推出的值一致。"""
    graph = json.loads((SAMPLE_PACK / "pipeline" / "main.nfg.json").read_text(encoding="utf-8"))
    graph["edges"].append(
        {"id": "E99", "from": "N05", "to": "N05", "from_port": "checked", "to_port": "final", "type": "data"}
    )
    envelope = _envelope(core, "graph-validate", {"graph": graph})
    assert envelope["ok"] is False
    assert envelope["exit"] == 1
    report = envelope["result"]
    assert report["verdict"] == "fail"
    assert report["verdict"] == oracle.verdict(report["issues"])
    assert report["summary"] == oracle.summary(report["issues"])
    assert any(issue["code"] == "NF-GRF-004" for issue in report["issues"]), report["issues"]
