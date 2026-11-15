"""13 个 schema 的正向样例（结构面：语义 digest 用确定性假值）。"""

from __future__ import annotations

from fixtures_common import d


def valid_docs() -> dict[str, list[dict]]:
    pack = {
        "schema": "nf-pack/1",
        "id": "demo-pack",
        "version": "1.0.0",
        "kind": "base",
        "title": "演示 Pack",
        "items": [
            {"path": "protocol/nf-protocol-pack.json", "kind": "protocol", "sha256": d("a"), "size": 128},
            {"path": "spec/main.nfspec.json", "kind": "md-spec", "sha256": d("b"), "size": 256, "mime": "application/json"},
        ],
        "hashes": {"tree": d("tree"), "count": 2},
        "requires": [{"id": "base-lib", "min": "1.0.0", "max": "1.9.9"}],
        "compat": {"min_app_version": "1.0.0", "schema_version": 1},
        "x-created_at": "2026-11-15T00:00:00Z",
    }
    import_doc = {
        "schema": "nf-import/1",
        "source": {"kind": "file", "name": "clip.md", "mime": "text/markdown", "size": 42, "sha256": d("c")},
        "detected": {
            "format": "markdown",
            "confidence": 92,
            "candidates": [{"format": "markdown", "confidence": 92}, {"format": "text", "confidence": 30}],
        },
        "text": "# 标题\n\n正文。",
        "text_digest": d("c"),
        "structure": {
            "headings": [{"line": 1, "level": 1, "text": "标题"}],
            "paragraphs": 1,
            "code_blocks": [{"lang": "markdown", "lines": 3}],
            "tables": [{"columns": 2, "rows": 1}],
        },
        "assets": [{"path": "assets/a.png", "sha256": d("e"), "size": 10, "mime": "image/png"}],
        "suggested": {
            "template_id": "demo-spec",
            "mappings": [
                {
                    "from_kind": "heading",
                    "from_index": 0,
                    "to_kind": "section",
                    "to_id": "SEC-01",
                    "confidence": 80,
                    "rationale": "一级标题映射到首节",
                }
            ],
            "unmapped": ["段落 2"],
        },
        "warnings": [{"code": "NF-IMP-002", "message": "低置信", "path": "/detected/confidence"}],
    }
    protocol = {
        "schema": "nf-protocol-pack/1",
        "id": "demo-protocol",
        "version": "1.0.0",
        "title": "演示协议",
        "proto_version": 1,
        "clauses": [
            {
                "id": "C-001",
                "title": "主题句先行",
                "level": "MUST",
                "text": "开篇必须给出主题句：{{F-001}}",
                "enabled": True,
                "fields": ["F-001"],
                "source": {"path": "01_核心协议.md", "anchor": "§1"},
            }
        ],
        "fields": [
            {
                "id": "F-001",
                "clause": "C-001",
                "label": "主题句",
                "type": "text",
                "required": True,
                "default": "在这里写主题句",
                "constraint": {"max_len": 120},
            }
        ],
        "rules": [
            {
                "id": "R-001",
                "expr": {"op": "and", "args": [{"op": "exists", "field": "F-001"}, {"field": "F-001"}]},
                "severity": "error",
                "message": "主题句必填",
                "fix": "补主题句",
            }
        ],
        "examples": [{"id": "EX-01", "title": "示例", "keywords": ["西幻"], "body": "示例正文"}],
        "compat": {"protocol_min": 1, "protocol_max": 1, "app_min": "1.0.0"},
        "migrations": [{"from": 1, "to": 2, "steps": ["声明式迁移：人工确认后再执行"]}],
    }
    graph = {
        "schema": "nf-pipeline-graph/1",
        "id": "demo-pipeline",
        "version": "1.0.0",
        "title": "演示管线",
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
        ],
        "edges": [
            {"id": "E01", "from": "N01", "to": "N02", "from_port": "text", "to_port": "text", "type": "data"}
        ],
        "weights": {"N01": 30, "N02": 40},
        "params": {"tone": "冷静"},
        "settings": {"required_stages": ["N01"], "seed": 42, "budget": {"max_tokens": 1000, "max_chars": 4000}},
    }
    spec = {
        "schema": "nf-md-spec/1",
        "id": "demo-spec",
        "title": "演示规范",
        "domain": "写作",
        "version": "1.0.0",
        "heading_level": 2,
        "sections": [
            {"id": "SEC-01", "title": "开篇", "order": 1, "required": True, "slots": ["SLT-01"]},
        ],
        "slots": [
            {
                "id": "SLT-01",
                "name": "主题句",
                "section": "SEC-01",
                "kind": "text",
                "required": True,
                "lang": "markdown",
                "constraints": [{"op": "max_chars", "value": 200}, {"op": "non_empty"}],
                "examples": ["雨夜，灯灭之前别回头。"],
                "acceptance": ["A-01"],
                "budget": {"max_chars": 200, "max_tokens": 100},
            }
        ],
        "constraints": [{"op": "min_chars", "value": 1}],
        "acceptance": [{"id": "A-01", "description": "开篇必须有主题句", "severity": "error"}],
        "references": [{"kind": "protocol", "ref": "demo-protocol", "digest": d("f")}],
    }
    plan = {
        "schema": "nf-assembly-plan/1",
        "pipeline": {"id": "demo-pipeline", "version": "1.0.0", "digest": d("10")},
        "steps": [
            {
                "id": "S01",
                "node": "N02",
                "stage": "N01",
                "module": "mod-outline",
                "weight": 40,
                "inputs": ["text"],
                "outputs": ["outline"],
                "params": {"tone": "冷静"},
            }
        ],
        "modules": [{"id": "mod-outline", "version": "1.0.0", "digest": d("11")}],
        "assets": [{"key": "tone", "digest": d("12")}],
        "slots": ["SLT-01"],
        "output": {"form": "md", "path": "result.md"},
        "fallback": {"on_failure": "abort", "max_retries": 0},
        "settings": {"seed": 42},
        "digest": d("13"),
    }
    report = {
        "schema": "nf-validate-report/1",
        "target": {"kind": "nf-pipeline-graph/1", "ref": "demo-pipeline", "digest": d("14")},
        "level": "L1",
        "issues": [
            {
                "code": "NF-GRF-005",
                "severity": "warn",
                "path": "$.settings.required_stages",
                "message": "未声明必需阶段",
                "fix": "补 settings.required_stages",
                "rule": "graph.required_stages",
            }
        ],
        "summary": {"error": 0, "warn": 1, "info": 0},
        "verdict": "warn",
    }
    update = {
        "schema": "nf-pack-update/1",
        "from": {"id": "demo-pack", "version": "1.0.0", "tree": d("15")},
        "to": {"id": "demo-pack", "version": "1.1.0", "tree": d("16")},
        "changes": {
            "added": [{"path": "assets/new.md", "sha256": d("17"), "size": 10}],
            "removed": [{"path": "docs/legacy.md", "sha256": d("18")}],
            "modified": [{"path": "spec/main.nfspec.json", "sha256": d("19"), "new_sha256": d("20")}],
        },
        "impact": {"breaking": True, "projects": ["demo-project"], "overlay_keys": ["clauses"], "notes": ["删除文件"]},
        "merge": {
            "actions": [
                {"kind": "take_new", "path": "assets/new.md", "reason": "added"},
                {"kind": "defer", "path": "docs/legacy.md", "reason": "removed"},
            ],
            "on_conflict": "require_user",
        },
        "conflicts": [
            {
                "id": "CFL-01",
                "kind": "delete",
                "path": "docs/legacy.md",
                "old_sha256": d("18"),
                "options": ["keep_mine", "take_new", "defer"],
                "default": "defer",
            }
        ],
        "policy": {"auto_merge": True, "backup": True, "rollback": True},
    }
    overlay = {
        "schema": "nf-overlay/1",
        "base": {"id": "demo-pack", "version": "1.0.0", "tree": d("21")},
        "clauses": {"C-001": {"enabled": False, "text_sha256": d("22")}},
        "params": {"tone": "冷静"},
        "presets": [{"id": "preset-a", "name": "预设 A", "graph": d("23")}],
        "custom_assets": [{"key": "brand", "path": "assets/notes-brand.md", "sha256": d("24"), "size": 10}],
    }
    project = {
        "schema": "nf-project/1",
        "id": "demo-project",
        "title": "演示项目",
        "refs": {
            "base_pack": {"id": "demo-pack", "version": "1.0.0", "tree": d("25")},
            "overlay": {"path": "overlay/nf-overlay.json", "sha256": d("26")},
            "protocol": {"id": "demo-protocol", "version": "1.0.0", "digest": d("27")},
            "graph": {
                "id": "demo-pipeline",
                "version": "1.0.0",
                "digest": d("29"),
                "path": "graph/main.nfg.json",
                "sha256": d("28"),
            },
            "spec": {
                "id": "demo-spec",
                "version": "1.0.0",
                "digest": d("31"),
                "path": "spec/main.nfspec.json",
                "sha256": d("30"),
            },
            "assembly": {
                "id": "demo-pipeline",
                "version": "1.0.0",
                "digest": d("33"),
                "path": "out/plan.nfplan.json",
                "sha256": d("32"),
            },
        },
        "status": "validated",
        "review": {"state": "approved", "reviewer": "reviewer-a", "note": "首闭环通过", "subject_digest": d("34")},
        "history": [{"op": "status:draft->authoring", "at": "2026-11-15T00:00:00Z", "digest": d("35")}],
    }
    template = {
        "schema": "nf-template/1",
        "manifest": {"id": "demo-template", "version": "1.0.0", "title": "演示模板", "description": "内嵌快照"},
        "template_md": {"path": "template/template.md", "sha256": d("40")},
        "spec": {"path": "template/spec.json", "sha256": d("41")},
        "protocol": {"path": "template/protocol.json", "sha256": d("42")},
        "pipeline": {"path": "template/pipeline.json", "sha256": d("43")},
        "assets": [{"path": "template/assets/a.md", "sha256": d("44"), "size": 10}],
        "hashes": {"tree": d("45"), "count": 5},
        "compat": {"min_app_version": "1.0.0", "schema_version": 1},
    }
    ccos_task = {
        "schema": "ccos-task/1",
        "id": "task-demo-0001",
        "created_at": "2026-11-15T00:00:00Z",
        "pack": {"id": "demo-pack", "version": "1.0.0", "tree": d("50")},
        "protocol": {"id": "demo-protocol", "version": "1.0.0", "digest": d("51")},
        "pipeline": {"id": "demo-pipeline", "version": "1.0.0", "digest": d("52")},
        "md_spec": {"id": "demo-spec", "version": "1.0.0", "digest": d("53")},
        "inputs": [{"slot": "SLT-01", "value": "雨夜，灯灭之前别回头。"}],
        "variables": {"tone": "冷静"},
        "constraints": ["字数在预算内"],
        "acceptance": ["A-01"],
        "budget": {"max_tokens": 1000, "max_chars": 4000, "max_seconds": 600},
        "policy": {"network": False, "tools": ["write"], "secrets": "ccos-only"},
        "provenance": {"project_id": "demo-project", "project_digest": d("54"), "app_version": "0.1.0"},
    }
    ccos_result = {
        "schema": "ccos-result/1",
        "task_id": "task-demo-0001",
        "task_digest": d("55"),
        "status": "succeeded",
        "artifacts": [
            {"name": "result.md", "mime": "text/markdown", "path": "artifacts/result.md", "sha256": d("56"), "bytes": 100}
        ],
        "evidence": [{"kind": "log", "ref": "evidence/run.log", "digest": d("57")}],
        "report": {"summary": "完成", "issues": []},
        "provenance": {
            "engine": "ccos-demo",
            "model": "demo-model",
            "started_at": "2026-11-15T00:00:00Z",
            "finished_at": "2026-11-15T00:01:00Z",
        },
        "human_review": {"required": True, "state": "pending"},
    }
    assemble_meta = {
        "schema": "nf-assemble-result/1",
        "plan_digest": d("60"),
        "spec_digest": d("61"),
        "markdown_digest": d("62"),
        "slots": [
            {"id": "SLT-01", "section": "SEC-01", "chars": 12},
            {"id": "SLT-02", "section": "SEC-01", "chars": 0},
        ],
        "missing": ["SLT-02"],
    }
    export_manifest = {
        "schema": "nf-export-manifest/1",
        "format": "md",
        "files": [{"name": "result.md", "sha256": d("63"), "bytes": 128}],
        "source": {"plan_digest": d("60"), "spec_digest": d("61"), "markdown_digest": d("62")},
    }
    backup = {
        "schema": "nf-backup/1",
        "created_at": "2026-11-15T00:00:00Z",
        "tree": d("64"),
        "files": [{"path": "docs/a.md", "sha256": d("65")}],
    }
    return {
        "nf-pack": [pack],
        "nf-import": [import_doc],
        "nf-protocol-pack": [protocol],
        "nf-pipeline-graph": [graph],
        "nf-md-spec": [spec],
        "nf-assembly-plan": [plan],
        "nf-validate-report": [report],
        "nf-pack-update": [update],
        "nf-overlay": [overlay],
        "nf-project": [project],
        "nf-template": [template],
        "ccos-task": [ccos_task],
        "ccos-result": [ccos_result],
        "nf-assemble-result": [assemble_meta],
        "nf-export-manifest": [export_manifest],
        "nf-backup": [backup],
    }