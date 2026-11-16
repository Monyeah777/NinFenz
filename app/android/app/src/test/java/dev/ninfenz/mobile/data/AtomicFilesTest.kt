package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AtomicFilesTest {
    @Test
    fun replaceKeepsPreviousContentAsBackup() {
        val dir = Files.createTempDirectory("nf-atomic").toFile()
        val target = dir.resolve("project.nfproject.json")

        AtomicFiles.writeText(target, "first")
        assertEquals("first", target.readText())

        AtomicFiles.writeText(target, "second")
        assertEquals("second", target.readText())
        assertEquals("first", dir.resolve("project.nfproject.json.bak").readText())
        assertFalse(dir.listFiles()!!.any { it.name.endsWith(".tmp") })
    }

    @Test
    fun writeBytesCreatesParentAndSurvivesInvalidUnicodeLikePayload() {
        val dir = Files.createTempDirectory("nf-atomic-2").toFile()
        val target = dir.resolve("nested/dir/data.bin")
        AtomicFiles.writeBytes(target, byteArrayOf(0, 1, 2, 3))
        assertTrue(target.isFile)
        assertEquals(listOf<Byte>(0, 1, 2, 3), target.readBytes().toList())
    }
}
