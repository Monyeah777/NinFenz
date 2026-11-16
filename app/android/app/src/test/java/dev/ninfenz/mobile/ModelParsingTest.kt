package dev.ninfenz.mobile

import dev.ninfenz.mobile.core.ModelException
import dev.ninfenz.mobile.model.CcosModel
import dev.ninfenz.mobile.model.GraphEdge
import dev.ninfenz.mobile.model.GraphModel
import dev.ninfenz.mobile.model.GraphNode
import dev.ninfenz.mobile.model.ImportDoc
import dev.ninfenz.mobile.model.ImportModel
import dev.ninfenz.mobile.model.PackUpdate
import dev.ninfenz.mobile.model.PackUpdateModel
import dev.ninfenz.mobile.model.ProjectModel
import dev.ninfenz.mobile.model.ProjectStatus
import dev.ninfenz.mobile.model.ProtocolModel
import dev.ninfenz.mobile.model.ReportModel
import dev.ninfenz.mobile.model.SpecModel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class ModelParsingTest {

    private val importJson = """
        {
          "schema": "nf-import/1",
          "source": {"kind": "file", "name": "clip.md", "mime": "text/markdown", "size": 42},
          "detected": {"format": "markdown", "confidence": 92,
            "candidates": [{"format": "markdown", "confidence": 92}, {"format": "text", "confidence": 30}]},
          "text": "# 标题",
          "structure": {"headings": [{"line": 1, "level": 1, "text": "标题"}], "paragraphs": 1,
            "code_blocks": [{"lang": "markdown", "lines": 3}], "tables": [{"columns": 2, "rows": 1}]},
          "assets": [],
          "suggested": {"mappings": [{"from_kind": "heading", "from_index": 0, "to_kind": "section",
            "to_id": "SEC-01", "confidence": 80, "rationale": "标题映射到首节"}], "unmapped": ["素材 2"]},
          "warnings": [{"code": "NF-IMP-002", "message": "低置信", "path": "/detected/confidence"}]
        }
    """.trimIndent()

    @Test
    fun parsesImportDoc() {
        val doc = ImportModel.parse(importJson)
        assertEquals("markdown", doc.format)
        assertEquals(92, doc.confidence)
        assertFalse(doc.lowConfidence)
        assertEquals(2, doc.candidates.size)
        assertEquals(1, doc.structure.headings.size)
        assertEquals(1, doc.mappings.size)
        assertEquals(1, doc.unmapped.size)
        assertTrue(doc.reviewNotes().any { it.contains("候选格式") })
    }

    @Test
    fun flagsLowConfidenceImport() {
        val low = importJson.replace("\"confidence\": 92,", "\"confidence\": 30,")
        val doc = ImportModel.parse(low)
        assertTrue(doc.lowConfidence)
    }

    @Test
    fun rejectsUnknownSchemaVersion() {
        val bad = importJson.replace("nf-import/1", "nf-import/2")
        val e = assertThrows(ModelException::class.java) { ImportModel.parse(bad) }
        assertEquals("NF-E-001", e.code)
    }

    @Test
    fun rejectsFloatWhereIntRequired() {
        val bad = importJson.replace("\"confidence\": 92,", "\"confidence\": 92.5,")
        val e = assertThrows(ModelException::class.java) { ImportModel.parse(bad) }
        assertEquals("NF-E-006", e.code)
    }

    @Test
    fun parsesGraphAndDetectsFormIssues() {
        val graph = GraphModel.parse(graphJson())
        assertEquals(2, graph.nodes.size)
        assertEquals(1, graph.edges.size)
        assertEquals(2, graph.weights.size)
        assertTrue(GraphModel.formIssues(graph).isEmpty())

        val dup = graph.copy(nodes = graph.nodes + graph.nodes[0])
        assertTrue(GraphModel.formIssues(dup).any { it.code == "NF-GRF-002" })

        val dangling = graph.copy(edges = graph.edges + GraphEdge("E02", "N01", "N99", "text", "text", "data"))
        assertTrue(GraphModel.formIssues(dangling).any { it.code == "NF-GRF-003" })

        val badWeight = graph.copy(weights = mapOf("N01" to 200))
        assertTrue(GraphModel.formIssues(badWeight).any { it.code == "NF-GRF-007" })
    }

    @Test
    fun detectsCycleInGraph() {
        val graph = GraphModel.parse(graphJson())
        val cyc = graph.copy(
            nodes = graph.nodes.map { if (it.portsIn.isEmpty()) it.copy(portsIn = listOf("text")) else it },
            edges = graph.edges + GraphEdge("E02", "N02", "N01", "outline", "in", "data")
        )
        assertTrue(GraphModel.hasCycle(cyc))
        assertTrue(GraphModel.formIssues(cyc).any { it.code == "NF-GRF-004" })
    }

    @Test
    fun graphEditingHelpersArePure() {
        val graph = GraphModel.parse(graphJson())
        val added = GraphModel.withNode(graph, GraphNode("N03", "stage", "第三阶段", listOf("in"), listOf("out"), null, null, null))
        assertEquals(3, added.nodes.size)
        assertEquals(graph.nodes.size, graph.nodes.size)
        assertEquals("N04", GraphModel.nextNodeId(added))
        assertEquals("E02", GraphModel.nextEdgeId(graph))
        val removed = GraphModel.withoutNode(graph, "N01")
        assertEquals(1, removed.nodes.size)
        assertTrue(removed.edges.isEmpty())
        assertTrue(removed.weights.keys.none { it == "N01" })
        val weighted = GraphModel.withWeight(graph, "N01", 55)
        assertEquals(55, weighted.weights["N01"])
        assertEquals(null, GraphModel.withWeight(weighted, "N01", null).weights["N01"])
        val roundTrip = GraphModel.parse(GraphModel.toJson(graph).toString())
        assertEquals(graph.id, roundTrip.id)
        assertEquals(graph.nodes.size, roundTrip.nodes.size)
        assertEquals(graph.weights, roundTrip.weights)
    }

    @Test
    fun protocolPlaceholderChecks() {
        val pack = ProtocolModel.parse(protocolJson())
        val clause = pack.clauses.first()
        val missing = ProtocolModel.checkClause(pack, clause, emptyMap())
        assertEquals(listOf("F-001"), missing.missing)
        assertTrue(missing.unknown.isEmpty())
        val withValue = ProtocolModel.checkClause(pack, clause, mapOf("F-001" to "值"))
        assertTrue(withValue.ok)
        assertEquals("正文：值", ProtocolModel.renderPreview(clause, pack, mapOf("F-001" to "值")))
    }

    @Test
    fun protocolDetectsUnknownPlaceholder() {
        val pack = ProtocolModel.parse(protocolJson().replace("{{F-001}}", "{{F-001}} {{F-999}}"))
        val check = ProtocolModel.checkClause(pack, pack.clauses.first(), mapOf("F-001" to "值"))
        assertEquals(listOf("F-999"), check.unknown)
        assertFalse(check.ok)
    }

    @Test
    fun specFormIssuesDetectBijectionBreak() {
        val spec = SpecModel.parse(specJson())
        assertTrue(SpecModel.formIssues(spec).isEmpty())
        val broken = spec.copy(slots = spec.slots.map { it.copy(section = "SEC-09") })
        assertTrue(SpecModel.formIssues(broken).any { it.code == "NF-SPC-002" })
    }

    @Test
    fun parsesValidateReport() {
        val report = ReportModel.parse(reportJson())
        assertEquals("warn", report.verdict)
        assertEquals(1, report.warnCount)
        assertEquals("NF-GRF-005", report.issues.first().code)
        assertTrue(report.isWarn)
        assertFalse(report.isPass)
    }

    @Test
    fun parsesPackUpdateAndReverses() {
        val update = PackUpdateModel.parse(updateJson())
        assertEquals("demo-pack", update.from.id)
        assertEquals(1, update.added.size)
        assertEquals(1, update.removed.size)
        assertEquals(1, update.modified.size)
        assertTrue(update.breaking)
        assertEquals(1, update.conflicts.size)
        assertEquals("defer", update.conflicts.first().defaultOption)

        val reversed = PackUpdateModel.reversed(update)
        assertEquals(update.to.tree, reversed.from.tree)
        assertEquals(update.from.tree, reversed.to.tree)
        assertEquals(update.removed.map { it.path }, reversed.added.map { it.path })
        assertEquals(update.added.map { it.path }, reversed.removed.map { it.path })
        assertTrue(reversed.conflicts.isEmpty())

        val roundTrip = PackUpdateModel.parse(PackUpdateModel.toJson(update).toString())
        assertEquals(update.totalChanges, roundTrip.totalChanges)
        assertEquals(update.conflicts.size, roundTrip.conflicts.size)
        assertEquals(update.actions.size, roundTrip.actions.size)
    }

    @Test
    fun ccosTaskRejectsNetworkPolicy() {
        val bad = taskJson().replace("\"network\": false", "\"network\": true")
        val e = assertThrows(ModelException::class.java) { CcosModel.parseTask(bad) }
        assertEquals("NF-CCOS-003", e.code)
    }

    @Test
    fun ccosResultRequiresHumanReview() {
        val result = CcosModel.parseResult(resultJson())
        assertTrue(result.reviewRequired)
        assertEquals("pending", result.reviewState)
        val bad = resultJson().replace("\"required\": true", "\"required\": false")
        val e = assertThrows(ModelException::class.java) { CcosModel.parseResult(bad) }
        assertEquals("NF-CCOS-004", e.code)
    }

    @Test
    fun ccosReviewStateMachine() {
        val result = CcosModel.parseResult(resultJson())
        assertFalse(CcosModel.review(result, true, "", "note").ok)
        assertFalse(CcosModel.review(result, true, "reviewer-a", "").ok)
        val approved = CcosModel.review(result, true, "reviewer-a", "通过")
        assertTrue(approved.ok)
        assertEquals("approved", approved.state)
        val reviewed = CcosModel.withReview(result, approved.state, "reviewer-a", "通过")
        assertFalse(CcosModel.review(reviewed, false, "reviewer-b", "再驳").ok)
        val json = CcosModel.resultJson(reviewed)
        assertTrue(json["human_review"].toString().contains("approved"))
        assertTrue(json["provenance"].toString().contains("ccos-demo"))
    }

    @Test
    fun parsesProjectAndTransitions() {
        val project = ProjectModel.parse(projectJson())
        assertEquals(ProjectStatus.VALIDATED, project.status)
        assertEquals("approved", project.review.state)
        assertEquals(1, project.history.size)
        assertEquals("status:draft->authoring", project.history[0].op)
        assertEquals("9f14025af0065b30e47e23ebb3b491d39ae8ed17d33739e5ff3827ffb3634953", project.history[0].digest)
        assertTrue(ProjectModel.reviewOk(project.review))
        assertTrue(ProjectModel.transition(ProjectStatus.VALIDATED, ProjectStatus.EXPORTED, false).ok)
        assertFalse(ProjectModel.transition(ProjectStatus.VALIDATED, ProjectStatus.DRAFT, false).ok)
        assertTrue(ProjectModel.transition(ProjectStatus.VALIDATED, ProjectStatus.DRAFT, true).ok)
        assertFalse(ProjectModel.transition(ProjectStatus.DRAFT, ProjectStatus.VALIDATED, false).ok)
        assertNull(ProjectModel.next(ProjectStatus.REVIEWED))
        assertEquals(ProjectStatus.AUTHORING, ProjectModel.next(ProjectStatus.DRAFT))
        val brokenReview = project.review.copy(subjectDigest = null)
        assertFalse(ProjectModel.reviewOk(brokenReview))
    }

    // ---- 夹具 ----

    private fun graphJson(): String = """
        {
          "schema": "nf-pipeline-graph/1", "id": "demo-pipeline", "version": "1.0.0",
          "title": "演示管线", "mode": "pro",
          "nodes": [
            {"id": "N01", "kind": "stage", "title": "阶段", "ports": {"in": ["in"], "out": ["text"]}},
            {"id": "N02", "kind": "module", "title": "模块",
             "module_ref": {"id": "mod-outline", "version": "1.0.0"},
             "ports": {"in": ["text"], "out": ["outline"]}}
          ],
          "edges": [{"id": "E01", "from": "N01", "to": "N02", "from_port": "text", "to_port": "text", "type": "data"}],
          "weights": {"N01": 30, "N02": 40},
          "params": {"tone": "冷静"},
          "settings": {"required_stages": ["N01"], "seed": 42}
        }
    """.trimIndent()

    private fun protocolJson(): String = """
        {
          "schema": "nf-protocol-pack/1", "id": "demo-protocol", "version": "1.0.0", "title": "演示协议",
          "proto_version": 1,
          "clauses": [{"id": "C-001", "title": "首条", "level": "MUST", "text": "正文：{{F-001}}",
                       "enabled": true, "fields": ["F-001"]}],
          "fields": [{"id": "F-001", "clause": "C-001", "label": "字段值", "type": "text", "required": true,
                      "default": "默认值", "constraint": {"max_len": 120}}],
          "rules": [{"id": "R-001", "expr": {"op": "and", "args": [{"op": "exists", "field": "F-001"}]},
                     "severity": "error", "message": "必填", "fix": "补值"}],
          "examples": [{"id": "EX-01", "title": "示例", "keywords": ["演示"], "body": "示例正文"}],
          "compat": {"protocol_min": 1, "protocol_max": 1, "app_min": "1.0.0"},
          "migrations": []
        }
    """.trimIndent()

    private fun specJson(): String = """
        {
          "schema": "nf-md-spec/1", "id": "demo-spec", "title": "演示规范", "domain": "写作",
          "version": "1.0.0", "heading_level": 2,
          "sections": [{"id": "SEC-01", "title": "开篇", "order": 1, "required": true, "slots": ["SLT-01"]}],
          "slots": [{"id": "SLT-01", "name": "开头段", "section": "SEC-01", "kind": "text", "required": true,
                     "constraints": [], "examples": [], "acceptance": [], "budget": {"max_chars": 200}}],
          "constraints": [], "acceptance": [], "references": []
        }
    """.trimIndent()

    private fun reportJson(): String = """
        {
          "schema": "nf-validate-report/1",
          "target": {"kind": "nf-pipeline-graph/1", "ref": "demo-pipeline",
                     "digest": "8527a891e224136950ff32ca212b45bc93f69fbb801c3b1ebedac52775f99e61"},
          "level": "L1",
          "issues": [{"code": "NF-GRF-005", "severity": "warn", "path": "$.settings.required_stages",
                      "message": "缺必需阶段", "fix": "补阶段"}],
          "summary": {"error": 0, "warn": 1, "info": 0},
          "verdict": "warn"
        }
    """.trimIndent()

    private fun updateJson(): String = """
        {
          "schema": "nf-pack-update/1",
          "from": {"id": "demo-pack", "version": "1.0.0", "tree": "e629fa6598d732768f7c726b4b621285f9c3b85303900aa912017db7617d8bdb"},
          "to": {"id": "demo-pack", "version": "1.1.0", "tree": "b17ef6d19c7a5b1ee83b907c595526dcb1eb06db8227d650d5dda0a9f4ce8cd9"},
          "changes": {
            "added": [{"path": "assets/new.md", "sha256": "4523540f1504cd17100c4835e85b7eefd49911580f8efff0599a8f283be6b9e3", "size": 10}],
            "removed": [{"path": "docs/legacy.md", "sha256": "4ec9599fc203d176a301536c2e091a19bc852759b255bd6818810a42c5fed14a"}],
            "modified": [{"path": "spec/main.nfspec.json",
                          "sha256": "9400f1b21cb527d7fa3d3eabba93557a18ebe7a2ca4e471cfe5e4c5b4ca7f767",
                          "new_sha256": "f5ca38f748a1d6eaf726b8a42fb575c3c71f1864a8143301782de13da2d9202b"}]
          },
          "impact": {"breaking": true, "projects": ["demo-project"], "overlay_keys": ["clauses"], "notes": ["删除文件"]},
          "merge": {"actions": [{"kind": "take_new", "path": "assets/new.md", "reason": "added"},
                                {"kind": "defer", "path": "docs/legacy.md", "reason": "removed"}],
                    "on_conflict": "require_user"},
          "conflicts": [{"id": "CFL-01", "kind": "delete", "path": "docs/legacy.md",
                         "old_sha256": "4ec9599fc203d176a301536c2e091a19bc852759b255bd6818810a42c5fed14a",
                         "options": ["keep_mine", "take_new", "defer"], "default": "defer"}],
          "policy": {"auto_merge": true, "backup": true, "rollback": true}
        }
    """.trimIndent()

    private fun taskJson(): String = """
        {
          "schema": "ccos-task/1", "id": "task-demo-0001", "created_at": "2026-11-15T00:00:00Z",
          "pack": {"id": "demo-pack", "version": "1.0.0", "tree": "1a6562590ef19d1045d06c4055742d38288e9e6dcd71ccde5cee80f1d5a774eb"},
          "protocol": {"id": "demo-protocol", "version": "1.0.0", "digest": "031b4af5197ec30a926f48cf40e11a7dbc470048a21e4003b7a3c07c5dab1baa"},
          "pipeline": {"id": "demo-pipeline", "version": "1.0.0", "digest": "41cfc0d1f2d127b04555b7246d84019b4d27710a3f3aff6e7764375b1e06e05d"},
          "md_spec": {"id": "demo-spec", "version": "1.0.0", "digest": "2858dcd1057d3eae7f7d5f782167e24b61153c01551450a628cee722509f6529"},
          "inputs": [{"slot": "SLT-01", "value": "开头"}], "variables": {"tone": "冷静"},
          "constraints": ["遵守预算"], "acceptance": ["A-01"],
          "budget": {"max_tokens": 1000, "max_chars": 4000, "max_seconds": 600},
          "policy": {"network": false, "tools": ["write"], "secrets": "ccos-only"},
          "provenance": {"project_id": "demo-project",
                         "project_digest": "2fca346db656187102ce806ac732e06a62df0dbb2829e511a770556d398e1a6e",
                         "app_version": "0.1.0"}
        }
    """.trimIndent()

    private fun resultJson(): String = """
        {
          "schema": "ccos-result/1", "task_id": "task-demo-0001",
          "task_digest": "02d20bbd7e394ad5999a4cebabac9619732c343a4cac99470c03e23ba2bdc2bc",
          "status": "succeeded",
          "artifacts": [{"name": "result.md", "mime": "text/markdown", "path": "artifacts/result.md",
                         "sha256": "7688b6ef52555962d008fff894223582c484517cea7da49ee67800adc7fc8866", "bytes": 100}],
          "evidence": [{"kind": "log", "ref": "evidence/run.log",
                        "digest": "c837649cce43f2729138e72cc315207057ac82599a59be72765a477f22d14a54"}],
          "report": {"summary": "完成", "issues": []},
          "provenance": {"engine": "ccos-demo", "model": "demo-model",
                         "started_at": "2026-11-15T00:00:00Z", "finished_at": "2026-11-15T00:01:00Z"},
          "human_review": {"required": true, "state": "pending"}
        }
    """.trimIndent()

    private fun projectJson(): String = """
        {
          "schema": "nf-project/1", "id": "demo-project", "title": "演示项目",
          "refs": {
            "base_pack": {"id": "demo-pack", "version": "1.0.0", "tree": "b7a56873cd771f2c446d369b649430b65a756ba278ff97ec81bb6f55b2e73569"},
            "overlay": {"path": "overlay/nf-overlay.json", "sha256": "5f9c4ab08cac7457e9111a30e4664920607ea2c115a1433d7be98e97e64244ca"},
            "protocol": {"id": "demo-protocol", "version": "1.0.0", "digest": "670671cd97404156226e507973f2ab8330d3022ca96e0c93bdbdb320c41adcaf"},
            "graph": {"path": "graph/main.nfg.json", "sha256": "59e19706d51d39f66711c2653cd7eb1291c94d9b55eb14bda74ce4dc636d015a",
                      "digest": "35135aaa6cc23891b40cb3f378c53a17a1127210ce60e125ccf03efcfdaec458"},
            "spec": {"path": "spec/main.nfspec.json", "sha256": "624b60c58c9d8bfb6ff1886c2fd605d2adeb6ea4da576068201b6c6958ce93f4",
                     "digest": "eb1e33e8a81b697b75855af6bfcdbcbf7cbbde9f94962ceaec1ed8af21f5a50f"},
            "assembly": {"path": "out/plan.nfplan.json", "sha256": "e29c9c180c6279b0b02abd6a1801c7c04082cf486ec027aa13515e4f3884bb6b",
                         "digest": "c6f3ac57944a531490cd39902d0f777715fd005efac9a30622d5f5205e7f6894"}
          },
          "status": "validated",
          "review": {"state": "approved", "reviewer": "reviewer-a", "note": "首闭环通过",
                     "subject_digest": "86e50149658661312a9e0b35558d84f6c6d3da797f552a9657fe0558ca40cdef"},
          "history": [{"op": "status:draft->authoring", "at": "2026-11-15T00:00:00Z",
                       "digest": "9f14025af0065b30e47e23ebb3b491d39ae8ed17d33739e5ff3827ffb3634953"}]
        }
    """.trimIndent()
}
