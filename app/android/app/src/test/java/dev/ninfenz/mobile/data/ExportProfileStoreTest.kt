package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ExportProfileStoreTest {
    @Test
    fun savesAppliesAndRemoves() {
        val dir = Files.createTempDirectory("nf-export-profile").toFile()
        val store = ExportProfileStore(dir)
        store.save(ExportProfileStore.ProfileInput("brand", "<styles/>", "<sectPr/>", "<theme/>", null, null, null, "作者", "en", "Letter", false))
        val profiles = store.load()
        assertEquals(1, profiles.size)
        assertEquals("brand", profiles.first().name)
        assertEquals("<styles/>", profiles.first().styles)
        assertEquals("作者", profiles.first().epubAuthor)
        assertEquals("Letter", profiles.first().pdfPageSize)
        assertEquals(false, profiles.first().pdfIncludeTitle)
        store.remove(profiles.first().id)
        assertTrue(store.load().isEmpty())
    }
}
