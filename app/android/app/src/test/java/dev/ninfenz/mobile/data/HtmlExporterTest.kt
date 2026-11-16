package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertTrue
import org.junit.Test

class HtmlExporterTest {
    @Test
    fun producesStandaloneHtmlAndEscapes() {
        val dir = Files.createTempDirectory("nf-html").toFile()
        val created = HtmlExporter.export("# 标题\n\n正文 <script>\n\n- 要点", "演示", dir)
        val text = created.file.readText()
        assertTrue(text.startsWith("<!DOCTYPE html>"))
        assertTrue(text.contains("&lt;script&gt;"))
        assertTrue(text.contains("<ul>"))
        assertTrue(text.contains("<title>演示</title>"))
    }

    @Test
    fun rendersPipeTable() {
        val dir = Files.createTempDirectory("nf-html-table").toFile()
        val created = HtmlExporter.export("| A | B |\n|---|---|\n| 1 | 2 |", "t", dir)
        val text = created.file.readText()
        assertTrue(text.contains("<table>"))
        assertTrue(text.contains("<th>A</th>"))
        assertTrue(text.contains("<td>1</td>"))
    }

    @Test
    fun rendersOnlySafeLinks() {
        val dir = Files.createTempDirectory("nf-html-link").toFile()
        val created = HtmlExporter.export("[官网](https://example.com) [坏](javascript:alert(1))", "t", dir)
        val text = created.file.readText()
        assertTrue(text.contains("<a href=\"https://example.com\">官网</a>"))
        assertTrue(text.contains("[坏](javascript:alert(1))"))
    }

    @Test
    fun rendersInlineCode() {
        val dir = Files.createTempDirectory("nf-html-code").toFile()
        val created = HtmlExporter.export("使用 `nf` 命令", "t", dir)
        assertTrue(created.file.readText().contains("<code>nf</code>"))
    }

    @Test
    fun rendersHorizontalRule() {
        val dir = Files.createTempDirectory("nf-html-hr").toFile()
        val created = HtmlExporter.export("前\n\n---\n\n后", "t", dir)
        assertTrue(created.file.readText().contains("<hr/>"))
    }

    @Test
    fun rendersBlockquote() {
        val dir = Files.createTempDirectory("nf-html-quote").toFile()
        val created = HtmlExporter.export("> 引用\n\n正文", "t", dir)
        assertTrue(created.file.readText().contains("<blockquote><p>引用</p></blockquote>"))
    }

    @Test
    fun rendersOrderedList() {
        val dir = Files.createTempDirectory("nf-html-ol").toFile()
        val created = HtmlExporter.export("1. 一\n2. 二", "t", dir)
        assertTrue(created.file.readText().contains("<ol><li>一</li><li>二</li></ol>"))
    }

    @Test
    fun rendersStrikethrough() {
        val dir = Files.createTempDirectory("nf-html-del").toFile()
        val created = HtmlExporter.export("~~旧~~ 新", "t", dir)
        assertTrue(created.file.readText().contains("<del>旧</del>"))
    }

    @Test
    fun rendersSafeImages() {
        val dir = Files.createTempDirectory("nf-html-img").toFile()
        val created = HtmlExporter.export("![图](https://e/x.png) ![坏](javascript:x)", "t", dir)
        val text = created.file.readText()
        assertTrue(text.contains("<img src=\"https://e/x.png\" alt=\"图\"/>"))
        assertTrue(text.contains("![坏](javascript:x)"))
    }

    @Test
    fun rendersCodeLanguageClass() {
        val dir = Files.createTempDirectory("nf-html-lang").toFile()
        val created = HtmlExporter.export("\u0060\u0060\u0060kotlin\nval x = 1\n\u0060\u0060\u0060", "t", dir)
        assertTrue(created.file.readText().contains("<code class=\"language-kotlin\">"))
    }

    @Test
    fun rendersTableAlignment() {
        val dir = Files.createTempDirectory("nf-html-align").toFile()
        val created = HtmlExporter.export("| A | B | C |\n|:---|:---:|---:|\n| 1 | 2 | 3 |", "t", dir)
        val text = created.file.readText()
        assertTrue(text.contains("style=\"text-align:left\""))
        assertTrue(text.contains("style=\"text-align:center\""))
        assertTrue(text.contains("style=\"text-align:right\""))
    }

    @Test
    fun handlesCodeFence() {
        val dir = Files.createTempDirectory("nf-html-2").toFile()
        val created = HtmlExporter.export("\u0060\u0060\u0060\ncode\n\u0060\u0060\u0060", "t", dir)
        assertTrue(created.file.readText().contains("<pre><code>code</code></pre>"))
    }
}
