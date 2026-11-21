package dev.ninfenz.mobile.ui

import java.nio.file.Files
import java.util.zip.ZipFile
import org.junit.Assert.assertTrue
import org.junit.Test

class BatchAssemblerTest {
    @Test
    fun writesMergedForMultipleSuccesses() {
        val out = Files.createTempDirectory("nf-batch-out").toFile()
        val items = listOf(
            BatchAssembler.Item("p1", "P1", true, "# P1", null),
            BatchAssembler.Item("p2", "P2", true, "# P2", null),
            BatchAssembler.Item("p3", "P3", false, null, "缺草稿")
        )
        val file = BatchAssembler.writeZip(items, out)
        ZipFile(file).use { zip ->
            assertTrue(zip.getEntry("merged.md") != null)
            assertTrue(zip.getEntry("projects/p1.md") != null)
            assertTrue(zip.getEntry("projects/p2.md") != null)
            assertTrue(zip.getEntry("projects/p3.md") == null)
            val manifest = zip.getInputStream(zip.getEntry("nf-batch.json")).readBytes().toString(Charsets.UTF_8)
            assertTrue(manifest.contains("\"merged\":\"merged.md\""))
            assertTrue(manifest.contains("缺草稿"))
        }
    }

    @Test
    fun omitsMergedForSingleSuccess() {
        val out = Files.createTempDirectory("nf-batch-one").toFile()
        val file = BatchAssembler.writeZip(listOf(BatchAssembler.Item("p1", "P1", true, "# P1", null)), out)
        ZipFile(file).use { zip ->
            assertTrue(zip.getEntry("merged.md") == null)
        }
    }
}
