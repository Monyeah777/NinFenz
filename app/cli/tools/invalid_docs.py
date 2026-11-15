"""13 个 schema 的反向样例（每个至少 2 个，按具体约束构造并登记期望错误码）。"""

from __future__ import annotations

from fixtures_common import d, mutate


def invalid_docs(valid: dict[str, list[dict]]) -> list[tuple[str, str, dict, list[str], str]]:
    """返回 (schema, 文件名, 文档, 期望码, 违反的约束说明)。"""
    rows: list[tuple[str, str, dict, list[str], str]] = []
    pack = valid["nf-pack"][0]
    protocol = valid["nf-protocol-pack"][0]
    graph = valid["nf-pipeline-graph"][0]
    spec = valid["nf-md-spec"][0]
    plan = valid["nf-assembly-plan"][0]
    report = valid["nf-validate-report"][0]
    update = valid["nf-pack-update"][0]
    overlay = valid["nf-overlay"][0]
    project = valid["nf-project"][0]
    template = valid["nf-template"][0]
    task = valid["ccos-task"][0]
    result = valid["ccos-result"][0]
    import_doc = valid["nf-import"][0]
    assemble_meta = valid["nf-assemble-result"][0]
    export_manifest = valid["nf-export-manifest"][0]
    backup = valid["nf-backup"][0]

    def add(stem, name, doc, codes, violated):
        rows.append((stem, name, doc, codes, violated))

    add("nf-pack", "inv-id-pattern.json", mutate(pack, lambda x: x.__setitem__("id", "Demo_Pack")), ["NF-PCK-001"], "id 必须 ^[a-z][a-z0-9-]{1,63}$（大写/下划线非法）")
    add("nf-pack", "inv-item-path-traversal.json", mutate(pack, lambda x: x["items"][0].__setitem__("path", "../escape.md")), ["NF-PCK-003"], "item.path 禁 .. 与出包路径")
    add("nf-pack", "inv-missing-requires.json", mutate(pack, lambda x: x.pop("requires")), ["NF-PCK-001"], "顶层 required 缺 requires")

    add("nf-import", "inv-detected-format-unknown.json", mutate(import_doc, lambda x: x["detected"].__setitem__("format", "xlsx")), ["NF-E-002"], "detected.format 不在 enum（未知格式 fail-closed）")
    add("nf-import", "inv-mapping-missing-rationale.json", mutate(import_doc, lambda x: x["suggested"]["mappings"][0].pop("rationale")), ["NF-IMP-001"], "suggested.mappings[] required rationale")
    add("nf-import", "inv-heading-level-range.json", mutate(import_doc, lambda x: x["structure"]["headings"][0].__setitem__("level", 7)), ["NF-IMP-001"], "structure.headings[].level maximum 6")

    add("nf-protocol-pack", "inv-rule-op-unknown.json", mutate(protocol, lambda x: x["rules"][0]["expr"].__setitem__("op", "xor")), ["NF-E-002"], "rule.expr.op 不在白名单（未知 op fail-closed）")
    add("nf-protocol-pack", "inv-clause-id-pattern.json", mutate(protocol, lambda x: x["clauses"][0].__setitem__("id", "C-1")), ["NF-PRT-001"], "clause.id 必须 ^C-[0-9]{3}$")
    add("nf-protocol-pack", "inv-compat-missing-app-min.json", mutate(protocol, lambda x: x["compat"].pop("app_min")), ["NF-PRT-001"], "compat required app_min")

    add("nf-pipeline-graph", "inv-node-id-pattern.json", mutate(graph, lambda x: x["nodes"][0].__setitem__("id", "AN01")), ["NF-GRF-001"], "node.id 必须 ^N[0-9]{2,3}$")
    add("nf-pipeline-graph", "inv-weight-out-of-range.json", mutate(graph, lambda x: x["weights"].__setitem__("N02", 150)), ["NF-GRF-007"], "weights 值 0..100")
    add("nf-pipeline-graph", "inv-settings-additional-props.json", mutate(graph, lambda x: x["settings"].__setitem__("unknown_key", 1)), ["NF-GRF-001"], "settings additionalProperties=false")

    add("nf-md-spec", "inv-slot-section-missing.json", mutate(spec, lambda x: x["slots"][0].pop("section")), ["NF-SPC-002"], "slot.section 必填（section/slot 双向一致的前置）")
    add("nf-md-spec", "inv-constraint-op-unknown.json", mutate(spec, lambda x: x["slots"][0]["constraints"][0].__setitem__("op", "equals")), ["NF-E-002"], "constraint.op enum")
    add("nf-md-spec", "inv-heading-level-range.json", mutate(spec, lambda x: x.__setitem__("heading_level", 7)), ["NF-SPC-001"], "heading_level 1..4")

    add("nf-assembly-plan", "inv-step-id-pattern.json", mutate(plan, lambda x: x["steps"][0].__setitem__("id", "S1")), ["NF-VAL-001"], "step.id 必须 ^S[0-9]{2}$")
    add("nf-assembly-plan", "inv-digest-uppercase.json", mutate(plan, lambda x: x.__setitem__("digest", d("13").upper())), ["NF-ASM-001"], "digest 必须小写 64hex")

    add("nf-validate-report", "inv-verdict-unknown.json", mutate(report, lambda x: x.__setitem__("verdict", "passed")), ["NF-VAL-001"], "verdict enum pass/warn/fail")
    add("nf-validate-report", "inv-target-missing-digest.json", mutate(report, lambda x: x["target"].pop("digest")), ["NF-VAL-003"], "target.digest 必填（不可追溯）")

    add("nf-pack-update", "inv-conflict-option-unknown.json", mutate(update, lambda x: x["conflicts"][0]["options"].append("keep_theirs")), ["NF-E-002"], "conflict.options enum")
    add("nf-pack-update", "inv-changes-missing-modified.json", mutate(update, lambda x: x["changes"].pop("modified")), ["NF-PCK-001"], "changes required added/removed/modified")
    add("nf-pack-update", "inv-breaking-string.json", mutate(update, lambda x: x["impact"].__setitem__("breaking", "yes")), ["NF-PCK-001"], "impact.breaking 必须是 boolean")

    add("nf-overlay", "inv-preset-id-pattern.json", mutate(overlay, lambda x: x["presets"][0].__setitem__("id", "Preset A")), ["NF-PCK-001"], "preset.id pattern")
    add("nf-overlay", "inv-base-tree-short.json", mutate(overlay, lambda x: x["base"].__setitem__("tree", "abc")), ["NF-PCK-001"], "base.tree 必须 64hex")

    add("nf-project", "inv-status-unknown.json", mutate(project, lambda x: x.__setitem__("status", "done")), ["NF-E-002"], "status enum（未知状态 fail-closed）")
    add("nf-project", "inv-refs-missing-spec.json", mutate(project, lambda x: x["refs"].pop("spec")), ["NF-VAL-001"], "refs required spec")
    add("nf-project", "inv-history-op-empty.json", mutate(project, lambda x: x["history"][0].__setitem__("op", "")), ["NF-VAL-001"], "history[].op minLength 1")

    add("nf-template", "inv-manifest-id-pattern.json", mutate(template, lambda x: x["manifest"].__setitem__("id", "Tpl")), ["NF-PCK-001"], "manifest.id pattern")
    add("nf-template", "inv-assets-missing-sha256.json", mutate(template, lambda x: x["assets"][0].pop("sha256")), ["NF-PCK-001"], "assets[] required sha256")

    add("ccos-task", "inv-policy-network-true.json", mutate(task, lambda x: x["policy"].__setitem__("network", True)), ["NF-CCOS-003"], "policy.network 必须 false（策略越界）")
    add("ccos-task", "inv-budget-missing-seconds.json", mutate(task, lambda x: x["budget"].pop("max_seconds")), ["NF-CCOS-001"], "budget required max_seconds")
    add("ccos-task", "inv-extra-secret-field.json", mutate(task, lambda x: x.__setitem__("api_key", "sk-should-not-be-here")), ["NF-CCOS-003"], "顶层 additionalProperties=false（禁密钥形状字段）")

    add("ccos-result", "inv-human-review-required-false.json", mutate(result, lambda x: x["human_review"].__setitem__("required", False)), ["NF-CCOS-004"], "human_review.required const true")
    add("ccos-result", "inv-task-digest-short.json", mutate(result, lambda x: x.__setitem__("task_digest", "deadbeef")), ["NF-CCOS-002"], "task_digest 必须 64hex（回钉）")
    add("ccos-result", "inv-artifact-missing-bytes.json", mutate(result, lambda x: x["artifacts"][0].pop("bytes")), ["NF-CCOS-001"], "artifacts[] required bytes")

    add("nf-assemble-result", "inv-slot-missing-section.json", mutate(assemble_meta, lambda x: x["slots"][0].pop("section")), ["NF-ASM-003"], "slots[] required section（nf-assemble-result/1）")
    add("nf-assemble-result", "inv-chars-negative.json", mutate(assemble_meta, lambda x: x["slots"][0].__setitem__("chars", -1)), ["NF-ASM-003"], "slots[].chars integer minimum 0")

    add("nf-export-manifest", "inv-format-unknown.json", mutate(export_manifest, lambda x: x.__setitem__("format", "html")), ["NF-E-002"], "format enum md/zip/json/docx/pdf（未知格式 fail-closed）")
    add("nf-export-manifest", "inv-files-missing-bytes.json", mutate(export_manifest, lambda x: x["files"][0].pop("bytes")), ["NF-EXP-001"], "files[] required bytes")

    add("nf-backup", "inv-tree-short.json", mutate(backup, lambda x: x.__setitem__("tree", "abc")), ["NF-PCK-007"], "tree 必须 64hex（备份清单不可校验）")
    add("nf-backup", "inv-file-path-empty.json", mutate(backup, lambda x: x["files"][0].__setitem__("path", "")), ["NF-PCK-007"], "files[].path minLength 1")
    return rows
