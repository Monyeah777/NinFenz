package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PackSigningKeyTest {
    @Test
    fun seedIsStableHex64() {
        val dir = Files.createTempDirectory("nf-sign-key").toFile()
        val first = PackSigningKey.seed(dir)
        val second = PackSigningKey.seed(dir)
        assertTrue(first.matches(Regex("^[0-9a-f]{64}$")))
        assertEquals(first, second)
    }
}
