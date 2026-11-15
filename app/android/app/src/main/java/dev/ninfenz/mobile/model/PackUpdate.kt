package dev.ninfenz.mobile.model

import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.core.ModelException
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

data class PackRef(val id: String, val version: String, val tree: String)

data class ChangeEntry(
    val path: String,
    val sha256: String,
    val newSha256: String?,
    val size: Long?
)

data class PackConflict(
    val id: String,
    val kind: String,
    val path: String,
    val oldSha256: String?,
    val newSha256: String?,
    val options: List<String>,
    val defaultOption: String
)

data class PackUpdate(
    val from: PackRef,
    val to: PackRef,
    val added: List<ChangeEntry>,
    val removed: List<ChangeEntry>,
    val modified: List<ChangeEntry>,
    val breaking: Boolean,
    val affectedProjects: List<String>,
    val overlayKeys: List<String>,
    val notes: List<String>,
    val onConflict: String,
    val conflicts: List<PackConflict>,
    val autoMerge: Boolean,
    val backup: Boolean,
    val rollback: Boolean,
    val actions: List<JsonObject>
) {
    val totalChanges: Int get() = added.size + removed.size + modified.size
    val hasBreaking: Boolean get() = breaking || removed.isNotEmpty()
}

object PackUpdateModel {
    const val SCHEMA = "nf-pack-update/1"
    val CONFLICT_OPTIONS = listOf("keep_mine", "take_new", "defer")

    fun parse(text: String): PackUpdate = parse(J.parseObject(text, SCHEMA))

    fun parse(o: JsonObject): PackUpdate {
        J.schema(o, SCHEMA)
        val fromObj = J.child(o, "from", "")
        val toObj = J.child(o, "to", "")
        val changes = J.child(o, "changes", "")
        fun changesOf(key: String): List<ChangeEntry> =
            J.array(changes, key, "/changes").mapIndexed { i, el ->
                val c = el as? JsonObject
                    ?: throw ModelException("NF-E-002", "/changes/" + key + "/" + i, "变更项应为对象", "按 schema 修正")
                val p = "/changes/" + key + "/" + i
                ChangeEntry(
                    path = J.string(c, "path", p),
                    sha256 = J.optString(c, "sha256") ?: "",
                    newSha256 = J.optString(c, "new_sha256"),
                    size = J.optLong(c, "size")
                )
            }
        val impact = J.child(o, "impact", "")
        val merge = J.child(o, "merge", "")
        val policy = J.child(o, "policy", "")
        val conflicts = J.array(o, "conflicts", "").mapIndexed { i, el ->
            val c = el as? JsonObject
                ?: throw ModelException("NF-E-002", "/conflicts/" + i, "冲突应为对象", "按 schema 修正")
            val p = "/conflicts/" + i
            PackConflict(
                id = J.string(c, "id", p),
                kind = J.string(c, "kind", p),
                path = J.string(c, "path", p),
                oldSha256 = J.optString(c, "old_sha256"),
                newSha256 = J.optString(c, "new_sha256"),
                options = J.optStringList(c, "options"),
                defaultOption = J.string(c, "default", p)
            )
        }
        return PackUpdate(
            from = PackRef(J.string(fromObj, "id", "/from"), J.string(fromObj, "version", "/from"), J.string(fromObj, "tree", "/from")),
            to = PackRef(J.string(toObj, "id", "/to"), J.string(toObj, "version", "/to"), J.string(toObj, "tree", "/to")),
            added = changesOf("added"),
            removed = changesOf("removed"),
            modified = changesOf("modified"),
            breaking = J.bool(impact, "breaking", "/impact"),
            affectedProjects = J.optStringList(impact, "projects"),
            overlayKeys = J.optStringList(impact, "overlay_keys"),
            notes = J.optStringList(impact, "notes"),
            onConflict = J.string(merge, "on_conflict", "/merge"),
            conflicts = conflicts,
            autoMerge = J.bool(policy, "auto_merge", "/policy"),
            backup = J.bool(policy, "backup", "/policy"),
            rollback = J.bool(policy, "rollback", "/policy"),
            actions = J.optArray(merge, "actions").mapNotNull { it as? JsonObject }
        )
    }

    /**
     * 回滚 = 反向更新：base(新版) → new(旧版)，added/removed 互换（CONTRACT §5.9 旧版保留 + 原子替换）。
     * 仍走核心 pack-merge（同一 op，不新造 op 名）。
     */
    fun reversed(update: PackUpdate): PackUpdate = update.copy(
        from = update.to,
        to = update.from,
        added = update.removed,
        removed = update.added,
        modified = update.modified.map { it.copy(sha256 = it.newSha256 ?: it.sha256, newSha256 = it.sha256) },
        breaking = update.removed.isNotEmpty(),
        // 回滚不含人工冲突裁决面：清空 conflicts 并要求 abort 语义（由 decisions 全空 + 核心复验）
        conflicts = emptyList(),
        onConflict = "abort",
        actions = emptyList()
    )

    /** 回写 nf-pack-update/1（回滚输入 / 保存证据用；保留 merge.actions 原文）。 */
    fun toJson(u: PackUpdate): JsonObject = buildJsonObject {
        put("schema", SCHEMA)
        put("from", packRefJson(u.from))
        put("to", packRefJson(u.to))
        put("changes", buildJsonObject {
            put("added", JsonArray(u.added.map { changeJson(it) }))
            put("removed", JsonArray(u.removed.map { changeJson(it) }))
            put("modified", JsonArray(u.modified.map { changeJson(it) }))
        })
        put("impact", buildJsonObject {
            put("breaking", u.breaking)
            put("projects", strArray(u.affectedProjects))
            put("overlay_keys", strArray(u.overlayKeys))
            put("notes", strArray(u.notes))
        })
        put("merge", buildJsonObject {
            put("actions", JsonArray(u.actions))
            put("on_conflict", u.onConflict)
        })
        put("conflicts", JsonArray(u.conflicts.map { c ->
            buildJsonObject {
                put("id", c.id)
                put("kind", c.kind)
                put("path", c.path)
                if (c.oldSha256 != null) put("old_sha256", c.oldSha256)
                if (c.newSha256 != null) put("new_sha256", c.newSha256)
                put("options", strArray(c.options))
                put("default", c.defaultOption)
            }
        }))
        put("policy", buildJsonObject {
            put("auto_merge", u.autoMerge)
            put("backup", u.backup)
            put("rollback", u.rollback)
        })
    }

    private fun packRefJson(ref: PackRef): JsonObject = buildJsonObject {
        put("id", ref.id)
        put("version", ref.version)
        put("tree", ref.tree)
    }

    private fun changeJson(c: ChangeEntry): JsonObject = buildJsonObject {
        put("path", c.path)
        if (c.sha256.isNotBlank()) put("sha256", c.sha256)
        if (c.newSha256 != null) put("new_sha256", c.newSha256)
        if (c.size != null) put("size", c.size)
    }

    private fun strArray(values: List<String>): JsonArray = JsonArray(values.map { JsonPrimitive(it) })
}

/**
 * 冲突决策台：默认 defer；未全部裁决不得应用（NF-PCK-006）。
 * 纯逻辑、可单测；UI 只渲染并驱动本类。
 */
class ConflictBoard(private val conflicts: List<PackConflict>) {

    private val decisions = LinkedHashMap<String, String>()

    fun conflictOf(id: String): PackConflict? = conflicts.firstOrNull { it.id == id }

    fun decide(id: String, option: String): Boolean {
        val conflict = conflictOf(id) ?: return false
        if (option !in conflict.options) return false
        decisions[id] = option
        return true
    }

    fun decisionOf(id: String): String = decisions[id] ?: (conflictOf(id)?.defaultOption ?: "defer")

    fun unresolved(): List<PackConflict> = conflicts.filter { decisionOf(it.id) == "defer" }

    fun isResolved(): Boolean = unresolved().isEmpty()

    fun decisionsMap(): Map<String, String> = LinkedHashMap(decisions)

    fun summary(): String {
        if (conflicts.isEmpty()) return "无冲突"
        val decided = conflicts.size - unresolved().size
        return "冲突 " + conflicts.size + " 个，已裁决 " + decided + " 个；未裁决（defer）不得应用"
    }
}
