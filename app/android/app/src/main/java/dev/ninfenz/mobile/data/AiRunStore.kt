package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.CcosResult
import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/** 本地 AI 运行记录：只存编排/结果元数据；不存密钥，不发起网络。 */
class AiRunStore(private val filesDir: File) {
    data class Run(val id: String, val projectId: String, val status: String, val tasks: Int, val json: JsonObject)

    private fun dir(): File = File(filesDir, "ai-runs").apply { mkdirs() }

    fun list(): List<Run> = dir().listFiles()
        ?.filter { it.isFile && it.name.endsWith(".json") }
        ?.sortedByDescending { it.lastModified() }
        ?.mapNotNull { f ->
            runCatching {
                val o = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
                Run(
                    id = o["id"]?.jsonPrimitive?.content ?: return@runCatching null,
                    projectId = o["project_id"]?.jsonPrimitive?.content.orEmpty(),
                    status = o["status"]?.jsonPrimitive?.content.orEmpty(),
                    tasks = o["tasks"]?.jsonArray?.size ?: 0,
                    json = o
                )
            }.getOrNull()
        }.orEmpty()

    fun save(run: JsonObject): File {
        val id = run["id"]?.jsonPrimitive?.content ?: throw IllegalArgumentException("AI run 缺 id")
        val safe = id.replace(Regex("[^A-Za-z0-9._-]"), "_")
        val file = File(dir(), safe + ".json")
        AtomicFiles.writeText(file, run.toString())
        return file
    }

    fun delete(id: String) {
        File(dir(), id.replace(Regex("[^A-Za-z0-9._-]"), "_") + ".json").delete()
    }

    /** 把 CCOS result 的终态回写到 AI 运行记录；只改状态/模型，不改本地任务标题。 */
    fun applyResult(run: JsonObject, result: CcosResult): JsonObject {
        val status = when (result.status) {
            "succeeded" -> "done"
            "partial" -> "partial"
            else -> "failed"
        }
        val taskStatus = when (status) {
            "done" -> "done"
            "partial" -> "partial"
            else -> "failed"
        }
        val tasks = run["tasks"]?.jsonArray?.map { element ->
            val task = element.jsonObject.toMutableMap()
            task["status"] = kotlinx.serialization.json.JsonPrimitive(taskStatus)
            JsonObject(task)
        } ?: emptyList()
        val map = run.toMutableMap()
        map["status"] = kotlinx.serialization.json.JsonPrimitive(status)
        map["tasks"] = kotlinx.serialization.json.JsonArray(tasks)
        if (!result.model.isNullOrBlank()) {
            map["model"] = kotlinx.serialization.json.JsonPrimitive(result.model)
        }
        return JsonObject(map)
    }
}
