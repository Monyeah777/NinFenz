"""sample-pack / sample-pack-v2：首闭环演示用的小 pack（内容真源按 ID+digest 引用）。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fixtures_common import write_canonical
from nf_app.canonical import canonical_text, digest
from nf_app.pack import compute_items, tree_digest

SAMPLE_MD = """# 西幻生存开篇（示例导入）

## 场景

雨夜的边境小镇，主角必须在一个时辰内找到落脚点。

## 结构

1. 开头：环境压力
2. 中段：选择与代价
3. 结尾：留下钩子

## 示例

{fen}markdown
> 引用：灯灭之前，别回头。
{fen}

| 项 | 值 |
|---|---|
| 语气 | 冷静 |
| 节奏 | 中速 |
""".replace("{fen}", chr(96) * 3)

SAMPLE_TONE = "# 语气规范\n\n- 冷静\n- 具体\n- 不喊口号\n"
SAMPLE_BRAND = "# 品牌备注\n\n- 保持克制\n- 不蹭热点\n"
SAMPLE_LEGACY = "# 旧版说明\n\n本文件只用于 pack 更新演示：v2 会删除它。\n"
SAMPLE_GLOSSARY = {
    "schema": "nf-glossary/1",
    "terms": [
        {"term": "钩子", "meaning": "结尾悬念"},
        {"term": "闭环", "meaning": "从输入到可交付产物的完整路径"},
    ],
}


def sample_protocol() -> dict:
    return {
        "schema": "nf-protocol-pack/1",
        "id": "demo-protocol",
        "version": "1.0.0",
        "title": "示例写作协议",
        "proto_version": 1,
        "clauses": [
            {
                "id": "C-001",
                "title": "主题句先行",
                "level": "MUST",
                "text": "开篇必须给出可验证的主题句：{{F-001}}",
                "enabled": True,
                "fields": ["F-001"],
                "source": {"path": "01_核心协议.md", "anchor": "§主题"},
            },
            {
                "id": "C-002",
                "title": "语气克制",
                "level": "SHOULD",
                "text": "全文语气保持{{F-002}}，禁止夸张广告语。",
                "enabled": True,
                "fields": ["F-002"],
            },
            {
                "id": "C-003",
                "title": "引用可追溯",
                "level": "SHOULD",
                "text": "引用素材时给出可追溯标识：{{F-003}}",
                "enabled": False,
                "fields": ["F-003"],
            },
        ],
        "fields": [
            {"id": "F-001", "clause": "C-001", "label": "主题句", "type": "text", "required": True},
            {
                "id": "F-002",
                "clause": "C-002",
                "label": "语气",
                "type": "enum",
                "required": True,
                "options": ["冷静", "温和", "犀利"],
                "default": "冷静",
            },
            {"id": "F-003", "clause": "C-003", "label": "素材标识", "type": "text", "required": False},
        ],
        "rules": [
            {
                "id": "R-001",
                "expr": {"op": "exists", "field": "F-001"},
                "severity": "error",
                "message": "主题句必填",
                "fix": "补 F-001",
            },
            {
                "id": "R-002",
                "expr": {"op": "in", "field": "F-002", "value": ["冷静", "温和", "犀利"]},
                "severity": "warn",
                "message": "语气需在白名单内",
                "fix": "选用白名单语气",
            },
        ],
        "examples": [
            {"id": "EX-01", "title": "雨夜开篇", "keywords": ["西幻", "生存"], "body": "灯灭之前，别回头。"}
        ],
        "compat": {"protocol_min": 1, "protocol_max": 1, "app_min": "0.1.0"},
        "migrations": [],
    }


def sample_graph() -> dict:
    return {
        "schema": "nf-pipeline-graph/1",
        "id": "demo-pipeline",
        "version": "1.0.0",
        "title": "示例管线",
        "mode": "pro",
        "nodes": [
            {"id": "N01", "kind": "stage", "title": "输入", "ports": {"in": [], "out": ["text"]}},
            {
                "id": "N02",
                "kind": "module",
                "title": "大纲",
                "module_ref": {"id": "mod-outline", "version": "1.0.0"},
                "ports": {"in": ["text"], "out": ["outline"]},
            },
            {"id": "N03", "kind": "stage", "title": "起草", "ports": {"in": ["outline"], "out": ["draft"]}},
            {
                "id": "N04",
                "kind": "module",
                "title": "润色",
                "module_ref": {"id": "mod-polish", "version": "1.0.0"},
                "ports": {"in": ["draft"], "out": ["final"]},
            },
            {"id": "N05", "kind": "gate", "title": "质检", "ports": {"in": ["final"], "out": ["checked"]}},
        ],
        "edges": [
            {"id": "E01", "from": "N01", "to": "N02", "from_port": "text", "to_port": "text", "type": "data"},
            {"id": "E02", "from": "N02", "to": "N03", "from_port": "outline", "to_port": "outline", "type": "data"},
            {"id": "E03", "from": "N03", "to": "N04", "from_port": "draft", "to_port": "draft", "type": "data"},
            {"id": "E04", "from": "N04", "to": "N05", "from_port": "final", "to_port": "final", "type": "data"},
        ],
        "weights": {"N01": 30, "N02": 40, "N04": 70},
        "params": {"tone": "冷静"},
        "settings": {
            "required_stages": ["N01", "N03"],
            "seed": 42,
            "budget": {"max_tokens": 4000, "max_chars": 12000},
        },
    }


def sample_spec(protocol_digest: str) -> dict:
    return {
        "schema": "nf-md-spec/1",
        "id": "demo-spec",
        "title": "示例开篇规范",
        "domain": "写作",
        "version": "1.0.0",
        "heading_level": 2,
        "sections": [
            {"id": "SEC-01", "title": "开篇", "order": 1, "required": True, "slots": ["SLT-01", "SLT-02"]},
            {"id": "SEC-02", "title": "正文", "order": 2, "required": True, "slots": ["SLT-03"]},
            {"id": "SEC-03", "title": "收束", "order": 3, "required": False, "slots": ["SLT-04"]},
        ],
        "slots": [
            {
                "id": "SLT-01",
                "name": "主题句",
                "section": "SEC-01",
                "kind": "text",
                "required": True,
                "constraints": [{"op": "max_chars", "value": 200}, {"op": "non_empty"}],
                "examples": ["灯灭之前，别回头。"],
                "acceptance": ["A-01"],
                "budget": {"max_chars": 200, "max_tokens": 100},
            },
            {
                "id": "SLT-02",
                "name": "读者设定",
                "section": "SEC-01",
                "kind": "text",
                "required": True,
                "constraints": [{"op": "max_chars", "value": 100}],
                "examples": [],
                "acceptance": ["A-01"],
                "budget": {"max_chars": 100, "max_tokens": 50},
            },
            {
                "id": "SLT-03",
                "name": "正文段落",
                "section": "SEC-02",
                "kind": "text",
                "required": True,
                "constraints": [{"op": "max_chars", "value": 2000}],
                "examples": [],
                "acceptance": ["A-02"],
                "budget": {"max_chars": 2000, "max_tokens": 800},
            },
            {
                "id": "SLT-04",
                "name": "补充",
                "section": "SEC-03",
                "kind": "text",
                "required": False,
                "constraints": [{"op": "max_chars", "value": 500}],
                "examples": [],
                "acceptance": [],
                "budget": {"max_chars": 500, "max_tokens": 200},
            },
        ],
        "constraints": [],
        "acceptance": [
            {"id": "A-01", "description": "开篇必须有主题句与读者设定", "severity": "error"},
            {"id": "A-02", "description": "正文不超预算", "severity": "warn"},
        ],
        "references": [{"kind": "protocol", "ref": "demo-protocol", "digest": protocol_digest}],
    }


def build_pack(root: Path, version: str, spec_mutator=None) -> None:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    protocol = sample_protocol()
    protocol_digest = digest(protocol)
    graph = sample_graph()
    spec = sample_spec(protocol_digest)
    if spec_mutator is not None:
        spec_mutator(spec)
    files = {
        "protocol/nf-protocol-pack.json": canonical_text(protocol),
        "pipeline/main.nfg.json": canonical_text(graph),
        "spec/main.nfspec.json": canonical_text(spec),
        "assets/tone.md": SAMPLE_TONE,
        "assets/glossary.json": canonical_text(SAMPLE_GLOSSARY),
        "assets/notes-brand.md": SAMPLE_BRAND,
        "docs/sample.md": SAMPLE_MD,
        "docs/legacy.md": SAMPLE_LEGACY,
    }
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))
    items = compute_items(root)
    manifest = {
        "schema": "nf-pack/1",
        "id": "demo-pack",
        "version": version,
        "kind": "base",
        "title": "示例 Pack（首闭环演示）",
        "description": "protocol + pipeline + md spec + assets + 示例 md；tree 由 nf_app.pack 独立计算。",
        "items": items,
        "hashes": {"tree": tree_digest(items), "count": len(items)},
        "requires": [],
        "compat": {"min_app_version": "0.1.0", "schema_version": 1},
    }
    write_canonical(root / "nf-pack.json", manifest)


def build_sample_packs(fixtures: Path) -> dict:
    v1 = fixtures / "sample-pack"
    build_pack(v1, "1.0.0")

    def v2_spec(spec: dict) -> None:
        spec["version"] = "1.1.0"
        for slot in spec["slots"]:
            if slot["id"] == "SLT-03":
                slot["budget"]["max_chars"] = 1800
                slot["constraints"] = [{"op": "max_chars", "value": 1800}]

    v2 = fixtures / "sample-pack-v2"
    build_pack(v2, "1.0.0", v2_spec)
    (v2 / "assets" / "v2-added.md").write_bytes("# v2 新增资产\n\n- 更新说明\n".encode("utf-8"))
    (v2 / "docs" / "legacy.md").unlink()
    (v2 / "assets" / "notes-brand.md").unlink()
    items = compute_items(v2)
    manifest = json.loads((v2 / "nf-pack.json").read_text(encoding="utf-8"))
    manifest["items"] = items
    manifest["version"] = "1.1.0"
    manifest["hashes"] = {"tree": tree_digest(items), "count": len(items)}
    write_canonical(v2 / "nf-pack.json", manifest)
    return {"v1_tree": json.loads((v1 / "nf-pack.json").read_text(encoding="utf-8"))["hashes"]["tree"],
            "v2_tree": manifest["hashes"]["tree"]}
