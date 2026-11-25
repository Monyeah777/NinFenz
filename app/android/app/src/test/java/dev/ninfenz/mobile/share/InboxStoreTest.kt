package dev.ninfenz.mobile.share

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Test

class InboxStoreTest {
    private fun payload(text: String): SharePayload = SharePayload(
        kind = SharePayloadParser.KIND_SEND,
        mime = "text/plain",
        items = listOf(SharedItem(null, text, "text/plain", null)),
        processText = null
    )

    @Test
    fun enqueueDeduplicatesAndPersists() {
        val dir = Files.createTempDirectory("nf-inbox").toFile()
        val store = InboxStore(dir)
        store.enqueue(payload("hello"))
        store.enqueue(payload("hello"))
        store.enqueue(payload("world"))
        val entries = store.load()
        assertEquals(2, entries.size)
        assertEquals("world", entries.first().payload.items.first().text)
    }

    @Test
    fun removeAndClear() {
        val dir = Files.createTempDirectory("nf-inbox-remove").toFile()
        val store = InboxStore(dir)
        store.enqueue(payload("a"))
        val id = store.load().first().id
        store.remove(id)
        assertEquals(0, store.load().size)
        store.enqueue(payload("b"))
        store.clear()
        assertEquals(0, store.load().size)
    }
}
