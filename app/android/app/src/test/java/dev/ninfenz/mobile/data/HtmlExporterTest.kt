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
    fun handlesCodeFence() {
        val dir = Files.createTempDirectory("nf-html-2").toFile()
        val created = HtmlExporter.export("\u0060\u0060\u0060\ncode\n\u0060\u0060\u0060", "t", dir)
        assertTrue(created.file.readText().contains("<pre><code>code</code></pre>"))
    }
}
