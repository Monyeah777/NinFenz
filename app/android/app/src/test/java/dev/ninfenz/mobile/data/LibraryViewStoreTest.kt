package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class LibraryViewStoreTest {
    @Test
    fun savesAndLoadsView() {
        val dir = Files.createTempDirectory("nf-library-view").toFile()
        val store = LibraryViewStore(dir)
        store.save("draft", "TITLE")
        assertEquals("draft", store.load()?.status)
        assertEquals("TITLE", store.load()?.sort)
        store.save(null, null)
        assertNull(store.load())
    }

    @Test
    fun corruptIsNull() {
        val dir = Files.createTempDirectory("nf-library-view-2").toFile()
        java.io.File(dir, "library-view.json").writeText("{bad")
        assertNull(LibraryViewStore(dir).load())
    }
}
