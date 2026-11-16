package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import java.security.MessageDigest
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ExportVerifierTest {
    private fun sha(file: File): String {
        val d = MessageDigest.getInstance("SHA-256").digest(file.readBytes())
        return d.joinToString("") { "%02x".format(it) }
    }

    private fun manifest(file: File, sha: String, bytes: Long): String =
        "{\"files\":[{\"name\":\"" + file.name + "\",\"sha256\":\"" + sha + "\",\"bytes\":" + bytes + "}]}"

    @Test
    fun passesMatchingManifest() {
        val dir = Files.createTempDirectory("nf-export-verify").toFile()
        val f = File(dir, "result.md").apply { writeText("# ok") }
        assertTrue(ExportVerifier.verify(f, manifest(f, sha(f), f.length())).ok)
    }

    @Test
    fun failsOnMissingFileWrongShaOrWrongBytes() {
        val dir = Files.createTempDirectory("nf-export-verify-2").toFile()
        val f = File(dir, "result.md").apply { writeText("# ok") }
        assertFalse(ExportVerifier.verify(File(dir, "missing.md"), manifest(f, sha(f), f.length())).ok)
        assertFalse(ExportVerifier.verify(f, manifest(f, sha(f), 999)).ok)
        assertFalse(ExportVerifier.verify(f, manifest(f, "deadbeef", f.length())).ok)
        assertFalse(ExportVerifier.verify(f, null).ok)
    }
}
