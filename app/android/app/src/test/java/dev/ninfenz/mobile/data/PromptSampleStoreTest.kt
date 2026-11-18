package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PromptSampleStoreTest {
    @Test
    fun savesAndListsSamples() {
        val dir = Files.createTempDirectory("nf-samples").toFile()
        val store = PromptSampleStore(dir)
        val file = store.save("demo/project", "# 标题")
        assertTrue(file.isFile)
        assertEquals("# 标题", file.readText())
        assertEquals(listOf(file), store.list())
        assertTrue(store.delete(file))
        assertTrue(store.list().isEmpty())
    }
}
