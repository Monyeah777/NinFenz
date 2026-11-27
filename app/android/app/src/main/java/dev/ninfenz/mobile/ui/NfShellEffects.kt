package dev.ninfenz.mobile.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import dev.ninfenz.mobile.data.CapabilityRegistry
import dev.ninfenz.mobile.data.CreateProjectResult
import dev.ninfenz.mobile.data.FeatureGate
import dev.ninfenz.mobile.share.ShareHandoff
import dev.ninfenz.mobile.ui.screens.OnboardingScreen
import dev.ninfenz.mobile.ui.shell.Detail
import dev.ninfenz.mobile.ui.shell.EditionRoutePolicy

/** 外壳副作用：路由净化、命令总线、生命周期刷新、分享接管与首启演示项目。 */
@Composable
internal fun NfShellEffects(host: NfShellHost) {
    LaunchedEffect(host.shell.detail, FeatureGate.tier(), CapabilityRegistry.revision) {
        val safe = EditionRoutePolicy.sanitize(host.shell)
        if (safe != host.shell) host.shell = safe
    }
    LaunchedEffect(Unit) {
        CommandBus.requests.collect { host.showCommands = true }
    }
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) host.refresh()
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }
    LaunchedEffect(Unit) { host.refresh() }
    // singleTop 再分享：观察 ShareHandoff.pending，而不是只在首次组合时消费。
    LaunchedEffect(ShareHandoff.pending) {
        val pending = ShareHandoff.consume()
        if (pending != null) {
            host.sharedPrefill = pending
            host.open(Detail.Import)
        }
    }
    // 示例载入且核心可用时，自动生成演示项目（失败不阻断，库页仍可手动新建）。
    LaunchedEffect(host.nativeReady, host.packs.packs.size, host.projects.size) {
        if (!host.demoTried && host.nativeReady && host.projects.isEmpty() && host.packs.packs.isNotEmpty()) {
            host.demoTried = true
            val pack = host.packs.packs.first()
            when (val result = host.projectCreator.create(pack, host.context.getString(dev.ninfenz.mobile.R.string.demo_project_title), "demo-project")) {
                is CreateProjectResult.Success -> host.refresh()
                is CreateProjectResult.Failure -> Unit
            }
        }
    }
}

@Composable
internal fun NfShortcutEffect(host: NfShellHost, shortcut: String?, onShortcutConsumed: () -> Unit) {
    LaunchedEffect(shortcut, host.onboardingDone) {
        if (host.onboardingDone && shortcut != null) {
            if (shortcut.startsWith("project:")) {
                val id = shortcut.removePrefix("project:")
                if (id.isNotBlank()) host.open(Detail.Project(id))
            } else {
                when (shortcut) {
                    "import" -> host.open(Detail.Import)
                    "inbox" -> host.open(Detail.Inbox)
                    "new_project" -> host.open(Detail.NewProject)
                    "search" -> host.open(Detail.Search)
                }
            }
            onShortcutConsumed()
        }
    }
}

@Composable
internal fun NfOnboardingGate(host: NfShellHost) {
    OnboardingScreen(
        seedState = host.seedState,
        seeding = host.seeding,
        onSeed = host::runSeed,
        onDone = {
            host.prefs.onboardingDone = true
            host.onboardingDone = true
            host.refresh()
        },
        onSkip = {
            host.prefs.onboardingDone = true
            host.onboardingDone = true
        }
    )
}
