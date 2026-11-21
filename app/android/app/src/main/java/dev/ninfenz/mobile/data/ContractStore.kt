package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray

/** 本地验收签收：记录已满足项与时间；不是密码学签名。 */
class ContractStore(private val filesDir: File) {
    data class Signoff(val projectId: String, val accepted: List<String>, val signedAt: String, val artifactSha256: String?)

    private fun file(projectId: String): File {
        val safe = projectId.replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "project" }
        return File(File(filesDir, "contracts").apply { mkdirs() }, safe + ".json")
    }

    fun load(projectId: String): Signoff? {
        val f = file(projectId)
        if (!f.isFile) return null
        return runCatching {
            val root = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
            Signoff(
                root["project_id"]?.jsonPrimitive?.content ?: projectId,
                root["accepted"]?.jsonArray?.map { it.jsonPrimitive.content }.orEmpty(),
                root["signed_at"]?.jsonPrimitive?.content.orEmpty(),
                root["artifact_sha256"]?.jsonPrimitive?.content
            )
        }.getOrNull()
    }

    fun sign(projectId: String, accepted: List<String>, at: String, artifactSha256: String? = null) {
        val payload = buildJsonObject {
            put("schema", "nf-contract-signoff/1")
            put("project_id", projectId)
            putJsonArray("accepted") { accepted.forEach { add(kotlinx.serialization.json.JsonPrimitive(it)) } }
            put("signed_at", at)
            artifactSha256?.let { put("artifact_sha256", it) }
        }
        AtomicFiles.writeText(file(projectId), payload.toString())
    }
}
