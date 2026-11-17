package dev.ninfenz.mobile.data

import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PackZipLoaderTest {

    private fun zip(vararg entries: Pair<String, String>): File {
        val file = File.createTempFile("nf-pack", ".zip")
        ZipOutputStream(FileOutputStream(file)).use { out ->
            for ((name, content) in entries) {
                out.putNextEntry(ZipEntry(name))
                out.write(content.toByteArray())
                out.closeEntry()
            }
        }
        return file
    }

    @Test
    fun extractsRootManifest() {
        val zip = zip("nf-pack.json" to "{\"id\":\"p\"}", "protocol/a.json" to "{}")
        val dest = File.createTempFile("nf-pack-out", "").let { it.delete(); it }
        val root = PackZipLoader.extract(zip, dest)
        assertEquals(dest.canonicalPath, root.canonicalPath)
        assertTrue(File(root, "protocol/a.json").isFile)
    }

    @Test
    fun extractsSingleTopLevelDirectory() {
        val zip = zip("pack/nf-pack.json" to "{\"id\":\"p\"}", "pack/spec/a.json" to "{}")
        val dest = File.createTempFile("nf-pack-out2", "").let { it.delete(); it }
        val root = PackZipLoader.extract(zip, dest)
        assertTrue(root.canonicalPath.endsWith("pack"))
        assertTrue(File(root, "spec/a.json").isFile)
    }

    @Test
    fun rejectsZipSlip() {
        val zip = zip("../evil.txt" to "x")
        val dest = File.createTempFile("nf-pack-out3", "").let { it.delete(); it }
        val failed = runCatching { PackZipLoader.extract(zip, dest) }.isFailure
        assertTrue(failed)
    }

    @Test
    fun rejectsControlCharacterEntryName() {
        val zip = zip("nf-\u0001.json" to "{}")
        val dest = File.createTempFile("nf-pack-out6", "").let { it.delete(); it }
        assertTrue(runCatching { PackZipLoader.extract(zip, dest) }.isFailure)
    }

    @Test
    fun rejectsCompressionBomb() {
        val file = File.createTempFile("nf-pack-bomb", ".zip")
        ZipOutputStream(FileOutputStream(file)).use { out ->
            out.putNextEntry(ZipEntry("nf-pack.json")); out.write("{}".toByteArray()); out.closeEntry()
            out.putNextEntry(ZipEntry("zeros.bin"))
            val chunk = ByteArray(1024 * 1024)
            repeat(20) { out.write(chunk) }
            out.closeEntry()
        }
        val dest = File.createTempFile("nf-pack-out7", "").let { it.delete(); it }
        assertTrue(runCatching { PackZipLoader.extract(file, dest) }.isFailure)
    }

    @Test
    fun rejectsEncryptedZipFromCentralDirectory() {
        fun put16(a: ByteArray, off: Int, v: Int) {
            a[off] = (v and 0xFF).toByte(); a[off + 1] = ((v shr 8) and 0xFF).toByte()
        }
        fun put32(a: ByteArray, off: Int, v: Long) {
            put16(a, off, (v and 0xFFFF).toInt()); put16(a, off + 2, ((v shr 16) and 0xFFFF).toInt())
        }
        val name = "a".toByteArray()
        val central = ByteArray(46)
        put32(central, 0, 0x02014b50L)
        put16(central, 8, 1) // encrypted flag
        put16(central, 28, name.size)
        val eocd = ByteArray(22)
        put32(eocd, 0, 0x06054b50L)
        put16(eocd, 8, 1); put16(eocd, 10, 1)
        put32(eocd, 12, (central.size + name.size).toLong())
        put32(eocd, 16, 0)
        val file = File.createTempFile("nf-pack-enc", ".zip")
        file.writeBytes(central + name + eocd)
        val dest = File.createTempFile("nf-pack-out8", "").let { it.delete(); it }
        assertTrue(runCatching { PackZipLoader.extract(file, dest) }.isFailure)
    }

    @Test
    fun rejectsWindowsReservedName() {
        val zip = zip("CON" to "x")
        val dest = File.createTempFile("nf-pack-out9", "").let { it.delete(); it }
        assertTrue(runCatching { PackZipLoader.extract(zip, dest) }.isFailure)
    }

    @Test
    fun rejectsSymlinkEntryFromCentralDirectory() {
        val file = zip("nf-pack.json" to "{}")
        val bytes = file.readBytes()
        val at = (0..bytes.size - 4).first { i ->
            bytes[i] == 0x50.toByte() && bytes[i + 1] == 0x4B.toByte() &&
                bytes[i + 2] == 0x01.toByte() && bytes[i + 3] == 0x02.toByte()
        }
        bytes[at + 5] = 3 // version made by: Unix
        bytes[at + 38] = 0
        bytes[at + 39] = 0
        bytes[at + 40] = 0xFF.toByte()
        bytes[at + 41] = 0xA1.toByte()
        file.writeBytes(bytes)
        val dest = File.createTempFile("nf-pack-out10", "").let { it.delete(); it }
        assertTrue(runCatching { PackZipLoader.extract(file, dest) }.isFailure)
    }

    @Test
    fun rejectsSpecialFileEntryFromCentralDirectory() {
        val file = zip("nf-pack.json" to "{}")
        val bytes = file.readBytes()
        val at = (0..bytes.size - 4).first { i ->
            bytes[i] == 0x50.toByte() && bytes[i + 1] == 0x4B.toByte() &&
                bytes[i + 2] == 0x01.toByte() && bytes[i + 3] == 0x02.toByte()
        }
        bytes[at + 5] = 3
        bytes[at + 38] = 0
        bytes[at + 39] = 0
        bytes[at + 40] = 0
        bytes[at + 41] = 0x10.toByte() // fifo mode 0x1000
        file.writeBytes(bytes)
        val dest = File.createTempFile("nf-pack-out11", "").let { it.delete(); it }
        assertTrue(runCatching { PackZipLoader.extract(file, dest) }.isFailure)
    }

    @Test
    fun rejectsMissingManifest() {
        val zip = zip("readme.txt" to "x")
        val dest = File.createTempFile("nf-pack-out4", "").let { it.delete(); it }
        val failed = runCatching { PackZipLoader.extract(zip, dest) }.isFailure
        assertTrue(failed)
    }
}
