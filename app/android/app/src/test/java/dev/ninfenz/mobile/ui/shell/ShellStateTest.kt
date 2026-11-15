package dev.ninfenz.mobile.ui.shell

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Test

class ShellStateTest {

    @Test
    fun startsAtLibraryRoot() {
        val state = ShellState()
        assertEquals(TopDestination.LIBRARY, state.destination)
        assertNull(state.detail)
    }

    @Test
    fun selectDestinationClearsDetail() {
        val state = ShellState(detail = Detail.Import).select(TopDestination.CREATE)
        assertEquals(TopDestination.CREATE, state.destination)
        assertNull(state.detail)
    }

    @Test
    fun openAndBackReturnsToRoot() {
        val opened = ShellState().open(Detail.Settings)
        assertSame(Detail.Settings, opened.detail)
        val back = opened.back()
        assertEquals(TopDestination.LIBRARY, back?.destination)
        assertNull(back?.detail)
    }

    @Test
    fun allKnownDetailsCanOpenAndBack() {
        val details = listOf(
            Detail.Import, Detail.Search, Detail.NewProject, Detail.Settings,
            Detail.Protocol, Detail.Graph, Detail.Assembly, Detail.PackCenter,
            Detail.PackUpdate, Detail.Ccos, Detail.Project("p"), Detail.Pack("p", "1.0.0"),
            Detail.Author("p"), Detail.Delivery("p")
        )
        for (detail in details) {
            val opened = ShellState().open(detail)
            assertEquals(detail, opened.detail)
            assertEquals(TopDestination.LIBRARY, opened.back()?.destination)
        }
    }

    @Test
    fun backAtRootIsNull() {
        assertNull(ShellState().back())
        assertNull(ShellState(destination = TopDestination.ME).back())
    }
}
