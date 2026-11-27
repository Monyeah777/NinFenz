package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.NfDocModel
import java.io.File
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray

/** 长期保存包的可选输入（参数对象化，避免超长参数表）。 */
data class PreservationOptions(
    val contractJson: String? = null,
    val grantJson: String? = null,
    val predecessorSha256: String? = null
)

/** 长期保存包：原文 + nf-doc + OAIS 风格信息包；固定 Zip 时间以便复算。 */
object PreservationExporter {
    data class Created(val file: File)

    private fun sha(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    fun export(
        markdown: String,
        title: String,
        projectId: String,
        outDir: File,
        options: PreservationOptions = PreservationOptions()
    ): Created {
        val contractJson = options.contractJson
        val grantJson = options.grantJson
        val predecessorSha256 = options.predecessorSha256
        val safe = projectId.replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "project" }
        outDir.mkdirs()
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
        val seed = md + doc + grant + (contract ?: ByteArray(0)) + (predecessorSha256?.toByteArray(Charsets.UTF_8) ?: ByteArray(0))
        val file = File(outDir, safe + "-" + sha(seed).take(12) + ".preserve.zip")

        val oais = oaisJson(title, projectId, content, predecessorSha256)
        val manifest = manifestJson(projectId, title, content, oais, predecessorSha256)
        writeZip(file, content, oais, manifest)
        return Created(file)
    }

    private fun oaisJson(
        title: String,
        projectId: String,
        content: List<Pair<String, ByteArray>>,
        predecessorSha256: String?
    ): ByteArray = buildJsonObject {
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
        predecessorSha256?.let {
            put("lineage", buildJsonObject { put("predecessor_sha256", it) })
        }
    }.toString().toByteArray(Charsets.UTF_8)

    private fun manifestJson(
        projectId: String,
        title: String,
        content: List<Pair<String, ByteArray>>,
        oais: ByteArray,
        predecessorSha256: String?
    ): ByteArray = buildJsonObject {
        put("schema", "nf-preservation/1")
        put("project_id", projectId)
        put("title", title)
        predecessorSha256?.let { put("predecessor_sha256", it) }
        putJsonArray("files") {
            (content + ("oais.json" to oais)).forEach { (name, bytes) ->
                add(buildJsonObject { put("path", name); put("sha256", sha(bytes)); put("bytes", bytes.size) })
            }
        }
    }.toString().toByteArray(Charsets.UTF_8)

    private fun writeZip(file: File, content: List<Pair<String, ByteArray>>, oais: ByteArray, manifest: ByteArray) {
        ZipOutputStream(file.outputStream()).use { out ->
            (content + ("oais.json" to oais) + ("preservation.json" to manifest)).forEach { (name, bytes) ->
                out.putNextEntry(ZipEntry(name).apply { time = 0L })
                out.write(bytes)
                out.closeEntry()
            }
        }
    }
}
