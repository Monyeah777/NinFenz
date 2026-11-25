package dev.ninfenz.mobile.model

import dev.ninfenz.mobile.data.SearchHit
import dev.ninfenz.mobile.data.SearchKind
import org.junit.Assert.assertEquals
import org.junit.Test

class SearchFilterTest {
    private fun hit(kind: SearchKind) = SearchHit(
        kind = kind, title = kind.name, detail = "", projectId = null,
        packId = null, packVersion = null
    )

    @Test
    fun nullKeepsAll() {
        val all = listOf(hit(SearchKind.PROJECT), hit(SearchKind.PACK))
        assertEquals(2, SearchFilter.apply(all, null).size)
    }

    @Test
    fun filtersByPackId() {
        val a = SearchHit(SearchKind.PACK, "a", "", "pack-a", "1.0.0")
        val b = SearchHit(SearchKind.PACK, "b", "", "pack-b", "1.0.0")
        assertEquals(listOf(a), SearchFilter.apply(listOf(a, b), null, "pack-a"))
        assertEquals(0, SearchFilter.apply(listOf(a), SearchKind.PROJECT, "pack-a").size)
    }

    @Test
    fun filtersByProjectId() {
        val a = SearchHit(SearchKind.PROJECT, "a", "", projectId = "p1")
        val b = SearchHit(SearchKind.PROJECT, "b", "", projectId = "p2")
        assertEquals(listOf(a), SearchFilter.apply(listOf(a, b), null, null, "p1"))
        assertEquals(0, SearchFilter.apply(listOf(a), SearchKind.PACK, null, "p1").size)
    }

    @Test
    fun filtersByKind() {
        val all = listOf(hit(SearchKind.PROJECT), hit(SearchKind.PACK), hit(SearchKind.PROJECT))
        assertEquals(2, SearchFilter.apply(all, SearchKind.PROJECT).size)
        assertEquals(1, SearchFilter.apply(all, SearchKind.PACK).size)
    }
}
