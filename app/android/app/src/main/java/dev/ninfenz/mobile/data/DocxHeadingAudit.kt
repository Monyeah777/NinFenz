package dev.ninfenz.mobile.data

import java.io.File

/** DOCX 标题样式应用核对：Markdown 标题数 vs 文档中 Heading1-6 段落数。 */
data class DocxHeadingAuditResult(
    val markdownHeadings: Int,
    val styledHeadings: Int
) {
    val ok: Boolean get() = styledHeadings >= markdownHeadings
}

object DocxHeadingAudit {
    private val headingStyle = Regex("w:pStyle w:val=\"Heading[1-6]\"")
    private val markdownHeading = Regex("^#{1,6}\\s+.+$", RegexOption.MULTILINE)

    fun check(markdown: String, exported: File): DocxHeadingAuditResult {
        val document = DocxReferenceStyles.extractDocument(exported).orEmpty()
        return DocxHeadingAuditResult(
            markdownHeadings = markdownHeading.findAll(markdown).count(),
            styledHeadings = headingStyle.findAll(document).count()
        )
    }
}
