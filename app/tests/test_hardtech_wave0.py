"""硬技术 Wave 0：SDIR 导入/校验/差异/合并、确定性构建、证据签名与离线验证。

判据只走核心 CLI；不在这里复刻语义。
"""

from __future__ import annotations

import json
from pathlib import Path

from conftest import run_core_raw
from nf_app.canonical import digest

CREATED = "2026-01-01T00:00:00Z"
SEED = "01" * 32

MD = """# 雨夜边境

雨夜的边境小镇，主角必须在一点辰内找到落脚点。见 [后文](#地图)。

## 地图

| 地点 | 风险 |
|---|---|
| 北门 | 高 |
| 旅店 | 低 |

- 灯灭之前，别回头。
- 不要相信戴面具的人。

![边境地图](map.png)

[^1]: 地图来自旧档案，坐标可能有偏差。
"""


def _req(markdown: str = MD, name: str = "doc.md") -> dict:
    return {
        "markdown": markdown,
        "source": {"name": name, "mime": "text/markdown"},
        "created_at": CREATED,
        "lang": "zh",
    }


def _call(core: Path, op: str, req: dict) -> tuple[int, dict]:
    code, stdout, stderr = run_core_raw(core, op, req)
    try:
        env = json.loads(stdout.decode("utf-8"))
    except Exception:  # pragma: no cover - 失败时给可读诊断
        raise AssertionError(f"{op} 非 JSON 响应: {stdout!r} stderr={stderr!r}")
    assert env["exit"] == code, (op, env, code)
    return code, env


def _sdir(core: Path, markdown: str = MD) -> dict:
    code, env = _call(core, "sdir-import", _req(markdown))
    assert code == 0, env
    return env["result"]


def _walk(block: dict):
    yield block
    for child in block.get("children", []):
        yield from _walk(child)


def _blocks(sdir: dict) -> list[dict]:
    return list(_walk(sdir["blocks"][0]))


def _set_block_text(sdir: dict, block_id: str, text: str) -> None:
    """测试侧改块并重算祖先 hash（模拟一次真实块编辑）。"""
    for block in _blocks(sdir):
        if block["id"] == block_id:
            block["text"] = text
            break
    else:
        raise AssertionError(block_id)

    def recalc(b: dict) -> str:
        child_hashes = [recalc(c) for c in b.get("children", [])]
        h = digest(
            {
                "type": b["type"],
                "text": b["text"],
                "attrs": b.get("attrs", {}),
                "children": child_hashes,
            }
        )
        b["hash"] = h
        return h

    recalc(sdir["blocks"][0])


def test_sdir_import_validates_and_has_block_trace(core: Path) -> None:
    sdir = _sdir(core)
    assert sdir["schema"] == "nf-sdir/1"
    blocks = _blocks(sdir)
    ids = {b["id"] for b in blocks}
    assert len(ids) == len(blocks)
    assert all(len(b["hash"]) == 64 for b in blocks)
    prov = {p["block"] for p in sdir["provenance"]}
    a11y = {a["block"] for a in sdir["accessibility"]}
    assert ids <= prov, "每个块必须有块级溯源"
    assert ids <= a11y, "每个块必须有可访问性记录"
    kinds = {r["kind"] for r in sdir["relations"]}
    assert "toc" in kinds and "crossref" in kinds
    code, env = _call(core, "sdir-validate", {"sdir": sdir})
    assert code == 0 and env["result"]["verdict"] == "pass"


def test_sdir_validate_detects_block_tamper(core: Path) -> None:
    sdir = _sdir(core)
    target = next(b for b in _blocks(sdir) if b["type"] == "paragraph")
    target["text"] += "（被篡改）"
    code, env = _call(core, "sdir-validate", {"sdir": sdir})
    assert code == 1
    assert env["error"]["code"] == "NF-SDIR-002"
    assert any("hash" in i["message"] for i in env["result"]["issues"])


def test_sdir_roundtrip_keeps_visible_text(core: Path, tmp_path: Path) -> None:
    sdir = _sdir(core)
    out = tmp_path / "roundtrip"
    out.mkdir()
    code, env = _call(
        core,
        "build-run",
        {"sdir": sdir, "outputs": [{"path": "out.md", "format": "md"}], "out_dir": str(out)},
    )
    assert code == 0, env
    code2, env2 = _call(core, "sdir-import", _req((out / "out.md").read_text(encoding="utf-8"), "roundtrip.md"))
    assert code2 == 0, env2
    before = "".join(b["text"] for b in _blocks(sdir) if b["type"] in ("heading", "paragraph", "list_item", "table_cell"))
    after = "".join(b["text"] for b in _blocks(env2["result"]) if b["type"] in ("heading", "paragraph", "list_item", "table_cell"))
    assert before == after


def test_build_is_byte_deterministic_and_cache_aware(core: Path, tmp_path: Path) -> None:
    sdir = _sdir(core)
    out = tmp_path / "build"
    out.mkdir()
    req = {
        "sdir": sdir,
        "outputs": [
            {"path": "a.md", "format": "md"},
            {"path": "a.html", "format": "html", "profile": "accessible"},
            {"path": "a.epub", "format": "epub"},
            {"path": "a.docx", "format": "docx"},
        ],
        "out_dir": str(out),
        "locale": "zh",
    }
    shas = []
    for _ in range(3):
        code, env = _call(core, "build-run", req)
        assert code == 0, env
        shas.append({a["path"]: a["sha256"] for a in env["result"]["artifacts"]})
    assert shas[0] == shas[1] == shas[2], "同输入同环境必须字节一致"

    code, plan1 = _call(
        core,
        "build-plan",
        {"sdir": sdir, "outputs": [{"path": "a.md", "format": "md"}], "locale": "zh"},
    )
    assert code == 0
    edited = json.loads(json.dumps(sdir))
    para = next(b for b in _blocks(edited) if b["type"] == "paragraph")
    _set_block_text(edited, para["id"], para["text"] + " 改一处。")
    code, plan2 = _call(
        core,
        "build-plan",
        {"sdir": edited, "outputs": [{"path": "a.md", "format": "md"}], "locale": "zh"},
    )
    assert code == 0
    key1 = next(n["cache_key"] for n in plan1["result"]["nodes"] if n["id"] == "t:0")
    key2 = next(n["cache_key"] for n in plan2["result"]["nodes"] if n["id"] == "t:0")
    assert key1 != key2, "块改动必须改变 transform cache_key"

    code, inc = _call(
        core,
        "build-incremental",
        {"old_graph": plan1["result"], "new_graph": plan2["result"], "out_dir": str(out)},
    )
    assert code == 0
    assert inc["result"]["rebuild"] == ["a.md"]


def test_build_incremental_reuses_unchanged_output(core: Path, tmp_path: Path) -> None:
    sdir = _sdir(core)
    out = tmp_path / "reuse"
    out.mkdir()
    spec = [{"path": "x.md", "format": "md"}, {"path": "x.html", "format": "html"}]
    code, built = _call(core, "build-run", {"sdir": sdir, "outputs": spec, "out_dir": str(out)})
    assert code == 0
    code, plan = _call(core, "build-plan", {"sdir": sdir, "outputs": spec})
    assert code == 0
    code, inc = _call(
        core,
        "build-incremental",
        {"old_graph": built["result"]["graph"], "new_graph": plan["result"], "out_dir": str(out)},
    )
    assert code == 0
    assert inc["result"]["rebuild"] == []
    assert sorted(inc["result"]["reuse"]) == ["x.html", "x.md"]


def test_evidence_offline_verify_and_tamper(core: Path, tmp_path: Path) -> None:
    sdir = _sdir(core)
    out = tmp_path / "ev"
    out.mkdir()
    code, built = _call(
        core,
        "build-run",
        {"sdir": sdir, "outputs": [{"path": "book.epub", "format": "epub"}], "out_dir": str(out)},
    )
    assert code == 0
    artifact = out / "book.epub"
    code, created = _call(
        core,
        "evidence-create",
        {
            "artifact_path": str(artifact),
            "sdir": sdir,
            "graph": built["result"]["graph"],
            "created_at": CREATED,
            "private_key": SEED,
            "profile": "accessible",
        },
    )
    assert code == 0, created
    ev = created["result"]
    assert ev["signature"]["alg"] == "ed25519"
    assert len(ev["provenance"]["block_lineage"]) == len(_blocks(sdir))

    code, verified = _call(core, "evidence-verify", {"evidence": ev, "artifact_path": str(artifact)})
    assert code == 0 and verified["result"]["ok"] is True

    tampered = out / "tampered.epub"
    tampered.write_bytes(artifact.read_bytes() + b"X")
    code, bad = _call(core, "evidence-verify", {"evidence": ev, "artifact_path": str(tampered)})
    assert code == 1 and bad["error"]["code"] == "NF-EVD-001"

    ev2 = json.loads(json.dumps(ev))
    ev2["artifact"]["path"] = "other.epub"
    code, bad2 = _call(core, "evidence-verify", {"evidence": ev2, "artifact_path": str(artifact)})
    assert code == 1 and bad2["error"]["code"] == "NF-EVD-003"


def test_semantic_merge_clean_and_conflict(core: Path) -> None:
    base = _sdir(core, "# T\n\nA\n\nB\n")
    ours = _sdir(core, "# T\n\nA ours\n\nB\n")
    theirs = _sdir(core, "# T\n\nA\n\nB theirs\n")
    code, merged = _call(core, "sdir-merge", {"base": base, "ours": ours, "theirs": theirs})
    assert code == 0, merged
    text = json.dumps(merged["result"]["merged"], ensure_ascii=False)
    assert "A ours" in text and "B theirs" in text

    conflict = _sdir(core, "# T\n\nA theirs\n\nB\n")
    code, bad = _call(core, "sdir-merge", {"base": base, "ours": ours, "theirs": conflict})
    assert code == 1
    assert bad["error"]["code"] == "NF-SDIR-004"

def test_evidence_package_is_deterministic_and_tamper_evident(core: Path, tmp_path: Path) -> None:
    import zipfile

    sdir = _sdir(core)
    out = tmp_path / "pkg"
    out.mkdir()
    code, built = _call(
        core,
        "build-run",
        {"sdir": sdir, "outputs": [{"path": "book.epub", "format": "epub"}], "out_dir": str(out)},
    )
    assert code == 0
    code, created = _call(
        core,
        "evidence-create",
        {
            "artifact_path": str(out / "book.epub"),
            "sdir": sdir,
            "graph": built["result"]["graph"],
            "created_at": CREATED,
            "private_key": SEED,
        },
    )
    assert code == 0
    ev = created["result"]
    pkg1, pkg2 = out / "a.nfpkg", out / "b.nfpkg"
    code, p1 = _call(core, "evidence-pack", {"artifact_path": str(out / "book.epub"), "evidence": ev, "out_path": str(pkg1)})
    assert code == 0
    code, p2 = _call(core, "evidence-pack", {"artifact_path": str(out / "book.epub"), "evidence": ev, "out_path": str(pkg2)})
    assert code == 0 and p1["result"]["sha256"] == p2["result"]["sha256"], "同输入证据包必须字节一致"
    code, verified = _call(core, "evidence-verify-package", {"package_path": str(pkg1)})
    assert code == 0 and verified["result"]["ok"] is True

    bad = out / "bad.nfpkg"
    with zipfile.ZipFile(pkg1) as z:
        entries = [(i.filename, z.read(i.filename)) for i in z.infolist()]
    with zipfile.ZipFile(bad, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries:
            z.writestr(name, data + b"X" if name.startswith("artifact/") else data)
    code, rejected = _call(core, "evidence-verify-package", {"package_path": str(bad)})
    assert code == 1 and rejected["error"]["code"] in ("NF-EVD-001", "NF-EVD-003")


def test_sdir_diff_reports_block_change(core: Path) -> None:
    a = _sdir(core, "# T\n\nA\n\nB\n")
    b = _sdir(core, "# T\n\nA changed\n\nB\n")
    code, env = _call(core, "sdir-diff", {"from": a, "to": b})
    assert code == 0
    changes = env["result"]["changes"]
    assert any(c["kind"] == "changed" and c["block"] for c in changes)
    assert env["result"]["summary"]["changed"] >= 1

def test_sdir_docx_import_preserves_headings_and_table(core: Path, tmp_path: Path) -> None:
    sdir = _sdir(core)
    out = tmp_path / "docx"
    out.mkdir()
    code, built = _call(
        core,
        "build-run",
        {"sdir": sdir, "outputs": [{"path": "doc.docx", "format": "docx"}], "out_dir": str(out)},
    )
    assert code == 0, built
    code, imported = _call(
        core,
        "sdir-import",
        {"docx_path": str(out / "doc.docx"), "created_at": CREATED, "lang": "zh"},
    )
    assert code == 0, imported
    got = imported["result"]
    level1 = [b for b in _blocks(got) if b["type"] == "heading" and b["attrs"].get("level") == 1]
    assert level1 and level1[0]["text"] == "雨夜边境"
    cells = [b["text"] for b in _blocks(got) if b["type"] == "table_cell"]
    assert "北门" in cells and "旅店" in cells
    code, valid = _call(core, "sdir-validate", {"sdir": got})
    assert code == 0 and valid["result"]["verdict"] == "pass"

def test_sdir_epub_import_preserves_spine_content(core: Path, tmp_path: Path) -> None:
    sdir = _sdir(core)
    out = tmp_path / "epub"
    out.mkdir()
    code, built = _call(
        core,
        "build-run",
        {"sdir": sdir, "outputs": [{"path": "book.epub", "format": "epub"}], "out_dir": str(out)},
    )
    assert code == 0, built
    code, imported = _call(
        core,
        "sdir-import",
        {"epub_path": str(out / "book.epub"), "created_at": CREATED, "lang": "zh"},
    )
    assert code == 0, imported
    got = imported["result"]
    headings = [(b["text"], b["attrs"].get("level")) for b in _blocks(got) if b["type"] == "heading"]
    assert ("雨夜边境", 1) in headings and ("地图", 2) in headings
    cells = [b["text"] for b in _blocks(got) if b["type"] == "table_cell"]
    assert "北门" in cells and "旅店" in cells
    assert any(b["type"] == "list_item" for b in _blocks(got))
    code, valid = _call(core, "sdir-validate", {"sdir": got})
    assert code == 0 and valid["result"]["verdict"] == "pass"

def test_plan_solve_sat_and_unsat(core: Path) -> None:
    req = {
        "slots": ["s1", "s2"],
        "modules": [
            {"id": "m1", "provides": ["s1"], "requires": ["m2"], "cost": 1},
            {"id": "m2", "provides": ["s2"], "cost": 2},
            {"id": "m3", "provides": ["s1", "s2"], "cost": 9},
        ],
        "budget": 5,
    }
    code, env = _call(core, "plan-solve", req)
    assert code == 0
    assert env["result"]["satisfiable"] is True
    assert env["result"]["selected"] == ["m1", "m2"]
    assert env["result"]["cost"] == 3

    code, env2 = _call(
        core,
        "plan-solve",
        {"slots": ["s1"], "modules": [{"id": "x", "provides": ["s2"], "cost": 1}], "budget": 5},
    )
    assert code == 0
    assert env2["result"]["satisfiable"] is False
    assert env2["result"]["unsat_core"] == ["s1"]

    code, explain = _call(core, "plan-explain", {"result": env["result"]})
    assert code == 0
    assert any("m1" in line for line in explain["result"]["explanation"])


def test_reuse_index_and_impact(core: Path) -> None:
    a = _sdir(core, "# A\n\n共享段落。\n\nA 独有。\n")
    b = _sdir(core, "# B\n\n共享段落。\n\nB 独有。\n")
    code, env = _call(core, "reuse-index", {"projects": [{"id": "p1", "sdir": a}, {"id": "p2", "sdir": b}]})
    assert code == 0
    assert env["result"]["summary"]["projects"] == 2
    shared = [x for x in env["result"]["blocks"] if len(x["projects"]) == 2 and x["type"] == "paragraph"]
    assert shared, "共享段落必须进入复用索引"
    h = shared[0]["hash"]
    code, impact = _call(core, "reuse-impact", {"index": env["result"], "changed": [h]})
    assert code == 0
    assert {x["project"] for x in impact["result"]["affected"]} == {"p1", "p2"}

def test_export_profile_and_accessible_guard(core: Path, tmp_path: Path) -> None:
    sdir = _sdir(core)
    out = tmp_path / "profiles"
    out.mkdir()
    code, env = _call(
        core,
        "export-profile",
        {"sdir": sdir, "profile": "print", "formats": ["html", "epub"], "out_dir": str(out)},
    )
    assert code == 0, env
    assert env["result"]["profile"] == "print"
    assert {a["path"].split("/")[0] for a in env["result"]["artifacts"]} == {"print"}
    assert (out / "print" / "index.html").is_file()

    code, acc = _call(
        core,
        "export-accessible",
        {"sdir": sdir, "formats": ["html", "epub", "docx"], "out_dir": str(out)},
    )
    assert code == 0, acc
    assert acc["result"]["accessibility"]["errors"] == 0
    assert len(acc["result"]["artifacts"]) == 3

    bad = _sdir(core, "# T\n\n![ ](map.png)\n")
    code, rejected = _call(core, "export-accessible", {"sdir": bad, "out_dir": str(out)})
    assert code == 1 and rejected["error"]["code"] == "NF-PROF-001"

def test_layout_import_pdf_blocks_and_fidelity(core: Path) -> None:
    pages = [
        {
            "number": 1,
            "width": 612,
            "height": 792,
            "words": [
                {"text": "Title", "x": 50, "y": 60, "w": 60, "h": 18},
                {"text": "Hello", "x": 50, "y": 110, "w": 40, "h": 10},
                {"text": "world", "x": 95, "y": 110, "w": 40, "h": 10},
                {"text": "Place", "x": 50, "y": 200, "w": 40, "h": 9},
                {"text": "Risk", "x": 200, "y": 200, "w": 30, "h": 9},
                {"text": "Inn", "x": 50, "y": 212, "w": 25, "h": 9},
                {"text": "Low", "x": 200, "y": 212, "w": 25, "h": 9},
                {"text": "[1]", "x": 50, "y": 700, "w": 15, "h": 8},
                {"text": "note", "x": 70, "y": 700, "w": 30, "h": 8},
            ],
        }
    ]
    code, env = _call(
        core,
        "layout-import",
        {
            "source": {"name": "x.pdf", "mime": "application/pdf", "bytes_sha": "0" * 64, "size": 100},
            "created_at": CREATED,
            "pages": pages,
            "lang": "en",
        },
    )
    assert code == 0, env
    sdir = env["result"]
    types = [b["type"] for b in _blocks(sdir)]
    assert "heading" in types and "paragraph" in types and "table" in types and "footnote" in types
    assert all(b.get("page") == 1 for b in _blocks(sdir) if b["type"] != "document")
    assert sdir["meta"]["fidelity"]["source_pages"] == 1
    assert sdir["meta"]["fidelity"]["features"]["table_cell"] == 4
    assert sdir["meta"]["fidelity"]["unprovenanced_blocks"] == 0
    code, valid = _call(core, "sdir-validate", {"sdir": sdir})
    assert code == 0 and valid["result"]["verdict"] == "pass"


def test_block_plan_parity_and_incremental(core: Path, tmp_path: Path) -> None:
    sdir = _sdir(core)
    out = tmp_path / "block"
    out.mkdir()
    code, bp = _call(core, "block-plan", {"sdir": sdir})
    assert code == 0
    code, built = _call(
        core,
        "build-run",
        {"sdir": sdir, "outputs": [{"path": "out.md", "format": "md"}], "out_dir": str(out)},
    )
    assert code == 0
    assert (out / "out.md").read_text(encoding="utf-8") == bp["result"]["output"]

    edited = json.loads(json.dumps(sdir))
    para = next(b for b in _blocks(edited) if b["type"] == "paragraph")
    _set_block_text(edited, para["id"], para["text"] + " block-edit")
    code, inc = _call(core, "block-incremental", {"sdir": edited, "old_blocks": bp["result"]["blocks"]})
    assert code == 0
    assert inc["result"]["recompute"] == [para["id"]]
    assert inc["result"]["stale"] == []
    code, built2 = _call(
        core,
        "build-run",
        {"sdir": edited, "outputs": [{"path": "out.md", "format": "md"}], "out_dir": str(out)},
    )
    assert code == 0
    assert (out / "out.md").read_text(encoding="utf-8") == inc["result"]["output"]


def test_template_and_schema_induction(core: Path) -> None:
    docs = [_sdir(core, "# A\n\na\n\n# B\n\nb\n\n# C\n\nc\n") for _ in range(3)]
    code, tpl = _call(core, "template-induce", {"docs": docs, "min_support": 1})
    assert code == 0
    assert {s["path"] for s in tpl["result"]["slots"]} == {"A", "B", "C"}

    old = _sdir(core, "# A\n\na\n\n# C\n\nc\n")
    code, mig = _call(core, "template-migrate", {"template": tpl["result"], "sdir": old})
    assert code == 0
    assert "B" in mig["result"]["added"] and mig["result"]["lost_blocks"] == []
    code, valid = _call(core, "sdir-validate", {"sdir": mig["result"]["sdir"]})
    assert code == 0

    code, spec = _call(core, "schema-induce", {"docs": docs, "id": "demo-spec", "title": "Demo"})
    assert code == 0
    assert {s["name"] for s in spec["result"]["slots"]} == {"A", "B", "C"}
    code, ok = _call(core, "spec-validate", {"spec": spec["result"]})
    assert code == 0 and ok["result"]["verdict"] == "pass"


def test_compose_isolation_and_fusion(core: Path, tmp_path: Path) -> None:
    sdir = _sdir(core)
    out = tmp_path / "compose"
    out.mkdir()
    code, comp = _call(
        core,
        "compose-run",
        {
            "out_dir": str(out),
            "jobs": [
                {"id": "ok", "sdir": sdir, "outputs": [{"path": "a.md", "format": "md"}]},
                {"id": "bad", "sdir": {"schema": "nf-sdir/1"}, "outputs": [{"path": "b.md", "format": "md"}]},
            ],
        },
    )
    assert code == 0
    jobs = {j["id"]: j for j in comp["result"]["jobs"]}
    assert jobs["ok"]["ok"] is True and jobs["bad"]["ok"] is False
    assert jobs["bad"]["recovered"] is True
    assert (out / "ok" / "a.md").is_file() and not (out / "bad").exists()

    a = _sdir(core, "# F\n\nA\n\nB\n")
    b = json.loads(json.dumps(a))
    c = json.loads(json.dumps(a))
    _set_block_text(b, next(x["id"] for x in _blocks(b) if x["text"] == "A"), "A alt")
    _set_block_text(c, next(x["id"] for x in _blocks(c) if x["text"] == "B"), "B alt")
    code, fused = _call(core, "sdir-fuse", {"sources": [a, b, c]})
    assert code == 1 and len(fused["result"]["conflicts"]) == 2
    code, valid = _call(core, "sdir-validate", {"sdir": fused["result"]["sdir"]})
    assert code == 0


def test_evidence_package_freeze_and_rollback(core: Path, tmp_path: Path) -> None:
    import zipfile

    sdir = _sdir(core)
    out = tmp_path / "freeze"
    out.mkdir()
    code, built = _call(
        core,
        "build-run",
        {"sdir": sdir, "outputs": [{"path": "book.epub", "format": "epub"}], "out_dir": str(out)},
    )
    assert code == 0
    code, created = _call(
        core,
        "evidence-create",
        {
            "artifact_path": str(out / "book.epub"),
            "sdir": sdir,
            "graph": built["result"]["graph"],
            "created_at": CREATED,
            "private_key": SEED,
        },
    )
    assert code == 0
    ev = created["result"]
    trust = out / "trust.json"
    v1, v2, tamper = out / "v1.nfpkg", out / "v2.nfpkg", out / "v1-tamper.nfpkg"
    for version, target in ((1, v1), (2, v2)):
        code, env = _call(
            core,
            "evidence-pack",
            {"artifact_path": str(out / "book.epub"), "evidence": ev, "out_path": str(target), "version": version},
        )
        assert code == 0, env
    code, frozen = _call(
        core,
        "evidence-freeze",
        {"package_path": str(v1), "trust_path": str(trust), "created_at": CREATED},
    )
    assert code == 0, frozen
    code, ok = _call(core, "evidence-verify-package", {"package_path": str(v1), "trust_path": str(trust)})
    assert code == 0 and ok["result"]["ok"] is True

    with zipfile.ZipFile(v1) as z:
        entries = [(i.filename, z.read(i.filename)) for i in z.infolist()]
    with zipfile.ZipFile(tamper, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries:
            z.writestr(name, data)
        z.writestr("extra.txt", b"freeze-probe")
    code, rejected = _call(core, "evidence-verify-package", {"package_path": str(tamper), "trust_path": str(trust)})
    assert code == 1 and rejected["error"]["code"] == "NF-EVD-004"

    code, frozen2 = _call(
        core,
        "evidence-freeze",
        {"package_path": str(v2), "trust_path": str(trust), "created_at": CREATED},
    )
    assert code == 0, frozen2
    code, rollback = _call(core, "evidence-verify-package", {"package_path": str(v1), "trust_path": str(trust)})
    assert code == 1 and rollback["error"]["code"] == "NF-EVD-004"

def test_pack_release_signature_and_rollback(core: Path, sample_pack: Path, tmp_path: Path) -> None:
    trust = tmp_path / "pack-trust.json"
    code, rel1 = _call(
        core,
        "pack-release-create",
        {"pack_root": str(sample_pack), "release_version": 1, "created_at": CREATED, "private_key": SEED},
    )
    assert code == 0, rel1
    r1 = rel1["result"]
    code, ok = _call(core, "pack-release-verify", {"release": r1, "pack_root": str(sample_pack)})
    assert code == 0 and ok["result"]["ok"] is True

    tampered = json.loads(json.dumps(r1))
    tampered["pack"]["tree"] = "0" * 64
    code, bad = _call(core, "pack-release-verify", {"release": tampered, "pack_root": str(sample_pack)})
    assert code == 1 and bad["error"]["code"] in ("NF-PCK-007", "NF-PCK-008")

    unsigned = json.loads(json.dumps(r1))
    unsigned.pop("signature")
    code, bad2 = _call(core, "pack-release-verify", {"release": unsigned, "pack_root": str(sample_pack)})
    assert code == 1 and bad2["error"]["code"] == "NF-PCK-007"

    code, fr1 = _call(
        core,
        "pack-release-freeze",
        {"release": r1, "trust_path": str(trust), "created_at": CREATED},
    )
    assert code == 0, fr1
    code, rel2 = _call(
        core,
        "pack-release-create",
        {"pack_root": str(sample_pack), "release_version": 2, "created_at": CREATED, "private_key": SEED},
    )
    assert code == 0, rel2
    r2 = rel2["result"]
    code, fr2 = _call(core, "pack-release-freeze", {"release": r2, "trust_path": str(trust), "created_at": CREATED})
    assert code == 0, fr2
    code, rollback = _call(core, "pack-release-verify", {"release": r1, "trust_path": str(trust)})
    assert code == 1 and rollback["error"]["code"] == "NF-PCK-009"
    code, latest = _call(core, "pack-release-verify", {"release": r2, "trust_path": str(trust)})
    assert code == 0 and latest["result"]["ok"] is True



def test_sdir_import_from_nf_doc_adapter(core: Path) -> None:
    doc = {
        "schema": "nf-doc/1",
        "meta": {"title": "迁移文档", "sources": ["a.md"]},
        "blocks": [
            {"id": "b1", "type": "section", "text": "", "title": "第一节"},
            {"id": "b2", "type": "paragraph", "text": "迁移段落。"},
            {"id": "b3", "type": "list", "text": "甲\n乙"},
        ],
    }
    code, env = _call(core, "sdir-import", {"doc": doc, "created_at": CREATED, "lang": "zh"})
    assert code == 0, env
    got = env["result"]
    types = [b["type"] for b in _blocks(got)]
    assert "heading" in types and "paragraph" in types and types.count("list_item") == 2
    assert got["meta"]["source_format"] == "nf-doc"






