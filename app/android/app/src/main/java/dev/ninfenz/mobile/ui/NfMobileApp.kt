package dev.ninfenz.mobile.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import dev.ninfenz.mobile.data.LibraryStore
import dev.ninfenz.mobile.share.ShareHandoff
import dev.ninfenz.mobile.share.SharePayload
import dev.ninfenz.mobile.state.NavState
import dev.ninfenz.mobile.state.Screen
import dev.ninfenz.mobile.ui.screens.AssemblyScreen
import dev.ninfenz.mobile.ui.screens.CcosScreen
import dev.ninfenz.mobile.ui.screens.GraphScreen
import dev.ninfenz.mobile.ui.screens.HomeScreen
import dev.ninfenz.mobile.ui.screens.ImportScreen
import dev.ninfenz.mobile.ui.screens.PackUpdateScreen
import dev.ninfenz.mobile.ui.screens.ProtocolScreen
import dev.ninfenz.mobile.ui.screens.SettingsScreen

/**
 * 应用外壳：紧凑宽度（手机竖屏）用单页导航栈；中等/扩展宽度（折叠展开/平板/Chromebook/多窗口）
 * 用常驻 NavigationRail + 内容区（PLAT-02 自适应）。分享/剪贴板入口在两种布局下共用同一导入流。
 */
@Composable
fun NfMobileApp() {
    val context = LocalContext.current
    val store = remember { LibraryStore(context.filesDir) }
    var nav by remember { mutableStateOf(NavState()) }
    var importPrefill by remember { mutableStateOf<SharePayload?>(null) }
    val layout = currentLayoutClass()

    val pending = ShareHandoff.pending
    LaunchedEffect(pending) {
        val payload = ShareHandoff.consume()
        if (payload != null) {
            importPrefill = payload
            nav = nav.push(Screen.IMPORT)
        }
    }

    if (layout == LayoutClass.COMPACT) {
        BackHandler(enabled = nav.canPop) { nav = nav.pop() }
        ScreenContent(nav, store, importPrefill) { nav = it }
    } else {
        Row(modifier = Modifier.fillMaxSize()) {
            AdaptiveNavigationRail(current = nav.current) { screen -> nav = nav.reset(screen) }
            Box(modifier = Modifier.weight(1f)) {
                ScreenContent(nav, store, importPrefill) { nav = it }
            }
        }
    }
}

@Composable
private fun ScreenContent(
    nav: NavState,
    store: LibraryStore,
    importPrefill: SharePayload?,
    setNav: (NavState) -> Unit
) {
    val pop = { setNav(nav.pop()) }
    when (nav.current) {
        Screen.HOME -> HomeScreen(
            store = store,
            onOpen = { screen -> setNav(nav.push(screen)) }
        )
        Screen.IMPORT -> ImportScreen(prefill = importPrefill, store = store, onBack = pop)
        Screen.PROTOCOL -> ProtocolScreen(onBack = pop)
        Screen.GRAPH -> GraphScreen(store = store, onBack = pop)
        Screen.ASSEMBLY -> AssemblyScreen(onBack = pop)
        Screen.PACK_UPDATE -> PackUpdateScreen(store = store, onBack = pop)
        Screen.CCOS -> CcosScreen(onBack = pop)
        Screen.SETTINGS -> SettingsScreen(onBack = pop)
    }
}
