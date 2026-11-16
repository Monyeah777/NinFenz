package dev.ninfenz.mobile.ui.shell

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ShellStateCodecTest {
    @Test
    fun roundTripsAllDetailTypes() {
        val details = listOf(
            Detail.Import, Detail.Search, Detail.NewProject, Detail.Settings,
            Detail.Protocol, Detail.Graph, Detail.Assembly, Detail.PackUpdate, Detail.ErrorCodes,
            Detail.PackCenter, Detail.Ccos, Detail.Project("p"), Detail.Author("p"),
            Detail.Delivery("p"), Detail.Pack("demo", "1.0.0")
        )
        for (detail in details) {
            val state = ShellState(TopDestination.DELIVER, detail)
            assertEquals(state, ShellStateCodec.decode(ShellStateCodec.encode(state)))
        }
    }

    @Test
    fun malformedOrMissingDetailFallsBackGracefully() {
        assertEquals(ShellState(), ShellStateCodec.decode(emptyList()))
        assertEquals(ShellState(), ShellStateCodec.decode(listOf("NOPE", "Project")))
        assertEquals(ShellState(TopDestination.LIBRARY, null), ShellStateCodec.decode(listOf("LIBRARY", "Pack", "id-only")))
        assertNull(ShellStateCodec.decode(listOf("LIBRARY", "Wat")).detail)
    }
}
