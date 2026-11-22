package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertTrue
import org.junit.Test

class ZeroSliceProjectDraftTest {
    @Test
    fun writesDraftSidecarAndMapping() {
        val dir = Files.createTempDirectory("nf-zero-project").toFile()
        val report = ZeroSliceReport(
            mappings = listOf(ZeroSliceMapping(0, "SLT-01", "主题句", 100)),
            exceptions = emptyList(),
            coverage = 100,
            slotValues = mapOf("SLT-01" to "甲"),
            projectSlots = mapOf("SLT-01" to "甲")
        )
        val prepared = ZeroSliceProjectDraft.prepare(dir, "{}", report, setOf(0), emptyList(), "切片")
        val drafts = java.io.File(dir, "drafts")
        val sidecar = java.io.File(drafts, prepared.file.name.removeSuffix(".json") + ".zero-slice.json")
        assertTrue(prepared.file.isFile)
        assertTrue(sidecar.isFile)
        assertTrue(sidecar.readText().contains("SLT-01"))
        assertTrue(java.io.File(drafts, prepared.file.name.removeSuffix(".json") + ".mapping.json").isFile)
    }
}
