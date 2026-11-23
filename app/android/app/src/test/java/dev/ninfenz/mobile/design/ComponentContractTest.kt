package dev.ninfenz.mobile.design

import dev.ninfenz.mobile.ui.design.ComponentContracts
import dev.ninfenz.mobile.ui.design.StateContracts
import dev.ninfenz.mobile.ui.design.UiState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ComponentContractTest {
    @Test
    fun allSevenStatesHaveContracts() {
        assertEquals(7, StateContracts.all.size)
        UiState.entries.forEach { assertNotNull(StateContracts.forState(it)) }
        assertNull(StateContracts.forState(UiState.LOADING).action)
        assertNotNull(StateContracts.forState(UiState.ERROR).action)
        assertTrue(StateContracts.forState(UiState.SIGNED).needsEvidence)
        assertTrue(StateContracts.forState(UiState.PARTIAL).needsEvidence)
    }

    @Test
    fun componentSizesStayOnGridAndTouchSafe() {
        assertTrue(ComponentContracts.onGrid())
        assertTrue(ComponentContracts.touchSafe())
        assertTrue(ComponentContracts.all.all { it.minTouch >= 48 })
        assertEquals(40, ComponentContracts.all.first { it.name == "primaryButton" }.height)
    }
}
