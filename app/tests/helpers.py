"""测试辅助：sample-pack 工作区、项目/Overlay/CCOS 结果夹具（不依赖核心）。

只做夹具装配与摘要；校验判据一律走 CLI/核心，不在这里实现另一套语义。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from nf_app.canonical import canonical_text, digest, digest_excluding, sha256_hex

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "app" / "fixtures"
SAMPLE_PACK = FIXTURES / "sample-pack"
SAMPLE_PACK_V2 = FIXTURES / "sample-pack-v2"


def load_json(path: Path | str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256_hex(data: bytes) -> str:
    """测试断言用：内容摘要（等价 sha256；不是 core 实现）。"""
    import hashlib

    return hashlib.sha256(data).hexdigest()


def pack_manifest(root: Path | str = SAMPLE_PACK) -> dict:
    return load_json(Path(root) / "nf-pack.json")


def rel(target: Path | str, base: Path | str) -> str:
    return Path(target).resolve().relative_to(Path(base).resolve()).as_posix()


def pack_files(root: Path | str = SAMPLE_PACK) -> dict[str, dict]:
    """{相对路径: {"path","sha256","size"}}，以 nf-pack.json items 为准。"""
    manifest = pack_manifest(root)
    return {item["path"]: item for item in manifest["items"]}


def make_workspace(tmp_path: Path, *, pack: Path = SAMPLE_PACK) -> Path:
    """复制 pack 到临时工作区：<ws>/pack/...，项目文件放在 <ws> 下。"""
    ws = Path(tmp_path) / "ws"
    shutil.copytree(Path(pack), ws / "pack")
    return ws


def project_doc(
    ws: Path,
    *,
    status: str = "authoring",
    project_id: str = "demo-project",
    overlay_path: Path | None = None,
) -> dict:
    pack_root = ws / "pack"
    manifest = pack_manifest(pack_root)
    graph_path = pack_root / "pipeline" / "main.nfg.json"
    spec_path = pack_root / "spec" / "main.nfspec.json"
    protocol_path = pack_root / "protocol" / "nf-protocol-pack.json"
    graph = load_json(graph_path)
    spec = load_json(spec_path)
    protocol = load_json(protocol_path)
    refs: dict = {
        "base_pack": {"id": manifest["id"], "version": manifest["version"], "tree": manifest["hashes"]["tree"]},
        "protocol": {"id": protocol["id"], "version": protocol["version"], "digest": digest(protocol)},
        "graph": {
            "id": graph["id"],
            "version": graph["version"],
            "digest": digest(graph),
            "path": rel(graph_path, ws),
            "sha256": sha256_hex(graph_path.read_bytes()),
        },
        "spec": {
            "id": spec["id"],
            "version": spec["version"],
            "digest": digest(spec),
            "path": rel(spec_path, ws),
            "sha256": sha256_hex(spec_path.read_bytes()),
        },
    }
    if overlay_path is not None:
        refs["overlay"] = {"path": rel(overlay_path, ws), "sha256": sha256_hex(Path(overlay_path).read_bytes())}
    return {
        "schema": "nf-project/1",
        "id": project_id,
        "title": "首闭环演示项目",
        "refs": refs,
        "status": status,
        "review": {"state": "none"},
        "history": [],
    }


def write_project(ws: Path, project: dict, name: str = "project.nfproject.json") -> Path:
    path = ws / name
    path.write_bytes(canonical_text(project).encode("utf-8"))
    return path


def write_json(path: Path | str, obj: object) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canonical_text(obj).encode("utf-8"))
    return target


def project_digest(project: dict) -> str:
    return digest_excluding(project, ["history"])


def inputs_doc() -> dict:
    return {
        "SLT-01": "灯灭之前，别回头。",
        "SLT-02": "面向喜欢西幻生存流的读者。",
        "SLT-03": "雨夜的边境小镇，主角必须在一个时辰内找到落脚点，否则只能露宿街头。",
    }


def overlay_doc(ws: Path) -> dict:
    """覆盖层：条款开关 + 自定义资产（assets/notes-brand.md，v2 会删除它 → 冲突）。"""
    pack_root = ws / "pack"
    manifest = pack_manifest(pack_root)
    protocol = load_json(pack_root / "protocol" / "nf-protocol-pack.json")
    brand_path = pack_root / "assets" / "notes-brand.md"
    clause_text = next(c["text"] for c in protocol["clauses"] if c["id"] == "C-001")
    return {
        "schema": "nf-overlay/1",
        "base": {"id": manifest["id"], "version": manifest["version"], "tree": manifest["hashes"]["tree"]},
        "clauses": {
            "C-001": {"enabled": False, "text_sha256": sha256_hex(clause_text.encode("utf-8"))},
            "C-002": {"enabled": True},
        },
        "params": {"tone": "冷静"},
        "presets": [],
        "custom_assets": [
            {
                "key": "brand",
                "path": "assets/notes-brand.md",
                "sha256": sha256_hex(brand_path.read_bytes()),
                "size": len(brand_path.read_bytes()),
            }
        ],
    }


def ccos_result_doc(task: dict, *, markdown_text: str = "# 结果\n\n灯灭之前，别回头。\n") -> dict:
    """模拟 CCOS 回传结果：task_digest 回钉 + 人审 pending。"""
    markdown_bytes = markdown_text.encode("utf-8")
    return {
        "schema": "ccos-result/1",
        "task_id": task["id"],
        "task_digest": digest(task),
        "status": "succeeded",
        "artifacts": [
            {
                "name": "result.md",
                "mime": "text/markdown",
                "path": "artifacts/result.md",
                "sha256": sha256_hex(markdown_bytes),
                "bytes": len(markdown_bytes),
            }
        ],
        "evidence": [{"kind": "log", "ref": "evidence/run.log", "digest": sha256_hex(b"selftest-log")}],
        "report": {"summary": "按规范完成", "issues": []},
        "provenance": {
            "engine": "ccos-sim",
            "model": "sim",
            "started_at": "2026-11-15T00:00:00Z",
            "finished_at": "2026-11-15T00:05:00Z",
        },
        "human_review": {"required": True, "state": "pending"},
    }
