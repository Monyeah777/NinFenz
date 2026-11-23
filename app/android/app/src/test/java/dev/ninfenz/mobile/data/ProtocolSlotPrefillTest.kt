package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.ProtocolField
import dev.ninfenz.mobile.model.SpecSlot
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ProtocolSlotPrefillTest {
    private fun field(id: String, label: String) = ProtocolField(
        id = id, clause = "", label = label, type = "text", required = false,
        defaultText = null, options = emptyList(), maxLen = null, pattern = null
    )

    private fun slot(id: String, name: String) = SpecSlot(
        id = id, name = name, section = "S", kind = "text", required = true
    )

    @Test
    fun bindsByNormalizedNameOnly() {
        val fields = listOf(field("F1", "主题句"), field("F2", "读者 设定"), field("F3", "无关"))
        val slots = listOf(slot("SLT-01", "主题句"), slot("SLT-02", "读者设定"))
        val out = ProtocolSlotPrefill.bind(fields, slots, mapOf("F1" to "甲", "F2" to "乙", "F3" to "丙"))
        assertEquals("甲", out["SLT-01"])
        assertEquals("乙", out["SLT-02"])
        assertTrue("F3" !in out.values)
    }

    @Test
    fun emptyValuesDoNotBind() {
        val out = ProtocolSlotPrefill.bind(
            listOf(field("F1", "主题句")),
            listOf(slot("SLT-01", "主题句")),
            mapOf("F1" to "  ")
        )
        assertTrue(out.isEmpty())
    }
}
