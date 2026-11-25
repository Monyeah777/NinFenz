package dev.ninfenz.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SearchRankingTest {
    private fun hit(kind: SearchKind, title: String, detail: String = "", body: String = "") = SearchHit(kind, title, detail, body = body)

    @Test
    fun cjkTermsMatchAndRankTitleFirst() {
        val index = SearchIndex(java.io.File("."))
        val hits = listOf(
            hit(SearchKind.PROJECT, "开篇钩子", "项目正文里有暴雨"),
            hit(SearchKind.CLAUSE, "节奏要求", "开篇 开篇钩子"),
            hit(SearchKind.FIELD, "主角名", "主角")
        )
        val out = index.search(hits, "开篇")
        assertTrue(out.isNotEmpty())
        assertEquals("开篇钩子", out.first().title)
    }

    @Test
    fun fullWidthAndCaseAreNormalized() {
        val index = SearchIndex(java.io.File("."))
        val hits = listOf(hit(SearchKind.PACK, "Demo Pack", "DEMO"))
        assertTrue(index.search(hits, "ｄｅｍｏ").isNotEmpty())
    }

    @Test
    fun fuzzyOneEditMatchesLongWord() {
        val index = SearchIndex(java.io.File("."))
        val hits = listOf(hit(SearchKind.PROJECT, "Lantern", "border town"))
        assertTrue(index.search(hits, "lantren").isNotEmpty())
    }

    @Test
    fun blankAndUnrelatedReturnEmpty() {
        val index = SearchIndex(java.io.File("."))
        val hits = listOf(hit(SearchKind.PROJECT, "Alpha"))
        assertTrue(index.search(hits, "   ").isEmpty())
        assertTrue(index.search(hits, "zzzzzz").isEmpty())
    }

    @Test
    fun allTermsRequired() {
        val index = SearchIndex(java.io.File("."))
        val hits = listOf(hit(SearchKind.PROJECT, "Alpha Beta"), hit(SearchKind.PROJECT, "Alpha Gamma"))
        val out = index.search(hits, "alpha beta")
        assertEquals(1, out.size)
        assertEquals("Alpha Beta", out[0].title)
    }
}
