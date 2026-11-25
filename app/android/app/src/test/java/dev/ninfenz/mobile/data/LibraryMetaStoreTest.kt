package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LibraryMetaStoreTest {
    @Test
    fun togglesFavorite() {
        val dir = Files.createTempDirectory("nf-lib-meta").toFile()
        val store = LibraryMetaStore(dir)
        assertTrue(store.toggle("p1"))
        assertTrue(store.isFavorite("p1"))
        assertFalse(store.toggle("p1"))
        assertFalse(store.isFavorite("p1"))
        assertEquals(emptySet<String>(), store.favorites())
    }

    @Test
    fun addsTagsAndKeepsFavorites() {
        val dir = Files.createTempDirectory("nf-lib-tags").toFile()
        val store = LibraryMetaStore(dir)
        store.toggle("p1")
        store.addTag("p1", "客户")
        store.addTag("p1", "重点")
        assertEquals(setOf("客户", "重点"), store.tags("p1"))
        assertEquals(setOf("客户", "重点"), store.allTags())
        assertTrue(store.isFavorite("p1"))
        store.removeTag("p1", "客户")
        assertEquals(setOf("重点"), store.tags("p1"))
    }
}
