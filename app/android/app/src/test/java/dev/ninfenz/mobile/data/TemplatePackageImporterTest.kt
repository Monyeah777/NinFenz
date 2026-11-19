package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.Assert.assertEquals
import org.junit.Test

class TemplatePackageImporterTest {
    @Test(expected = IllegalArgumentException::class)
    fun rejectsBadManifestId() {
        val dir = Files.createTempDirectory("nf-template-bad").toFile()
        val zip = File(dir, "bad.zip")
        ZipOutputStream(zip.outputStream()).use { out ->
            out.putNextEntry(ZipEntry("nf-template.json"))
            out.write("""{"schema":"nf-template/1","manifest":{"id":"BAD","version":"0.1.0","title":"x"},"compat":{"schema_version":1}}""".toByteArray())
            out.closeEntry()
        }
        TemplatePackageImporter.inspect(zip, dir)
    }

    @Test
    fun readsTemplatePackage() {
        val dir = Files.createTempDirectory("nf-template-import").toFile()
        val zip = File(dir, "t.zip")
        val spec = "{\"schema\":\"nf-md-spec/1\",\"id\":\"tpl-demo\"}"
        val md = "# Demo"
        val proto = "{}"
        val pipe = "{}"
        val manifest = "{\"schema\":\"nf-template/1\",\"manifest\":{\"id\":\"tpl-demo\",\"version\":\"0.1.0\",\"title\":\"Demo\"},\"template_md\":{\"path\":\"template.md\",\"sha256\":\"311bf7b773261f50f85145f553ac0ea393044607e83e7c91485f9fa28c0f69ae\"},\"spec\":{\"path\":\"spec/main.nfspec.json\",\"sha256\":\"cfc2205f51b864bdbc997d13c422d64e4fe3d6e3cb25714e88508fb2a587f4de\"},\"protocol\":{\"path\":\"protocol/nf-protocol-pack.json\",\"sha256\":\"44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a\"},\"pipeline\":{\"path\":\"pipeline/main.nfg.json\",\"sha256\":\"44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a\"},\"assets\":[],\"hashes\":{\"tree\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\",\"count\":4},\"compat\":{\"min_app_version\":\"0.2.0\",\"schema_version\":1}}"
        ZipOutputStream(zip.outputStream()).use { out ->
            fun put(name: String, text: String) {
                out.putNextEntry(ZipEntry(name)); out.write(text.toByteArray()); out.closeEntry()
            }
            put("nf-template.json", manifest)
            put("template.md", md)
            put("spec/main.nfspec.json", spec)
            put("protocol/nf-protocol-pack.json", proto)
            put("pipeline/main.nfg.json", pipe)
        }
        val imported = TemplatePackageImporter.inspect(zip, dir)
        assertEquals("Demo", imported.title)
        assertEquals(spec, imported.specText)
        assertEquals(4, imported.count)
    }
}
