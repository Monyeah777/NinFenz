package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.NfDocModel
import java.io.File
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray

/** 长期保存包：原文 + nf-doc + OAIS 风格信息包；固定 Zip 时间以便复算。 */
object PreservationExporter {
    data class Created(val file: File)

    private fun sha(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    fun export(markdown: String, title: String, projectId: String, outDir: File, contractJson: String? = null, grantJson: String? = null): Created {
        val safe = projectId.replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "project" }
        outDir.mkdirs()
        val file = File(outDir, safe + ".preserve.zip")
        val md = markdown.toByteArray(Charsets.UTF_8)
        val doc = NfDocModel.toJson(NfDocModel.fromMarkdown(title, projectId, markdown)).toString().toByteArray(Charsets.UTF_8)
        val contract = contractJson?.toByteArray(Charsets.UTF_8)
        val grant = (grantJson ?: CapabilityGrant.defaultForPackage().toJson().toString()).toByteArray(Charsets.UTF_8)

        val content = buildList {
            add("document.md" to md)
            add("document.nfdoc.json" to doc)
            add("grant.json" to grant)
            contract?.let { add("contract.json" to it) }
        }

        val oais = buildJsonObject {
            put("schema", "nf-oais/1")
            put("package_id", projectId)
            put("title", title)
            put("agent", buildJsonObject {
                put("name", "NF Mobile")
                put("version", "0.2.0")
            })
            put("rights", buildJsonObject {
                put("basis", "user-provided")
                put("license", "unknown")
            })
            putJsonArray("fixity") {
                content.forEach { (name, bytes) ->
                    add(buildJsonObject { put("path", name); put("sha256", sha(bytes)); put("bytes", bytes.size) })
                }
            }
            putJsonArray("events") {
                add(buildJsonObject {
                    put("type", "export")
                    put("detail", "local deterministic package")
                })
            }
        }.toString().toByteArray(Charsets.UTF_8)

        val manifest = buildJsonObject {
            put("schema", "nf-preservation/1")
            put("project_id", projectId)
            put("title", title)
            putJsonArray("files") {
                (content + ("oais.json" to oais)).forEach { (name, bytes) ->
                    add(buildJsonObject { put("path", name); put("sha256", sha(bytes)); put("bytes", bytes.size) })
                }
            }
        }.toString().toByteArray(Charsets.UTF_8)

        ZipOutputStream(file.outputStream()).use { out ->
            (content + ("oais.json" to oais) + ("preservation.json" to manifest)).forEach { (name, bytes) ->
                out.putNextEntry(ZipEntry(name).apply { time = 0L })
                out.write(bytes)
                out.closeEntry()
            }
        }
        return Created(file)
    }
}
