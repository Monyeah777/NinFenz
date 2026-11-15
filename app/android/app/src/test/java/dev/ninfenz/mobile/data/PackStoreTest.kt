package dev.ninfenz.mobile.data

import java.nio.file.Files
import java.nio.file.Path
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PackStoreTest {

    private fun tempRoot(): Path = Files.createTempDirectory("nf-pack-store-test")

    private fun writePack(root: Path, id: String, version: String, manifest: String) {
        val dir = root.resolve("library/packs").resolve(id).resolve(version)
        Files.createDirectories(dir)
        dir.resolve("nf-pack.json").toFile().writeText(manifest, Charsets.UTF_8)
    }

    @Test
    fun scansValidPack() {
        val root = tempRoot()
        writePack(
            root, "demo-pack", "1.0.0",
            "{\"id\":\"demo-pack\",\"version\":\"1.0.0\",\"title\":\"示例\",\"description\":\"d\",\"items\":[{},{}],\"hashes\":{\"tree\":\"abc\"}}"
        )
        val snapshot = PackStore(root.toFile()).scan()
        assertEquals(1, snapshot.packs.size)
        assertEquals("demo-pack", snapshot.packs[0].id)
        assertEquals(2, snapshot.packs[0].itemCount)
        assertEquals("abc", snapshot.packs[0].tree)
        assertTrue(snapshot.errors.isEmpty())
    }

    @Test
    fun malformedManifestIsReportedNotSkipped() {
        val root = tempRoot()
        writePack(root, "bad", "1.0.0", "{not-json")
        val snapshot = PackStore(root.toFile()).scan()
        assertTrue(snapshot.packs.isEmpty())
        assertEquals(1, snapshot.errors.size)
    }

    @Test
    fun missingPacksDirIsEmpty() {
        val snapshot = PackStore(tempRoot().toFile()).scan()
        assertTrue(snapshot.packs.isEmpty())
        assertTrue(snapshot.errors.isEmpty())
    }
}
