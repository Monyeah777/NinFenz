package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 信任钉：记录已通过签名校验的扩展清单摘要；清单变化即失效。 */
class ExtensionTrustStore(private val filesDir: File) {
    private fun file(): File = File(filesDir, "extension-trust.json")

    private fun all(): Map<String, String> {
        val f = file()
        if (!f.isFile) return emptyMap()
        return runCatching {
            Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject["trusted"]?.jsonObject
                ?.mapNotNull { (k, v) -> v.jsonPrimitive.content.takeIf { it.isNotBlank() }?.let { k to it } }
                ?.toMap().orEmpty()
        }.getOrElse { emptyMap() }
    }

    fun isTrusted(id: String, digest: String): Boolean = all()[id] == digest

    fun trust(id: String, digest: String) {
        AtomicFiles.writeText(file(), buildJsonObject {
            put("trusted", buildJsonObject {
                all().forEach { (k, v) -> put(k, v) }
                put(id, digest)
            })
        }.toString())
    }

    fun revoke(id: String) {
        val next = all() - id
        AtomicFiles.writeText(file(), buildJsonObject {
            put("trusted", buildJsonObject { next.forEach { (k, v) -> put(k, v) } })
        }.toString())
    }
}
