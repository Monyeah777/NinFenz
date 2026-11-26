package dev.ninfenz.mobile.data

import java.io.File
import java.security.MessageDigest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 信任台账：清单摘要 + 签名公钥指纹；清单变化即失效。兼容旧 trusted 映射。 */
class ExtensionTrustStore(private val filesDir: File) {
    data class Entry(
        val id: String,
        val digest: String,
        val fingerprint: String = "",
        val at: Long = 0L,
        val note: String = ""
    )

    private fun file(): File = File(filesDir, "extension-trust.json")

    private fun root(): JsonObject {
        val f = file()
        if (!f.isFile) return buildJsonObject {}
        return runCatching { Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject }
            .getOrElse { buildJsonObject {} }
    }

    fun entries(): List<Entry> {
        val o = root()
        val modern = o["entries"] as? JsonObject
        if (modern != null) {
            return modern.entries.mapNotNull { (id, value) ->
                val obj = value as? JsonObject ?: return@mapNotNull null
                val digest = obj.str("digest") ?: return@mapNotNull null
                if (!isDigest(digest)) return@mapNotNull null
                Entry(
                    id = id,
                    digest = digest,
                    fingerprint = obj.str("fingerprint").orEmpty(),
                    at = obj.str("at")?.toLongOrNull() ?: 0L,
                    note = obj.str("note").orEmpty()
                )
            }.sortedBy { it.id }
        }
        val legacy = o["trusted"] as? JsonObject ?: return emptyList()
        return legacy.entries.mapNotNull { (id, value) ->
            val digest = (value as? JsonPrimitive)?.content ?: return@mapNotNull null
            if (!isDigest(digest)) return@mapNotNull null
            Entry(id, digest)
        }.sortedBy { it.id }
    }

    fun entry(id: String): Entry? = entries().firstOrNull { it.id == id }

    fun isTrusted(id: String, digest: String): Boolean = entry(id)?.digest == digest

    fun trust(id: String, digest: String, fingerprint: String = "", note: String = "") {
        if (!isDigest(digest)) return
        val next = entries().filterNot { it.id == id } + Entry(
            id = id,
            digest = digest,
            fingerprint = fingerprint,
            at = System.currentTimeMillis(),
            note = note
        )
        write(next)
    }

    fun revoke(id: String) {
        write(entries().filterNot { it.id == id })
    }

    fun revokeAll() {
        write(emptyList())
    }

    fun exportJson(): String {
        val entries = entries()
        return buildJsonObject {
            put("schema", "nf-extension-trust/1")
            put("version", 1)
            put("entries", buildJsonObject {
                entries.forEach { entry ->
                    put(entry.id, buildJsonObject {
                        put("digest", entry.digest)
                        if (entry.fingerprint.isNotBlank()) put("fingerprint", entry.fingerprint)
                        if (entry.at > 0) put("at", entry.at)
                        if (entry.note.isNotBlank()) put("note", entry.note)
                    })
                }
            })
        }.toString()
    }

    fun importJson(text: String): List<Entry> {
        val root = Json.parseToJsonElement(text).jsonObject
        if (root.str("schema") != "nf-extension-trust/1") {
            throw PrefsFormatException("信任台账 schema 必须是 nf-extension-trust/1")
        }
        if (root.str("version")?.toIntOrNull() != 1) {
            throw PrefsFormatException("信任台账 version 必须是 1")
        }
        val entries = (root["entries"] as? JsonObject ?: throw PrefsFormatException("信任台账缺 entries"))
        val parsed = entries.entries.map { (id, value) ->
            val obj = value as? JsonObject ?: throw PrefsFormatException("信任台账条目必须是对象")
            val digest = obj.str("digest") ?: throw PrefsFormatException("信任台账条目不完整")
            if (!isDigest(digest)) throw PrefsFormatException("信任台账 digest 非法")
            Entry(
                id = id,
                digest = digest,
                fingerprint = obj.str("fingerprint").orEmpty(),
                at = obj.str("at")?.toLongOrNull() ?: 0L,
                note = obj.str("note").orEmpty()
            )
        }.sortedBy { it.id }
        write(parsed)
        return parsed
    }

    companion object {
        fun fingerprint(publicKeyHex: String): String {
            if (publicKeyHex.isBlank()) return ""
            val digest = MessageDigest.getInstance("SHA-256")
                .digest(publicKeyHex.toByteArray(Charsets.UTF_8))
            return digest.joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }
        }

        private fun isDigest(value: String): Boolean =
            value.length == 64 && value.all { it.isDigit() || it.lowercaseChar() in 'a'..'f' }
    }

    private fun write(entries: List<Entry>) {
        val text = buildJsonObject {
            put("schema", "nf-extension-trust/1")
            put("version", 1)
            put("entries", buildJsonObject {
                entries.forEach { entry ->
                    put(entry.id, buildJsonObject {
                        put("digest", entry.digest)
                        if (entry.fingerprint.isNotBlank()) put("fingerprint", entry.fingerprint)
                        if (entry.at > 0) put("at", entry.at)
                        if (entry.note.isNotBlank()) put("note", entry.note)
                    })
                }
            })
        }.toString()
        AtomicFiles.writeText(file(), text)
    }

    private fun JsonObject.str(key: String): String? =
        (this[key] as? JsonPrimitive)?.content?.takeIf { it.isNotBlank() }
}
