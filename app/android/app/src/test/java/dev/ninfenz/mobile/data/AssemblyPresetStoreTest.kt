package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AssemblyPresetStoreTest {
    @Test
    fun savesAppliesAndRemoves() {
        val dir = Files.createTempDirectory("nf-preset").toFile()
        val store = AssemblyPresetStore(dir)
        store.save("p1", "客户 A", mapOf("s1" to "a", "s2" to "", "s3" to "c"))
        val presets = store.load("p1")
        assertEquals(1, presets.size)
        assertEquals("客户 A", presets.first().name)
        assertEquals(mapOf("s1" to "a", "s3" to "c"), presets.first().inputs)
        store.remove("p1", presets.first().id)
        assertTrue(store.load("p1").isEmpty())
    }

    @Test
    fun capsAtTwenty() {
        val dir = Files.createTempDirectory("nf-preset-cap").toFile()
        val store = AssemblyPresetStore(dir)
        repeat(25) { store.save("p1", "p$it", mapOf("s" to "v$it")) }
        assertEquals(20, store.load("p1").size)
    }
}
