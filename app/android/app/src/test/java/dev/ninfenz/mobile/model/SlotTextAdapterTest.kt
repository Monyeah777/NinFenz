package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SlotTextAdapterTest {
    @Test
    fun markdownIsAdaptedToPlainText() {
        val raw = """
            ---
            title: demo
            ---
            # 开篇

            **冷静** 的 *语气*，参见 [文档](https://example.com)。

            - 要点一
            - 要点二
        """.trimIndent()
        val out = SlotTextAdapter.adapt(raw, "sample.md")
        assertEquals("markdown", out.format)
        assertTrue(out.changed)
        assertEquals("开篇\n\n冷静 的 语气，参见 文档。\n\n• 要点一\n• 要点二", out.adapted)
    }

    @Test
    fun plainTextOnlyNormalizesLineEndingsAndBom() {
        val out = SlotTextAdapter.adapt("\uFEFF第一行\r\n第二行\r第三行", "notes.txt")
        assertEquals("text", out.format)
        assertEquals("第一行\n第二行\n第三行", out.adapted)
    }
}
