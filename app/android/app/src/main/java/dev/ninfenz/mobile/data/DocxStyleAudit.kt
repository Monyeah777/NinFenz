package dev.ninfenz.mobile.data

import java.io.File

/** DOCX 导出后样式核对：只检查 applied styles 的 styleId 是否出现在导出的 word/styles.xml。 */
data class DocxStyleAuditResult(
    val checked: Int,
    val found: Int,
    val missing: List<String>
) {
    val ok: Boolean get() = missing.isEmpty()
}

object DocxStyleAudit {
    fun check(appliedStylesXml: String, exported: File): DocxStyleAuditResult {
        val expected = StyleMatch.styleIds(appliedStylesXml)
        if (expected.isEmpty()) return DocxStyleAuditResult(0, 0, emptyList())
        val actual = StyleMatch.styleIds(DocxReferenceStyles.extract(exported))
        val missing = expected.filter { it !in actual }
        return DocxStyleAuditResult(expected.size, expected.size - missing.size, missing)
    }
}
