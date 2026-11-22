package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.FlashFillModel
import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 按项目保存一条 M1 变换，供之后复用。 */
class TransformStore(private val filesDir: File) {
    private fun file(projectId: String): File {
        val safe = projectId.replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "project" }
        return File(File(filesDir, "transforms").apply { mkdirs() }, safe + ".json")
    }

    fun save(projectId: String, transform: FlashFillModel.Transform) {
        val payload = buildJsonObject {
            put("schema", "nf-flash-fill/1")
            put("project_id", projectId)
            put("kind", transform.kind)
            put("a", transform.a)
            put("b", transform.b)
        }
        AtomicFiles.writeText(file(projectId), payload.toString())
    }

    fun load(projectId: String): FlashFillModel.Transform? {
        val f = file(projectId)
        if (!f.isFile) return null
        return runCatching {
            val root = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
            FlashFillModel.Transform(
                root["kind"]?.jsonPrimitive?.content ?: return null,
                root["a"]?.jsonPrimitive?.content ?: "",
                root["b"]?.jsonPrimitive?.content ?: ""
            )
        }.getOrNull()
    }
}
