package dev.ninfenz.mobile.data

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class PdfStyleExtractorTest {
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
    fun extractsFromMinimalPdfFixture() {
        val source = File("src/test/resources/hello.pdf")
        assumeTrue("pdf fixture missing", source.isFile)
        val context = ApplicationProvider.getApplicationContext<Context>()
        val style = PdfStyleExtractor.extract(source, context)
        assertEquals(1, style.pages)
        assertTrue(style.sizes.containsKey(12))
        assertTrue(style.fonts.isNotEmpty())
    }


}
