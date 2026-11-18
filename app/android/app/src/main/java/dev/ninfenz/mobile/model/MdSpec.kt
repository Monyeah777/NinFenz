package dev.ninfenz.mobile.model

import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.core.ModelException
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

data class SpecSection(val id: String, val title: String, val order: Int, val required: Boolean, val slots: List<String>)
data class SpecSlot(
    val id: String,
    val name: String,
    val section: String,
    val kind: String,
    val required: Boolean,
    val minChars: Int? = null,
    val maxChars: Int? = null
)

data class MdSpec(
    val id: String,
    val title: String,
    val version: String,
    val headingLevel: Int,
    val sections: List<SpecSection>,
    val slots: List<SpecSlot>
)

object SpecModel {
    const val SCHEMA = "nf-md-spec/1"

    fun parse(text: String): MdSpec = parse(J.parseObject(text, SCHEMA))

    fun parse(o: JsonObject): MdSpec {
        J.schema(o, SCHEMA)
        val sections = J.array(o, "sections", "").mapIndexed { i, el ->
            val s = el as? JsonObject
                ?: throw ModelException("NF-E-002", "/sections/" + i, "章节应为对象", "按 schema 修正")
            val p = "/sections/" + i
            SpecSection(
                id = J.string(s, "id", p),
                title = J.string(s, "title", p),
                order = J.int(s, "order", p),
                required = J.bool(s, "required", p),
                slots = J.optStringList(s, "slots")
            )
        }
        val slots = J.array(o, "slots", "").mapIndexed { i, el ->
            val s = el as? JsonObject
                ?: throw ModelException("NF-E-002", "/slots/" + i, "槽位应为对象", "按 schema 修正")
            val p = "/slots/" + i
            SpecSlot(
                id = J.string(s, "id", p),
                name = J.string(s, "name", p),
                section = J.string(s, "section", p),
                kind = J.string(s, "kind", p),
                required = J.bool(s, "required", p),
                minChars = constraintInt(s, "min_chars"),
                maxChars = J.optChild(s, "budget")?.let { J.optInt(it, "max_chars") } ?: constraintInt(s, "max_chars")
            )
        }
        return MdSpec(
            id = J.string(o, "id", ""),
            title = J.string(o, "title", ""),
            version = J.string(o, "version", ""),
            headingLevel = J.int(o, "heading_level", ""),
            sections = sections,
            slots = slots
        )
    }

    private fun constraintInt(slot: JsonObject, op: String): Int? =
        J.optArray(slot, "constraints").mapNotNull { it as? JsonObject }.firstOrNull {
            J.optString(it, "op") == op
        }?.let { J.optInt(it, "value") }

    /** 本地表单检查（CONTRACT §5.5 的双向一致与 order 连续）。 */
    fun formIssues(spec: MdSpec): List<FormIssue> {
        val issues = mutableListOf<FormIssue>()
        val byId = spec.sections.associateBy { it.id }
        val orders = spec.sections.map { it.order }.sorted()
        val expected = (1..spec.sections.size).toList()
        if (orders != expected) {
            issues.add(FormIssue("NF-SPC-001", "/sections", "order 必须从 1 连续且唯一：" + orders.joinToString(","), "重排 order"))
        }
        for (section in spec.sections) {
            for (slotId in section.slots) {
                val slot = spec.slots.firstOrNull { it.id == slotId }
                if (slot == null) {
                    issues.add(FormIssue("NF-SPC-002", "/sections/" + section.id, "section.slots 指向不存在的槽位：" + slotId, "补槽位或删除引用"))
                } else if (slot.section != section.id) {
                    issues.add(FormIssue("NF-SPC-002", "/slots/" + slot.id, "槽位 section 与章节不一致：" + slot.section + " != " + section.id, "两侧对齐"))
                }
            }
        }
        for (slot in spec.slots) {
            val section = byId[slot.section]
            if (section == null) {
                issues.add(FormIssue("NF-SPC-002", "/slots/" + slot.id, "槽位指向不存在的章节：" + slot.section, "补章节或修槽位"))
            } else if (slot.id !in section.slots) {
                issues.add(FormIssue("NF-SPC-002", "/sections/" + section.id, "章节 slots 未登记槽位：" + slot.id, "补 section.slots"))
            }
        }
        return issues
    }

    /** 回写 nf-md-spec/1（供核心 spec-validate / 项目引用保存使用）。 */
    fun toJson(s: MdSpec): JsonObject = buildJsonObject {
        put("schema", SCHEMA)
        put("id", s.id)
        put("title", s.title)
        put("version", s.version)
        put("heading_level", s.headingLevel)
        put("sections", buildJsonArray {
            for (section in s.sections) add(buildJsonObject {
                put("id", section.id)
                put("title", section.title)
                put("order", section.order)
                put("required", section.required)
                put("slots", buildJsonArray { for (slot in section.slots) add(kotlinx.serialization.json.JsonPrimitive(slot)) })
            })
        })
        put("slots", buildJsonArray {
            for (slot in s.slots) add(buildJsonObject {
                put("id", slot.id)
                put("name", slot.name)
                put("section", slot.section)
                put("kind", slot.kind)
                put("required", slot.required)
            })
        })
    }
}
