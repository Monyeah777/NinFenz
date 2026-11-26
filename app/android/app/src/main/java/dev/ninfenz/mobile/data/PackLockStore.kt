package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.Project
import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 项目 Pack 锁：锁 id/version/tree；校验失败 fail-closed，不静默换 Pack。 */
class PackLockStore(private val filesDir: File) {
    data class Lock(val projectId: String, val packId: String, val version: String, val tree: String, val lockedAt: Long)

    enum class Status { OK, MISSING, PROJECT_CHANGED, PACK_MISSING, TREE_MISMATCH }

    data class Check(val status: Status, val message: String = "")

    fun file(projectId: String): File =
        File(File(File(filesDir, "projects"), projectId), "pack-lock.json")

    fun load(projectId: String): Lock? = runCatching {
        val f = file(projectId)
        if (!f.isFile) return null
        val o = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
        Lock(
            projectId = o["project_id"]?.jsonPrimitive?.content ?: return null,
            packId = o["pack_id"]?.jsonPrimitive?.content ?: return null,
            version = o["version"]?.jsonPrimitive?.content ?: return null,
            tree = o["tree"]?.jsonPrimitive?.content ?: return null,
            lockedAt = o["locked_at"]?.jsonPrimitive?.content?.toLongOrNull() ?: 0L
        )
    }.getOrNull()

    fun lock(project: Project): Lock {
        val lock = Lock(
            projectId = project.id,
            packId = project.refs.basePackId,
            version = project.refs.basePackVersion,
            tree = project.refs.basePackTree,
            lockedAt = System.currentTimeMillis()
        )
        val text = buildJsonObject {
            put("schema", "nf-pack-lock/1")
            put("project_id", lock.projectId)
            put("pack_id", lock.packId)
            put("version", lock.version)
            put("tree", lock.tree)
            put("locked_at", lock.lockedAt)
        }.toString()
        AtomicFiles.writeText(file(project.id), text)
        return lock
    }

    fun unlock(projectId: String) {
        file(projectId).delete()
    }

    fun verify(project: Project, packs: List<PackEntry>): Check {
        val lock = load(project.id) ?: return Check(Status.MISSING, "项目未锁定 Pack")
        if (lock.tree != project.refs.basePackTree) {
            return Check(Status.PROJECT_CHANGED, "项目 Pack 引用已变化")
        }
        val installed = packs.firstOrNull { it.id == lock.packId && it.version == lock.version }
            ?: return Check(Status.PACK_MISSING, "锁定的 Pack 未安装")
        if (installed.tree != lock.tree) {
            return Check(Status.TREE_MISMATCH, "已安装 Pack 摘要与锁不符")
        }
        return Check(Status.OK, "Pack 锁校验通过")
    }
}
