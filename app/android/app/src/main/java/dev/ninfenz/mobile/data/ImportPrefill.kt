package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.model.ImportModel
import dev.ninfenz.mobile.model.MarkdownBlocks

/** 从项目 authoring/import-*（nf-import/1）提取槽位预填，纯函数便于单测。 */
object ImportPrefill {
    fun fromJson(raw: String): Map<String, String> = runCatching {
        val doc = ImportModel.parse(J.parseObject(raw, ImportModel.SCHEMA))
        val blocks = MarkdownBlocks.parse(doc.text.orEmpty())
        doc.mappings.mapNotNull { mapping ->
            blocks.getOrNull(mapping.fromIndex)?.text?.takeIf { it.isNotBlank() }?.let { text ->
                mapping.toId to text
            }
        }.toMap()
    }.getOrDefault(emptyMap())
}
