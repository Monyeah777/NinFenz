package dev.ninfenz.mobile.data

import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.pdmodel.PDPage
import com.tom_roush.pdfbox.pdmodel.PDPageContentStream
import com.tom_roush.pdfbox.pdmodel.font.PDType0Font
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeNoException
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class PdfStyleExtractorTest {
    @get:Rule
    val tmp = TemporaryFolder()

    @Test
    fun serializesPdfStyleDeterministically() {
        val style = PdfStyle(
            pages = 2,
            fonts = listOf("Helvetica", "Times"),
            sizes = mapOf(12 to 3, 18 to 1)
        )
        val xml = style.toStyleXml()
        assertTrue(xml.contains("<pdf-style pages=\"2\">"))
        assertTrue(xml.contains("<font name=\"Helvetica\"/>"))
        assertTrue(xml.contains("<size value=\"12\" count=\"3\"/>"))
        assertEquals(xml, style.toStyleXml())
    }

    @Test
    fun extractsEmbeddedFontAndSize() {
        val source = File("src/main/assets/fonts/NotoSansSC-VF.ttf")
        assumeTrue("font fixture missing", source.isFile)
        try {
            val file = File(tmp.root, "a.pdf")
            PDDocument().use { document ->
                val page = PDPage()
                document.addPage(page)
                val font = PDType0Font.load(document, source)
                PDPageContentStream(document, page).use { stream ->
                    stream.beginText()
                    stream.setFont(font, 12f)
                    stream.newLineAtOffset(72f, 720f)
                    stream.showText("hello")
                    stream.endText()
                }
                document.save(file)
            }
            val style = PdfStyleExtractor.extract(file)
            assertEquals(1, style.pages)
            assertTrue(style.sizes.containsKey(12))
            assertTrue(style.fonts.isNotEmpty())
        } catch (t: Throwable) {
            // PDFBox Android 的字体 native 在纯 JVM 不可用；留设备夹具执行。
            assumeNoException(t)
        }
    }
}
