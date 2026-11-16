package dev.ninfenz.mobile.data

import java.io.File
import java.util.zip.ZipFile

/** DOCX 轻量导入：段落/标题/列表/表格转 Markdown；不处理图片与复杂样式。 */
object DocxImporter {
    fun detect(file: File): Boolean = try {
        ZipFile(file).use { it.getEntry("word/document.xml") != null }
    } catch (t: Throwable) {
        false
    }

    fun extract(file: File): String {
        ZipFile(file).use { zip ->
            val entry = zip.getEntry("word/document.xml") ?: throw IllegalArgumentException("DOCX 缺 document.xml")
            val xml = zip.getInputStream(entry).use { String(it.readBytes(), Charsets.UTF_8) }
            val out = StringBuilder()
            var last = 0
            Regex("(?s)<w:tbl[ >].*?</w:tbl>").findAll(xml).forEach { m ->
                appendParagraphs(out, xml.substring(last, m.range.first))
                val table = table(m.value)
                if (table.isNotBlank()) {
                    if (out.isNotEmpty()) out.append("\n\n")
                    out.append(table)
                }
                last = m.range.last + 1
            }
            appendParagraphs(out, xml.substring(last))
            val text = out.toString().trim()
            if (text.isBlank()) throw IllegalArgumentException("DOCX 无可读段落")
            return text
        }
    }

    private fun appendParagraphs(out: StringBuilder, xml: String) {
        Regex("(?s)<w:p[ >].*?</w:p>").findAll(xml).forEach { m ->
            val para = m.value
            val text = Regex("(?s)<w:t(?:\\s[^>]*)?>(.*?)</w:t>").findAll(para).joinToString("") { esc(it.groupValues[1]) }
                .replace("<w:br/>", "\n")
                .trim()
            if (text.isBlank()) return@forEach
            val block = when {
                para.contains("<w:numPr") -> "- " + text
                else -> {
                    val style = Regex("w:pStyle\\s+w:val=\"([^\"]+)\"").find(para)?.groupValues?.getOrNull(1).orEmpty()
                    val level = Regex("(?i)heading\\s*([1-6])").find(style)?.groupValues?.getOrNull(1)?.toIntOrNull()
                    if (level != null) "#".repeat(level) + " " + text else text
                }
            }
            if (out.isNotEmpty()) out.append("\n\n")
            out.append(block)
        }
    }

    private fun table(html: String): String {
        val rows = Regex("(?s)<w:tr[ >].*?</w:tr>").findAll(html).map { row ->
            Regex("(?s)<w:tc[ >].*?</w:tc>").findAll(row.value).map { cell ->
                Regex("(?s)<w:t(?:\\s[^>]*)?>(.*?)</w:t>").findAll(cell.value).joinToString("") { esc(it.groupValues[1]) }
                    .replace("|", "\\|").trim()
            }.toList()
        }.filter { it.isNotEmpty() }.toList()
        if (rows.isEmpty()) return ""
        val width = rows.maxOf { it.size }
        val out = StringBuilder()
        rows.forEachIndexed { index, cells ->
            out.append("| ")
            for (i in 0 until width) {
                out.append(cells.getOrElse(i) { "" })
                if (i < width - 1) out.append(" | ")
            }
            out.append(" |\n")
            if (index == 0) {
                out.append("|")
                repeat(width) { out.append(" --- |") }
                out.append("\n")
            }
        }
        return out.toString().trimEnd()
    }

    private fun esc(s: String): String = s
        .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", "\"").replace("&amp;", "&")
}
