package dev.ninfenz.mobile

import android.content.res.Configuration
import android.os.Bundle
import java.util.Locale
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import dev.ninfenz.mobile.data.AppPrefs
import dev.ninfenz.mobile.data.LanguageMode
import dev.ninfenz.mobile.data.ThemeMode
import dev.ninfenz.mobile.ui.NfMobileApp
import dev.ninfenz.mobile.ui.theme.NfTheme

/** 主界面：edge-to-edge + 预测返回；主题三态由 AppPrefs 持久化。 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        val prefs = AppPrefs(this)
        setContent {
            var themeMode by remember { mutableStateOf(prefs.themeMode) }
            var languageMode by remember { mutableStateOf(prefs.languageMode) }
            var dynamicColor by remember { mutableStateOf(prefs.dynamicColor) }
            val dark = when (themeMode) {
                ThemeMode.SYSTEM -> isSystemInDarkTheme()
                ThemeMode.LIGHT -> false
                ThemeMode.DARK -> true
            }
            val localizedContext = remember(languageMode) {
                val tag = languageMode.tag
                if (tag == null) {
                    this@MainActivity
                } else {
                    val config = Configuration(resources.configuration).apply {
                        setLocale(Locale.forLanguageTag(tag))
                    }
                    createConfigurationContext(config)
                }
            }
            CompositionLocalProvider(
                LocalContext provides localizedContext,
                LocalConfiguration provides localizedContext.resources.configuration
            ) {
                NfTheme(darkTheme = dark, dynamicColor = dynamicColor) {
                    NfMobileApp(
                        prefs = prefs,
                        themeMode = themeMode,
                        onThemeMode = { mode ->
                            prefs.themeMode = mode
                            themeMode = mode
                        },
                        languageMode = languageMode,
                        onLanguageMode = { mode ->
                            prefs.languageMode = mode
                            languageMode = mode
                        },
                        dynamicColor = dynamicColor,
                        onDynamicColor = { enabled ->
                            prefs.dynamicColor = enabled
                            dynamicColor = enabled
                        }
                    )
                }
            }
        }
    }
}
