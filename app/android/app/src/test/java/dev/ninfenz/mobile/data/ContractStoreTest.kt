package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class ContractStoreTest {
    @Test
    fun signsAndReloads() {
        val dir = Files.createTempDirectory("contract").toFile()
        val signer = SoftwareContractSigner()
        val store = ContractStore(dir, signer)
        assertNull(store.load("p1"))
        store.sign("p1", listOf("L1", "required-slots"), "2026-11-21T00:00:00Z", "abc123")
        val loaded = store.load("p1")!!
        assertEquals("p1", loaded.projectId)
        assertEquals(listOf("L1", "required-slots"), loaded.accepted)
        assertEquals("2026-11-21T00:00:00Z", loaded.signedAt)
        assertEquals("abc123", loaded.artifactSha256)
        assertNotNull(loaded.keyFingerprint)
    }

    @Test
    fun tamperedPayloadFails() {
        val dir = Files.createTempDirectory("contract-tamper").toFile()
        val store = ContractStore(dir, SoftwareContractSigner())
        store.sign("p1", listOf("L1"), "2026-11-21T00:00:00Z", "abc123")
        val f = File(File(dir, "contracts"), "p1.json")
        f.writeText(f.readText(Charsets.UTF_8).replace("L1", "L9"), Charsets.UTF_8)
        assertNull(store.load("p1"))
    }

    @Test
    fun wrongKeyFails() {
        val dir = Files.createTempDirectory("contract-key").toFile()
        ContractStore(dir, SoftwareContractSigner()).sign("p1", listOf("L1"), "2026-11-21T00:00:00Z", "abc123")
        assertNull(ContractStore(dir, SoftwareContractSigner()).load("p1"))
    }
}
