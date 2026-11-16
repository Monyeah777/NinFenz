package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.share.SharedItem
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ShareQueueStoreTest {
    @Test
    fun savesAndLoadsQueue() {
        val dir = Files.createTempDirectory("nf-share-queue").toFile()
        val store = ShareQueueStore(dir)
        val items = listOf(
            SharedItem("content://a", null, "text/plain", "a.txt"),
            SharedItem(null, "hello", null, null)
        )
        store.save(items, 1)
        val saved = store.load()!!
        assertEquals(2, saved.items.size)
        assertEquals(1, saved.cursor)
        assertEquals("content://a", saved.items[0].uri)
        assertEquals("hello", saved.items[1].text)
        store.clear()
        assertNull(store.load())
    }

    @Test
    fun emptyOrCorruptIsNull() {
        val dir = Files.createTempDirectory("nf-share-queue-2").toFile()
        val store = ShareQueueStore(dir)
        store.save(emptyList(), 0)
        assertNull(store.load())
        java.io.File(dir, "share-queue.json").writeText("{bad")
        assertNull(store.load())
    }
}
