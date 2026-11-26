package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ImportBatchTest {
    @Test
    fun queueTracksSuccessFailureAndProcessed() {
        var state = ImportBatchState.start(listOf("u1" to "a.md", "u2" to "b.md", "u3" to "c.md"))
        assertEquals(0, state.processed)
        state = state.markRunning(0).markSuccess(0)
        state = state.markRunning(1).markFailure(1, "bad file")
        assertEquals(2, state.processed)
        assertEquals(1, state.success)
        assertEquals(1, state.failed)
        assertEquals(listOf(1), state.failedIndices())
        assertEquals("bad file", state.items[1].error)
    }

    @Test
    fun cancelMarksPendingOnly() {
        var state = ImportBatchState.start(listOf("u1" to "a", "u2" to "b", "u3" to "c"))
        state = state.markRunning(0).markSuccess(0)
        state = state.cancel()
        assertTrue(state.cancelled)
        assertEquals(ImportBatchStatus.SUCCESS, state.items[0].status)
        assertEquals(ImportBatchStatus.CANCELLED, state.items[1].status)
        assertEquals(ImportBatchStatus.CANCELLED, state.items[2].status)
        assertFalse(state.running)
    }

    @Test
    fun retryCanReturnFailedIndices() {
        var state = ImportBatchState.start(listOf("u1" to "a", "u2" to "b"))
        state = state.markRunning(0).markFailure(0, "x")
        state = state.markRunning(1).markFailure(1, "y")
        assertEquals(listOf(0, 1), state.failedIndices())
        state = state.markRunning(0).markSuccess(0)
        assertEquals(listOf(1), state.failedIndices())
    }
}
