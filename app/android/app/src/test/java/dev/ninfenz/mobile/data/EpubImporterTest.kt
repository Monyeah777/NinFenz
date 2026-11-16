package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.Assert.assertTrue
import org.junit.Test

class EpubImporterTest {
    private fun epub(entries: List<Pair<String, String>>): File {
        val f = File.createTempFile("nf-epub-import", ".epub")
        ZipOutputStream(f.outputStream()).use { out ->
            entries.forEach { (name, text) ->
                out.putNextEntry(ZipEntry(name)); out.write(text.toByteArray()); out.closeEntry()
            }
        }
        return f
    }

    @Test
    fun extractsSpineChapters() {
        val file = epub(
            listOf(
                "META-INF/container.xml" to "<container><rootfiles><rootfile full-path=\"OEBPS/content.opf\"/></rootfiles></container>",
                "OEBPS/content.opf" to "<package><manifest><item id=\"c1\" href=\"chapter1.xhtml\" media-type=\"application/xhtml+xml\"/></manifest><spine><itemref idref=\"c1\"/></spine></package>",
                "OEBPS/chapter1.xhtml" to "<h1>章</h1><p>正文</p>"
            )
        )
        val text = EpubImporter.extract(file)
        assertTrue(text.contains("# 章"))
        assertTrue(text.contains("正文"))
    }

    @Test
    fun followsSpineOrder() {
        val file = epub(
            listOf(
                "META-INF/container.xml" to "<container><rootfiles><rootfile full-path=\"OEBPS/content.opf\"/></rootfiles></container>",
                "OEBPS/content.opf" to "<package><manifest>" +
                    "<item id=\"c1\" href=\"one.xhtml\" media-type=\"application/xhtml+xml\"/>" +
                    "<item id=\"c2\" href=\"two.xhtml\" media-type=\"application/xhtml+xml\"/>" +
                    "</manifest><spine><itemref idref=\"c2\"/><itemref idref=\"c1\"/></spine></package>",
                "OEBPS/one.xhtml" to "<h1>一</h1>",
                "OEBPS/two.xhtml" to "<h1>二</h1>"
            )
        )
        val text = EpubImporter.extract(file)
        assertTrue(text.indexOf("# 二") < text.indexOf("# 一"))
    }

    @Test
    fun addsTitleWhenMissingHeading() {
        val file = epub(
            listOf(
                "META-INF/container.xml" to "<container><rootfiles><rootfile full-path=\"OEBPS/content.opf\"/></rootfiles></container>",
                "OEBPS/content.opf" to "<package><metadata><dc:title>书名</dc:title></metadata>" +
                    "<manifest><item id=\"c1\" href=\"one.xhtml\" media-type=\"application/xhtml+xml\"/></manifest>" +
                    "<spine><itemref idref=\"c1\"/></spine></package>",
                "OEBPS/one.xhtml" to "<p>正文</p>"
            )
        )
        assertTrue(EpubImporter.extract(file).startsWith("# 书名"))
    }

    @Test
    fun detectsEpubContainer() {
        val good = epub(
            listOf(
                "mimetype" to "application/epub+zip",
                "META-INF/container.xml" to "<container/>"
            )
        )
        assertTrue(EpubImporter.isEpub(good))
        val plain = epub(listOf("data/a.txt" to "x"))
        assertTrue(!EpubImporter.isEpub(plain))
    }

    @Test
    fun embedsImageAsDataUri() {
        val file = epub(
            listOf(
                "META-INF/container.xml" to "<container><rootfiles><rootfile full-path=\"OEBPS/content.opf\"/></rootfiles></container>",
                "OEBPS/content.opf" to "<package><manifest><item id=\"c1\" href=\"one.xhtml\" media-type=\"application/xhtml+xml\"/></manifest><spine><itemref idref=\"c1\"/></spine></package>",
                "OEBPS/one.xhtml" to "<p><img src=\"img/a.png\" alt=\"图\"/></p>",
                "OEBPS/img/a.png" to "PNG"
            )
        )
        val text = EpubImporter.extract(file)
        assertTrue(text.contains("data:image/png;base64,"))
    }

    @Test
    fun rejectsMissingContainer() {
        val f = epub(listOf("OEBPS/chapter.xhtml" to "<p>x</p>"))
        assertTrue(runCatching { EpubImporter.extract(f) }.isFailure)
    }
}
