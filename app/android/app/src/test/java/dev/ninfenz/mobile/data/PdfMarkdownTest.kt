package dev.ninfenz.mobile.data

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
    fun bulletsUseDotPrefix() {
        assertEquals(listOf("• 一", "• 二"), PdfMarkdown.lines("- 一\n* 二"))
    }
}
