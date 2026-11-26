package dev.ninfenz.mobile.data

import java.util.Date
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class OutputNamingTest {
    @Test
    fun resolvesTemplateAndExtension() {
        val date = Date(0L)
        val name = OutputNaming.resolve("{project}-{date}", "客户/案例", "pdf", date)
        assertEquals("客户_案例-19700101.pdf", name)
    }

    @Test
    fun keepsExistingExtensionAndDefaults() {
        assertTrue(OutputNaming.resolve("x.epub", "t", "epub").endsWith(".epub"))
        assertEquals("result.html", OutputNaming.resolve(null, "t", "html"))
    }
}
