package dev.ninfenz.mobile.data

import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 0.3 评审包：nf-handoff/1 zip，带文件清单与 sha256；导入只读校验，不执行代码。 */
object HandoffService {
    data class Inspect(val ok: Boolean, val projectId: String, val files: List<String>, val error: String? = null)

    private fun sha(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    fun export(projectId: String, projectJson: String, reviewJson: String, markdown: String?, outDir: File): File {
        outDir.mkdirs()
        val target = File(outDir, "nf-handoff-" + projectId + "-" + System.nanoTime() + ".zip")
        val entries = listOf(
            Triple("project.nfproject.json", projectJson.toByteArray(Charsets.UTF_8), "project"),
            Triple("review.json", reviewJson.toByteArray(Charsets.UTF_8), "review"),
            Triple("markdown.md", (markdown ?: "").toByteArray(Charsets.UTF_8), "markdown")
        )
        val manifest = buildJsonObject {
            put("schema", "nf-handoff/1")
            put("project_id", projectId)
            put("subject_digest", sha(projectJson.toByteArray(Charsets.UTF_8)))
            put("created_at", System.currentTimeMillis())
            put("app", "0.3.0")
            put("files", buildJsonArray {
                entries.forEach { (path, bytes, role) ->
                    add(buildJsonObject {
                        put("path", path)
                        put("sha256", sha(bytes))
                        put("role", role)
                    })
                }
            })
        }
        ZipOutputStream(FileOutputStream(target)).use { zip ->
            entries.forEach { (path, bytes, _) ->
                zip.putNextEntry(ZipEntry(path))
                zip.write(bytes)
                zip.closeEntry()
            }
            zip.putNextEntry(ZipEntry("handoff.json"))
            zip.write(manifest.toString().toByteArray(Charsets.UTF_8))
            zip.closeEntry()
        }
        return target
    }

    fun inspect(file: File): Inspect {
        if (!file.isFile) return Inspect(false, "", emptyList(), "file missing")
        return try {
            ZipFile(file).use { zip ->
                val manifestEntry = zip.getEntry("handoff.json")
                    ?: return Inspect(false, "", emptyList(), "handoff.json missing")
                val manifest = Json.parseToJsonElement(
                    zip.getInputStream(manifestEntry).use { it.readBytes() }.toString(Charsets.UTF_8)
                ).jsonObject
                if (manifest["schema"]?.jsonPrimitive?.content != "nf-handoff/1") {
                    return Inspect(false, "", emptyList(), "schema mismatch")
                }
                val projectId = manifest["project_id"]?.jsonPrimitive?.content.orEmpty()
                val files = manifest["files"]?.jsonArray.orEmpty()
                val names = mutableListOf<String>()
                for (el in files) {
                    val o = el.jsonObject
                    val path = o["path"]?.jsonPrimitive?.content.orEmpty()
                    val expected = o["sha256"]?.jsonPrimitive?.content.orEmpty()
                    if (path.isBlank() || path.startsWith("/") || path.contains("..") || path.contains('\\')) {
                        return Inspect(false, projectId, names, "illegal path: " + path)
                    }
                    val entry = zip.getEntry(path) ?: return Inspect(false, projectId, names, "missing: " + path)
                    val bytes = zip.getInputStream(entry).use { it.readBytes() }
                    if (sha(bytes) != expected) return Inspect(false, projectId, names, "sha mismatch: " + path)
                    names.add(path)
                }
                Inspect(true, projectId, names)
            }
        } catch (t: Throwable) {
            Inspect(false, "", emptyList(), t.message ?: t.javaClass.simpleName)
        }
    }
}
