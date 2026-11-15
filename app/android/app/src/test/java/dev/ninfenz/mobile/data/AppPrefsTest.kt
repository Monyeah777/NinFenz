package dev.ninfenz.mobile.data

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class AppPrefsTest {
    @Test
    fun languageAndDynamicColorPersist() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val prefs = AppPrefs(context)
        prefs.languageMode = LanguageMode.EN
        prefs.dynamicColor = true
        assertEquals(LanguageMode.EN, AppPrefs(context).languageMode)
        assertTrue(AppPrefs(context).dynamicColor)
        val fresh = AppPrefs(context)
        fresh.languageMode = LanguageMode.SYSTEM
        fresh.dynamicColor = false
        assertEquals(LanguageMode.SYSTEM, AppPrefs(context).languageMode)
        assertFalse(AppPrefs(context).dynamicColor)
    }
}
