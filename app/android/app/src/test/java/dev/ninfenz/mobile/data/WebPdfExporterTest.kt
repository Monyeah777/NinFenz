package dev.ninfenz.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Test

class WebPdfExporterTest {
    @Test
    fun webViewSecurityConfigIsClosed() {
        val config = WebPdfExporter.securityConfig()
        assertEquals(false, config.javaScriptEnabled)
        assertEquals(true, config.blockNetworkLoads)
        assertEquals(false, config.allowFileAccess)
        assertEquals(false, config.allowContentAccess)
    }

    @Test
    fun pageCountUsesA4Scale() {
        assertEquals(1, WebPdfExporter.pageCount(1000, 794))
        assertEquals(2, WebPdfExporter.pageCount(2000, 794))
    }

    @Test
    fun pageCountUsesLetterSize() {
        assertEquals(1, WebPdfExporter.pageCount(1000, 794, 612, 792))
        assertEquals(2, WebPdfExporter.pageCount(1800, 794, 612, 792))
    }

    @Test
    fun pageCountHandlesEmptyAndTinyWidth() {
        assertEquals(1, WebPdfExporter.pageCount(0, 794))
        assertEquals(1, WebPdfExporter.pageCount(1, 1))
    }
}
