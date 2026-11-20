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
        ImportPreflight.check(file)
        ZipFile(file).use { zip ->
            val entry = zip.getEntry("word/document.xml") ?: throw IllegalArgumentException("DOCX 缺 document.xml")
            require(entry.size in 0..(64L * 1024 * 1024)) { "DOCX document.xml 过大" }
            val xml = zip.getInputStream(entry).use { String(readLimited(it, 64L * 1024 * 1024), Charsets.UTF_8) }
            val links = zip.getEntry("word/_rels/document.xml.rels")?.let { rel ->
                val relXml = zip.getInputStream(rel).use { String(readLimited(it, 2L * 1024 * 1024), Charsets.UTF_8) }
                Regex("(?is)<Relationship\\s[^>]*>").findAll(relXml).mapNotNull { m ->
                    val type = attr(m.value, "Type").orEmpty()
                    val id = attr(m.value, "Id") ?: return@mapNotNull null
                    val target = attr(m.value, "Target") ?: return@mapNotNull null
                    if (type.contains("hyperlink")) id to target else null
                }.toMap()
            } ?: emptyMap()
            val out = StringBuilder()
            var last = 0
            Regex("(?s)<w:tbl[ >].*?</w:tbl>").findAll(xml).forEach { m ->
                appendParagraphs(out, xml.substring(last, m.range.first), links)
                val table = table(m.value, links)
                if (table.isNotBlank()) {
                    if (out.isNotEmpty()) out.append("\n\n")
                    out.append(table)
                }
                last = m.range.last + 1
            }
            appendParagraphs(out, xml.substring(last), links)
            val text = out.toString().trim()
            if (text.isBlank()) throw IllegalArgumentException("DOCX 无可读段落")
            return text
        }
    }

    private fun readLimited(input: java.io.InputStream, max: Long): ByteArray {
        val out = java.io.ByteArrayOutputStream()
        val buf = ByteArray(16 * 1024)
        var read = 0L
        while (true) {
            val n = input.read(buf)
            if (n < 0) break
            read += n
            require(read <= max) { "DOCX 条目超限" }
            out.write(buf, 0, n)
        }
        return out.toByteArray()
    }

    private fun appendParagraphs(out: StringBuilder, xml: String, links: Map<String, String>) {
        Regex("(?s)<w:p[ >].*?</w:p>").findAll(xml).forEach { m ->
            val para = m.value
            val text = runs(para, links).trim()
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

    private fun runs(para: String, links: Map<String, String>): String {
        val refs = mutableListOf<String>()
        val withLinks = Regex("(?is)<w:hyperlink[^>]*r:id=\"([^\"]+)\"[^>]*>(.*?)</w:hyperlink>").replace(para) { m ->
            val target = links[m.groupValues[1]]
            if (target == null || !SafeLink.allowed(target)) {
                m.value
            } else {
                refs.add("[" + runs(m.groupValues[2], links).trim() + "](" + target + ")")
                "<w:r><w:t>%%NF_LINK_" + (refs.size - 1) + "%%</w:t></w:r>"
            }
        }
        val rendered = Regex("(?s)<w:r[ >].*?</w:r>").findAll(withLinks).joinToString("") { m ->
            val run = m.value
            val text = Regex("(?s)<w:t(?:\\s[^>]*)?>(.*?)</w:t>").findAll(run).joinToString("") { esc(it.groupValues[1]) }
            if (text.isBlank()) return@joinToString ""
            var styled = text
            if (on(run, "b")) styled = "**" + styled + "**"
            if (on(run, "i")) styled = "*" + styled + "*"
            styled
        }
        var result = rendered
        refs.forEachIndexed { i, link -> result = result.replace("%%NF_LINK_" + i + "%%", link) }
        return result
    }

    private fun on(run: String, tag: String): Boolean {
        val m = Regex("(?s)<w:" + tag + "(?:\\s[^>]*)?/?>").find(run) ?: return false
        val v = Regex("w:val=\"([^\"]+)\"").find(m.value)?.groupValues?.getOrNull(1)
        return v == null || v == "1" || v.equals("true", true)
    }

    private fun table(html: String, links: Map<String, String>): String {
        val rows = Regex("(?s)<w:tr[ >].*?</w:tr>").findAll(html).map { row ->
            Regex("(?s)<w:tc[ >].*?</w:tc>").findAll(row.value).map { cell ->
                runs(cell.value, links).replace("|", "\\|").trim()
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

    private fun attr(tag: String, name: String): String? =
        Regex("(?i)" + Regex.escape(name) + "\\s*=\\s*[\"']([^\"']*)[\"']").find(tag)?.groupValues?.getOrNull(1)

    private fun esc(s: String): String = s
        .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", "\"").replace("&amp;", "&")
}
