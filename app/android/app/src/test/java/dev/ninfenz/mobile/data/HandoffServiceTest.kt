package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class HandoffServiceTest {
    @Test
    fun exportAndInspectRoundTrip() {
        val dir = Files.createTempDirectory("nf-handoff").toFile()
        val zip = HandoffService.export("p1", "{\"id\":\"p1\"}", "{\"schema\":\"nf-review/1\"}", "# hello", dir)
        assertTrue(zip.isFile)
        val info = HandoffService.inspect(zip)
        assertTrue(info.error ?: "", info.ok)
        assertEquals("p1", info.projectId)
        assertEquals(listOf("project.nfproject.json", "review.json", "markdown.md"), info.files)
    }

    @Test
    fun tamperedPayloadRejected() {
        val dir = Files.createTempDirectory("nf-handoff-bad").toFile()
        val zip = HandoffService.export("p2", "{\"id\":\"p2\"}", "{}", "# x", dir)
        // zip 是普通文件；用同目录副本改一个字节，inspect 必须拒绝
        val bytes = zip.readBytes()
        bytes[bytes.size / 2] = (bytes[bytes.size / 2].toInt() xor 0xff).toByte()
        val bad = File(dir, "bad.zip").apply { writeBytes(bytes) }
        assertFalse(HandoffService.inspect(bad).ok)
    }
}
