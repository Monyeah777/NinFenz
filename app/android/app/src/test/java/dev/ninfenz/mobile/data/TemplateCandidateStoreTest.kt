package dev.ninfenz.mobile.data

import java.nio.file.Files
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TemplateCandidateStoreTest {
    @Test
    fun savesListsAndDeletesCandidate() {
        val dir = Files.createTempDirectory("nf-template-store").toFile()
        val store = TemplateCandidateStore(dir)
        val spec = buildJsonObject {
            put("id", "tpl-demo")
            put("title", "演示模板")
        }
        val file = store.save(spec)
        assertTrue(file.isFile)
        assertEquals(listOf(file), store.list())
        assertEquals("演示模板", store.titleOf(file))
        assertTrue(store.delete(file))
        assertTrue(store.list().isEmpty())
    }
}
