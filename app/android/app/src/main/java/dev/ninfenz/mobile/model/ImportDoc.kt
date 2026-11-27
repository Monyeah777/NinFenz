package dev.ninfenz.mobile.model

import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.core.ModelException
import kotlinx.serialization.json.JsonObject

/** nf-import/1 §5.2：嗅探结果 + 结构抽取 + 映射建议。 */
data class ImportCandidate(val format: String, val confidence: Int)

data class ImportSource(
    val kind: String,
    val name: String,
    val mime: String?,
    val size: Long?,
    val sha256: String?
)

data class ImportHeading(val line: Int, val level: Int, val text: String)
data class ImportCodeBlock(val lang: String, val lines: Int)
data class ImportTableShape(val columns: Int, val rows: Int)

data class ImportStructure(
    val headings: List<ImportHeading>,
    val paragraphs: Int,
    val codeBlocks: List<ImportCodeBlock>,
    val tables: List<ImportTableShape>
)

data class MappingSuggestion(
    val fromKind: String,
    val fromIndex: Int,
    val toKind: String,
    val toId: String,
    val confidence: Int,
    val rationale: String
)

data class ImportWarning(val code: String, val message: String, val path: String?)

data class ImportDoc(
    val format: String,
    val confidence: Int,
    val candidates: List<ImportCandidate>,
    val source: ImportSource,
    val text: String?,
    val textPath: String?,
    val textDigest: String?,
    val structure: ImportStructure,
    val mappings: List<MappingSuggestion>,
    val unmapped: List<String>,
    val warnings: List<ImportWarning>
) {
    /** CONTRACT §5.2：置信度 < 60 必须人工确认，不得自动入库。 */
    val lowConfidence: Boolean get() = confidence < 60

    fun structureDigest(): String = textDigest ?: "（无 text_digest）"

    /** 预览页的「待确认事项」：全部来自解析结果，不添油加醋。 */
    fun reviewNotes(): List<String> {
        val notes = mutableListOf<String>()
        if (lowConfidence) {
            notes.add("嗅探置信度 " + confidence + " < 60：必须人工选择格式，不得自动入库")
        }
        if (candidates.size > 1) {
            notes.add("候选格式 " + candidates.size + " 个：" + candidates.joinToString { it.format + "(" + it.confidence + ")" })
        }
        if (mappings.isEmpty()) {
            notes.add("无映射建议（NF-MAP-001）：导入后归入素材/未分类")
        }
        if (unmapped.isNotEmpty()) {
            notes.add("未映射条目 " + unmapped.size + " 个")
        }
        for (w in warnings) {
            notes.add(w.code + "：" + w.message + (w.path?.let { " @ " + it } ?: ""))
        }
        return notes
    }
}

object ImportModel {
    const val SCHEMA = "nf-import/1"
    const val LOW_CONFIDENCE = 60

    fun parse(text: String): ImportDoc {
        return parse(J.parseObject(text, SCHEMA))
    }

    fun parse(o: JsonObject): ImportDoc {
        J.schema(o, SCHEMA)

        val sourceObj = J.child(o, "source", "")
        val source = ImportSource(
            kind = J.string(sourceObj, "kind", "/source"),
            name = J.string(sourceObj, "name", "/source"),
            mime = J.optString(sourceObj, "mime"),
            size = J.optLong(sourceObj, "size"),
            sha256 = J.optString(sourceObj, "sha256")
        )

        val detected = J.child(o, "detected", "")
        val candidates = parseCandidates(o)
        val structureObj = J.child(o, "structure", "")
        val headings = parseHeadings(structureObj)
        val codeBlocks = parseCodeBlocks(structureObj)
        val tables = parseTables(structureObj)

        val suggested = J.child(o, "suggested", "")
        val mappings = parseMappings(o)

        return ImportDoc(
            format = J.string(detected, "format", "/detected"),
            confidence = J.int(detected, "confidence", "/detected"),
            candidates = candidates,
            source = source,
            text = J.optString(o, "text"),
            textPath = J.optString(o, "text_path"),
            textDigest = J.optString(o, "text_digest"),
            structure = ImportStructure(
                headings = headings,
                paragraphs = J.int(structureObj, "paragraphs", "/structure"),
                codeBlocks = codeBlocks,
                tables = tables
            ),
            mappings = mappings,
            unmapped = J.optStringList(suggested, "unmapped"),
            warnings = parseWarnings(o)
        )
    }

    private fun parseCandidates(o: JsonObject): List<ImportCandidate> =
        J.array(J.child(o, "detected", ""), "candidates", "/detected").mapIndexed { i, el ->
            val c = el as? JsonObject
                ?: throw ModelException("NF-E-002", "/detected/candidates/" + i, "候选应为对象", "按 schema 修正")
            ImportCandidate(
                format = J.string(c, "format", "/detected/candidates/" + i),
                confidence = J.int(c, "confidence", "/detected/candidates/" + i)
            )
        }

    private fun parseHeadings(structureObj: JsonObject): List<ImportHeading> =
        J.array(structureObj, "headings", "/structure").mapIndexed { i, el ->
            val h = el as? JsonObject
                ?: throw ModelException("NF-E-002", "/structure/headings/" + i, "标题应为对象", "按 schema 修正")
            ImportHeading(
                line = J.int(h, "line", "/structure/headings/" + i),
                level = J.int(h, "level", "/structure/headings/" + i),
                text = J.string(h, "text", "/structure/headings/" + i)
            )
        }

    private fun parseCodeBlocks(structureObj: JsonObject): List<ImportCodeBlock> =
        J.array(structureObj, "code_blocks", "/structure").mapIndexed { i, el ->
            val c = el as? JsonObject
                ?: throw ModelException("NF-E-002", "/structure/code_blocks/" + i, "代码块应为对象", "按 schema 修正")
            ImportCodeBlock(
                lang = J.string(c, "lang", "/structure/code_blocks/" + i),
                lines = J.int(c, "lines", "/structure/code_blocks/" + i)
            )
        }

    private fun parseTables(structureObj: JsonObject): List<ImportTableShape> =
        J.array(structureObj, "tables", "/structure").mapIndexed { i, el ->
            val t = el as? JsonObject
                ?: throw ModelException("NF-E-002", "/structure/tables/" + i, "表格应为对象", "按 schema 修正")
            ImportTableShape(
                columns = J.int(t, "columns", "/structure/tables/" + i),
                rows = J.int(t, "rows", "/structure/tables/" + i)
            )
        }

    private fun parseMappings(o: JsonObject): List<MappingSuggestion> =
        J.array(J.child(o, "suggested", ""), "mappings", "/suggested").mapIndexed { i, el ->
            val m = el as? JsonObject
                ?: throw ModelException("NF-E-002", "/suggested/mappings/" + i, "映射建议应为对象", "按 schema 修正")
            val p = "/suggested/mappings/" + i
            MappingSuggestion(
                fromKind = J.string(m, "from_kind", p),
                fromIndex = J.int(m, "from_index", p),
                toKind = J.string(m, "to_kind", p),
                toId = J.string(m, "to_id", p),
                confidence = J.int(m, "confidence", p),
                rationale = J.string(m, "rationale", p)
            )
        }

    private fun parseWarnings(o: JsonObject): List<ImportWarning> =
        J.array(o, "warnings", "").mapIndexed { i, el ->
            val w = el as? JsonObject
                ?: throw ModelException("NF-E-002", "/warnings/" + i, "警告应为对象", "按 schema 修正")
            ImportWarning(
                code = J.string(w, "code", "/warnings/" + i),
                message = J.string(w, "message", "/warnings/" + i),
                path = J.optString(w, "path")
            )
        }
}
