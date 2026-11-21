package dev.ninfenz.mobile.model

import dev.ninfenz.mobile.core.J
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray

/** 再装配用结构：不把 Markdown 当唯一真相，保留块类型与来源。 */
data class NfDocBlock(
    val id: String,
    val type: String,
    val text: String,
    val title: String? = null,
    val slot: String? = null,
    val source: String? = null
)

data class NfDoc(
    val title: String,
    val sources: List<String>,
    val blocks: List<NfDocBlock>
)

object NfDocModel {
    const val SCHEMA = "nf-doc/1"
    private val TYPES = setOf("section", "slot", "paragraph", "list", "table", "code", "quote")

    fun fromMarkdown(title: String, source: String, markdown: String): NfDoc {
        val blocks = MarkdownBlocks.parse(markdown).mapIndexed { index, block ->
            val type = when (block.kind) {
                "heading" -> "section"
                "table" -> "table"
                "code" -> "code"
                "list" -> "list"
                "quote" -> "quote"
                else -> "paragraph"
            }
            NfDocBlock(
                id = "b" + (index + 1),
                type = type,
                text = block.text,
                title = if (type == "section") block.text.trimStart('#', ' ').trim().takeIf { it.isNotEmpty() } else null,
                source = source
            )
        }
        return NfDoc(title.ifBlank { "未命名文档" }, listOf(source), blocks)
    }

    fun append(docs: List<NfDoc>, title: String): NfDoc {
        val sources = docs.flatMap { it.sources }.distinct()
        val blocks = docs.flatMap { doc -> doc.blocks }
            .mapIndexed { index, block -> block.copy(id = "b" + (index + 1)) }
        return NfDoc(title.ifBlank { "合并文档" }, sources, blocks)
    }

    fun toJson(doc: NfDoc): JsonObject = buildJsonObject {
        put("schema", SCHEMA)
        put("meta", buildJsonObject {
            put("title", doc.title)
            putJsonArray("sources") { doc.sources.forEach { add(kotlinx.serialization.json.JsonPrimitive(it)) } }
        })
        putJsonArray("blocks") {
            doc.blocks.forEach { block ->
                add(buildJsonObject {
                    put("id", block.id)
                    put("type", if (block.type in TYPES) block.type else "paragraph")
                    put("text", block.text)
                    block.title?.let { put("title", it) }
                    block.slot?.let { put("slot", it) }
                    block.source?.let { put("source", it) }
                })
            }
        }
    }

    fun parse(o: JsonObject): NfDoc {
        J.schema(o, SCHEMA)
        val meta = J.child(o, "meta", "")
        val blocks = J.array(o, "blocks", "").mapIndexed { index, element ->
            val b = element as? JsonObject ?: throw dev.ninfenz.mobile.core.ModelException("NF-E-002", "/blocks/" + index, "块必须是对象", "按 nf-doc/1 修正")
            NfDocBlock(
                id = J.string(b, "id", "/blocks/" + index + "/id"),
                type = J.string(b, "type", "/blocks/" + index + "/type"),
                text = J.string(b, "text", "/blocks/" + index + "/text"),
                title = J.optString(b, "title"),
                slot = J.optString(b, "slot"),
                source = J.optString(b, "source")
            )
        }
        return NfDoc(J.string(meta, "title", "/meta/title"), J.stringList(meta, "sources", "/meta/sources"), blocks)
    }

}
