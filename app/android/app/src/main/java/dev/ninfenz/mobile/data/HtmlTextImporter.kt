package dev.ninfenz.mobile.data

import androidx.core.text.HtmlCompat

/** HTML 转纯文本/Markdown 的轻量入口；只取可读正文，不执行脚本。 */
object HtmlTextImporter {
    fun extract(html: String): String {
        var clean = html.replace(Regex("(?is)<(script|style)[^>]*>.*?</\\1>"), " ")
        clean = Regex("(?is)<h([1-6])[^>]*>(.*?)</h\\1>").replace(clean) { match ->
            val level = match.groupValues[1].toIntOrNull() ?: 1
            val body = match.groupValues[2].replace(Regex("(?is)<[^>]+>"), "").trim()
            if (body.isBlank()) "" else "\n\n" + "#".repeat(level) + " " + body + "\n\n"
        }
        clean = clean.replace(Regex("(?is)<li[^>]*>"), "\n- ")
        clean = Regex("(?is)<table[^>]*>(.*?)</table>").replace(clean) { table ->
            val rows = Regex("(?is)<tr[^>]*>(.*?)</tr>").findAll(table.groupValues[1]).map { row ->
                Regex("(?is)<t[hd][^>]*>(.*?)</t[hd]>").findAll(row.groupValues[1]).map { cell ->
                    cell.groupValues[1].replace(Regex("(?is)<[^>]+>"), " ").replace(Regex("\\s+"), " ").trim()
                }.toList()
            }.filter { it.isNotEmpty() }.toList()
            if (rows.isEmpty()) "" else buildString {
                append("\n\n")
                rows.forEachIndexed { index, cells ->
                    append("| ").append(cells.joinToString(" | ")).append(" |\n")
                    if (index == 0) append("|").append(" --- |".repeat(cells.size)).append("\n")
                }
                append("\n")
            }
        }
        val text = HtmlCompat.fromHtml(clean, HtmlCompat.FROM_HTML_MODE_LEGACY).toString()
        return text
            .replace("\r\n", "\n")
            .replace(Regex("\n{3,}"), "\n\n")
            .trim()
    }
}
