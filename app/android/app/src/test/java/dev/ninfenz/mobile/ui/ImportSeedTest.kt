package dev.ninfenz.mobile.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ImportSeedTest {
    @Test
    fun consumesOnlyOnce() {
        ImportSeed.put("粘贴内容")
        assertEquals("粘贴内容", ImportSeed.consume())
        assertNull(ImportSeed.consume())
    }
}
