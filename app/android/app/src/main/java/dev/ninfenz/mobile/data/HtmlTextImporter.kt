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
        val text = HtmlCompat.fromHtml(clean, HtmlCompat.FROM_HTML_MODE_LEGACY).toString()
        return text
            .replace("\r\n", "\n")
            .replace(Regex("\n{3,}"), "\n\n")
            .trim()
    }
}
