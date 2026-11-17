package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class PackRegistrySqliteTest {
    @Test
    fun migratesLegacyJsonOnFirstRecord() {
        val root = Files.createTempDirectory("nf-pack-registry-migrate").toFile()
        val json = File(root, "library/pack-registry.json").apply { parentFile?.mkdirs() }
        json.writeText(
            "{\"schema\":\"nf-pack-registry/1\",\"packs\":{\"old@1.0.0\":{\"installed_at\":123,\"source\":\"legacy\"}}}",
            Charsets.UTF_8
        )
        val target = File(root, "library/packs/new/2.0.0").apply { mkdirs() }
        PackRegistry.record(target, "sqlite")
        val loaded = PackRegistry.load(root)
        assertEquals("legacy", loaded["old@1.0.0"]?.source)
        assertEquals(123L, loaded["old@1.0.0"]?.installedAt)
        assertEquals("sqlite", loaded["new@2.0.0"]?.source)
    }

    @Test
    fun scanMigratesLegacyJsonToSqlite() {
        val root = Files.createTempDirectory("nf-pack-registry-scan").toFile()
        val json = File(root, "library/pack-registry.json").apply { parentFile?.mkdirs() }
        json.writeText(
            "{\"schema\":\"nf-pack-registry/1\",\"packs\":{\"old@1.0.0\":{\"installed_at\":123,\"source\":\"legacy\"}}}",
            Charsets.UTF_8
        )
        PackStore(root).scan()
        assertTrue(File(root, "library/pack-registry.db").isFile)
        assertEquals("legacy", PackRegistry.load(root)["old@1.0.0"]?.source)
    }

    @Test
    fun removeDropsSqliteAndJsonEntry() {
        val root = Files.createTempDirectory("nf-pack-registry-remove").toFile()
        val target = File(root, "library/packs/demo/1.0.0").apply { mkdirs() }
        PackRegistry.record(target, "sqlite")
        PackRegistry.remove(root, "demo", "1.0.0")
        assertFalse(PackRegistry.load(root).containsKey("demo@1.0.0"))
    }

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
