package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class PackRegistrySqliteTest {
    @Test
    fun recordsAndLoadsSqliteRegistry() {
        val root = Files.createTempDirectory("nf-pack-registry").toFile()
        val target = File(root, "library/packs/demo/1.0.0").apply { mkdirs() }
        PackRegistry.record(target, "sqlite")
        assertTrue(File(root, "library/pack-registry.db").isFile)
        val loaded = PackRegistry.load(root)
        assertEquals("sqlite", loaded["demo@1.0.0"]?.source)
    }
}
