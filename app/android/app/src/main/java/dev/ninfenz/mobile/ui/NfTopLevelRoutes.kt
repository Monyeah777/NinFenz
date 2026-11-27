package dev.ninfenz.mobile.ui

import androidx.compose.runtime.Composable
import dev.ninfenz.mobile.ui.screens.CreateScreen
import dev.ninfenz.mobile.ui.screens.DeliverScreen
import dev.ninfenz.mobile.ui.screens.LibraryHomeScreen
import dev.ninfenz.mobile.ui.screens.MeScreen
import dev.ninfenz.mobile.ui.screens.WorkflowHubScreen
import dev.ninfenz.mobile.ui.shell.Detail
import dev.ninfenz.mobile.ui.shell.TopDestination

/** 顶层面（库/工作台/创作/交付/我的）路由，原 NfMobileApp.topLevelContent 内联 when。 */
@Composable
internal fun NfTopLevelContent(host: NfShellHost) {
    when (host.shell.destination) {
        TopDestination.LIBRARY -> NfLibraryDestination(host)
        TopDestination.FLOW -> NfFlowDestination(host)
        TopDestination.CREATE -> NfCreateDestination(host)
        TopDestination.DELIVER -> NfDeliverDestination(host)
        TopDestination.ME -> NfMeDestination(host)
    }
}

@Composable
private fun NfLibraryDestination(host: NfShellHost) {
    LibraryHomeScreen(
        packs = host.packs.packs,
        projects = host.projects,
        errors = host.packs.errors + host.projectErrors,
        seedState = host.seedState,
        seeding = host.seeding,
        onSeed = host::runSeed,
        onImport = {
            host.quickPasteImport = false
            host.open(Detail.Import)
        },
        onQuickPaste = {
            host.quickPasteImport = true
            host.open(Detail.Import)
        },
        onDailyText = { text ->
            ImportSeed.put(text)
            host.quickPasteImport = false
            host.open(Detail.Import)
        },
        onNewProject = { host.open(Detail.NewProject) },
        onOpenPack = { host.open(Detail.Pack(it.id, it.version)) },
        onOpenProject = { host.open(Detail.Project(it.project.id)) },
        onOpenFlow = { host.open(Detail.Flow(it.project.id)) },
        onSearch = { host.open(Detail.Search) },
        onPackCenter = { host.open(Detail.PackCenter) },
        onSettings = { host.open(Detail.Settings) },
        onCommands = { host.showCommands = true },
        archived = host.archivedProjects,
        onRestoreArchive = { file -> host.restoreArchive(file) },
        refreshing = host.refreshing,
        onRefresh = { host.refresh() }
    )
}

@Composable
private fun NfFlowDestination(host: NfShellHost) {
    WorkflowHubScreen(
        projects = host.projects,
        onOpenProject = { host.open(Detail.Project(it.project.id)) },
        onAuthor = { host.open(Detail.Author(it.project.id)) },
        onDelivery = { host.open(Detail.Delivery(it.project.id)) },
        onNewProject = { host.open(Detail.NewProject) },
        onImport = {
            host.quickPasteImport = false
            host.open(Detail.Import)
        }
    )
}

@Composable
private fun NfCreateDestination(host: NfShellHost) {
    CreateScreen(
        projects = host.projects,
        packs = host.packs.packs,
        onImport = { host.open(Detail.Import) },
        onCreateProject = { host.open(Detail.NewProject) },
        onOpenProject = { host.open(Detail.Project(it.project.id)) },
        onGoLibrary = { host.select(TopDestination.LIBRARY) },
        onLoadSample = host::runSeed
    )
}

@Composable
private fun NfDeliverDestination(host: NfShellHost) {
    DeliverScreen(
        projects = host.projects,
        onOpenProject = { host.open(Detail.Project(it.project.id)) },
        onOpenDelivery = { host.open(Detail.Delivery(it.project.id)) },
        onGoCreate = { host.select(TopDestination.CREATE) },
        onPackUpdate = { host.open(Detail.PackCenter) },
        onCcos = { host.open(Detail.Ccos) }
    )
}

@Composable
private fun NfMeDestination(host: NfShellHost) {
    MeScreen(
        themeMode = host.themeMode,
        onThemeMode = host.onThemeMode,
        languageMode = host.languageMode,
        onLanguageMode = host.onLanguageMode,
        dynamicColor = host.dynamicColor,
        onDynamicColor = host.onDynamicColor,
        storageText = host.storageText,
        nativeReady = host.nativeReady,
        abi = host.abi,
        onSettings = { host.open(Detail.Settings) },
        onAbout = { host.showAbout = true }
    )
}
