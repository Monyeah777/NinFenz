package dev.ninfenz.mobile.data

import java.nio.file.Files
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class EpubExporterTest {
    @Test
    fun createsEpub3Structure() {
        val dir = Files.createTempDirectory("nf-epub").toFile()
        val md = "# 第一章\n\n正文 <script>\n\n- 要点\n\n# 第二章\n\n第二段"
        val created = EpubExporter.export(md, "演示书", dir)
        assertEquals(2, created.chapters)
        ZipFile(created.file).use { zip ->
            val names = zip.entries().toList().map { it.name }
            assertEquals("mimetype", names.first())
            assertEquals("application/epub+zip", zip.getInputStream(zip.getEntry("mimetype")).bufferedReader().readText())
            assertEquals(ZipEntry.STORED, zip.getEntry("mimetype").method)
            assertTrue(names.contains("META-INF/container.xml"))
            assertTrue(names.contains("OEBPS/content.opf"))
            assertTrue(names.contains("OEBPS/nav.xhtml"))
            assertTrue(names.contains("OEBPS/chapter-001.xhtml"))
            val chapter = zip.getInputStream(zip.getEntry("OEBPS/chapter-001.xhtml")).bufferedReader().readText()
            assertTrue(chapter.contains("&lt;script&gt;"))
            assertTrue(chapter.contains("<ul>"))
        }
    }

    @Test
    fun rendersPipeTableInChapter() {
        val dir = Files.createTempDirectory("nf-epub-table").toFile()
        val created = EpubExporter.export("# 表\n\n| A | B |\n|---|---|\n| 1 | 2 |", "表", dir)
        ZipFile(created.file).use { zip ->
            val chapter = zip.getInputStream(zip.getEntry("OEBPS/chapter-001.xhtml")).bufferedReader().readText()
            assertTrue(chapter.contains("<table>"))
            assertTrue(chapter.contains("<th>A</th>"))
            assertTrue(chapter.contains("<td>1</td>"))
        }
    }

    @Test
    fun rendersOnlySafeLinks() {
        val dir = Files.createTempDirectory("nf-epub-link").toFile()
        val created = EpubExporter.export("# 链\n\n[官网](https://example.com)", "链", dir)
        ZipFile(created.file).use { zip ->
            val chapter = zip.getInputStream(zip.getEntry("OEBPS/chapter-001.xhtml")).bufferedReader().readText()
            assertTrue(chapter.contains("<a href=\"https://example.com\">官网</a>"))
        }
    }

    @Test
    fun rendersHorizontalRule() {
        val dir = Files.createTempDirectory("nf-epub-hr").toFile()
        val created = EpubExporter.export("# 章\n\n前\n\n---\n\n后", "章", dir)
        ZipFile(created.file).use { zip ->
            val chapter = zip.getInputStream(zip.getEntry("OEBPS/chapter-001.xhtml")).bufferedReader().readText()
            assertTrue(chapter.contains("<hr/>"))
        }
    }

    @Test
    fun rendersBlockquote() {
        val dir = Files.createTempDirectory("nf-epub-quote").toFile()
        val created = EpubExporter.export("# 章\n\n> 引用", "章", dir)
        ZipFile(created.file).use { zip ->
            val chapter = zip.getInputStream(zip.getEntry("OEBPS/chapter-001.xhtml")).bufferedReader().readText()
            assertTrue(chapter.contains("<blockquote><p>引用</p></blockquote>"))
        }
    }

    @Test
    fun rendersOrderedList() {
        val dir = Files.createTempDirectory("nf-epub-ol").toFile()
        val created = EpubExporter.export("# 章\n\n1. 一\n2. 二", "章", dir)
        ZipFile(created.file).use { zip ->
            val chapter = zip.getInputStream(zip.getEntry("OEBPS/chapter-001.xhtml")).bufferedReader().readText()
            assertTrue(chapter.contains("<ol><li>一</li><li>二</li></ol>"))
        }
    }

    @Test
    fun rendersStrikethrough() {
        val dir = Files.createTempDirectory("nf-epub-del").toFile()
        val created = EpubExporter.export("# 章\n\n~~旧~~ 新", "章", dir)
        ZipFile(created.file).use { zip ->
            val chapter = zip.getInputStream(zip.getEntry("OEBPS/chapter-001.xhtml")).bufferedReader().readText()
            assertTrue(chapter.contains("<del>旧</del>"))
        }
    }

    @Test
    fun noHeadingFallsBackToSingleChapter() {
        assertEquals(1, EpubExporter.chapters("只有一段正文").size)
        assertEquals("正文", EpubExporter.chapters("只有一段正文").first().title)
    }
}
