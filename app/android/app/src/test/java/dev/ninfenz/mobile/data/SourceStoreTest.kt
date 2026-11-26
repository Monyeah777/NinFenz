package dev.ninfenz.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class SourceStoreTest {
    @get:Rule
    val tmp = TemporaryFolder()

    @Test
    fun addsDeduplicatesAndCites() {
        val store = SourceStore(tmp.root, "p1")
        val first = store.add("A", "hello", "https://example.com")
        val second = store.add("A2", "hello")
        assertEquals(first.id, second.id)
        assertEquals(1, store.list().size)
        assertEquals("[[src:" + first.id + "]]", store.citation(first.id))
        assertTrue(store.appendix().contains("https://example.com"))
        val rendered = store.renderCitations("正文 [[" + "src:" + first.id + "]]")
        assertTrue(rendered.contains("[^" + first.id + "]"))
        assertTrue(rendered.contains("## 来源"))
        store.remove(first.id)
        assertTrue(store.list().isEmpty())
    }

    @Test
    fun excerptIsCappedAt4096() {
        val store = SourceStore(tmp.root, "p1")
        val source = store.add("Long", "x".repeat(5000))
        assertEquals(4096, source.excerpt.length)
        assertEquals(4096, store.list().first().excerpt.length)
    }
}
