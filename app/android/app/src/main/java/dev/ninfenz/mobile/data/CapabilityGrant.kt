package dev.ninfenz.mobile.data

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray

/** M25：随包携带的能力授权；只声明范围/到期，不提供密码学身份。 */
data class CapabilityGrant(
    val caps: Set<String> = setOf(READ, EXPORT),
    val expiresAt: Long? = null,
    val revoked: Boolean = false
) {
    fun allows(cap: String, now: Long): Boolean {
        if (cap !in CAPS) return false
        if (revoked) return false
        if (expiresAt != null && now >= expiresAt) return false
        return "admin" in caps || cap in caps
    }

    fun toJson(): JsonObject = buildJsonObject {
        put("schema", SCHEMA)
        putJsonArray("caps") { caps.sorted().forEach { add(kotlinx.serialization.json.JsonPrimitive(it)) } }
        expiresAt?.let { put("expires_at", it) }
        put("revoked", revoked)
    }

    companion object {
        const val SCHEMA = "nf-capability/1"
        const val READ = "read"
        const val COMMENT = "comment"
        const val REASSEMBLE = "reassemble"
        const val EXPORT = "export"
        const val SHARE = "share"
        val CAPS = setOf(READ, COMMENT, REASSEMBLE, EXPORT, SHARE)

        fun defaultForPackage(): CapabilityGrant = CapabilityGrant(setOf(READ, REASSEMBLE, EXPORT))

        fun parse(o: JsonObject): CapabilityGrant {
            require(o["schema"]?.jsonPrimitive?.content == SCHEMA) { "未知能力授权 schema" }
            val caps = o["caps"]?.jsonArray?.map { it.jsonPrimitive.content }?.toSet().orEmpty()
            require(caps.all { it in CAPS }) { "未知能力" }
            return CapabilityGrant(caps, o["expires_at"]?.jsonPrimitive?.content?.toLongOrNull(), o["revoked"]?.jsonPrimitive?.content == "true")
        }
    }
}
