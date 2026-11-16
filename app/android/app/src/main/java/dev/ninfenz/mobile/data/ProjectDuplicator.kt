package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put

/** 项目复制：保留 refs（仍引用同一 Pack），重置状态/评审/历史。 */
object ProjectDuplicator {
    fun duplicate(source: File, filesDir: File, titleSuffix: String = "副本"): File {
        require(source.isFile) { "源项目不存在" }
        val root = source.readText(Charsets.UTF_8)
        val sourceJson = Json.parseToJsonElement(root).jsonObject
        val sourceId = sourceJson["id"]?.toString()?.trim('"') ?: "project"
        val sourceTitle = sourceJson["title"]?.toString()?.trim('"') ?: "项目"
        val projects = File(filesDir, "projects").apply { mkdirs() }
        var newId = sourceId + "-copy"
        var index = 2
        while (File(projects, newId + ".nfproject.json").exists()) {
            newId = sourceId + "-copy-" + index
            index++
        }
        val target = File(projects, newId + ".nfproject.json")
        val next = sourceJson.toMutableMap()
        next["id"] = kotlinx.serialization.json.JsonPrimitive(newId)
        next["title"] = kotlinx.serialization.json.JsonPrimitive(sourceTitle + " " + titleSuffix)
        next["status"] = kotlinx.serialization.json.JsonPrimitive("draft")
        next["review"] = buildJsonObject { put("state", "pending") }
        next["history"] = kotlinx.serialization.json.buildJsonArray { }
        AtomicFiles.writeText(target, JsonObject(next).toString())
        val sourceDir = File(File(filesDir, "projects"), sourceId)
        if (sourceDir.isDirectory) {
            copyDir(sourceDir, File(File(filesDir, "projects"), newId))
        }
        return target
    }

    private fun copyDir(source: File, target: File) {
        target.mkdirs()
        source.walkTopDown().forEach { file ->
            if (file.isFile) {
                val rel = file.relativeTo(source)
                val out = File(target, rel.path)
                out.parentFile?.mkdirs()
                file.copyTo(out, overwrite = true)
            }
        }
    }
}
