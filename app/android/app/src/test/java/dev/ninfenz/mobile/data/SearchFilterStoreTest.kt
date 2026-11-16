package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class SearchFilterStoreTest {
    @Test
    fun savesAndClearsFilter() {
        val dir = Files.createTempDirectory("nf-search-filter").toFile()
        val store = SearchFilterStore(dir)
        store.save("PROJECT", "pack-a")
        assertEquals("PROJECT", store.load()?.kind)
        assertEquals("pack-a", store.load()?.packId)
        store.save(null, null)
        assertNull(store.load())
    }

    @Test
    fun corruptIsNull() {
        val dir = Files.createTempDirectory("nf-search-filter-2").toFile()
        java.io.File(dir, "search-filter.json").writeText("{bad")
        assertNull(SearchFilterStore(dir).load())
    }
}
