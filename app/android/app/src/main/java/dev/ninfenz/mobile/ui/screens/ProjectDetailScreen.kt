package dev.ninfenz.mobile.ui.screens
import dev.ninfenz.mobile.util.orNullLogged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.style.TextOverflow
import dev.ninfenz.mobile.ui.theme.NfMotion
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.outlined.Star as StarOutlined
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextField
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.data.UriIo
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.PackLockStore
import dev.ninfenz.mobile.data.PackTrustStore
import dev.ninfenz.mobile.data.PackVerifier
import dev.ninfenz.mobile.data.ProjectArchiver
import dev.ninfenz.mobile.data.ProjectEntry
import dev.ninfenz.mobile.data.RecentProjectStore
import dev.ninfenz.mobile.data.SeedResult
import dev.ninfenz.mobile.data.LanguageMode
import dev.ninfenz.mobile.data.ExtensionStore
import dev.ninfenz.mobile.data.LibraryMetaStore
import dev.ninfenz.mobile.data.SavedViewStore
import dev.ninfenz.mobile.data.SmartCollectionStore
import dev.ninfenz.mobile.data.LibraryViewStore
import dev.ninfenz.mobile.data.ThemeMode
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ProjectFilter
import dev.ninfenz.mobile.model.ProjectDiff
import dev.ninfenz.mobile.model.ProjectHistoryExport
import dev.ninfenz.mobile.model.ProjectModel
import dev.ninfenz.mobile.model.ProjectSort
import dev.ninfenz.mobile.model.ProjectSorter
import dev.ninfenz.mobile.model.ProjectStatus
import dev.ninfenz.mobile.share.ShareExporter
import dev.ninfenz.mobile.ui.components.NfActionBarSurface
import dev.ninfenz.mobile.ui.components.NfCard
import dev.ninfenz.mobile.ui.components.nfExpandableEnter
import dev.ninfenz.mobile.ui.components.nfExpandableExit
import dev.ninfenz.mobile.ui.components.SwipeableProjectCard
import dev.ninfenz.mobile.ui.components.NfEmptyState
import dev.ninfenz.mobile.ui.components.NfListRow
import dev.ninfenz.mobile.ui.components.NfSectionHeader
import dev.ninfenz.mobile.ui.components.NfStatusChip
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.theme.NfLayout
import dev.ninfenz.mobile.ui.design.NfType
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProjectDetailScreen(
    project: Project,
    onBack: () -> Unit,
    onAuthor: () -> Unit,
    onAssembly: () -> Unit,
    onDuplicate: () -> Unit = {},
    onChangePack: (PackEntry) -> Unit = {},
    packs: List<PackEntry> = emptyList(),
    onArchive: () -> Unit = {},
    onRename: (String) -> Unit = {},
    onReview: (Boolean, String, String) -> Unit = { _, _, _ -> },
    onReviewBlocks: () -> Unit = {},
    onFavoriteChanged: () -> Unit = {},
    onShare: () -> Unit = {},
    onShareFull: () -> Unit = {},
    onSaveAsTemplate: () -> Unit = {},
    onExportTemplatePackage: () -> Unit = {},
    onDelete: () -> Unit = {},
    onFlow: () -> Unit = {},
    compareCandidates: List<ProjectEntry> = emptyList()
) {
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val diffScope = rememberCoroutineScope()
    val historyExpandedState = rememberSaveable { mutableStateOf(false) }
    val reviewerState = rememberSaveable { mutableStateOf("") }
    val reviewNoteState = rememberSaveable { mutableStateOf("") }
    val s = remember {
        ProjectDetailState(
            project = project, context = context, clipboard = clipboard, diffScope = diffScope,
            packs = packs, compareCandidates = compareCandidates, projects = emptyList(),
            onBack = onBack, onAuthor = onAuthor, onAssembly = onAssembly, onDuplicate = onDuplicate, onChangePack = onChangePack, onArchive = onArchive, onRename = onRename, onReview = onReview, onReviewBlocks = onReviewBlocks, onFavoriteChanged = onFavoriteChanged, onShare = onShare, onShareFull = onShareFull, onSaveAsTemplate = onSaveAsTemplate, onExportTemplatePackage = onExportTemplatePackage, onDelete = onDelete, onFlow = onFlow,
            historyExpandedState = historyExpandedState, reviewerState = reviewerState, reviewNoteState = reviewNoteState
        )
    }
    s.project = project
    s.packs = packs
    s.compareCandidates = compareCandidates
    s.onBack = onBack
    s.onAuthor = onAuthor
    s.onAssembly = onAssembly
    s.onDuplicate = onDuplicate
    s.onChangePack = onChangePack
    s.onArchive = onArchive
    s.onRename = onRename
    s.onReview = onReview
    s.onReviewBlocks = onReviewBlocks
    s.onFavoriteChanged = onFavoriteChanged
    s.onShare = onShare
    s.onShareFull = onShareFull
    s.onSaveAsTemplate = onSaveAsTemplate
    s.onExportTemplatePackage = onExportTemplatePackage
    s.onDelete = onDelete
    s.onFlow = onFlow
    if (s.projectId != project.id) s.resetForProject(project)
    val diffPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: android.net.Uri? ->
        s.onDiffPicked(uri)
    }
    s.launchDiffPicker = { args -> diffPicker.launch(args) }
    s.templateReference = remember(project.id, s.hasSpecOverride) {
        dev.ninfenz.mobile.data.ProjectPaths.templateMd(context.filesDir, project.id)
            .takeIf { it.isFile }?.readText(Charsets.UTF_8)
    }
    LaunchedEffect(project.id, project.review.state, project.review.subjectDigest) { s.refreshReviewStale() }
    ProjectDetailContent(s)
    ProjectDetailTemplateRefDialog(s)
    ProjectDetailRemoveOverrideDialog(s)
    ProjectDetailMoreActionsSheet(s)
    ProjectDetailTagsDialog(s)
    ProjectDetailChangePackSheet(s)
    ProjectDetailDeleteDialog(s)
    ProjectDetailReviewDialog(s)
    ProjectDetailRenameDialog(s)
    ProjectDetailComparePickerDialog(s)
    ProjectDetailDiffErrorDialog(s)
    ProjectDetailDiffReportDialog(s)
    ProjectDetailArchiveDialog(s)
}

@Composable
fun PackDetailScreen(pack: PackEntry, onBack: () -> Unit, onUpdate: () -> Unit) {
    val context = LocalContext.current
    val audit = dev.ninfenz.mobile.data.FeatureGate.auditEnabled()
    val trustStore = remember { PackTrustStore(context.filesDir) }
    var pinnedTree by remember { mutableStateOf(trustStore.pinnedTree(pack.id, pack.version)) }
    val trustMatches = pinnedTree == null || pinnedTree == pack.tree
    var verifying by remember { mutableStateOf(false) }
    var report by remember { mutableStateOf<String?>(null) }
    var errorText by remember { mutableStateOf<String?>(null) }

    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = pack.title, onBack = onBack)
        LazyColumn(
            contentPadding = androidx.compose.foundation.layout.PaddingValues(NfSpacing.page),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
        ) {
            item {
                PackInfoCard(pack, audit, pinnedTree, trustMatches) {
                    if (pinnedTree != null && trustMatches) {
                        trustStore.clear(pack.id, pack.version)
                    } else {
                        trustStore.pin(pack.id, pack.version, pack.tree)
                    }
                    pinnedTree = trustStore.pinnedTree(pack.id, pack.version)
                }
            }
            item {
                if (audit) {
                    PackVerifyRow(
                        pack = pack,
                        verifying = verifying,
                        onVerifying = { verifying = it },
                        onReport = { report = it },
                        onErrorText = { errorText = it },
                        onUpdate = onUpdate
                    )
                }
            }
            if (report != null) {
                item {
                    Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = MaterialTheme.shapes.medium) {
                        Text(report!!, modifier = Modifier.padding(NfSpacing.m), style = NfType.meta)
                    }
                }
            }
            if (errorText != null) {
                item {
                    Surface(color = MaterialTheme.colorScheme.errorContainer, shape = MaterialTheme.shapes.medium) {
                        Text(errorText!!, modifier = Modifier.padding(NfSpacing.m), style = NfType.meta, color = MaterialTheme.colorScheme.onErrorContainer)
                    }
                }
            }
        }
    }
}

@Composable
internal fun PackInfoCard(
    pack: PackEntry,
    audit: Boolean,
    pinnedTree: String?,
    trustMatches: Boolean,
    onPinToggle: () -> Unit
) {
    val clipboard = LocalClipboardManager.current
    NfCard {
        Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
            Text(pack.id + " · " + pack.version, style = NfType.itemTitle)
            Text(pack.description, style = NfType.secondary)
            TextButton(onClick = {
                clipboard.setText(androidx.compose.ui.text.AnnotatedString(pack.id))
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.pack_detail_copy_id)) }
            Text(stringResource(dev.ninfenz.mobile.R.string.pack_detail_items, pack.itemCount), style = NfType.meta)
            Text(stringResource(dev.ninfenz.mobile.R.string.pack_detail_tree, pack.tree.take(16) + "…"), style = NfType.meta)
            Text(stringResource(dev.ninfenz.mobile.R.string.pack_detail_dir, pack.dir.absolutePath), style = NfType.meta)
            if (audit) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        when {
                            pinnedTree == null -> stringResource(dev.ninfenz.mobile.R.string.pack_trust_unpinned)
                            trustMatches -> stringResource(dev.ninfenz.mobile.R.string.pack_trust_pinned)
                            else -> stringResource(dev.ninfenz.mobile.R.string.pack_trust_mismatch)
                        },
                        style = NfType.meta,
                        color = when {
                            pinnedTree == null -> MaterialTheme.colorScheme.onSurfaceVariant
                            trustMatches -> MaterialTheme.colorScheme.primary
                            else -> MaterialTheme.colorScheme.error
                        },
                        modifier = Modifier.weight(1f)
                    )
                    TextButton(onClick = onPinToggle) {
                        Text(
                            stringResource(
                                when {
                                    pinnedTree == null -> dev.ninfenz.mobile.R.string.pack_trust_pin
                                    trustMatches -> dev.ninfenz.mobile.R.string.pack_trust_clear
                                    else -> dev.ninfenz.mobile.R.string.pack_trust_update
                                }
                            )
                        )
                    }
                }
            }
        }
    }
}

@Composable
internal fun PackVerifyRow(
    pack: PackEntry,
    verifying: Boolean,
    onVerifying: (Boolean) -> Unit,
    onReport: (String?) -> Unit,
    onErrorText: (String?) -> Unit,
    onUpdate: () -> Unit
) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
        Button(
            onClick = {
                if (verifying) return@Button
                onVerifying(true)
                onErrorText(null)
                onReport(null)
                scope.launch {
                    val response = PackVerifier().verify(pack)
                    val result = response.resultObject()
                    val verdict = result?.get("verdict")?.let { it.toString().trim('"') }
                    val issues = result?.get("issues")?.toString() ?: ""
                    if (response.ok) {
                        onReport(context.getString(dev.ninfenz.mobile.R.string.validate_passed, verdict ?: "pass") + (if (issues == "[]") "" else " · issues=" + issues))
                    } else {
                        val err = response.error
                        onErrorText(
                            "[" + (err?.code ?: "NF-VAL-001") + "] " +
                                (err?.message ?: context.getString(dev.ninfenz.mobile.R.string.validate_failed)) +
                                context.getString(dev.ninfenz.mobile.R.string.error_fix_suffix) +
                                (err?.fix ?: context.getString(dev.ninfenz.mobile.R.string.view_diagnostics))
                        )
                    }
                    onVerifying(false)
                }
            },
            enabled = !verifying
        ) { Text(if (verifying) context.getString(dev.ninfenz.mobile.R.string.validating) else context.getString(dev.ninfenz.mobile.R.string.validate_pack)) }
        Button(onClick = onUpdate) { Text(stringResource(dev.ninfenz.mobile.R.string.pack_detail_update)) }
    }
}

@Composable
fun projectStatusLabel(project: Project): String = projectStatusLabel(project.status)

@Composable
fun projectStatusLabel(status: dev.ninfenz.mobile.model.ProjectStatus): String = when (status) {
    dev.ninfenz.mobile.model.ProjectStatus.DRAFT -> stringResource(dev.ninfenz.mobile.R.string.status_draft)
    dev.ninfenz.mobile.model.ProjectStatus.AUTHORING -> stringResource(dev.ninfenz.mobile.R.string.status_authoring)
    dev.ninfenz.mobile.model.ProjectStatus.ASSEMBLED -> stringResource(dev.ninfenz.mobile.R.string.status_assembled)
    dev.ninfenz.mobile.model.ProjectStatus.VALIDATED ->
        if (dev.ninfenz.mobile.data.FeatureGate.auditEnabled()) stringResource(dev.ninfenz.mobile.R.string.status_validated)
        else stringResource(dev.ninfenz.mobile.R.string.status_exported)
    dev.ninfenz.mobile.model.ProjectStatus.EXPORTED -> stringResource(dev.ninfenz.mobile.R.string.status_exported)
    dev.ninfenz.mobile.model.ProjectStatus.REVIEWED ->
        if (dev.ninfenz.mobile.data.FeatureGate.auditEnabled()) stringResource(dev.ninfenz.mobile.R.string.status_reviewed)
        else stringResource(dev.ninfenz.mobile.R.string.status_exported)
}

@Composable
fun themeModeLabel(mode: ThemeMode): String = when (mode) {
    ThemeMode.SYSTEM -> stringResource(dev.ninfenz.mobile.R.string.theme_system)
    ThemeMode.LIGHT -> stringResource(dev.ninfenz.mobile.R.string.theme_light)
    ThemeMode.DARK -> stringResource(dev.ninfenz.mobile.R.string.theme_dark)
}
