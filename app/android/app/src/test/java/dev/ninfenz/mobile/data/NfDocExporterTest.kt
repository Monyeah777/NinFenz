package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.model.NfDocModel
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class NfDocExporterTest {
    @Test
    fun writesParsableJson() {
        val out = Files.createTempDirectory("nfdoc-export").toFile()
        val created = NfDocExporter.export("# 开篇\n\n正文", "标题", "p1", out)
        assertTrue(created.file.isFile)
        val doc = NfDocModel.parse(J.parseObject(created.file.readText(), NfDocModel.SCHEMA))
        assertEquals("标题", doc.title)
        assertEquals(listOf("p1"), doc.sources)
    }
}
