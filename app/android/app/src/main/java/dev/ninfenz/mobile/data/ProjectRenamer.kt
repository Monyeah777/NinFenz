package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ProjectModel

/** 重命名项目：只改 title，保留 refs/status/review/history。 */
object ProjectRenamer {
    fun rename(projectFile: File, newTitle: String): Project {
        val title = newTitle.trim()
        require(title.isNotBlank()) { "标题不能为空" }
        val source = Json.parseToJsonElement(projectFile.readText(Charsets.UTF_8)).jsonObject
        val next = source.toMutableMap()
        next["title"] = JsonPrimitive(title)
        AtomicFiles.writeText(projectFile, JsonObject(next).toString())
        return ProjectModel.parse(projectFile.readText(Charsets.UTF_8))
    }
}
