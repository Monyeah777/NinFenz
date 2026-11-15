package dev.ninfenz.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import dev.ninfenz.mobile.data.AppPrefs
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
            val dark = when (themeMode) {
                ThemeMode.SYSTEM -> isSystemInDarkTheme()
                ThemeMode.LIGHT -> false
                ThemeMode.DARK -> true
            }
            NfTheme(darkTheme = dark) {
                NfMobileApp(
                    prefs = prefs,
                    themeMode = themeMode,
                    onThemeMode = { mode ->
                        prefs.themeMode = mode
                        themeMode = mode
                    }
                )
            }
        }
    }
}
