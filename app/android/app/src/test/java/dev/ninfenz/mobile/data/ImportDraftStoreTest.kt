package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ImportDraftStoreTest {
    @Test
    fun savesLoadsAndClearsRawJson() {
        val dir = Files.createTempDirectory("nf-import-draft").toFile()
        val store = ImportDraftStore(dir)
        assertNull(store.load())
        store.save("{\"schema\":\"nf-import/1\"}")
        assertEquals("{\"schema\":\"nf-import/1\"}", store.load())
        store.clear()
        assertNull(store.load())
    }

    @Test
    fun blankIsIgnoredAndCorruptFileDoesNotThrow() {
        val dir = Files.createTempDirectory("nf-import-draft-2").toFile()
        val store = ImportDraftStore(dir)
        store.save("   ")
        assertNull(store.load())
        val f = java.io.File(dir, "drafts/import-last.json")
        f.parentFile?.mkdirs()
        f.writeText("not-json", Charsets.UTF_8)
        assertEquals("not-json", store.load())
    }
}
