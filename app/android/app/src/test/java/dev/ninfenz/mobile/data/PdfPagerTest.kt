package dev.ninfenz.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PdfPagerTest {
    @Test
    fun wrapsLongLineByMeasure() {
        val wrapped = PdfPager.wrap("abcdef", 3f) { it.length.toFloat() }
        assertTrue(wrapped.size > 1)
        assertTrue(wrapped.joinToString("") == "abcdef")
    }

    @Test
    fun paginatesByWeightForImages() {
        val ranges = PdfPager.paginateWeighted(listOf(1, 8, 1), 8)
        assertEquals(listOf(0..0, 1..1, 2..2), ranges)
    }

    @Test
    fun paginatesAndKeepsEmptyPage() {
        assertEquals(listOf(listOf("a", "b"), listOf("c")), PdfPager.paginate(listOf("a", "b", "c"), 2))
        assertEquals(listOf(listOf("")), PdfPager.paginate(emptyList(), 10))
    }
}
