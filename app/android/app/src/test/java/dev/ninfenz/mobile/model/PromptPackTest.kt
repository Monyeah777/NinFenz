package dev.ninfenz.mobile.model

import org.junit.Assert.assertTrue
import org.junit.Test

class PromptPackTest {
    @Test
    fun includesSampleStructureAndConstraints() {
        val slices = MarkdownSlicer.slice(MarkdownBlocks.parse("# 标题\n\n正文"))
        val pack = PromptPack.from("source", "# 标题\n\n正文", slices)
        assertTrue(pack.contains("# NF Prompt Pack"))
        assertTrue(pack.contains("## 样本"))
        assertTrue(pack.contains("## 约束"))
        assertTrue(pack.contains("## 验收"))
        assertTrue(pack.contains("标题"))
    }
}
