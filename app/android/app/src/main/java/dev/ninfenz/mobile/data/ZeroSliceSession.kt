package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray

data class ZeroSliceMapping(
    val fromIndex: Int,
    val toId: String,
    val toName: String,
    val confidence: Int
)

data class ZeroSliceException(val text: String, val target: String?, val reason: String)

data class ZeroSliceReport(
    val mappings: List<ZeroSliceMapping>,
    val exceptions: List<ZeroSliceException>,
    val coverage: Int
)

object ZeroSliceModel {
    fun parse(o: JsonObject): ZeroSliceReport = ZeroSliceReport(
        mappings = o["mappings"]?.jsonArray?.map { el ->
            val m = el.jsonObject
            ZeroSliceMapping(
                fromIndex = m["from_index"]?.jsonPrimitive?.content?.toIntOrNull() ?: 0,
                toId = m["to_id"]?.jsonPrimitive?.content.orEmpty(),
                toName = m["to_name"]?.jsonPrimitive?.content.orEmpty(),
                confidence = m["confidence"]?.jsonPrimitive?.content?.toIntOrNull() ?: 0
            )
        }.orEmpty(),
        exceptions = o["exceptions"]?.jsonArray?.map { el ->
            val e = el.jsonObject
            ZeroSliceException(
                text = e["text"]?.jsonPrimitive?.content.orEmpty(),
                target = e["target"]?.jsonPrimitive?.content,
                reason = e["reason"]?.jsonPrimitive?.content.orEmpty()
            )
        }.orEmpty(),
        coverage = o["coverage"]?.jsonPrimitive?.content?.toIntOrNull() ?: 0
    )

    fun toJson(report: ZeroSliceReport): JsonObject = buildJsonObject {
        putJsonArray("mappings") {
            report.mappings.forEach { m ->
                add(buildJsonObject {
                    put("from_index", m.fromIndex)
                    put("to_id", m.toId)
                    put("to_name", m.toName)
                    put("confidence", m.confidence)
                })
            }
        }
        putJsonArray("exceptions") {
            report.exceptions.forEach { e ->
                add(buildJsonObject {
                    put("text", e.text)
                    e.target?.let { put("target", it) }
                    put("reason", e.reason)
                })
            }
        }
        put("coverage", report.coverage)
    }
}

/** 当前导入会话的 zero-slice 结果；按来源摘要恢复，避免跨文件串用。 */
class ZeroSliceStore(private val filesDir: File) {
    private fun file(): File = File(File(filesDir, "imports").apply { mkdirs() }, "zero-slice.json")

    fun save(sourceDigest: String, report: ZeroSliceReport) {
        val root = buildJsonObject {
            put("source_digest", sourceDigest)
            put("report", ZeroSliceModel.toJson(report))
        }
        AtomicFiles.writeText(file(), root.toString())
    }

    fun load(sourceDigest: String): ZeroSliceReport? {
        val f = file()
        if (!f.isFile || sourceDigest.isBlank()) return null
        return runCatching {
            val root = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
            if (root["source_digest"]?.jsonPrimitive?.content != sourceDigest) return null
            ZeroSliceModel.parse(root["report"]?.jsonObject ?: return null)
        }.getOrNull()
    }

    fun clear() {
        file().delete()
    }
}
