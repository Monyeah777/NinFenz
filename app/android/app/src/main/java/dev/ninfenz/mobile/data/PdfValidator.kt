package dev.ninfenz.mobile.data

import java.io.File

/** PDF 基础结构自检：文件头、尾部、startxref、加密标记、页对象。 */
object PdfValidator {
    data class Result(val ok: Boolean, val message: String, val issues: List<String>)

    fun inspect(file: File): Result {
        if (!file.isFile) return Result(false, "PDF 不存在", listOf("missing file"))
        val bytes = file.readBytes()
        if (bytes.size < 20) return Result(false, "PDF 过短", listOf("too short"))
        val head = String(bytes, 0, minOf(8, bytes.size), Charsets.ISO_8859_1)
        if (!head.startsWith("%PDF-")) return Result(false, "缺少 %PDF- 文件头", listOf("bad header"))
        val tail = String(bytes, maxOf(0, bytes.size - 2048), minOf(2048, bytes.size), Charsets.ISO_8859_1)
        val issues = mutableListOf<String>()
        if (!tail.contains("%%EOF")) issues.add("缺少 %%EOF")
        if (!tail.contains("startxref")) issues.add("缺少 startxref")
        val text = String(bytes, Charsets.ISO_8859_1)
        if (text.contains("/Encrypt")) issues.add("PDF 已加密")
        val pages = Regex("/Type\\s*/Page[^s]").findAll(text).count()
        if (pages == 0) issues.add("未发现页对象")
        return Result(issues.isEmpty(), if (issues.isEmpty()) "PDF 结构校验通过（" + pages + " 页）" else issues.first(), issues)
    }
}
