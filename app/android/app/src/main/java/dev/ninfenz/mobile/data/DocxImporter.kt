package dev.ninfenz.mobile.data

import java.io.File
import java.util.zip.ZipFile

/** DOCX 轻量导入：读取 word/document.xml 的段落文本，Heading 样式转 Markdown 标题。 */
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
            val paragraphs = Regex("(?s)<w:p[ >].*?</w:p>").findAll(xml).mapNotNull { m ->
                val para = m.value
                val text = Regex("(?s)<w:t[^>]*>(.*?)</w:t>").findAll(para).joinToString("") { esc(it.groupValues[1]) }
                    .replace("<w:br/>", "\n")
                    .trim()
                if (text.isBlank()) return@mapNotNull null
                val style = Regex("w:pStyle\\s+w:val=\"([^\"]+)\"").find(para)?.groupValues?.getOrNull(1).orEmpty()
                val level = Regex("(?i)heading\\s*([1-6])").find(style)?.groupValues?.getOrNull(1)?.toIntOrNull()
                when {
                    level != null -> "#".repeat(level) + " " + text
                    para.contains("<w:numPr") -> "- " + text
                    else -> text
                }
            }.toList()
            if (paragraphs.isEmpty()) throw IllegalArgumentException("DOCX 无可读段落")
            return paragraphs.joinToString("\n\n")
        }
    }

    private fun esc(s: String): String = s
        .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", "\"").replace("&amp;", "&")
}
