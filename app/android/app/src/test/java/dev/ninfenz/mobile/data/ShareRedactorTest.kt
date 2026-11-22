package dev.ninfenz.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class ShareRedactorTest {
    @Test
    fun stripsCommentsAndSourceLines() {
        val input = "# 标题\n\n<!-- source: p1 -->\n\n正文\n\nsource: C:\\secret.md\n\n尾"
        val out = ShareRedactor.redact(input)
        assertFalse(out.contains("<!--"))
        assertFalse(out.contains("secret.md"))
        assertEquals("# 标题\n\n正文\n\n尾", out)
    }
}
