package dev.ninfenz.mobile.model

/** 导入保真报告：只从当前解析结果计算，不声称比解析器知道得更多。 */
data class FidelityReport(
    val sourceFormat: String,
    val headings: Int,
    val paragraphs: Int,
    val code: Int,
    val tables: Int,
    val unmapped: Int,
    val lost: List<String>,
    val score: Int,
    val notes: List<String>
) {
    companion object {
        fun from(doc: ImportDoc): FidelityReport {
            val headings = doc.structure.headings.size
            val paragraphs = doc.structure.paragraphs
            val code = doc.structure.codeBlocks.size
            val tables = doc.structure.tables.size
            val unmapped = doc.unmapped.size
            val total = headings + paragraphs + code + tables + unmapped
            val score = if (total == 0) 100 else ((total - unmapped) * 100) / total
            val lost = doc.warnings.map { it.message }.filter { it.isNotBlank() }.distinct()
            val notes = buildList {
                if (doc.lowConfidence) add("嗅探置信度低，需人工确认格式")
                if (unmapped > 0) add("有 " + unmapped + " 条未映射")
                if (lost.isNotEmpty()) add("解析警告 " + lost.size + " 条")
            }
            return FidelityReport(
                sourceFormat = doc.format,
                headings = headings,
                paragraphs = paragraphs,
                code = code,
                tables = tables,
                unmapped = unmapped,
                lost = lost,
                score = score,
                notes = notes
            )
        }
    }
}
