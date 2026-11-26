package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FidelityReconcilerTest {
    @Test
    fun matchesSectionHeadings() {
        val result = FidelityReconciler.reconcile(
            listOf("开场", "推进"),
            "# 开场\n\n正文\n\n## 推进\n\n正文"
        )
        assertEquals(100, result.score)
        assertEquals(2, result.matched)
        assertTrue(result.missing.isEmpty())
    }

    @Test
    fun reportsMissingAndExtraHeadings() {
        val result = FidelityReconciler.reconcile(
            listOf("开场", "推进"),
            "# 开场\n\n## 多出"
        )
        assertEquals(50, result.score)
        assertEquals(listOf("推进"), result.missing)
        assertEquals(listOf("多出"), result.extra)
    }
}
