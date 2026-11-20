package dev.ninfenz.mobile.data

import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/** nf-bundle/1 导入：内层包先落盘校验摘要，再复用 ProjectPackageImporter。 */
object ProjectBundleImporter {
    data class Imported(val count: Int, val ids: List<String>)

    fun hasBundle(zipFile: File): Boolean = runCatching {
        ZipFile(zipFile).use { it.getEntry("nf-bundle.json") != null }
    }.getOrDefault(false)

    fun import(filesDir: File, bundleFile: File): Imported {
        require(bundleFile.isFile) { "bundle 不存在" }
        val staging = File(filesDir, "bundle-import-" + System.nanoTime()).apply { mkdirs() }
        try {
            val items = mutableListOf<Pair<String, File>>()
            var total = 0L
            ZipFile(bundleFile).use { zip ->
                val manifestEntry = zip.getEntry("nf-bundle.json") ?: error("缺 nf-bundle.json")
                val manifestBytes = zip.getInputStream(manifestEntry).use { it.readBytes() }
                require(manifestBytes.size <= 4 * 1024 * 1024) { "bundle manifest 过大" }
                val manifest = Json.parseToJsonElement(manifestBytes.toString(Charsets.UTF_8)).jsonObject
                require(manifest["schema"]?.jsonPrimitive?.content == "nf-bundle/1") { "不是 nf-bundle/1" }
                manifest["projects"]?.jsonArray?.forEach { item ->
                    val obj = item.jsonObject
                    val path = obj["path"]?.jsonPrimitive?.content ?: error("bundle 条目缺 path")
                    val sha = obj["sha256"]?.jsonPrimitive?.content ?: error("bundle 条目缺 sha256")
                    require(path.isNotBlank() && !path.startsWith("/") && !path.contains("\\") && path.split("/").none { it == ".." }) { "bundle 路径非法" }
                    val entry = zip.getEntry(path) ?: error("bundle 缺条目：" + path)
                    val target = File(staging, "item-" + items.size + ".zip")
                    val copied = copyLimited(zip, entry, target, 256L * 1024 * 1024)
                    total += copied
                    require(total <= 512L * 1024 * 1024) { "bundle 总量超限" }
                    require(ProjectPackage.sha256(target) == sha) { "bundle 摘要不匹配：" + path }
                    items.add(path to target)
                }
            }
            require(items.isNotEmpty()) { "bundle 没有项目" }
            val ids = items.map { (_, inner) -> ProjectPackageImporter.import(filesDir, inner).id }
            return Imported(ids.size, ids)
        } finally {
            staging.deleteRecursively()
        }
    }

    private fun copyLimited(zip: ZipFile, entry: ZipEntry, target: File, max: Long): Long {
        var total = 0L
        zip.getInputStream(entry).use { input ->
            target.outputStream().use { output ->
                val buffer = ByteArray(1024 * 1024)
                while (true) {
                    val read = input.read(buffer)
                    if (read < 0) break
                    total += read
                    require(total <= max) { "bundle 条目过大" }
                    output.write(buffer, 0, read)
                }
            }
        }
        return total
    }
}
