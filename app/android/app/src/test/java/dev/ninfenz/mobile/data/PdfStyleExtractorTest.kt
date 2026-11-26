package dev.ninfenz.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

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
}
