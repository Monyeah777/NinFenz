package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import java.util.zip.ZipFile
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PackDraftStoreTest {
    private fun pack(dir: File): PackEntry {
        dir.mkdirs()
        File(dir, "nf-pack.json").writeText("{\"schema\":\"nf-pack/1\",\"id\":\"src\",\"version\":\"1.0.0\",\"title\":\"Source\"}", Charsets.UTF_8)
        File(dir, "protocol").mkdirs()
        File(dir, "protocol/nf-protocol-pack.json").writeText("{}", Charsets.UTF_8)
        return PackEntry("src", "1.0.0", "Source", "tree", 1, "tree", dir, 0L)
    }

    @Test
    fun cloneEditAndPackage() {
        val root = Files.createTempDirectory("nf-pack-draft").toFile()
        val source = pack(File(root, "source"))
        val store = PackDraftStore(root)
        val draft = store.createFrom(source, "src-draft", "1.0.1", "Draft")
        assertTrue(draft.dir.isDirectory)
        store.updateMeta(draft, "src-draft", "1.0.1", "Draft 2")
        val loaded = store.load("src-draft")
        assertEquals("Draft 2", loaded?.title)
        store.saveGolden(draft, "# golden")
        assertEquals("# golden", store.loadGolden(draft))
        val zip = store.packageToZip(draft, File(root, "out"))
        ZipFile(zip).use { z ->
            val names = z.entries().asSequence().map { it.name }.toList()
            assertTrue(names.contains("nf-pack.json"))
            assertTrue(names.contains("protocol/nf-protocol-pack.json"))
            assertTrue(names.none { it == ".golden.md" })
        }
    }
}
