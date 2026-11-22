package dev.ninfenz.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PropertyHarnessTest {
    @Test
    fun deterministicFailureIncludesSeed() {
        val report = PropertyHarness.check(7, 5, { it.nextInt(10) }, { it < 0 })
        assertFalse(report.ok)
        assertEquals(7, report.failures.first().seed)
        assertEquals(5, report.checked)
    }

    @Test
    fun selfCheckPasses() {
        val report = AppSelfCheck.run()
        assertTrue(report.failures.toString(), report.ok)
        assertEquals(150, report.checked)
    }
}
