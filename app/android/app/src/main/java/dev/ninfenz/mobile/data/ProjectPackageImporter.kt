package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ProjectModel
import java.io.File
import java.util.zip.ZipFile
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject

/** 完整项目 zip 导入：一个项目 JSON + 可选 data/ 目录；不覆盖已有项目。 */
object ProjectPackageImporter {
    data class Imported(val id: String, val file: File, val dataFiles: Int)

    fun import(filesDir: File, zipFile: File): Imported {
        require(zipFile.isFile) { "zip 不存在" }
        val projectsDir = File(filesDir, "projects").apply { mkdirs() }
        var projectText: String? = null
        val data = mutableListOf<Pair<String, ByteArray>>()
        ZipFile(zipFile).use { zip ->
            var total = 0L
            var count = 0
            for (entry in zip.entries()) {
                if (entry.isDirectory) continue
                count++
                require(count <= 5000) { "条目过多" }
                val name = entry.name.replace('\\', '/')
                require(!name.startsWith("/") && name.split('/').none { it == ".." }) { "非法路径：" + name }
                val bytes = zip.getInputStream(entry).use { it.readBytes() }
                total += bytes.size
                require(total <= 512L * 1024 * 1024) { "解压总量超限" }
                if (name.endsWith(".nfproject.json") && !name.contains('/')) {
                    require(projectText == null) { "包含多个项目文件" }
                    projectText = String(bytes, Charsets.UTF_8)
                } else if (name.startsWith("data/")) {
                    data.add(name.removePrefix("data/") to bytes)
                }
            }
        }
        val text = projectText ?: throw IllegalArgumentException("zip 缺少项目 JSON")
        val source = Json.parseToJsonElement(text).jsonObject
        val sourceId = source["id"]?.let { (it as? JsonPrimitive)?.content } ?: throw IllegalArgumentException("项目缺 id")
        var id = sourceId
        var index = 2
        while (File(projectsDir, id + ".nfproject.json").exists()) {
            id = sourceId + "-import" + (if (index == 2) "" else "-" + index)
            index++
        }
        val next = source.toMutableMap()
        next["id"] = JsonPrimitive(id)
        val json = JsonObject(next)
        ProjectModel.parse(json) // fail-closed
        val target = File(projectsDir, id + ".nfproject.json")
        AtomicFiles.writeText(target, json.toString())
        val dataDir = File(projectsDir, id)
        data.forEach { (path, bytes) ->
            val out = File(dataDir, path)
            require(out.canonicalPath.startsWith(dataDir.canonicalPath + File.separator)) { "data 路径越界" }
            out.parentFile?.mkdirs()
            out.writeBytes(bytes)
        }
        return Imported(id, target, data.size)
    }
}
