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
        "smart_collection" -> requireArray(config, "rules", "smart_collection 需要 rules")
        "spec_snippet" -> requireNestedText(config, "section", "id", "spec_snippet 需要 section.id")
        "clause_library" -> requireArray(config, "clauses", "clause_library 需要 clauses")
        "graph_recipe" -> requireArray(config, "nodes", "graph_recipe 需要 nodes")
        "delivery_variant" -> requireInputs(config, "delivery_variant 需要 inputs")
        "assembly_recipe" -> requireAssembly(config)
        "slot_transform" -> requireTransformKind(config)
        "export_profile" -> requirePresent(config, "export_profile 为空", exportProfileKeys)
        "output_rule" -> required(config, "template")
        "workspace_preset" -> requirePresent(config, "workspace_preset 为空", workspacePresetKeys)
        "review_checklist" -> requireArray(config, "items", "review_checklist 需要 items")
        else -> null
    }

    private val exportProfileKeys = listOf(
        "docx_styles", "docx_sect_pr", "docx_theme", "docx_numbering", "docx_header", "docx_footer",
        "epub_author", "epub_language", "pdf_page_size", "pdf_include_title"
    )
    private val workspacePresetKeys = listOf("theme", "language", "dynamic_color")

    private fun required(config: JsonObject, key: String): String? =
        if (text(config, key).isBlank()) "缺少 " + key else null

    private fun requireArray(config: JsonObject, key: String, message: String): String? =
        if (array(config, key).isEmpty()) message else null

    private fun requireNestedText(config: JsonObject, parent: String, key: String, message: String): String? =
        if (child(config, parent)?.let { text(it, key) }.isNullOrBlank()) message else null

    private fun requireInputs(config: JsonObject, message: String): String? =
        if (child(config, "inputs")?.isEmpty() != false) message else null

    private fun requireAssembly(config: JsonObject): String? =
        if (text(config, "name").isBlank() || child(config, "inputs")?.isEmpty() != false) "assembly_recipe 需要 name 和 inputs" else null

    private fun requireTransformKind(config: JsonObject): String? =
        if (text(config, "kind") !in transforms) "slot_transform 的 kind 不受支持" else null

    private fun requirePresent(config: JsonObject, message: String, keys: List<String>): String? =
        if (keys.none { config[it] != null }) message else null

    private fun text(o: JsonObject, key: String): String =
        o[key]?.jsonPrimitive?.content.orEmpty()

    private fun child(o: JsonObject, key: String): JsonObject? = o[key] as? JsonObject

    private fun array(o: JsonObject, key: String): List<JsonPrimitive> =
        (o[key] as? JsonArray)?.mapNotNull { it as? JsonPrimitive }.orEmpty()
}
