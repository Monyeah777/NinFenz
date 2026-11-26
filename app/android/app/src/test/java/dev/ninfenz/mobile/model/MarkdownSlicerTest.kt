package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Test

class MarkdownSlicerTest {
    @Test
    fun groupsBlocksUnderHeadings() {
        val md = "# 第一章\n\n正文一\n\n# 第二章\n\n正文二\n\n正文三"
        val slices = MarkdownSlicer.slice(MarkdownBlocks.parse(md))
        assertEquals(2, slices.size)
        assertEquals("第一章", slices[0].heading)
        assertEquals(1, slices[0].blocks.size)
        assertEquals("第二章", slices[1].heading)
        assertEquals(2, slices[1].blocks.size)
    }

    @Test
    fun mergesSectionsBelowMinimum() {
        val md = "# A\n\nshort\n\n# B\n\nshort too"
        val slices = MarkdownSlicer.slice(MarkdownBlocks.parse(md), minChars = 50)
        assertEquals(1, slices.size)
        assertEquals("A", slices[0].heading)
        assertEquals(2, slices[0].blocks.size)
    }

    @Test
    fun preambleWithoutHeadingStaysOneSlice() {
        val slices = MarkdownSlicer.slice(MarkdownBlocks.parse("开头段落\n\n第二段"))
        assertEquals(1, slices.size)
        assertEquals(null, slices[0].heading)
        assertEquals(2, slices[0].blocks.size)
    }
}
