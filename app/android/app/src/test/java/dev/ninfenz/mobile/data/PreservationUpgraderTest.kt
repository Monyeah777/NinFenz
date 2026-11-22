package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PreservationUpgraderTest {
    @Test
    fun upgradesLegacyArchiveAndLinksLineage() {
        val dir = Files.createTempDirectory("upgrade").toFile()
        val old = File(dir, "old.preserve.zip")
        ZipOutputStream(old.outputStream()).use { out ->
            out.putNextEntry(ZipEntry("document.md").apply { time = 0L })
            out.write("# 标题\n\n正文".toByteArray())
            out.closeEntry()
        }
        val result = PreservationUpgrader.upgrade(old, File(dir, "out").apply { mkdirs() })
        assertTrue(result.file.isFile)
        val verified = PreservationVerifier.verify(result.file)
        assertTrue(verified.errors.toString(), verified.ok)
        assertEquals(result.predecessor, PreservationVerifier.predecessor(result.file))
    }
}
