package dev.ninfenz.mobile.data

import java.io.File
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import kotlinx.serialization.json.putJsonObject

/** 生成 nf-template/1 包：先写 payload，pack-hash 算 tree，再写 manifest 并 zip。 */
object TemplatePackageBuilder {
    data class Prepared(val dir: File, val files: List<Pair<String, ByteArray>>, val manifestBase: JsonObject)

    fun prepare(cacheDir: File, pack: PackEntry, spec: JsonObject, title: String): Prepared {
        val dir = File(cacheDir, "template-build").apply { deleteRecursively(); mkdirs() }
        val protocol = File(pack.dir, "protocol/nf-protocol-pack.json").readBytes()
        val pipeline = File(pack.dir, "pipeline/main.nfg.json").readBytes()
        val specBytes = spec.toString().toByteArray(Charsets.UTF_8)
        val markdown = buildString {
            appendLine("# " + title.ifBlank { "模板" })
            appendLine()
            appendLine("由 NF 模板候选导出。")
        }.toByteArray(Charsets.UTF_8)
        val files = listOf(
            "template.md" to markdown,
            "spec/main.nfspec.json" to specBytes,
            "protocol/nf-protocol-pack.json" to protocol,
            "pipeline/main.nfg.json" to pipeline
        )
        files.forEach { (path, bytes) ->
            File(dir, path).apply { parentFile?.mkdirs() }.writeBytes(bytes)
        }
        val id = slug((spec["id"] as? kotlinx.serialization.json.JsonPrimitive)?.content ?: title)
        val manifest = buildJsonObject {
            put("schema", "nf-template/1")
            putJsonObject("manifest") {
                put("id", id)
                put("version", "0.1.0")
                put("title", title.ifBlank { id })
            }
            putJsonObject("template_md") { put("path", "template.md"); put("sha256", sha256(markdown)) }
            putJsonObject("spec") { put("path", "spec/main.nfspec.json"); put("sha256", sha256(specBytes)) }
            putJsonObject("protocol") { put("path", "protocol/nf-protocol-pack.json"); put("sha256", sha256(protocol)) }
            putJsonObject("pipeline") { put("path", "pipeline/main.nfg.json"); put("sha256", sha256(pipeline)) }
            putJsonArray("assets") { }
            putJsonObject("compat") { put("min_app_version", "0.2.0"); put("schema_version", 1) }
        }
        return Prepared(dir, files, manifest)
    }

    fun finalize(prepared: Prepared, tree: String, count: Int, outDir: File): File {
        val manifest = JsonObject(
            prepared.manifestBase.toMutableMap().apply {
                put("hashes", buildJsonObject { put("tree", tree); put("count", count) })
            }
        )
        File(prepared.dir, "nf-template.json").writeText(manifest.toString(), Charsets.UTF_8)
        outDir.mkdirs()
        val target = File(outDir, "nf-template-" + System.currentTimeMillis() + ".zip")
        ZipOutputStream(target.outputStream()).use { out ->
            val all = prepared.files + ("nf-template.json" to manifest.toString().toByteArray(Charsets.UTF_8))
            all.sortedBy { it.first }.forEach { (name, bytes) ->
                out.putNextEntry(ZipEntry(name).apply { time = 0L })
                out.write(bytes)
                out.closeEntry()
            }
        }
        prepared.dir.deleteRecursively()
        return target
    }

    fun sha256(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    private fun slug(raw: String): String {
        val base = raw.lowercase().replace(Regex("[^a-z0-9-]+"), "-").trim('-')
        val safe = if (base.length < 2) "template" else base
        return safe.take(63)
    }
}
