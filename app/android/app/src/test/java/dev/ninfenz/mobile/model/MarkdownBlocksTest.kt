package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Test

class MarkdownBlocksTest {
    @Test
    fun keepsFencedCodeAsOneBlock() {
        val md = "# 标题\n\n段落一\n\n```kotlin\nval a = 1\n\nval b = 2\n```\n\n段落二"
        val blocks = MarkdownBlocks.parse(md)
        assertEquals(4, blocks.size)
        assertEquals("段落二", blocks.last().text)
        assertEquals(md, MarkdownBlocks.render(blocks))
        assertEquals("heading", blocks.first().kind)
        assertEquals("code", blocks[2].kind)
        assertEquals("paragraph", blocks.last().kind)
    }

    @Test
    fun yearIsParagraphButOrderedListIsList() {
        val blocks = MarkdownBlocks.parse("2026 年计划\n\n1. 第一项\n\n2) 第二项")
        assertEquals("paragraph", blocks[0].kind)
        assertEquals("list", blocks[1].kind)
        assertEquals("list", blocks[2].kind)
    }

    @Test
    fun emptyInputRendersEmpty() {
        assertEquals(emptyList<MarkdownBlock>(), MarkdownBlocks.parse("  "))
        assertEquals("", MarkdownBlocks.render(emptyList()))
    }
}
