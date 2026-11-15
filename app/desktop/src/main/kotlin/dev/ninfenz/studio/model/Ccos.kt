package dev.ninfenz.studio.model

import dev.ninfenz.studio.core.J
import dev.ninfenz.studio.core.ModelException
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

data class CcosArtifact(val name: String, val mime: String, val path: String, val sha256: String, val bytes: Long)
data class CcosEvidence(val kind: String, val ref: String, val digest: String)
data class CcosIssue(val code: String, val message: String, val path: String?)

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
    const val RESULT_SCHEMA = "ccos-result/1"

    fun parseResult(text: String): CcosResult = parseResult(J.parseObject(text, RESULT_SCHEMA))

    fun parseResult(o: JsonObject): CcosResult {
        J.schema(o, RESULT_SCHEMA)
        val artifacts = J.array(o, "artifacts", "").mapIndexed { i, el ->
            val a = el as? JsonObject ?: throw ModelException("NF-E-002", "/artifacts/" + i, "artifact 应为对象", "按 schema 修正")
            val ptr = "/artifacts/" + i
            CcosArtifact(
                name = J.string(a, "name", ptr),
                mime = J.optString(a, "mime") ?: "",
                path = J.string(a, "path", ptr),
                sha256 = J.string(a, "sha256", ptr),
                bytes = J.optLong(a, "bytes") ?: 0L
            )
        }
        val evidence = J.array(o, "evidence", "").mapIndexed { i, el ->
            val e = el as? JsonObject ?: throw ModelException("NF-E-002", "/evidence/" + i, "evidence 应为对象", "按 schema 修正")
            val ptr = "/evidence/" + i
            CcosEvidence(
                kind = J.string(e, "kind", ptr),
                ref = J.string(e, "ref", ptr),
                digest = J.string(e, "digest", ptr)
            )
        }
        val report = J.child(o, "report", "")
        val review = J.child(o, "human_review", "")
        val provenance = J.child(o, "provenance", "")
        val required = J.bool(review, "required", "/human_review")
        if (!required) {
            throw ModelException("NF-CCOS-004", "/human_review/required", "human_review.required 必须为 true", "拒绝导入该结果")
        }
        return CcosResult(
            taskId = J.string(o, "task_id", ""),
            taskDigest = J.string(o, "task_digest", ""),
            status = J.string(o, "status", ""),
            artifacts = artifacts,
            evidence = evidence,
            reportSummary = J.string(report, "summary", "/report"),
            issues = J.optArray(report, "issues").mapIndexed { i, el ->
                val it = el as? JsonObject ?: throw ModelException("NF-E-002", "/report/issues/" + i, "issue 应为对象", "按 schema 修正")
                CcosIssue(J.optString(it, "code") ?: "", J.optString(it, "message") ?: "", J.optString(it, "path"))
            },
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

    fun review(result: CcosResult, approve: Boolean, reviewer: String, note: String): ReviewOutcome {
        if (result.reviewState != "pending") {
            return ReviewOutcome(false, result.reviewState, "结果已裁决（" + result.reviewState + "），不可重复人审")
        }
        if (reviewer.isBlank()) return ReviewOutcome(false, result.reviewState, "reviewer 不能为空")
        if (note.isBlank()) return ReviewOutcome(false, result.reviewState, "note 不能为空")
        return ReviewOutcome(true, if (approve) "approved" else "rejected", "决策已记录：绑定 task_digest")
    }

    fun withReview(result: CcosResult, state: String, reviewer: String, note: String): CcosResult =
        result.copy(reviewState = state, reviewer = reviewer, note = note)

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
