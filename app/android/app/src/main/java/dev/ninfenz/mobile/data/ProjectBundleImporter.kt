package dev.ninfenz.mobile.data

import java.io.File
import java.util.zip.ZipFile
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/** nf-bundle/1 导入：逐个校验内层项目包摘要后复用 ProjectPackageImporter。 */
object ProjectBundleImporter {
    data class Imported(val count: Int, val ids: List<String>)

    fun hasBundle(zipFile: File): Boolean = runCatching {
        ZipFile(zipFile).use { it.getEntry("nf-bundle.json") != null }
    }.getOrDefault(false)

    fun import(filesDir: File, bundleFile: File): Imported {
        require(bundleFile.isFile) { "bundle 不存在" }
        val staging = File(filesDir, "bundle-import-" + System.nanoTime()).apply { mkdirs() }
        try {
            val items = mutableListOf<Pair<String, ByteArray>>()
            var total = 0L
            ZipFile(bundleFile).use { zip ->
                val manifestEntry = zip.getEntry("nf-bundle.json") ?: error("缺 nf-bundle.json")
                require(manifestEntry.size in 0..(4L * 1024 * 1024)) { "bundle manifest 过大" }
                val manifest = Json.parseToJsonElement(
                    zip.getInputStream(manifestEntry).use { it.readBytes().toString(Charsets.UTF_8) }
                ).jsonObject
                require(manifest["schema"]?.jsonPrimitive?.content == "nf-bundle/1") { "不是 nf-bundle/1" }
                manifest["projects"]?.jsonArray?.forEach { item ->
                    val obj = item.jsonObject
                    val path = obj["path"]?.jsonPrimitive?.content ?: error("bundle 条目缺 path")
                    val sha = obj["sha256"]?.jsonPrimitive?.content ?: error("bundle 条目缺 sha256")
                    require(path.isNotBlank() && !path.startsWith("/") && !path.contains("\\") && path.split("/").none { it == ".." }) { "bundle 路径非法" }
                    val entry = zip.getEntry(path) ?: error("bundle 缺条目：" + path)
                    require(entry.size in 0..(256L * 1024 * 1024)) { "bundle 条目过大" }
                    val bytes = zip.getInputStream(entry).use { it.readBytes() }
                    total += bytes.size
                    require(total <= 512L * 1024 * 1024) { "bundle 总量超限" }
                    require(ProjectPackage.sha256(bytes) == sha) { "bundle 摘要不匹配：" + path }
                    items.add(path to bytes)
                }
            }
            require(items.isNotEmpty()) { "bundle 没有项目" }
            val ids = items.mapIndexed { index, (path, bytes) ->
                val inner = File(staging, "item-" + index + ".zip")
                inner.writeBytes(bytes)
                ProjectPackageImporter.import(filesDir, inner).id
            }
            return Imported(ids.size, ids)
        } finally {
            staging.deleteRecursively()
        }
    }
}
