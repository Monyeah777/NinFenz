package dev.ninfenz.mobile.model

import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.core.ModelException
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

data class CcosArtifact(val name: String, val mime: String, val path: String, val sha256: String, val bytes: Long)
data class CcosEvidence(val kind: String, val ref: String, val digest: String)
data class CcosIssue(val code: String, val message: String, val path: String?)

data class CcosTask(
    val id: String,
    val createdAt: String,
    val packId: String,
    val packVersion: String,
    val packTree: String,
    val protocolId: String,
    val protocolDigest: String,
    val pipelineDigest: String,
    val specDigest: String,
    val inputsCount: Int,
    val maxTokens: Int,
    val maxChars: Int,
    val maxSeconds: Int,
    val networkAllowed: Boolean,
    val secretsPolicy: String,
    val projectId: String,
    val projectDigest: String
)

data class CcosResult(
    val taskId: String,
    val taskDigest: String,
    val status: String,
    val artifacts: List<CcosArtifact>,
    val evidence: List<CcosEvidence>,
    val reportSummary: String,
    val issues: List<CcosIssue>,
    val reviewRequired: Boolean,
    val reviewState: String,
    val reviewer: String?,
    val note: String?,
    val engine: String,
    val startedAt: String,
    val finishedAt: String,
    val model: String?
)

data class ReviewOutcome(val ok: Boolean, val state: String, val message: String)

object CcosModel {
    const val TASK_SCHEMA = "ccos-task/1"
    const val RESULT_SCHEMA = "ccos-result/1"

    fun parseTask(text: String): CcosTask = parseTask(J.parseObject(text, TASK_SCHEMA))

    fun parseTask(o: JsonObject): CcosTask {
        J.schema(o, TASK_SCHEMA)
        val pack = J.child(o, "pack", "")
        val protocol = J.child(o, "protocol", "")
        val pipeline = J.child(o, "pipeline", "")
        val spec = J.child(o, "md_spec", "")
        val budget = J.child(o, "budget", "")
        val policy = J.child(o, "policy", "")
        val provenance = J.child(o, "provenance", "")
        // policy.network 必须 false（CONTRACT §5.11：APP 不直连 API）
        val network = J.bool(policy, "network", "/policy")
        if (network) {
            throw ModelException("NF-CCOS-003", "/policy/network", "ccos-task 策略越界：network=true", "改回 false；APP 不直连 API")
        }
        return CcosTask(
            id = J.string(o, "id", ""),
            createdAt = J.optString(o, "created_at") ?: "",
            packId = J.string(pack, "id", "/pack"),
            packVersion = J.string(pack, "version", "/pack"),
            packTree = J.string(pack, "tree", "/pack"),
            protocolId = J.string(protocol, "id", "/protocol"),
            protocolDigest = J.string(protocol, "digest", "/protocol"),
            pipelineDigest = J.string(pipeline, "digest", "/pipeline"),
            specDigest = J.string(spec, "digest", "/md_spec"),
            inputsCount = J.optArray(o, "inputs").size,
            maxTokens = J.int(budget, "max_tokens", "/budget"),
            maxChars = J.int(budget, "max_chars", "/budget"),
            maxSeconds = J.int(budget, "max_seconds", "/budget"),
            networkAllowed = network,
            secretsPolicy = J.string(policy, "secrets", "/policy"),
            projectId = J.string(provenance, "project_id", "/provenance"),
            projectDigest = J.string(provenance, "project_digest", "/provenance")
        )
    }

    fun parseResult(text: String): CcosResult {
        return parseResult(J.parseObject(text, RESULT_SCHEMA))
    }

    fun parseResult(o: JsonObject): CcosResult {
        J.schema(o, RESULT_SCHEMA)
        val artifacts = parseArtifacts(o)
        val evidence = parseEvidence(o)
        val report = J.child(o, "report", "")
        val review = J.child(o, "human_review", "")
        val provenance = J.child(o, "provenance", "")
        val required = J.bool(review, "required", "/human_review")
        if (!required) {
            throw ModelException(
                "NF-CCOS-004", "/human_review/required", "human_review.required 必须为 true（APP 人审不可关闭）",
                "拒绝导入该结果，要求 CCOS 重发"
            )
        }
        val issues = parseIssues(report)
        return CcosResult(
            taskId = J.string(o, "task_id", ""),
            taskDigest = J.string(o, "task_digest", ""),
            status = J.string(o, "status", ""),
            artifacts = artifacts,
            evidence = evidence,
            reportSummary = J.string(report, "summary", "/report"),
            issues = issues,
            reviewRequired = required,
            reviewState = J.string(review, "state", "/human_review"),
            reviewer = J.optString(review, "reviewer"),
            note = J.optString(review, "note"),
            engine = J.string(provenance, "engine", "/provenance"),
            startedAt = J.string(provenance, "started_at", "/provenance"),
            finishedAt = J.string(provenance, "finished_at", "/provenance"),
            model = J.optString(provenance, "model")
        )
    }

    private fun parseArtifacts(o: JsonObject): List<CcosArtifact> =
        J.array(o, "artifacts", "").mapIndexed { i, el ->
            val a = el as? JsonObject
                ?: throw ModelException("NF-E-002", "/artifacts/" + i, "artifact 应为对象", "按 schema 修正")
            val p = "/artifacts/" + i
            CcosArtifact(
                name = J.string(a, "name", p),
                mime = J.optString(a, "mime") ?: "",
                path = J.string(a, "path", p),
                sha256 = J.string(a, "sha256", p),
                bytes = J.optLong(a, "bytes") ?: 0L
            )
        }

    private fun parseEvidence(o: JsonObject): List<CcosEvidence> =
        J.array(o, "evidence", "").mapIndexed { i, el ->
            val e = el as? JsonObject
                ?: throw ModelException("NF-E-002", "/evidence/" + i, "evidence 应为对象", "按 schema 修正")
            val p = "/evidence/" + i
            CcosEvidence(
                kind = J.string(e, "kind", p),
                ref = J.string(e, "ref", p),
                digest = J.string(e, "digest", p)
            )
        }

    private fun parseIssues(report: JsonObject): List<CcosIssue> =
        J.optArray(report, "issues").mapIndexed { i, el ->
            val it = el as? JsonObject
                ?: throw ModelException("NF-E-002", "/report/issues/" + i, "issue 应为对象", "按 schema 修正")
            val p = "/report/issues/" + i
            CcosIssue(
                code = J.optString(it, "code") ?: "",
                message = J.optString(it, "message") ?: "",
                path = J.optString(it, "path")
            )
        }

    /** 人审状态机：pending 才能裁决；approved 必须 reviewer + note；rejected 必须有 note。 */
    fun review(result: CcosResult, approve: Boolean, reviewer: String, note: String): ReviewOutcome {
        if (result.reviewState != "pending") {
            return ReviewOutcome(false, result.reviewState, "结果已裁决（" + result.reviewState + "），不可重复人审")
        }
        if (reviewer.isBlank()) {
            return ReviewOutcome(false, result.reviewState, "reviewer 不能为空（评审要留痕）")
        }
        if (note.isBlank()) {
            return ReviewOutcome(false, result.reviewState, "note 不能为空（评审要留痕）")
        }
        val state = if (approve) "approved" else "rejected"
        return ReviewOutcome(true, state, "人审通过：reviewer=" + reviewer + "，绑定 task_digest")
    }

    fun withReview(result: CcosResult, state: String, reviewer: String, note: String): CcosResult =
        result.copy(reviewState = state, reviewer = reviewer, note = note)

    /** 构造送核心 ccos-import-result 的完整 result JSON（含人审裁决；不丢 provenance）。 */
    fun resultJson(result: CcosResult): JsonObject = buildJsonObject {
        put("schema", RESULT_SCHEMA)
        put("task_id", result.taskId)
        put("task_digest", result.taskDigest)
        put("status", result.status)
        put("artifacts", JsonArray(result.artifacts.map { a ->
            buildJsonObject {
                put("name", a.name)
                put("mime", a.mime)
                put("path", a.path)
                put("sha256", a.sha256)
                put("bytes", a.bytes)
            }
        }))
        put("evidence", JsonArray(result.evidence.map { e ->
            buildJsonObject {
                put("kind", e.kind)
                put("ref", e.ref)
                put("digest", e.digest)
            }
        }))
        put("report", buildJsonObject {
            put("summary", result.reportSummary)
            put("issues", JsonArray(result.issues.map { it ->
                buildJsonObject {
                    if (it.code.isNotEmpty()) put("code", it.code)
                    if (it.message.isNotEmpty()) put("message", it.message)
                    if (it.path != null) put("path", it.path)
                }
            }))
        })
        put("provenance", buildJsonObject {
            put("engine", result.engine)
            if (result.model != null) put("model", result.model)
            put("started_at", result.startedAt)
            put("finished_at", result.finishedAt)
        })
        put("human_review", buildJsonObject {
            put("required", true)
            put("state", result.reviewState)
            if (result.reviewer != null) put("reviewer", result.reviewer)
            if (result.note != null) put("note", result.note)
        })
    }
}
