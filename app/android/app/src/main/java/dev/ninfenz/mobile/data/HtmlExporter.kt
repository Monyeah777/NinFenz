package dev.ninfenz.mobile.data

import java.io.File

/** 单文件 HTML 导出：基础 Markdown 转 HTML；离线、无外部资源。 */
object HtmlExporter {
    data class Created(val file: File, val bytes: Long)

    fun export(markdown: String, title: String, outDir: File, fileName: String = "result.html"): Created {
        outDir.mkdirs()
        val target = File(outDir, fileName)
        target.writeText(html(markdown, title), Charsets.UTF_8)
        return Created(target, target.length())
    }

    fun html(markdown: String, title: String): String {
        val body = MarkdownHtml.body(markdown, MarkdownHtml.ImagePolicy.REMOTE_AND_DATA)
        val html = StringBuilder()
        html.append("<!DOCTYPE html>\n<html lang=\"zh\"><head><meta charset=\"utf-8\"/>")
        html.append("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>")
        html.append("<title>").append(MarkdownHtml.esc(title)).append("</title>")
        html.append("<style>body{font-family:serif;line-height:1.7;max-width:760px;margin:2em auto;padding:0 1em;color:#222}pre{background:#f5f5f5;padding:1em;overflow:auto}code{font-family:monospace}h1,h2,h3{line-height:1.3}</style>")
        html.append("</head><body><h1>").append(MarkdownHtml.esc(title)).append("</h1>\n")
        html.append(body)
        html.append("</body></html>\n")
        return html.toString()
    }
}
