package dev.ninfenz.mobile.data

import androidx.core.text.HtmlCompat

/** HTML 转纯文本/Markdown 的轻量入口；只取可读正文，不执行脚本。 */
object HtmlTextImporter {
    fun extract(html: String): String {
        val withoutScripts = html.replace(Regex("(?is)<(script|style)[^>]*>.*?</\\1>"), " ")
        val text = HtmlCompat.fromHtml(withoutScripts, HtmlCompat.FROM_HTML_MODE_LEGACY).toString()
        return text
            .replace("\r\n", "\n")
            .replace(Regex("\n{3,}"), "\n\n")
            .trim()
    }
}
