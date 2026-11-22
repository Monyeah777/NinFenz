package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject

/** 按项目保存分享授权；只存声明，不执行接收方能力。 */
class CapabilityGrantStore(private val filesDir: File) {
    private fun file(projectId: String): File {
        val safe = projectId.replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "project" }
        return File(File(filesDir, "grants").apply { mkdirs() }, safe + ".json")
    }

    fun load(projectId: String): CapabilityGrant? {
        val f = file(projectId)
        if (!f.isFile) return null
        return runCatching {
            CapabilityGrant.parse(Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject)
        }.getOrNull()
    }

    fun save(projectId: String, grant: CapabilityGrant) {
        AtomicFiles.writeText(file(projectId), grant.toJson().toString())
    }
}
