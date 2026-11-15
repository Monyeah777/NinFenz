package dev.ninfenz.mobile.model

import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.core.ModelException
import kotlinx.serialization.json.JsonObject

data class SpecSection(val id: String, val title: String, val order: Int, val required: Boolean, val slots: List<String>)
data class SpecSlot(val id: String, val name: String, val section: String, val kind: String, val required: Boolean)

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
                required = J.bool(s, "required", p)
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
}
