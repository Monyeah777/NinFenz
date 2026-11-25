package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ReviewStoreTest {
    private fun store(): ReviewStore {
        val dir = Files.createTempDirectory("nf-review").toFile()
        return ReviewStore(dir)
    }

    @Test
    fun addResolveAndVerdictPersist() {
        val store = store()
        val digest = ReviewStore.sha256("subject")
        var doc = store.load("p1", digest)
        doc = store.add(doc, "0", "block text", "请补主题句", "reviewer")
        assertEquals(1, doc.comments.size)
        assertEquals("unresolved", doc.comments.first().status)
        val id = doc.comments.first().id
        doc = store.setStatus(doc, id, "resolved")
        assertEquals("resolved", doc.comments.first().status)
        doc = store.verdict(doc, "reject", "reviewer", "需要修改")
        val loaded = store.load("p1", digest)
        assertEquals("reject", loaded.verdict)
        assertEquals("resolved", loaded.comments.first().status)
        assertTrue(loaded.comments.first().blockDigest.matches(Regex("^[0-9a-f]{64}$")))
    }

    @Test
    fun clearRemovesSidecar() {
        val store = store()
        var doc = store.load("p2", ReviewStore.sha256("x"))
        doc = store.add(doc, "1", "x", "note", "r")
        store.clear("p2")
        assertEquals(0, store.load("p2", ReviewStore.sha256("x")).comments.size)
    }
}
