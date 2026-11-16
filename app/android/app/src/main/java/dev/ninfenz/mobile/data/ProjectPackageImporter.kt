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
    data class Imported(
        val id: String,
        val file: File,
        val dataFiles: Int,
        val packId: String,
        val packVersion: String
    )

    fun hasProjectJson(zipFile: File): Boolean = try {
        if (!zipFile.isFile) false else ZipFile(zipFile).use { zip ->
            zip.entries().asSequence().any { entry ->
                !entry.isDirectory && entry.name.replace('\\', '/').endsWith(".nfproject.json") &&
                    entry.name.replace('\\', '/').split('/').size <= 2
            }
        }
    } catch (t: Throwable) {
        false
    }

    fun import(filesDir: File, zipFile: File): Imported {
        require(zipFile.isFile) { "zip 不存在" }
        val projectsDir = File(filesDir, "projects").apply { mkdirs() }
        val entries = mutableListOf<Pair<String, ByteArray>>()
        ZipFile(zipFile).use { zip ->
            var total = 0L
            var count = 0
            for (entry in zip.entries()) {
                if (entry.isDirectory) continue
                count++
                require(count <= 5000) { "条目过多" }
                val name = entry.name.replace('\\', '/')
                require(!name.startsWith("/") && name.split('/').none { it == ".." }) { "非法路径：" + name }
                require(entry.size in 0..(512L * 1024 * 1024)) { "条目过大：" + name }
                total += entry.size.coerceAtLeast(0)
                require(total <= 512L * 1024 * 1024) { "解压总量超限" }
                entries.add(name to zip.getInputStream(entry).use { it.readBytes() })
            }
        }
        val projectEntries = entries.filter { (name, _) ->
            name.endsWith(".nfproject.json") && name.split('/').size <= 2
        }
        require(projectEntries.size == 1) { "zip 需且仅需一个项目 JSON" }
        val (projectPath, projectBytes) = projectEntries.first()
        val text = String(projectBytes, Charsets.UTF_8)
        val prefix = projectPath.substringBeforeLast('/', "")
        val dataPrefix = if (prefix.isBlank()) "data/" else prefix + "/data/"
        val data = entries.filter { (name, _) -> name.startsWith(dataPrefix) }
            .map { (name, bytes) -> name.removePrefix(dataPrefix) to bytes }
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
        val dataDir = File(projectsDir, id)
        val staging = File(projectsDir, ".import-" + id + "-" + System.nanoTime())
        try {
            data.forEach { (path, bytes) ->
                val out = File(staging, path)
                require(out.canonicalPath.startsWith(staging.canonicalPath + File.separator)) { "data 路径越界" }
                out.parentFile?.mkdirs()
                out.writeBytes(bytes)
            }
            if (staging.exists()) {
                java.nio.file.Files.move(
                    staging.toPath(),
                    dataDir.toPath(),
                    java.nio.file.StandardCopyOption.ATOMIC_MOVE
                )
            }
            AtomicFiles.writeText(target, json.toString())
        } catch (t: Throwable) {
            staging.deleteRecursively()
            dataDir.deleteRecursively()
            target.delete()
            throw t
        }
        val pack = source["refs"]?.let { refs ->
            (refs as? JsonObject)?.get("base_pack") as? JsonObject
        }
        return Imported(
            id = id,
            file = target,
            dataFiles = data.size,
            packId = pack?.get("id")?.let { (it as? JsonPrimitive)?.content }.orEmpty(),
            packVersion = pack?.get("version")?.let { (it as? JsonPrimitive)?.content }.orEmpty()
        )
    }
}
