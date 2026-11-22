package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import java.util.zip.ZipFile
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PreservationExporterTest {
    @Test
    fun bundleHasManifestAndIsReproducible() {
        val dir = Files.createTempDirectory("preserve").toFile()
        val contract = "{\"schema\":\"nf-contract-signoff/1\"}"
        val a = PreservationExporter.export("# 标题\n\n正文", "标题", "p1", dir, contract)
        val b = PreservationExporter.export("# 标题\n\n正文", "标题", "p1", File(dir, "b").apply { mkdirs() }, contract)
        assertTrue(a.file.isFile)
        assertTrue(a.file.readBytes().contentEquals(b.file.readBytes()))
        ZipFile(a.file).use { zip ->
            val manifest = zip.getInputStream(zip.getEntry("preservation.json")).readBytes().decodeToString()
            assertTrue(manifest.contains("nf-preservation/1"))
            assertTrue(manifest.contains("document.md"))
            assertTrue(manifest.contains("document.nfdoc.json"))
            assertTrue(manifest.contains("contract.json"))
            assertTrue(manifest.contains("oais.json"))
            val oais = zip.getInputStream(zip.getEntry("oais.json")).readBytes().decodeToString()
            assertTrue(oais.contains("nf-oais/1"))
        }
    }
}
