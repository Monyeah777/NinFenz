package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Test

class SpecModelSlotBudgetTest {
    @Test
    fun readsSlotBudgetAndMinChars() {
        val spec = SpecModel.parse("""
        {
          "schema": "nf-md-spec/1",
          "id": "demo",
          "title": "Demo",
          "version": "1.0.0",
          "heading_level": 1,
          "sections": [{"id":"SEC-01","title":"S","order":1,"required":true,"slots":["SLT-01"]}],
          "slots": [{
            "id":"SLT-01","name":"A","section":"SEC-01","kind":"text","required":true,
            "constraints":[{"op":"min_chars","value":3}],
            "examples":["示例正文"],"budget":{"max_chars":10}
          }]
        }
        """.trimIndent())
        assertEquals(3, spec.slots.first().minChars)
        assertEquals(10, spec.slots.first().maxChars)
        assertEquals(listOf("示例正文"), spec.slots.first().examples)
    }
}
