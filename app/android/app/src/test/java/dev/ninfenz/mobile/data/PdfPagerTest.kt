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
    fun repeatsTableHeaderOnContinuationPage() {
        val items = listOf("H", "r1", "r2", "r3")
        val pages = PdfPager.repeatTableHeaders(
            items,
            listOf(0..1, 2..3),
            isTable = { it.startsWith("r") },
            isHeader = { it == "H" }
        )
        assertEquals(listOf(listOf("H", "r1"), listOf("H", "r2", "r3")), pages)
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
