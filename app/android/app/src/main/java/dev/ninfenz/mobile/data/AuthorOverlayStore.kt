package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.core.Core
import dev.ninfenz.mobile.core.CoreBridge
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ProjectModel
import dev.ninfenz.mobile.model.ProjectStatus
import java.io.File
import java.security.MessageDigest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject

sealed interface SaveOverlayResult {
    data class Saved(val project: Project, val overlaySha256: String, val status: ProjectStatus) : SaveOverlayResult
    data class Failure(val code: String, val message: String, val fix: String) : SaveOverlayResult
}

/** 纯构造器：nf-overlay/1（条款开关 + 字段参数）；可单测。 */
object AuthorOverlayFactory {
    fun build(
        pack: PackEntry,
        clausesEnabled: Map<String, Boolean>,
        params: Map<String, String>
    ): JsonObject = buildJsonObject {
        put("schema", "nf-overlay/1")
        putJsonObject("base") {
            put("id", pack.id)
            put("version", pack.version)
            put("tree", pack.tree)
        }
        putJsonObject("clauses") {
            for ((id, enabled) in clausesEnabled) {
                putJsonObject(id) { put("enabled", enabled) }
            }
        }
        putJsonObject("params") {
            for ((id, value) in params) put(id, value)
        }
        put("presets", buildJsonArray {})
        put("custom_assets", buildJsonArray {})
    }
}

/**
 * W4b 作者覆盖保存：写 overlay（clauses/params）→ 更新 project.refs.overlay + status/history
 * → core project-validate（fail-closed）→ 原子写项目文件。不修改 base pack。
 */
class AuthorOverlayStore(
    private val filesDir: File,
    private val injectedBridge: CoreBridge? = null
) {
    private fun bridge(): CoreBridge? = injectedBridge ?: runCatching { Core.bridge }.getOrNull()

    suspend fun save(
        project: Project,
        pack: PackEntry,
        clausesEnabled: Map<String, Boolean>,
        params: Map<String, String>
    ): SaveOverlayResult = withContext(Dispatchers.IO) {
        val core = bridge() ?: return@withContext SaveOverlayResult.Failure(
            "NF-E-005", "原生核心不可用，无法保存作者覆盖", "重装原生库并运行诊断"
        )
        try {
            val projectFile = File(File(filesDir, "projects"), project.id + ".nfproject.json")
            if (!projectFile.isFile) {
                return@withContext SaveOverlayResult.Failure("NF-PCK-003", "项目文件不存在", "重新创建项目")
            }
            val overlay = AuthorOverlayFactory.build(pack, clausesEnabled, params)
            val overlayBytes = overlay.toString().toByteArray(Charsets.UTF_8)
            val overlaySha = sha256(overlayBytes)

            val overlayDir = File(File(filesDir, "projects"), project.id + "/overlay").apply { mkdirs() }
            val overlayFile = File(overlayDir, "nf-overlay.json")
            atomicWrite(overlayFile, overlay.toString())

            val raw = Json.parseToJsonElement(projectFile.readText(Charsets.UTF_8)).jsonObject
            val newProject = updatedProjectJson(raw, overlaySha)

            val validate = core.call("project-validate", buildJsonObject { put("project", newProject) })
            if (!validate.ok) {
                val e = validate.error
                return@withContext SaveOverlayResult.Failure(
                    e?.code ?: "NF-VAL-001",
                    e?.message ?: "项目校验失败",
                    e?.fix ?: "检查 overlay 引用"
                )
            }
            atomicWrite(projectFile, newProject.toString())
            val parsed = ProjectModel.parse(newProject.toString())
            SaveOverlayResult.Saved(parsed, overlaySha, parsed.status)
        } catch (t: Throwable) {
            SaveOverlayResult.Failure(
                "NF-E-005",
                "保存覆盖失败：" + (t.message ?: t.javaClass.simpleName),
                "检查项目文件与核心桥；诊断见设置页"
            )
        }
    }

    private fun updatedProjectJson(raw: JsonObject, overlaySha: String): JsonObject {
        val oldRefs = raw["refs"]?.jsonObject ?: buildJsonObject {}
        val newRefs = buildJsonObject {
            for ((key, value) in oldRefs) {
                if (key != "overlay") put(key, value)
            }
            putJsonObject("overlay") {
                put("path", "overlay/nf-overlay.json")
                put("sha256", overlaySha)
            }
        }
        val oldHistory = raw["history"]?.jsonArray ?: JsonArray(emptyList())
        val newHistory = buildJsonArray {
            for (entry in oldHistory) add(entry)
            add(buildJsonObject {
                put("op", "overlay:save")
                put("digest", overlaySha)
            })
        }
        val oldStatus = raw["status"]?.toString()?.trim('"') ?: "draft"
        val newStatus = if (oldStatus == "draft") "authoring" else oldStatus
        return buildJsonObject {
            for ((key, value) in raw) {
                when (key) {
                    "refs" -> put("refs", newRefs)
                    "history" -> put("history", newHistory)
                    "status" -> put("status", newStatus)
                    else -> put(key, value)
                }
            }
        }
    }

    private fun atomicWrite(target: File, text: String) = AtomicFiles.writeText(target, text)

    private fun sha256(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
}
