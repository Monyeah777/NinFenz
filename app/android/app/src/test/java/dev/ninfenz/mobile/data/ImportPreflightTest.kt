package dev.ninfenz.mobile.data

import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.Assert.assertTrue
import org.junit.Test

class ImportPreflightTest {
    private fun zip(name: String, count: Int = 1, content: ByteArray = "x".toByteArray()): File {
        val file = File.createTempFile("nf-preflight", ".zip")
        ZipOutputStream(FileOutputStream(file)).use { out ->
            repeat(count) { i ->
                out.putNextEntry(ZipEntry(if (count == 1) name else name + i))
                out.write(content)
                out.closeEntry()
            }
        }
        return file
    }

    @Test
    fun acceptsSmallZip() {
        ImportPreflight.check(zip("a.txt"))
    }

    @Test
    fun rejectsTooManyEntries() {
        val file = zip("e", ImportPreflight.MAX_ENTRIES + 1)
        assertTrue(runCatching { ImportPreflight.check(file) }.isFailure)
    }

    @Test
    fun rejectsHighCompressionRatio() {
        val file = zip("zeros.bin", content = ByteArray(20 * 1024 * 1024))
        assertTrue(runCatching { ImportPreflight.check(file) }.isFailure)
    }
}
