package dev.ninfenz.mobile.data

import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PdfMarkdownTest {
    @Test
    fun stripsHeadingAndInlineMarkers() {
        val lines = PdfMarkdown.lines("# 标题\n\n正文 **粗** 和 `代码`")
        assertEquals(listOf("标题", "正文 粗 和 代码"), lines)
    }

    @Test
    fun convertsLinksAndImagesToText() {
        assertEquals("链 图", PdfMarkdown.inline("[链](https://e) ![图](a.png)"))
    }

    @Test
    fun keepsCodeFenceContentWithoutFenceLines() {
        assertEquals(listOf("val x = 1"), PdfMarkdown.lines("```kotlin\nval x = 1\n```"))
    }

    @Test
    fun tableRowsBecomeSpacedColumns() {
        val blocks = PdfMarkdown.blocks("| A | B |\n|---|---|\n| 1 | 2 |")
        assertEquals(listOf("A  B", "1  2"), blocks.map { it.text })
        assertTrue(blocks[0].tableHeader)
        assertFalse(blocks[1].tableHeader)
        assertEquals(listOf("A", "B"), blocks[0].cells)
    }

    @Test
    fun quoteAndHorizontalRuleAreMarked() {
        val blocks = PdfMarkdown.blocks("> 引用\n\n---")
        assertTrue(blocks[0].quote)
        assertEquals("│ 引用", PdfMarkdown.lines("> 引用")[0])
        assertTrue(blocks[1].rule)
    }

    @Test
    fun inlineSpansCarryEmphasis() {
        val spans = PdfMarkdown.spanize("a **b** *c* `d`")
        assertEquals("a ", spans[0].text)
        assertTrue(spans.first { it.text == "b" }.bold)
        assertTrue(spans.first { it.text == "c" }.italic)
        assertTrue(spans.first { it.text == "d" }.code)
    }

    @Test
    fun dataUriImageIsDecoded() {
        val png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        val blocks = PdfMarkdown.blocks("![图](data:image/png;base64," + png + ")")
        assertEquals("图", blocks[0].text)
        assertTrue(blocks[0].image != null && blocks[0].image!!.isNotEmpty())
    }

    @Test
    fun malformedMarkdownDoesNotThrow() {
        val samples = listOf(
            "**unclosed",
            "![no](data:image/png;base64,@@@)",
            "[link](",
            "| a | b",
            "> ",
            "~~~",
            "***",
            "#".repeat(10) + " x",
            "a\u0000b"
        )
        for (s in samples) {
            assertNotNull(PdfMarkdown.blocks(s))
            assertNotNull(PdfMarkdown.lines(s))
        }
    }

    @Test
    fun bulletsUseDotPrefix() {
        assertEquals(listOf("• 一", "• 二"), PdfMarkdown.lines("- 一\n* 二"))
    }
}
