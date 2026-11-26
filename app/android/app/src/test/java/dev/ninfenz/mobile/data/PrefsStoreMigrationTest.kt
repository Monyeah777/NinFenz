package dev.ninfenz.mobile.data

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class PrefsStoreMigrationTest {
    @Test
    fun migratesLegacyThemeAndLanguage() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        File(context.filesDir, "nf-prefs.json").delete()
        File(context.filesDir, "nf-prefs.json.bak").delete()
        AppPrefs(context).apply {
            themeMode = ThemeMode.DARK
            languageMode = LanguageMode.EN
            dynamicColor = true
        }

        val loaded = PrefsStore(context).load()
        assertEquals(PrefsTheme.DARK, loaded.ui.theme)
        assertEquals(LanguageMode.EN, loaded.language)
        assertFalse(loaded.modules.enabled(Capability.NETWORK))
        assertEquals(true, AppPrefs(context).dynamicColor)
    }
}
