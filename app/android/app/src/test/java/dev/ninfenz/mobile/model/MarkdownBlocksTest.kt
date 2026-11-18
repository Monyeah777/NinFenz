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
    }

    @Test
    fun emptyInputRendersEmpty() {
        assertEquals(emptyList<MarkdownBlock>(), MarkdownBlocks.parse("  "))
        assertEquals("", MarkdownBlocks.render(emptyList()))
    }
}
