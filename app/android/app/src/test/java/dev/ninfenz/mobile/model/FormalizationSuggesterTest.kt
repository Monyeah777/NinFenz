package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class FormalizationSuggesterTest {
    private fun slot(id: String, name: String, required: Boolean = false) =
        SpecSlot(id, name, "s", "text", required)

    @Test
    fun exactNameWins() {
        val result = FormalizationSuggester.suggest(
            "读者是第一次接触这个主题。",
            "开篇",
            listOf(slot("SLT-01", "主题句"), slot("SLT-02", "读者设定", true))
        )
        assertEquals("SLT-02", result?.slotId)
    }

    @Test
    fun headingAddsScore() {
        val result = FormalizationSuggester.suggest(
            "这是一段说明。",
            "主题句",
            listOf(slot("SLT-01", "主题句"))
        )
        assertEquals("SLT-01", result?.slotId)
    }

    @Test
    fun takenSlotSkipped() {
        val slots = listOf(slot("SLT-01", "主题句"), slot("SLT-02", "读者设定"))
        val result = FormalizationSuggester.suggest("读者设定如下", null, slots, setOf("SLT-02"))
        assertNull(result)
    }

    @Test
    fun blankTextNoSuggestion() {
        assertNull(FormalizationSuggester.suggest("   ", "主题句", listOf(slot("SLT-01", "主题句"))))
    }

    @Test
    fun unrelatedTextNoSuggestion() {
        assertNull(FormalizationSuggester.suggest("灯灭之前，别回头。", "开篇", listOf(slot("SLT-01", "主题句"))))
    }
}
