package dev.ninfenz.mobile.ui

import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.VerticalDivider
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.ui.shell.Detail
import dev.ninfenz.mobile.ui.shell.TopDestination
import dev.ninfenz.mobile.ui.theme.NfLayout
import dev.ninfenz.mobile.ui.theme.NfMotion

/** 应用外壳骨架：内容容器、自适应导航栏与 Scaffold 装配（原 NfMobileApp 内联结构）。 */
@Composable
private fun NfContentFrame(content: @Composable () -> Unit) {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.TopCenter) {
        Box(modifier = Modifier.fillMaxHeight().widthIn(max = NfLayout.contentMaxWidth)) {
            content()
        }
    }
}

@Composable
private fun NfProjectImportLauncher(host: NfShellHost) {
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) host.importProject(uri)
    }
    host.launchProjectImport = { launcher.launch(arrayOf("application/zip", "*/*")) }
}

@Composable
internal fun NfShellFrame(host: NfShellHost) {
    val compact = layoutClassFor(currentWindowWidthDp()) == LayoutClass.COMPACT
    BackHandler(enabled = host.shell.detail != null || host.shell.destination != TopDestination.LIBRARY) {
        host.backToLibrary()
    }
    Scaffold(
        contentWindowInsets = WindowInsets(0),
        bottomBar = {
            if (compact && host.shell.detail == null) {
                NfBottomBar(host.shell.destination) { host.select(it) }
            }
        },
    ) { padding ->
        Row(modifier = Modifier.fillMaxSize()) {
            if (!compact) {
                NfRail(host.shell.destination) { host.select(it) }
            }
            Box(modifier = Modifier.weight(1f).padding(padding)) {
                Crossfade(
                    targetState = host.shell.detail,
                    animationSpec = tween(durationMillis = NfMotion.MEDIUM_MS),
                    label = "nf-shell"
                ) { detail ->
                    NfShellContent(host, detail, compact)
                }
            }
        }
    }
}

@Composable
private fun NfShellContent(host: NfShellHost, detail: Detail?, compact: Boolean) {
    if (detail == null) {
        NfContentFrame { NfTopLevelContent(host) }
    } else if (!compact && currentWindowWidthDp() >= 840) {
        NfSplitContent(host, detail)
    } else {
        NfContentFrame { NfDetailContent(host, detail) }
    }
}

@Composable
private fun NfSplitContent(host: NfShellHost, detail: Detail) {
    Row(modifier = Modifier.fillMaxSize()) {
        Box(modifier = Modifier.width(380.dp).fillMaxHeight()) {
            NfContentFrame { NfTopLevelContent(host) }
        }
        VerticalDivider()
        Box(modifier = Modifier.weight(1f)) {
            NfContentFrame { NfDetailContent(host, detail) }
        }
    }
}

/** 供 NfMobileApp 调用的入口：注册导入 Launcher 并挂载外壳。 */
@Composable
internal fun NfShellRoot(host: NfShellHost) {
    NfProjectImportLauncher(host)
    NfShellFrame(host)
}

private val bottomDestinations = listOf(
    TopDestination.LIBRARY,
    TopDestination.FLOW,
    TopDestination.ME
)

@Composable
private fun NfDestinationIcon(destination: TopDestination) {
    Icon(destinationIcon(destination), contentDescription = null)
}

@Composable
private fun NfBottomBar(current: TopDestination, onSelect: (TopDestination) -> Unit) {
    NavigationBar {
        bottomDestinations.forEach { destination ->
            NavigationBarItem(
                selected = destination == current,
                onClick = { onSelect(destination) },
                icon = { NfDestinationIcon(destination) },
                label = { Text(stringResource(destination.labelRes)) }
            )
        }
    }
}

@Composable
private fun NfRail(current: TopDestination, onSelect: (TopDestination) -> Unit) {
    NavigationRail {
        bottomDestinations.forEach { destination ->
            NavigationRailItem(
                selected = destination == current,
                onClick = { onSelect(destination) },
                icon = { NfDestinationIcon(destination) },
                label = { Text(stringResource(destination.labelRes)) }
            )
        }
    }
}

private fun destinationIcon(destination: TopDestination) = when (destination) {
    TopDestination.LIBRARY -> Icons.Filled.Home
    TopDestination.FLOW -> Icons.Filled.PlayArrow
    TopDestination.CREATE -> Icons.Filled.Edit
    TopDestination.DELIVER -> Icons.AutoMirrored.Filled.List
    TopDestination.ME -> Icons.Filled.Person
}
