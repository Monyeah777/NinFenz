package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.core.Core
import dev.ninfenz.mobile.core.CoreResponse
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 语义宏本地库：一条一个文件；回放先走核心 macro-plan（dry-run），不直接写文件。 */
class MacroStore(private val filesDir: File) {
    data class Macro(val id: String, val title: String, val steps: Int, val json: JsonObject)

    private fun dir(): File = File(filesDir, "macros").apply { mkdirs() }

    fun list(): List<Macro> = dir().listFiles()
        ?.filter { it.isFile && it.name.endsWith(".json") }
        ?.sortedBy { it.name }
        ?.mapNotNull { f ->
            runCatching {
                val root = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
                Macro(
                    id = root["id"]?.jsonPrimitive?.content ?: return@runCatching null,
                    title = root["title"]?.jsonPrimitive?.content.orEmpty(),
                    steps = root["steps"]?.jsonArray?.size ?: 0,
                    json = root
                )
            }.getOrNull()
        }.orEmpty()

    fun save(json: JsonObject): Macro {
        val id = json["id"]?.jsonPrimitive?.content
            ?: throw IllegalArgumentException("宏缺 id")
        val safe = id.replace(Regex("[^A-Za-z0-9._-]"), "_")
        AtomicFiles.writeText(File(dir(), safe + ".json"), json.toString())
        return Macro(id, json["title"]?.jsonPrimitive?.content.orEmpty(), json["steps"]?.jsonArray?.size ?: 0, json)
    }

    fun delete(id: String) {
        File(dir(), id.replace(Regex("[^A-Za-z0-9._-]"), "_") + ".json").delete()
    }

    suspend fun plan(macro: JsonObject): Result<JsonObject> = withContext(Dispatchers.IO) {
        runCatching {
            val response: CoreResponse = Core.bridge.call("macro-plan", buildJsonObject { put("macro", macro) })
            if (!response.ok) throw IllegalStateException(response.error?.message ?: "macro-plan failed")
            response.resultObject() ?: throw IllegalStateException("宏计划为空")
        }
    }
}
