package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.NfDocModel
import java.io.File
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray

/** 长期保存包：原文 + nf-doc + 文件摘要清单；固定 Zip 时间以便复算。 */
object PreservationExporter {
    data class Created(val file: File)

    private fun sha(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    fun export(markdown: String, title: String, projectId: String, outDir: File): Created {
        val safe = projectId.replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "project" }
        outDir.mkdirs()
        val file = File(outDir, safe + ".preserve.zip")
        val md = markdown.toByteArray(Charsets.UTF_8)
        val doc = NfDocModel.toJson(NfDocModel.fromMarkdown(title, projectId, markdown)).toString().toByteArray(Charsets.UTF_8)
        val manifest = buildJsonObject {
            put("schema", "nf-preservation/1")
            put("project_id", projectId)
            put("title", title)
            putJsonArray("files") {
                add(buildJsonObject { put("path", "document.md"); put("sha256", sha(md)); put("bytes", md.size) })
                add(buildJsonObject { put("path", "document.nfdoc.json"); put("sha256", sha(doc)); put("bytes", doc.size) })
            }
        }.toString().toByteArray(Charsets.UTF_8)
        ZipOutputStream(file.outputStream()).use { out ->
            listOf("document.md" to md, "document.nfdoc.json" to doc, "preservation.json" to manifest).forEach { (name, bytes) ->
                out.putNextEntry(ZipEntry(name).apply { time = 0L })
                out.write(bytes)
                out.closeEntry()
            }
        }
        return Created(file)
    }
}
