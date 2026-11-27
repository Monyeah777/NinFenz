package dev.ninfenz.mobile.data

import java.io.File
import java.security.MessageDigest
import java.util.zip.ZipFile
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/** 复核 preservation.zip 的三个条目、字节数与 sha256；不修改文件。 */
object PreservationVerifier {
    private const val MAX_ENTRIES = 32
    private const val MAX_ENTRY_BYTES = 20L * 1024 * 1024
    private const val MAX_TOTAL_BYTES = 40L * 1024 * 1024

    data class Result(val ok: Boolean, val title: String?, val errors: List<String>, val grant: CapabilityGrant? = null)

    private fun sha(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    fun predecessor(file: File): String? = runCatching {
        ZipFile(file).use { zip ->
            val entry = zip.getEntry("preservation.json") ?: return null
            Json.parseToJsonElement(zip.getInputStream(entry).readBytes().decodeToString())
                .jsonObject["predecessor_sha256"]?.jsonPrimitive?.content
        }
    }.getOrNull()

    /** 跨包迁移链：next 的 predecessor 必须等于 previous 的文件摘要。 */
    fun chain(previous: File, next: File): Result {
        val prev = verify(previous)
        val nxt = verify(next)
        val errors = (prev.errors + nxt.errors).toMutableList()
        if (errors.isEmpty()) {
            val prevSha = sha(previous.readBytes())
            val declared = predecessor(next)
            if (declared != prevSha) errors += "next predecessor 与 previous 摘要不符"
        }
        return Result(errors.isEmpty(), nxt.title, errors)
    }

    fun title(file: File): String? = runCatching {
        ZipFile(file).use { zip ->
            val entry = zip.getEntry("preservation.json") ?: return null
            Json.parseToJsonElement(zip.getInputStream(entry).readBytes().decodeToString())
                .jsonObject["title"]?.jsonPrimitive?.content
        }
    }.getOrNull()

    fun extractEntry(file: File, name: String, maxBytes: Long = MAX_ENTRY_BYTES): String? = runCatching {
        ZipFile(file).use { zip ->
            val entry = zip.getEntry(name) ?: return null
            if (entry.size > maxBytes) return null
            zip.getInputStream(entry).readBytes().decodeToString()
        }
    }.getOrNull()

    fun extractMarkdown(file: File): String? = runCatching {
        ZipFile(file).use { zip ->
            val entry = zip.getEntry("document.md") ?: return null
            if (entry.size > MAX_ENTRY_BYTES) return null
            zip.getInputStream(entry).readBytes().decodeToString()
        }
    }.getOrNull()

    fun verify(file: File): Result {
        val errors = mutableListOf<String>()
        var title: String? = null
        var grant: CapabilityGrant? = null
        try {
            ZipFile(file).use { zip ->
                if (zip.size() > MAX_ENTRIES) return Result(false, null, listOf("zip 条目过多"))
                val manifestEntry = zip.getEntry("preservation.json")
                    ?: return Result(false, null, listOf("缺 preservation.json"))
                if (manifestEntry.size > 1024 * 1024) return Result(false, null, listOf("preservation.json 过大"))
                val manifest = Json.parseToJsonElement(zip.getInputStream(manifestEntry).readBytes().decodeToString()).jsonObject
                if (manifest["schema"]?.jsonPrimitive?.content != "nf-preservation/1") {
                    errors += "未知 preservation schema"
                }
                title = manifest["title"]?.jsonPrimitive?.content
                val packageId = manifest["project_id"]?.jsonPrimitive?.content
                val predecessor = manifest["predecessor_sha256"]?.jsonPrimitive?.content
                if (predecessor != null && !predecessor.matches(Regex("[0-9a-f]{64}"))) errors += "predecessor_sha256 非法"
                val files = manifest["files"]?.jsonArray
                if (files == null || files.isEmpty()) errors += "manifest.files 为空"
                if (files != null) verifyManifestFiles(zip, files, errors)
                grant = verifyGrant(zip, errors)
                verifyOais(zip, packageId, predecessor, errors)
                verifyRequired(zip, errors)
            }
        } catch (t: Throwable) {
            errors += t.message ?: t.javaClass.simpleName
        }
        return Result(errors.isEmpty(), title, errors, grant)
    }

    private fun verifyManifestFiles(zip: ZipFile, files: JsonArray, errors: MutableList<String>) {
        var total = 0L
        files.forEach { item ->
            val obj = item.jsonObject
            val path = obj["path"]?.jsonPrimitive?.content ?: return@forEach
            val expectedSha = obj["sha256"]?.jsonPrimitive?.content ?: ""
            val expectedBytes = obj["bytes"]?.jsonPrimitive?.content?.toLongOrNull() ?: -1L
            val entry = zip.getEntry(path)
            if (entry == null) {
                errors += "缺 " + path
                return@forEach
            }
            if (entry.size > MAX_ENTRY_BYTES) {
                errors += path + " 过大"
                return@forEach
            }
            total += entry.size
            if (total > MAX_TOTAL_BYTES) {
                errors += "zip 解压总量过大"
                return@forEach
            }
            val bytes = zip.getInputStream(entry).readBytes()
            if (expectedBytes >= 0 && bytes.size.toLong() != expectedBytes) errors += path + " 字节数不符"
            if (sha(bytes) != expectedSha) errors += path + " sha256 不符"
        }
    }

    private fun verifyGrant(zip: ZipFile, errors: MutableList<String>): CapabilityGrant? {
        var grant: CapabilityGrant? = null
        val grantEntry = zip.getEntry("grant.json")
        if (grantEntry == null) {
            errors += "缺 grant.json"
        } else if (grantEntry.size > 64 * 1024) {
            errors += "grant.json 过大"
        } else {
            runCatching {
                CapabilityGrant.parse(Json.parseToJsonElement(zip.getInputStream(grantEntry).readBytes().decodeToString()).jsonObject)
            }.onSuccess { grant = it }
                .onFailure { errors += "grant.json 非法：" + (it.message ?: it.javaClass.simpleName) }
        }
        return grant
    }

    private fun verifyOais(zip: ZipFile, packageId: String?, predecessor: String?, errors: MutableList<String>) {
        val oaisEntry = zip.getEntry("oais.json")
        if (oaisEntry == null) {
            errors += "缺 oais.json"
        } else if (oaisEntry.size > 1024 * 1024) {
            errors += "oais.json 过大"
        } else {
            val oais = Json.parseToJsonElement(zip.getInputStream(oaisEntry).readBytes().decodeToString()).jsonObject
            if (oais["schema"]?.jsonPrimitive?.content != "nf-oais/1") errors += "未知 oais schema"
            if (packageId != null && oais["package_id"]?.jsonPrimitive?.content != packageId) errors += "oais package_id 不符"
            val oaisLineage = oais["lineage"]?.jsonObject?.get("predecessor_sha256")?.jsonPrimitive?.content
            if (predecessor != null && oaisLineage != predecessor) errors += "oais lineage 不符"
            val fixity = oais["fixity"]?.jsonArray
            if (fixity == null || fixity.isEmpty()) {
                errors += "oais.fixity 为空"
            } else {
                fixity.forEach { item ->
                    val obj = item.jsonObject
                    val path = obj["path"]?.jsonPrimitive?.content ?: return@forEach
                    val expectedSha = obj["sha256"]?.jsonPrimitive?.content ?: ""
                    val entry = zip.getEntry(path)
                    if (entry == null) {
                        errors += "oais 缺 " + path
                    } else if (sha(zip.getInputStream(entry).readBytes()) != expectedSha) {
                        errors += "oais fixity 不符 " + path
                    }
                }
            }
        }
    }

    private fun verifyRequired(zip: ZipFile, errors: MutableList<String>) {
        listOf("document.md", "document.nfdoc.json", "grant.json", "oais.json").forEach { required ->
            if (zip.getEntry(required) == null) errors += "缺 " + required
        }
    }
}
