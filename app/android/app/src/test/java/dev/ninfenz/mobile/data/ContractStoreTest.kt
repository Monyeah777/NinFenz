package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ContractStoreTest {
    @Test
    fun signsAndReloads() {
        val dir = Files.createTempDirectory("contract").toFile()
        val store = ContractStore(dir)
        assertNull(store.load("p1"))
        store.sign("p1", listOf("L1", "required-slots"), "2026-11-21T00:00:00Z", "abc123")
        val loaded = store.load("p1")!!
        assertEquals("p1", loaded.projectId)
        assertEquals(listOf("L1", "required-slots"), loaded.accepted)
        assertEquals("2026-11-21T00:00:00Z", loaded.signedAt)
        assertEquals("abc123", loaded.artifactSha256)
    }
}
