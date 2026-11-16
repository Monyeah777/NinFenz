package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SlotBatchImporterTest {
    @Test
    fun splitsOnExplicitHorizontalRules() {
        val chunks = SlotBatchImporter.split("第一段\n\n---\n\n第二段\n\n---\n第三段")
        assertEquals(listOf("第一段", "第二段", "第三段"), chunks)
    }

    @Test
    fun fallsBackToBlankLineBlocks() {
        val chunks = SlotBatchImporter.split("第一段\n\n第二段\n\n\n第三段")
        assertEquals(listOf("第一段", "第二段", "第三段"), chunks)
    }

    @Test
    fun ignoresEmptyChunks() {
        assertEquals(listOf("只有一段"), SlotBatchImporter.split("\n\n---\n\n只有一段\n\n---\n\n"))
    }

    @Test
    fun chunksKeepExplicitSeparatorsAndAdaptEachBlock() {
        val raw = "---\ntitle: demo\n---\n第一段\n\n---\n# 第二段\n\n**冷静** 的 *语气*"
        val chunks = SlotBatchImporter.chunks(raw, "batch.md")
        assertEquals(2, chunks.size)
        assertEquals("第一段", chunks[0].text)
        assertEquals("第二段\n\n冷静 的 语气", chunks[1].text)
    }

    @Test
    fun onlyEmptyFillsBlanksAndDropsOverflow() {
        val chunks = listOf("a", "b", "c").map { SlotBatchImporter.Chunk(it, "text") }
        val result = SlotBatchImporter.apply(chunks, listOf("S1", "S2"), mapOf("S1" to "old"), onlyEmpty = true)
        assertEquals("old", result.values["S1"])
        assertEquals("b", result.values["S2"])
        assertEquals(1, result.filled)
        assertEquals(1, result.skipped)
        assertEquals(0, result.appended)
        assertEquals(1, result.dropped)
    }

    @Test
    fun overwriteAppendsOverflowToLastSlot() {
        val chunks = listOf("a", "b", "c").map { SlotBatchImporter.Chunk(it, "text") }
        val result = SlotBatchImporter.apply(chunks, listOf("S1", "S2"), mapOf("S1" to "old"), onlyEmpty = false)
        assertEquals("a", result.values["S1"])
        assertEquals("b\n\nc", result.values["S2"])
        assertEquals(2, result.filled)
        assertEquals(0, result.skipped)
        assertEquals(1, result.appended)
        assertEquals(0, result.dropped)
    }

    @Test
    fun fewerChunksLeavesRemainingSlotsUntouched() {
        val chunks = listOf("a").map { SlotBatchImporter.Chunk(it, "text") }
        val result = SlotBatchImporter.apply(chunks, listOf("S1", "S2", "S3"), mapOf("S2" to "keep"), onlyEmpty = false)
        assertEquals("a", result.values["S1"])
        assertEquals("keep", result.values["S2"])
        assertEquals(1, result.filled)
        assertTrue(!result.values.containsKey("S3"))
    }
}
