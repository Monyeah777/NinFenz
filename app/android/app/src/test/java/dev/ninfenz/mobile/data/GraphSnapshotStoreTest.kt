package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.PipelineGraph
import kotlinx.serialization.json.buildJsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class GraphSnapshotStoreTest {
    @get:Rule
    val tmp = TemporaryFolder()

    @Test
    fun savesListsAndRemovesSnapshots() {
        val store = GraphSnapshotStore(tmp.root, "p1")
        val graph = PipelineGraph(
            id = "g1",
            version = "0.1.0",
            title = "Graph",
            mode = "simple",
            nodes = emptyList(),
            edges = emptyList(),
            weights = emptyMap(),
            requiredStages = emptyList(),
            seed = null,
            params = buildJsonObject {}
        )
        val saved = store.save(graph)
        assertEquals(1, saved.size)
        assertEquals(0, saved.first().nodes)
        val id = saved.first().id
        assertTrue(store.list().any { it.id == id })
        store.remove(id)
        assertTrue(store.list().isEmpty())
    }
}
