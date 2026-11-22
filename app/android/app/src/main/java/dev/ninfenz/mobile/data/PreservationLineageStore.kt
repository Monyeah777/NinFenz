package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.buildJsonObject

/** 记录每个项目上一次 preservation 包的摘要，形成可核对的本地产线。 */
class PreservationLineageStore(private val filesDir: File) {
    private fun file(projectId: String): File {
        val safe = projectId.replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "project" }
        return File(File(filesDir, "lineage").apply { mkdirs() }, safe + ".json")
    }

    fun load(projectId: String): String? {
        val f = file(projectId)
        if (!f.isFile) return null
        return runCatching {
            Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject["predecessor_sha256"]?.jsonPrimitive?.content
        }.getOrNull()
    }

    fun save(projectId: String, sha256: String) {
        AtomicFiles.writeText(file(projectId), buildJsonObject {
            put("project_id", projectId)
            put("predecessor_sha256", sha256)
        }.toString())
    }
}
