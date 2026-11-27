package dev.ninfenz.mobile.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.platform.LocalContext
import dev.ninfenz.mobile.data.AppPrefs
import dev.ninfenz.mobile.data.LanguageMode
import dev.ninfenz.mobile.data.ThemeMode
import dev.ninfenz.mobile.ui.shell.ShellState
import dev.ninfenz.mobile.ui.shell.ShellStateCodec

private val ShellStateSaver = Saver<ShellState, List<String>>(
    save = { ShellStateCodec.encode(it) },
    restore = { ShellStateCodec.decode(it) }
)

/**
 * v0.02 应用外壳：四目的地（库/创作/交付/我的）+ 自适应底部栏/rail + FAB 导入 + 单层详情。
 * 旧的 8 个功能页保留在详情层，保证 v1 能力可达；首启示例与引导在 W1 接入。
 *
 * 状态与后台动作集中在 [NfShellHost]；顶层/详情路由分别在 NfTopLevelRoutes、NfDetailRoutes；
 * 壳层骨架在 NfShellChrome；对话框在 NfShellDialogs。行为与拆分前一致。
 */
@Composable
fun NfMobileApp(
    prefs: AppPrefs,
    themeMode: ThemeMode,
    onThemeMode: (ThemeMode) -> Unit,
    languageMode: LanguageMode = LanguageMode.SYSTEM,
    onLanguageMode: (LanguageMode) -> Unit = {},
    dynamicColor: Boolean = false,
    onDynamicColor: (Boolean) -> Unit = {},
    shortcut: String? = null,
    onShortcutConsumed: () -> Unit = {}
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val host = remember { NfShellHost(context, scope, prefs) }
    val shellState = rememberSaveable(stateSaver = ShellStateSaver) { mutableStateOf(ShellState()) }
    val showCommandsState = rememberSaveable { mutableStateOf(false) }
    host.bind(shellState, showCommandsState)
    host.themeMode = themeMode
    host.onThemeMode = onThemeMode
    host.languageMode = languageMode
    host.onLanguageMode = onLanguageMode
    host.dynamicColor = dynamicColor
    host.onDynamicColor = onDynamicColor
    NfShellEffects(host)
    if (!host.onboardingDone) {
        NfOnboardingGate(host)
        return
    }
    NfShortcutEffect(host, shortcut, onShortcutConsumed)
    NfShellRoot(host)
    NfShellDialogs(host)
}
