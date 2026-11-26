package dev.ninfenz.mobile.data

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonPrimitive

/** 对已知 contribution 做 config 形状校验；不执行扩展代码。 */
object ExtensionContributionValidator {
    private val transforms = setOf(
        "prefix", "suffix", "strip_prefix", "strip_suffix", "replace",
        "truncate", "lower", "upper", "trim", "collapse"
    )

    fun validate(kind: String, config: JsonObject): String? = when (kind) {
        "saved_view" -> required(config, "name")
        "smart_collection" -> if (array(config, "rules").isEmpty()) "smart_collection 需要 rules" else null
        "spec_snippet" -> if (child(config, "section")?.let { text(it, "id") }.isNullOrBlank()) "spec_snippet 需要 section.id" else null
        "clause_library" -> if (array(config, "clauses").isEmpty()) "clause_library 需要 clauses" else null
        "graph_recipe" -> if (array(config, "nodes").isEmpty()) "graph_recipe 需要 nodes" else null
        "delivery_variant" -> if (child(config, "inputs")?.isEmpty() != false) "delivery_variant 需要 inputs" else null
        "assembly_recipe" -> if (text(config, "name").isBlank() || child(config, "inputs")?.isEmpty() != false) "assembly_recipe 需要 name 和 inputs" else null
        "slot_transform" -> {
            val kindName = text(config, "kind")
            if (kindName !in transforms) "slot_transform 的 kind 不受支持" else null
        }
        "export_profile" -> if (listOf("docx_styles", "docx_sect_pr", "docx_theme", "docx_numbering", "docx_header", "docx_footer", "epub_author", "epub_language", "pdf_page_size", "pdf_include_title").none { config[it] != null }) "export_profile 为空" else null
        "output_rule" -> required(config, "template")
        "workspace_preset" -> if (config["theme"] == null && config["language"] == null && config["dynamic_color"] == null) "workspace_preset 为空" else null
        "review_checklist" -> if (array(config, "items").isEmpty()) "review_checklist 需要 items" else null
        else -> null
    }

    private fun required(config: JsonObject, key: String): String? =
        if (text(config, key).isBlank()) "缺少 " + key else null

    private fun text(o: JsonObject, key: String): String =
        o[key]?.jsonPrimitive?.content.orEmpty()

    private fun child(o: JsonObject, key: String): JsonObject? = o[key] as? JsonObject

    private fun array(o: JsonObject, key: String): List<JsonPrimitive> =
        (o[key] as? JsonArray)?.mapNotNull { it as? JsonPrimitive }.orEmpty()
}
