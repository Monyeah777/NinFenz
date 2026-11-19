package dev.ninfenz.mobile.data

import java.nio.file.Files
import java.util.zip.ZipFile
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertTrue
import org.junit.Test

class TemplatePackageBuilderTest {
    @Test
    fun buildsTemplateZip() {
        val root = Files.createTempDirectory("nf-template-build").toFile()
        val packDir = java.io.File(root, "pack").apply { mkdirs() }
        java.io.File(packDir, "protocol").mkdirs()
        java.io.File(packDir, "pipeline").mkdirs()
        java.io.File(packDir, "protocol/nf-protocol-pack.json").writeText("{}")
        java.io.File(packDir, "pipeline/main.nfg.json").writeText("{}")
        val pack = PackEntry("demo", "1.0.0", "Demo", "", 0, "tree", packDir)
        val spec = buildJsonObject { put("schema", "nf-md-spec/1"); put("id", "123"); put("title", "Demo") }
        val prepared = TemplatePackageBuilder.prepare(root, pack, spec, "Demo")
        val template = java.io.File(prepared.dir, "template.md")
        assertTrue(template.isFile)
        assertTrue(template.readText().contains("# Demo"))
        val zip = TemplatePackageBuilder.finalize(prepared, "a".repeat(64), 4, java.io.File(root, "out"))
        ZipFile(zip).use { z ->
            assertTrue(z.getEntry("nf-template.json") != null)
            assertTrue(z.getEntry("spec/main.nfspec.json") != null)
            val manifest = z.getInputStream(z.getEntry("nf-template.json")).use { it.readBytes().toString(Charsets.UTF_8) }
            assertTrue(manifest.contains("\"id\":\"tpl-123\""))
        }
    }
}
