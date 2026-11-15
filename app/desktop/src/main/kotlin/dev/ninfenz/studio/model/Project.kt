package dev.ninfenz.studio.model

import dev.ninfenz.studio.core.J
import dev.ninfenz.studio.core.ModelException
import kotlinx.serialization.json.JsonObject

enum class ProjectStatus(val wire: String) {
    DRAFT("draft"),
    AUTHORING("authoring"),
    ASSEMBLED("assembled"),
    VALIDATED("validated"),
    EXPORTED("exported"),
    REVIEWED("reviewed");

    companion object {
        fun fromWire(value: String): ProjectStatus? = values().firstOrNull { it.wire == value }
    }
}

data class ProjectRefs(
    val basePackId: String,
    val basePackVersion: String,
    val basePackTree: String,
    val protocolId: String,
    val protocolDigest: String,
    val graphDigest: String,
    val specDigest: String,
    val assemblyDigest: String?
)

data class ProjectReview(
    val state: String,
    val reviewer: String?,
    val note: String?,
    val subjectDigest: String?
)

data class Project(
    val id: String,
    val title: String,
    val refs: ProjectRefs,
    val status: ProjectStatus,
    val review: ProjectReview,
    val historyCount: Int
)

data class TransitionResult(val ok: Boolean, val status: ProjectStatus, val message: String)

object ProjectModel {
    const val SCHEMA = "nf-project/1"
    private val ORDER = ProjectStatus.values().toList()

    fun parse(text: String): Project = parse(J.parseObject(text, SCHEMA))

    fun parse(o: JsonObject): Project {
        J.schema(o, SCHEMA)
        val refs = J.child(o, "refs", "")
        val base = J.child(refs, "base_pack", "/refs")
        val protocol = J.child(refs, "protocol", "/refs")
        val graph = J.child(refs, "graph", "/refs")
        val spec = J.child(refs, "spec", "/refs")
        val assembly = J.optChild(refs, "assembly")
        val wire = J.string(o, "status", "")
        val status = ProjectStatus.fromWire(wire)
            ?: throw ModelException("NF-E-002", "/status", "未知项目状态：" + wire, "改用 draft/authoring/assembled/validated/exported/reviewed")
        val review = J.child(o, "review", "")
        return Project(
            id = J.string(o, "id", ""),
            title = J.string(o, "title", ""),
            refs = ProjectRefs(
                basePackId = J.string(base, "id", "/refs/base_pack"),
                basePackVersion = J.string(base, "version", "/refs/base_pack"),
                basePackTree = J.optString(base, "tree") ?: "",
                protocolId = J.optString(protocol, "id") ?: "",
                protocolDigest = J.optString(protocol, "digest") ?: "",
                graphDigest = J.optString(graph, "digest") ?: "",
                specDigest = J.optString(spec, "digest") ?: "",
                assemblyDigest = assembly?.let { J.optString(it, "digest") }
            ),
            status = status,
            review = ProjectReview(
                state = J.string(review, "state", "/review"),
                reviewer = J.optString(review, "reviewer"),
                note = J.optString(review, "note"),
                subjectDigest = J.optString(review, "subject_digest")
            ),
            historyCount = J.optArray(o, "history").size
        )
    }

    fun transition(current: ProjectStatus, target: ProjectStatus, force: Boolean): TransitionResult {
        if (current == target) return TransitionResult(false, current, "已处于 " + current.wire)
        val ci = ORDER.indexOf(current)
        val ti = ORDER.indexOf(target)
        if (ti == ci + 1) return TransitionResult(true, target, "前进：" + current.wire + " -> " + target.wire)
        if (ti < ci) {
            return if (force) TransitionResult(true, target, "强制回退：" + current.wire + " -> " + target.wire)
            else TransitionResult(false, current, "回退必须 force：" + current.wire + " -> " + target.wire)
        }
        return if (force) TransitionResult(true, target, "强制跳跃：" + current.wire + " -> " + target.wire)
        else TransitionResult(false, current, "禁止跳跃：" + current.wire + " -> " + target.wire)
    }

    fun reviewOk(review: ProjectReview): Boolean = when (review.state) {
        "none", "pending" -> true
        "approved" -> !review.reviewer.isNullOrBlank() && !review.note.isNullOrBlank() && !review.subjectDigest.isNullOrBlank()
        "rejected" -> !review.note.isNullOrBlank()
        else -> false
    }
}
