package dev.ninfenz.mobile.data

import java.io.File

/** DOCX 导出后样式核对：只检查 applied styles 的 styleId 是否出现在导出的 word/styles.xml。 */
data class DocxStyleAuditResult(
    val checked: Int,
    val found: Int,
    val missing: List<String>,
    val referenced: Int = 0
) {
    val ok: Boolean get() = missing.isEmpty()
    /** 样式已定义但没有在文档里引用，版式可能没生效。 */
    val definedButUnused: Boolean get() = checked > 0 && referenced == 0
}

object DocxStyleAudit {
    fun check(appliedStylesXml: String, exported: File): DocxStyleAuditResult {
        val expected = StyleMatch.styleIds(appliedStylesXml)
        if (expected.isEmpty()) return DocxStyleAuditResult(0, 0, emptyList())
        val actual = StyleMatch.styleIds(DocxReferenceStyles.extract(exported))
        val missing = expected.filter { it !in actual }
        val used = Regex("w:(?:p|r)Style w:val=\"([^\"]+)\"")
            .findAll(DocxReferenceStyles.extractDocument(exported).orEmpty())
            .map { it.groupValues[1] }
            .toSet()
        val referenced = expected.count { it in used }
        return DocxStyleAuditResult(expected.size, expected.size - missing.size, missing, referenced)
    }
}
