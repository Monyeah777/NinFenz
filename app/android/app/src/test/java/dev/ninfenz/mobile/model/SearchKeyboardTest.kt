package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Test

class SearchKeyboardTest {
    @Test
    fun movesWithinBounds() {
        assertEquals(2, SearchKeyboard.move(1, 5, 1))
        assertEquals(0, SearchKeyboard.move(1, 5, -1))
        assertEquals(4, SearchKeyboard.move(4, 5, 1))
        assertEquals(0, SearchKeyboard.move(0, 5, -1))
    }

    @Test
    fun emptyResultsStayAtZero() {
        assertEquals(0, SearchKeyboard.move(0, 0, 1))
        assertEquals(0, SearchKeyboard.move(3, 0, -1))
    }
}
