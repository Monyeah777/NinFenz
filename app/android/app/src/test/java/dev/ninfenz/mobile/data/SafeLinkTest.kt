package dev.ninfenz.mobile.data

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SafeLinkTest {
    @Test
    fun allowsWebAndRelativeOnly() {
        assertTrue(SafeLink.allowed("https://example.com"))
        assertTrue(SafeLink.allowed("mailto:a@b.c"))
        assertTrue(SafeLink.allowed("../a.md"))
        assertTrue(SafeLink.allowed("#a"))
        assertFalse(SafeLink.allowed("javascript:alert(1)"))
        assertFalse(SafeLink.allowed("file:///etc/passwd"))
        assertFalse(SafeLink.allowed("data:text/html,x"))
        assertTrue(SafeLink.allowedImage("data:image/png;base64,AA"))
    }
}
