package dev.ninfenz.mobile.ui

import androidx.activity.compose.BackHandler
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
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

@Composable
fun NfMobileApp() {
    val context = LocalContext.current
    val store = remember { LibraryStore(context.filesDir) }
    var nav by remember { mutableStateOf(NavState()) }
    var importPrefill by remember { mutableStateOf<SharePayload?>(null) }

    val pending = ShareHandoff.pending
    LaunchedEffect(pending) {
        val payload = ShareHandoff.consume()
        if (payload != null) {
            importPrefill = payload
            nav = nav.push(Screen.IMPORT)
        }
    }

    BackHandler(enabled = nav.canPop) { nav = nav.pop() }

    when (nav.current) {
        Screen.HOME -> HomeScreen(
            store = store,
            onOpen = { screen -> nav = nav.push(screen) }
        )
        Screen.IMPORT -> ImportScreen(
            prefill = importPrefill,
            store = store,
            onBack = { nav = nav.pop() }
        )
        Screen.PROTOCOL -> ProtocolScreen(onBack = { nav = nav.pop() })
        Screen.GRAPH -> GraphScreen(store = store, onBack = { nav = nav.pop() })
        Screen.ASSEMBLY -> AssemblyScreen(onBack = { nav = nav.pop() })
        Screen.PACK_UPDATE -> PackUpdateScreen(store = store, onBack = { nav = nav.pop() })
        Screen.CCOS -> CcosScreen(onBack = { nav = nav.pop() })
        Screen.SETTINGS -> SettingsScreen(onBack = { nav = nav.pop() })
    }
}
