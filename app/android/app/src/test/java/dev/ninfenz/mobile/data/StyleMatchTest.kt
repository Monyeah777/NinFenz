package dev.ninfenz.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Test

class StyleMatchTest {
    @Test
    fun identicalStylesScoreFullAndDisjointScoreZero() {
        val a = "<w:style w:styleId=\"Heading1\"/><w:style w:styleId=\"Normal\"/>"
        assertEquals(100, StyleMatch.score(a, a))
        val b = "<w:style w:styleId=\"Quote\"/>"
        assertEquals(0, StyleMatch.score(a, b))
    }

    @Test
    fun partialOverlapUsesJaccard() {
        val a = "<w:style w:styleId=\"A\"/><w:style w:styleId=\"B\"/>"
        val b = "<w:style w:styleId=\"B\"/><w:style w:styleId=\"C\"/>"
        assertEquals(33, StyleMatch.score(a, b))
    }
}
