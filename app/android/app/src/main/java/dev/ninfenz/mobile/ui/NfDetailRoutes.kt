package dev.ninfenz.mobile.ui

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Info
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import dev.ninfenz.mobile.ui.components.NfEmptyState
import dev.ninfenz.mobile.ui.screens.AssemblyScreen
import dev.ninfenz.mobile.ui.screens.AuthorScreen
import dev.ninfenz.mobile.ui.screens.CcosScreen
import dev.ninfenz.mobile.ui.screens.DecisionLogScreen
import dev.ninfenz.mobile.ui.screens.DeliveryScreen
import dev.ninfenz.mobile.ui.screens.DesignSystemScreen
import dev.ninfenz.mobile.ui.screens.ErrorCodesScreen
import dev.ninfenz.mobile.ui.screens.ExtensionCenterScreen
import dev.ninfenz.mobile.ui.screens.GraphScreen
import dev.ninfenz.mobile.ui.screens.ImportScreen
import dev.ninfenz.mobile.ui.screens.InboxScreen
import dev.ninfenz.mobile.ui.screens.NewProjectScreen
import dev.ninfenz.mobile.ui.screens.NfDocMergeScreen
import dev.ninfenz.mobile.ui.screens.PackBuilderScreen
import dev.ninfenz.mobile.ui.screens.PackCenterScreen
import dev.ninfenz.mobile.ui.screens.PackDetailScreen
import dev.ninfenz.mobile.ui.screens.PackUpdateScreen
import dev.ninfenz.mobile.ui.screens.PatchScreen
import dev.ninfenz.mobile.ui.screens.ProjectDetailScreen
import dev.ninfenz.mobile.ui.screens.ProjectFlowScreen
import dev.ninfenz.mobile.ui.screens.ProjectReviewScreen
import dev.ninfenz.mobile.ui.screens.ProtocolScreen
import dev.ninfenz.mobile.ui.screens.SearchScreen
import dev.ninfenz.mobile.ui.screens.SettingsScreen
import dev.ninfenz.mobile.ui.screens.TemplateGalleryScreen
import dev.ninfenz.mobile.ui.shell.Detail
import dev.ninfenz.mobile.ui.shell.TopDestination

/** 详情层路由，原 NfMobileApp.detailContent 内联 when。 */
@Composable
internal fun NfDetailContent(host: NfShellHost, detail: Detail) {
    when (detail) {
        is Detail.Inbox -> NfInboxDetail(host)
        is Detail.Import -> NfImportDetail(host)
        is Detail.NewProject -> NfNewProjectDetail(host)
        is Detail.Search -> NfSearchDetail(host)
        is Detail.DesignSystem -> DesignSystemScreen(onBack = host::back)
        is Detail.DecisionLog -> DecisionLogScreen(onBack = host::back)
        is Detail.Settings -> NfSettingsDetail(host)
        is Detail.ErrorCodes -> ErrorCodesScreen(onBack = host::back)
        is Detail.Extensions -> ExtensionCenterScreen(onBack = host::back)
        is Detail.Templates -> NfTemplatesDetail(host)
        is Detail.Author -> NfAuthorDetail(host, detail.id)
        is Detail.Protocol -> ProtocolScreen(onBack = host::back)
        is Detail.Graph -> GraphScreen(store = host.library, onBack = host::back)
        is Detail.Delivery -> NfDeliveryDetail(host, detail.id)
        is Detail.PackBuilder -> NfPackBuilderDetail(host, detail.id)
        is Detail.Review -> NfReviewDetail(host, detail.id)
        is Detail.Flow -> NfFlowDetail(host, detail.id)
        is Detail.Assembly -> AssemblyScreen(onBack = host::back)
        is Detail.PackCenter -> NfPackCenterDetail(host)
        is Detail.PackUpdate -> PackUpdateScreen(
            store = host.library,
            onBack = host::back,
            onOpenProject = { id -> host.open(Detail.Project(id)) }
        )
        is Detail.Ccos -> CcosScreen(onBack = host::back)
        is Detail.NfDocMerge -> NfDocMergeScreen(host.context.filesDir, onBack = host::back)
        is Detail.Patch -> PatchScreen(host.context.filesDir, detail.projectId, onBack = host::back)
        is Detail.Pack -> NfPackDetail(host, detail)
        is Detail.Project -> NfProjectDetail(host, detail.id)
    }
}

@Composable
private fun NfMissingProject(host: NfShellHost, icon: ImageVector) {
    NfEmptyState(
        icon = icon,
        title = stringResource(dev.ninfenz.mobile.R.string.project_missing_title),
        message = stringResource(dev.ninfenz.mobile.R.string.project_missing_body),
        actionLabel = stringResource(dev.ninfenz.mobile.R.string.back_to_library),
        onAction = host::back
    )
}

@Composable
private fun NfMissingPack(host: NfShellHost) {
    NfEmptyState(
        icon = Icons.Filled.Home,
        title = stringResource(dev.ninfenz.mobile.R.string.pack_missing_title),
        message = stringResource(dev.ninfenz.mobile.R.string.pack_missing_body),
        actionLabel = stringResource(dev.ninfenz.mobile.R.string.back_to_library),
        onAction = host::back
    )
}

@Composable
private fun NfInboxDetail(host: NfShellHost) {
    InboxScreen(
        onBack = host::back,
        onImport = { payload ->
            host.sharedPrefill = payload
            host.open(Detail.Import)
        }
    )
}

@Composable
private fun NfImportDetail(host: NfShellHost) {
    ImportScreen(
        prefill = host.sharedPrefill,
        store = host.library,
        onBack = {
            host.sharedPrefill = null
            host.back()
        },
        onPrefillConsumed = { host.sharedPrefill = null },
        autoClipboard = host.quickPasteImport,
        onAutoClipboardConsumed = { host.quickPasteImport = false },
        packs = host.packs.packs,
        onBundleImported = { host.onBundleImported() },
        onProjectImported = { id, packId, packVersion -> host.openProjectImported(id, packId, packVersion) },
        onCreateProjectFromDraft = { pack, title, draft -> host.createProjectFromDraft(pack, title, draft, false) },
        onCreateProjectFromTemplate = { pack, title, spec, templateText -> host.createProjectFromTemplate(pack, title, spec, templateText) },
        onQuickProjectFromDraft = { pack, title, draft -> host.createProjectFromDraft(pack, title, draft, true) }
    )
}

@Composable
private fun NfNewProjectDetail(host: NfShellHost) {
    NewProjectScreen(
        packs = host.packs.packs,
        creating = host.creatingProject,
        error = host.createError,
        onBack = host::back,
        onLoadSample = {
            host.select(TopDestination.LIBRARY)
            host.runSeed()
        },
        onCreate = { pack, title -> host.createProject(pack, title) }
    )
}

@Composable
private fun NfSearchDetail(host: NfShellHost) {
    SearchScreen(
        onBack = host::back,
        onOpenPack = { id, version -> host.open(Detail.Pack(id, version)) },
        onOpenProject = { id -> host.open(Detail.Project(id)) },
        packIds = host.packs.packs.map { it.id }.distinct().sorted(),
        projects = host.projects
    )
}

@Composable
private fun NfSettingsDetail(host: NfShellHost) {
    SettingsScreen(
        onBack = host::back,
        onErrorCodes = { host.open(Detail.ErrorCodes) },
        onDataRestored = { host.refresh() },
        onNfDocMerge = { host.open(Detail.NfDocMerge) },
        onPatch = { host.open(Detail.Patch()) },
        onDesignSystem = { host.open(Detail.DesignSystem) },
        onDecisionLog = { host.open(Detail.DecisionLog) },
        onExtensions = { host.open(Detail.Extensions) },
        onTemplates = { host.open(Detail.Templates) },
        onThemeMode = host.onThemeMode,
        onLanguageMode = host.onLanguageMode,
        onDynamicColor = host.onDynamicColor
    )
}

@Composable
private fun NfTemplatesDetail(host: NfShellHost) {
    TemplateGalleryScreen(
        onBack = host::back,
        packs = host.packs.packs,
        onUse = { file, pack, title -> host.useTemplate(file, pack, title) }
    )
}

@Composable
private fun NfAuthorDetail(host: NfShellHost, id: String) {
    val entry = host.projects.firstOrNull { it.project.id == id }
    if (entry == null) {
        NfMissingProject(host, Icons.Filled.Edit)
    } else {
        val pack = host.packs.packs.firstOrNull {
            it.id == entry.project.refs.basePackId && it.version == entry.project.refs.basePackVersion
        }
        AuthorScreen(
            project = entry.project,
            pack = pack,
            onBack = host::back,
            onOpenPacks = { host.open(Detail.PackCenter) },
            onAssembly = { host.open(Detail.Delivery(entry.project.id)) },
            onSaved = { host.refresh() }
        )
    }
}

@Composable
private fun NfDeliveryDetail(host: NfShellHost, id: String) {
    val entry = host.projects.firstOrNull { it.project.id == id }
    if (entry == null) {
        NfMissingProject(host, Icons.Filled.Info)
    } else {
        val pack = host.packs.packs.firstOrNull {
            it.id == entry.project.refs.basePackId && it.version == entry.project.refs.basePackVersion
        }
        DeliveryScreen(
            project = entry.project,
            pack = pack,
            onBack = host::back,
            onOpenPacks = { host.open(Detail.PackCenter) },
            onPatch = { host.open(Detail.Patch(entry.project.id)) },
            onStatusChanged = { host.refresh() }
        )
    }
}

@Composable
private fun NfPackBuilderDetail(host: NfShellHost, id: String) {
    PackBuilderScreen(
        draftId = id,
        onBack = host::back,
        onInstalled = { host.refresh() }
    )
}

@Composable
private fun NfReviewDetail(host: NfShellHost, id: String) {
    val entry = host.projects.firstOrNull { it.project.id == id }
    if (entry == null) {
        NfMissingProject(host, Icons.Filled.Info)
    } else {
        ProjectReviewScreen(project = entry.project, onBack = host::back)
    }
}

@Composable
private fun NfFlowDetail(host: NfShellHost, id: String) {
    val entry = host.projects.firstOrNull { it.project.id == id }
    if (entry == null) {
        NfMissingProject(host, Icons.Filled.Info)
    } else {
        ProjectFlowScreen(
            project = entry.project,
            onBack = host::back,
            onAuthor = { host.open(Detail.Author(entry.project.id)) },
            onDelivery = { host.open(Detail.Delivery(entry.project.id)) }
        )
    }
}

@Composable
private fun NfPackCenterDetail(host: NfShellHost) {
    PackCenterScreen(
        packs = host.packs.packs,
        projects = host.projects,
        onUninstall = { pack -> host.uninstallPack(pack) },
        onBack = host::back,
        onOpenPack = { pack -> host.open(Detail.Pack(pack.id, pack.version)) },
        onUpdatePlan = { host.open(Detail.PackUpdate) },
        onLoadSample = host::runSeed,
        onNewPackDraft = { host.newPackDraft() },
        refreshing = host.refreshing,
        onRefresh = { host.refresh() }
    )
}

@Composable
private fun NfPackDetail(host: NfShellHost, detail: Detail.Pack) {
    val pack = host.packs.packs.firstOrNull { it.id == detail.id && it.version == detail.version }
    if (pack == null) {
        NfMissingPack(host)
    } else {
        PackDetailScreen(pack, onBack = host::back, onUpdate = { host.open(Detail.PackUpdate) })
    }
}

@Composable
private fun NfProjectDetail(host: NfShellHost, id: String) {
    val entry = host.projects.firstOrNull { it.project.id == id }
    if (entry == null) {
        NfMissingProject(host, Icons.Filled.Edit)
    } else {
        ProjectDetailScreen(
            project = entry.project,
            onBack = host::back,
            onAuthor = { host.open(Detail.Author(entry.project.id)) },
            onAssembly = { host.open(Detail.Delivery(entry.project.id)) },
            onFlow = { host.open(Detail.Flow(entry.project.id)) },
            onReviewBlocks = { host.open(Detail.Review(entry.project.id)) },
            onFavoriteChanged = { host.refresh() },
            compareCandidates = host.projects,
            onShare = { host.shareProject(entry) },
            onDelete = { host.deleteProject(entry) },
            onShareFull = { host.shareProjectFull(entry) },
            onSaveAsTemplate = { host.saveAsTemplate(entry) },
            onExportTemplatePackage = { host.exportTemplatePackage(entry) },
            onReview = { approve, reviewer, note -> host.reviewProject(entry, approve, reviewer, note) },
            onRename = { title -> host.renameProject(entry, title) },
            onArchive = { host.archiveProject(entry) },
            onDuplicate = { host.duplicateProject(entry) },
            packs = host.packs.packs,
            onChangePack = { pack -> host.changeProjectPack(entry, pack) }
        )
    }
}
