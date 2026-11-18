package dev.ninfenz.mobile.model

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** 从导入切片生成 nf-md-spec/1 候选；只做结构，不伪造约束或验收。 */
object TemplateCandidate {
    fun fromSlices(sourceTitle: String, slices: List<MarkdownSlice>): JsonObject? {
        val usable = slices.filter { it.heading != null || it.blocks.isNotEmpty() }.take(20)
        if (usable.isEmpty()) return null
        val title = usable.firstOrNull { it.heading != null }?.heading ?: sourceTitle.ifBlank { "导入稿" }
        val slug = title.lowercase()
            .replace(Regex("[^a-z0-9]+"), "-")
            .trim('-')
            .ifBlank { "import" }
            .take(40)
        val id = "tpl-" + slug
        val sections = mutableListOf<JsonObject>()
        val slots = mutableListOf<JsonObject>()
        usable.forEachIndexed { index, slice ->
            val sec = "SEC-" + (index + 1).toString().padStart(2, '0')
            val slot = "SLT-" + (index + 1).toString().padStart(2, '0')
            val name = slice.heading ?: ("第 " + (index + 1) + " 段")
            sections.add(buildJsonObject {
                put("id", sec)
                put("title", name)
                put("order", index + 1)
                put("required", false)
                put("slots", buildJsonArray { add(JsonPrimitive(slot)) })
            })
            slots.add(buildJsonObject {
                put("id", slot)
                put("name", name)
                put("section", sec)
                put("kind", "text")
                put("required", false)
                put("constraints", buildJsonArray {})
                put("examples", buildJsonArray {
                    slice.blocks.firstOrNull()?.text?.take(200)?.let { add(JsonPrimitive(it)) }
                })
                put("acceptance", buildJsonArray {})
                put("budget", buildJsonObject {
                    put("max_chars", maxOf(200, slice.charCount))
                })
            })
        }
        return buildJsonObject {
            put("schema", "nf-md-spec/1")
            put("id", id)
            put("title", title)
            put("domain", "general")
            put("version", "0.1.0")
            put("heading_level", 1)
            put("sections", buildJsonArray { sections.forEach { add(it) } })
            put("slots", buildJsonArray { slots.forEach { add(it) } })
            put("constraints", buildJsonArray {})
            put("acceptance", buildJsonArray {})
            put("references", buildJsonArray {})
        }
    }
}
