package dev.ninfenz.mobile.ui.screens

import org.junit.Assert.assertEquals
import org.junit.Test

class UndoStackTest {
    @Test
    fun keepsNewestWithinLimit() {
        var stack = emptyList<Int>()
        repeat(250) { stack = UndoStack.push(stack, it) }
        assertEquals(UndoStack.DEFAULT_LIMIT, stack.size)
        assertEquals(249, stack.last())
        assertEquals(150, stack.first())
    }

    @Test
    fun underLimitPreservesOrder() {
        val stack = UndoStack.push(UndoStack.push(emptyList<String>(), "a"), "b")
        assertEquals(listOf("a", "b"), stack)
    }

    @Test
    fun zeroLimitDisablesHistory() {
        assertEquals(emptyList<Int>(), UndoStack.push(listOf(1, 2), 3, limit = 0))
    }
}
