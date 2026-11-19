package dev.ninfenz.mobile.data

import java.io.File
import java.security.MessageDigest
import java.util.zip.ZipFile
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/** 读取并校验 nf-template/1 zip；只解包声明过的文件，拒绝路径穿越/超限。 */
object TemplatePackageImporter {
    data class Imported(
        val dir: File,
        val title: String,
        val specText: String,
        val templateText: String,
        val tree: String,
        val count: Int
    )

    private const val MAX_BYTES = 64L * 1024 * 1024
    private const val MAX_ENTRIES = 512

    fun hasTemplateJson(zipFile: File): Boolean = runCatching {
        ZipFile(zipFile).use { it.getEntry("nf-template.json") != null }
    }.getOrDefault(false)

    fun inspect(zipFile: File, cacheDir: File): Imported {
        require(zipFile.isFile) { "模板包不存在" }
        val out = File(cacheDir, "template-import-" + System.nanoTime()).apply { mkdirs() }
        ZipFile(zipFile).use { zip ->
            require(zip.size() <= MAX_ENTRIES) { "模板包条目过多" }
            val manifestEntry = zip.getEntry("nf-template.json") ?: error("缺少 nf-template.json")
            require(manifestEntry.size in 0..(1024L * 1024L)) { "模板清单过大" }
            val manifestText = zip.getInputStream(manifestEntry).use { readLimited(it, 1024L * 1024L).toString(Charsets.UTF_8) }
            val manifest = Json.parseToJsonElement(manifestText).jsonObject
            require(manifest["schema"]?.jsonPrimitive?.content == "nf-template/1") { "不是 nf-template/1" }
            val info = manifest["manifest"] as? JsonObject ?: error("模板缺少 manifest")
            val id = info["id"]?.jsonPrimitive?.content.orEmpty()
            val version = info["version"]?.jsonPrimitive?.content.orEmpty()
            val title = info["title"]?.jsonPrimitive?.content.orEmpty()
            require(Regex("^[a-z][a-z0-9-]{1,63}$").matches(id)) { "模板 id 非法" }
            require(Regex("^[0-9]+\\.[0-9]+\\.[0-9]+$").matches(version)) { "模板版本非法" }
            require(title.isNotBlank()) { "模板标题为空" }
            val compat = manifest["compat"] as? JsonObject ?: error("模板缺少 compat")
            require(compat["schema_version"]?.jsonPrimitive?.content == "1") { "模板 schema_version 不支持" }
            val refs = listOf("template_md", "spec", "protocol", "pipeline").mapNotNull { key ->
                val obj = manifest[key] as? JsonObject ?: return@mapNotNull null
                val path = obj["path"]?.jsonPrimitive?.content ?: return@mapNotNull null
                val sha = obj["sha256"]?.jsonPrimitive?.content ?: return@mapNotNull null
                Triple(key, path, sha)
            }
            require(refs.size == 4) { "模板清单缺少必要文件引用" }
            var total = 0L
            val assets = (manifest["assets"] as? kotlinx.serialization.json.JsonArray)?.mapIndexed { index, el ->
                val o = el as? JsonObject ?: error("assets/" + index + " 不是对象")
                val path = o["path"]?.jsonPrimitive?.content ?: error("assets/" + index + " 缺 path")
                val sha = o["sha256"]?.jsonPrimitive?.content ?: error("assets/" + index + " 缺 sha256")
                path to sha
            }.orEmpty()
            val seen = mutableSetOf<String>()
            (refs.map { it.second to it.third } + assets).forEach { (path, sha) ->
                require(seen.add(path.lowercase())) { "模板路径重复：" + path }
                require(safe(path)) { "非法模板路径：" + path }
                val entry = zip.getEntry(path) ?: error("模板缺少：" + path)
                total += entry.size
                require(total <= MAX_BYTES) { "模板包过大" }
                val bytes = zip.getInputStream(entry).use { readLimited(it, MAX_BYTES - total + entry.size) }
                total = total - entry.size + bytes.size
                require(total <= MAX_BYTES) { "模板包过大" }
                require(sha256(bytes) == sha) { "模板文件摘要不匹配：" + path }
                File(out, path).apply { parentFile?.mkdirs() }.writeBytes(bytes)
            }
            val specPath = refs.first { it.first == "spec" }.second
            val specBytes = File(out, specPath).readBytes()
            val specText = specBytes.toString(Charsets.UTF_8)
            val templatePath = refs.first { it.first == "template_md" }.second
            val templateText = File(out, templatePath).readText(Charsets.UTF_8)
            require(templateText.isNotBlank()) { "模板正文为空" }
            val hashes = manifest["hashes"] as? JsonObject ?: error("模板缺少 hashes")
            val tree = hashes["tree"]?.jsonPrimitive?.content ?: error("模板缺少 tree")
            val count = hashes["count"]?.jsonPrimitive?.content?.toIntOrNull() ?: error("模板缺少 count")
            return Imported(out, title, specText, templateText, tree, count)
        }
    }

    private fun readLimited(input: java.io.InputStream, max: Long): ByteArray {
        val out = java.io.ByteArrayOutputStream()
        val buf = ByteArray(16 * 1024)
        var read = 0L
        while (true) {
            val n = input.read(buf)
            if (n < 0) break
            read += n
            require(read <= max && read <= MAX_BYTES) { "模板包条目超限" }
            out.write(buf, 0, n)
        }
        return out.toByteArray()
    }

    private fun safe(path: String): Boolean =
        path.isNotBlank() && !path.startsWith("/") && !path.contains(":") && !path.contains("\\") && !path.split("/").contains("..")

    private fun sha256(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
}
