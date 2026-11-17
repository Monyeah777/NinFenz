package dev.ninfenz.mobile.data

import org.junit.Assert.assertEquals
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
        val lines = PdfMarkdown.lines("| A | B |\n|---|---|\n| 1 | 2 |")
        assertEquals(listOf("A  B", "1  2"), lines)
    }

    @Test
    fun bulletsUseDotPrefix() {
        assertEquals(listOf("• 一", "• 二"), PdfMarkdown.lines("- 一\n* 二"))
    }
}
