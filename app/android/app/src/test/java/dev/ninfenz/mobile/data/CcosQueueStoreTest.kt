package dev.ninfenz.mobile.data

import java.nio.file.Files
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CcosQueueStoreTest {
    private fun task(id: String) = buildJsonObject { put("schema", "ccos-task/1"); put("id", id) }

    @Test
    fun addsDeduplicatesAndRemoves() {
        val dir = Files.createTempDirectory("nf-ccos-queue").toFile()
        val store = CcosQueueStore(dir)
        store.add(task("t1"))
        store.add(task("t1"))
        store.add(task("t2"))
        assertEquals(2, store.load().size)
        val id = store.load().first().id
        store.remove(id)
        assertEquals(1, store.load().size)
    }

    @Test
    fun capsAtFifty() {
        val dir = Files.createTempDirectory("nf-ccos-queue-cap").toFile()
        val store = CcosQueueStore(dir)
        repeat(55) { store.add(task("t$it")) }
        assertEquals(50, store.load().size)
    }
}
