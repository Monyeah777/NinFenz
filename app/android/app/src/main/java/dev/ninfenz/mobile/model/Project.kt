package dev.ninfenz.mobile.model

import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.core.ModelException
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
    private val ORDER = listOf(
        ProjectStatus.DRAFT,
        ProjectStatus.AUTHORING,
        ProjectStatus.ASSEMBLED,
        ProjectStatus.VALIDATED,
        ProjectStatus.EXPORTED,
        ProjectStatus.REVIEWED
    )

    fun parse(text: String): Project = parse(J.parseObject(text, SCHEMA))

    fun parse(o: JsonObject): Project {
        J.schema(o, SCHEMA)
        val refs = J.child(o, "refs", "")
        val base = J.child(refs, "base_pack", "/refs")
        val protocol = J.child(refs, "protocol", "/refs")
        val graph = J.child(refs, "graph", "/refs")
        val spec = J.child(refs, "spec", "/refs")
        val assembly = J.optChild(refs, "assembly")
        val statusWire = J.string(o, "status", "")
        val status = ProjectStatus.fromWire(statusWire)
            ?: throw ModelException("NF-E-002", "/status", "未知项目状态：" + statusWire, "改用 draft/authoring/assembled/validated/exported/reviewed")
        val reviewObj = J.child(o, "review", "")
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
                state = J.string(reviewObj, "state", "/review"),
                reviewer = J.optString(reviewObj, "reviewer"),
                note = J.optString(reviewObj, "note"),
                subjectDigest = J.optString(reviewObj, "subject_digest")
            ),
            historyCount = J.optArray(o, "history").size
        )
    }

    fun next(status: ProjectStatus): ProjectStatus? {
        val index = ORDER.indexOf(status)
        if (index < 0 || index + 1 >= ORDER.size) return null
        return ORDER[index + 1]
    }

    /**
     * 状态机（CONTRACT §5.10）：只能前进到相邻状态；回退/跳跃必须显式 force。
     */
    fun transition(current: ProjectStatus, target: ProjectStatus, force: Boolean): TransitionResult {
        if (current == target) {
            return TransitionResult(false, current, "已处于 " + current.wire + "，无需变更")
        }
        val currentIndex = ORDER.indexOf(current)
        val targetIndex = ORDER.indexOf(target)
        if (targetIndex == currentIndex + 1) {
            return TransitionResult(true, target, "前进：" + current.wire + " -> " + target.wire)
        }
        if (targetIndex < currentIndex) {
            if (!force) {
                return TransitionResult(false, current, "回退必须显式 force：" + current.wire + " -> " + target.wire + "，并记录 history")
            }
            return TransitionResult(true, target, "强制回退：" + current.wire + " -> " + target.wire + "（记 history）")
        }
        if (!force) {
            return TransitionResult(false, current, "禁止跳跃：" + current.wire + " -> " + target.wire + "（先走相邻状态或 force）")
        }
        return TransitionResult(true, target, "强制跳跃：" + current.wire + " -> " + target.wire + "（记 history）")
    }

    /** 评审约束：approved 必须 reviewer + note + subject_digest（CONTRACT §5.10）。 */
    fun reviewOk(review: ProjectReview): Boolean = when (review.state) {
        "none" -> true
        "pending" -> true
        "approved" -> !review.reviewer.isNullOrBlank() && !review.note.isNullOrBlank() && !review.subjectDigest.isNullOrBlank()
        "rejected" -> !review.note.isNullOrBlank()
        else -> false
    }
}
