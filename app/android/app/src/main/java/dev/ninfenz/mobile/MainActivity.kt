package dev.ninfenz.mobile

import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import com.google.android.play.core.splitcompat.SplitCompat
import android.os.Bundle
import android.view.KeyEvent
import java.util.Locale
import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivityResultRegistryOwner
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
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.unit.LayoutDirection
import dev.ninfenz.mobile.data.AppPrefs
import dev.ninfenz.mobile.data.CapabilityRegistry
import dev.ninfenz.mobile.data.CrashLogStore
import dev.ninfenz.mobile.data.PrefsStore
import dev.ninfenz.mobile.data.PrefsTheme
import dev.ninfenz.mobile.data.RecentProjectShortcuts
import dev.ninfenz.mobile.data.LanguageMode
import dev.ninfenz.mobile.data.ThemeMode
import dev.ninfenz.mobile.ui.CommandBus
import dev.ninfenz.mobile.ui.NfMobileApp
import dev.ninfenz.mobile.ui.theme.NfTheme

/** 主界面：edge-to-edge + 预测返回；主题三态由 AppPrefs 持久化。 */
class MainActivity : ComponentActivity() {
    override fun attachBaseContext(newBase: Context) {
        super.attachBaseContext(newBase)
        SplitCompat.install(this)
    }

    private var pendingShortcut by mutableStateOf<String?>(null)

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        pendingShortcut = shortcutFrom(intent)
    }

    private fun shortcutFrom(intent: Intent?): String? = when (intent?.action) {
        RecentProjectShortcuts.ACTION_OPEN_PROJECT ->
            intent.getStringExtra(RecentProjectShortcuts.EXTRA_PROJECT_ID)?.takeIf { it.isNotBlank() }?.let { id ->
                RecentProjectShortcuts.reportUsed(this, id)
                "project:" + id
            }
        "dev.ninfenz.mobile.SHORTCUT_IMPORT" -> "import"
        "dev.ninfenz.mobile.SHORTCUT_NEW_PROJECT" -> "new_project"
        "dev.ninfenz.mobile.SHORTCUT_SEARCH" -> "search"
        else -> null
    }

    private fun syncSystemLocale(mode: LanguageMode) {
        if (android.os.Build.VERSION.SDK_INT < 33) return
        runCatching {
            val manager = getSystemService(android.app.LocaleManager::class.java) ?: return
            val desired = if (mode.tag == null) {
                android.os.LocaleList.getEmptyLocaleList()
            } else {
                android.os.LocaleList.forLanguageTags(mode.tag)
            }
            if (manager.applicationLocales != desired) {
                manager.applicationLocales = desired
            }
        }
    }

    private fun installCrashHandler() {
        if (crashHandlerInstalled) return
        crashHandlerInstalled = true
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
            runCatching { CrashLogStore(filesDir).record(throwable) }
            if (previous != null) {
                previous.uncaughtException(thread, throwable)
            } else {
                android.os.Process.killProcess(android.os.Process.myPid())
                kotlin.system.exitProcess(10)
            }
        }
    }

    private companion object {
        var crashHandlerInstalled = false
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (event != null && (event.isCtrlPressed || event.isMetaPressed) && keyCode == KeyEvent.KEYCODE_K) {
            CommandBus.request()
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        installCrashHandler()
        dev.ninfenz.mobile.ui.installCoreCallContext(this)
        pendingShortcut = shortcutFrom(intent)
        val prefs = AppPrefs(this)
        val nfPrefs = PrefsStore(filesDir, prefs).load()
        CapabilityRegistry.install(nfPrefs)
        if (nfPrefs.language != LanguageMode.SYSTEM) {
            syncSystemLocale(nfPrefs.language)
        }
        setContent {
            MainActivityContent(prefs, nfPrefs)
        }
    }

    @androidx.compose.runtime.Composable
    private fun MainActivityContent(prefs: AppPrefs, nfPrefs: dev.ninfenz.mobile.data.NfPrefs) {
        var themeMode by remember {
            mutableStateOf(
                when (nfPrefs.ui.theme) {
                    PrefsTheme.LIGHT -> ThemeMode.LIGHT
                    PrefsTheme.DARK, PrefsTheme.HIGH_CONTRAST -> ThemeMode.DARK
                    PrefsTheme.SYSTEM -> ThemeMode.SYSTEM
                }
            )
        }
        var languageMode by remember { mutableStateOf(nfPrefs.language) }
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
            LocalConfiguration provides localizedContext.resources.configuration,
            LocalLayoutDirection provides if (languageMode == LanguageMode.PSEUDO) LayoutDirection.Rtl else LayoutDirection.Ltr,
            LocalActivityResultRegistryOwner provides this@MainActivity
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
                        syncSystemLocale(mode)
                    },
                    dynamicColor = dynamicColor,
                    onDynamicColor = { enabled ->
                        prefs.dynamicColor = enabled
                        dynamicColor = enabled
                    },
                    shortcut = pendingShortcut,
                    onShortcutConsumed = { pendingShortcut = null }
                )
            }
        }
    }
}
