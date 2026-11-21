package dev.ninfenz.mobile.data

import java.io.File
import java.security.MessageDigest
import java.util.zip.ZipFile
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/** 复核 preservation.zip 的三个条目、字节数与 sha256；不修改文件。 */
object PreservationVerifier {
    data class Result(val ok: Boolean, val title: String?, val errors: List<String>)

    private fun sha(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    fun verify(file: File): Result {
        val errors = mutableListOf<String>()
        var title: String? = null
        try {
            ZipFile(file).use { zip ->
                val manifestEntry = zip.getEntry("preservation.json")
                    ?: return Result(false, null, listOf("缺 preservation.json"))
                val manifest = Json.parseToJsonElement(zip.getInputStream(manifestEntry).readBytes().decodeToString()).jsonObject
                if (manifest["schema"]?.jsonPrimitive?.content != "nf-preservation/1") {
                    errors += "未知 preservation schema"
                }
                title = manifest["title"]?.jsonPrimitive?.content
                val files = manifest["files"]?.jsonArray
                if (files == null || files.isEmpty()) errors += "manifest.files 为空"
                files?.forEach { item ->
                    val obj = item.jsonObject
                    val path = obj["path"]?.jsonPrimitive?.content ?: return@forEach
                    val expectedSha = obj["sha256"]?.jsonPrimitive?.content ?: ""
                    val expectedBytes = obj["bytes"]?.jsonPrimitive?.content?.toLongOrNull() ?: -1L
                    val entry = zip.getEntry(path)
                    if (entry == null) {
                        errors += "缺 " + path
                        return@forEach
                    }
                    val bytes = zip.getInputStream(entry).readBytes()
                    if (expectedBytes >= 0 && bytes.size.toLong() != expectedBytes) errors += path + " 字节数不符"
                    if (sha(bytes) != expectedSha) errors += path + " sha256 不符"
                }
                listOf("document.md", "document.nfdoc.json").forEach { required ->
                    if (zip.getEntry(required) == null) errors += "缺 " + required
                }
            }
        } catch (t: Throwable) {
            errors += t.message ?: t.javaClass.simpleName
        }
        return Result(errors.isEmpty(), title, errors)
    }
}
