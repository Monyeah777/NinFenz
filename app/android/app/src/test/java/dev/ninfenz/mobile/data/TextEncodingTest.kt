package dev.ninfenz.mobile.data

import java.nio.charset.Charset
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class TextEncodingTest {
    @Test
    fun decodesUtf16LeBom() {
        val bytes = byteArrayOf(0xFF.toByte(), 0xFE.toByte()) + "你好".toByteArray(Charset.forName("UTF-16LE"))
        val decoded = TextEncoding.decode(bytes)
        assertEquals("你好", decoded?.text)
        assertEquals("UTF-16LE", decoded?.encoding)
    }

    @Test
    fun decodesUtf8BomAndIgnoresPlainText() {
        val bytes = byteArrayOf(0xEF.toByte(), 0xBB.toByte(), 0xBF.toByte()) + "hi".toByteArray()
        assertEquals("hi", TextEncoding.decode(bytes)?.text)
        assertNull(TextEncoding.decode("hi".toByteArray()))
    }
}
