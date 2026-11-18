package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Test

class SlotInputTest {
    @Test
    fun filtersNumberAndDecimal() {
        assertEquals("12", SlotInput.sanitize("number", "1a2"))
        assertEquals("1.5", SlotInput.sanitize("decimal", "1.5x"))
        assertEquals("文本", SlotInput.sanitize("text", "文本"))
    }
}
