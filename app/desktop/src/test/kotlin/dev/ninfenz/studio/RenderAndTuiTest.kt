package dev.ninfenz.studio

import dev.ninfenz.studio.print.PrintService
import dev.ninfenz.studio.render.MarkdownRenderer
import dev.ninfenz.studio.tui.TuiRunner
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File

class RenderAndTuiTest {

    private val md = "# 标题\n\n正文 **加粗** 与 __下划线__。\n\n- 要点一\n- 要点二\n\n```kotlin\nval x = 1\n```\n\n## 二级\n"

    @Test
    fun plainTextStripsMarkdownMarkers() {
        val text = MarkdownRenderer.toPlainText(md)
        assertTrue(text.contains("标题".uppercase()) || text.contains("标题"))
        assertTrue(text.contains("加粗"))
        assertFalse(text.contains("**"))
        assertFalse(text.contains("__"))
        assertTrue(text.contains("• 要点一"))
        assertTrue(text.contains("[code]"))
        assertTrue(text.contains("    val x = 1"))
    }

    @Test
    fun htmlEscapesAndStructures() {
        val html = MarkdownRenderer.toHtml("<script>alert(1)</script>\n\n# 标题\n\n- a\n")
        assertFalse(html.contains("<script>alert(1)</script>"))
        assertTrue(html.contains("&lt;script&gt;"))
        assertTrue(html.contains("<h1>标题</h1>"))
        assertTrue(html.contains("<ul>"))
        assertTrue(html.contains("<li>a</li>"))
    }

    @Test
    fun htmlHasDeterministicHeader() {
        val html = MarkdownRenderer.toHtml("body")
        assertTrue(html.startsWith("<!DOCTYPE html>"))
        assertTrue(html.contains("charset=\"utf-8\""))
    }

    @Test
    fun htmlFileGeneratedInTempDir() {
        val file = PrintService.writeHtml("# 打印\n\n正文", "unit-test")
        assertTrue(file.isFile)
        assertTrue(file.readText(Charsets.UTF_8).contains("<h1>打印</h1>"))
    }

    @Test
    fun findsRepoRootForTui() {
        val root = TuiRunner.findRepoRoot()
        assumeTrue("不在 NinFenz 检出内，跳过", root != null)
        assertTrue(File(root!!, "tui/nf.py").isFile || File(root, "app/core/Cargo.toml").isFile)
    }

    @Test
    fun emptyCommandFailsClosed() {
        val result = TuiRunner.run(emptyList(), File("."))
        assertEquals(-1, result.exit)
        assertTrue(result.output.contains("空命令"))
    }
}
