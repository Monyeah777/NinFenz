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

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun LibraryHomeScreen(
    packs: List<PackEntry>,
    projects: List<ProjectEntry>,
    errors: List<String>,
    seedState: SeedResult?,
    seeding: Boolean,
    onSeed: () -> Unit,
    onImport: () -> Unit,
    onQuickPaste: () -> Unit = {},
    onDailyText: (String) -> Unit = {},
    onNewProject: () -> Unit = {},
    onOpenPack: (PackEntry) -> Unit,
    onOpenProject: (ProjectEntry) -> Unit,
    onOpenFlow: (ProjectEntry) -> Unit = {},
    onSearch: () -> Unit,
    onPackCenter: () -> Unit,
    onSettings: () -> Unit,
    onCommands: () -> Unit = {},
    archived: List<File> = emptyList(),
    onRestoreArchive: (File) -> Unit = {},
    refreshing: Boolean = false,
    onRefresh: () -> Unit = {}
) {
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val snackbarScope = rememberCoroutineScope()
    val viewFilesDirInit = remember { runCatching { context.filesDir }.orNullLogged("TopLevelScreens") }
    val savedViewInit = remember(viewFilesDirInit) { viewFilesDirInit?.let { LibraryViewStore(it) }?.load() }
    val dailyTextState = rememberSaveable { mutableStateOf("") }
    val statusFilterState = rememberSaveable { mutableStateOf(savedViewInit?.status) }
    val favoritesOnlyState = rememberSaveable { mutableStateOf(false) }
    val viewNameState = rememberSaveable { mutableStateOf("") }
    val tagFilterState = rememberSaveable { mutableStateOf(null as String?) }
    val sortNameState = rememberSaveable { mutableStateOf(savedViewInit?.sort ?: ProjectSort.RECENT.name) }
    val projectsExpandedState = rememberSaveable { mutableStateOf(true) }
    val groupModeState = rememberSaveable { mutableStateOf("none") }
    val selectionModeState = rememberSaveable { mutableStateOf(false) }
    val s = remember {
        LibraryHomeState(
            context = context, clipboard = clipboard, snackbarScope = snackbarScope,
            packs = packs, projects = projects, errors = errors, seedState = seedState, seeding = seeding,
            archived = archived, refreshing = refreshing,
            onSeed = onSeed, onImport = onImport, onQuickPaste = onQuickPaste, onDailyText = onDailyText,
            onNewProject = onNewProject, onOpenPack = onOpenPack, onOpenProject = onOpenProject,
            onOpenFlow = onOpenFlow, onSearch = onSearch, onPackCenter = onPackCenter,
            onSettings = onSettings, onCommands = onCommands, onRestoreArchive = onRestoreArchive,
            onRefresh = onRefresh,
            dailyTextState = dailyTextState, statusFilterState = statusFilterState, favoritesOnlyState = favoritesOnlyState, viewNameState = viewNameState, tagFilterState = tagFilterState, sortNameState = sortNameState, projectsExpandedState = projectsExpandedState, groupModeState = groupModeState, selectionModeState = selectionModeState
        )
    }
    s.packs = packs
    s.projects = projects
    s.errors = errors
    s.seedState = seedState
    s.seeding = seeding
    s.archived = archived
    s.refreshing = refreshing
    s.onSeed = onSeed
    s.onImport = onImport
    s.onQuickPaste = onQuickPaste
    s.onDailyText = onDailyText
    s.onNewProject = onNewProject
    s.onOpenPack = onOpenPack
    s.onOpenProject = onOpenProject
    s.onOpenFlow = onOpenFlow
    s.onSearch = onSearch
    s.onPackCenter = onPackCenter
    s.onSettings = onSettings
    s.onCommands = onCommands
    s.onRestoreArchive = onRestoreArchive
    s.onRefresh = onRefresh
    LaunchedEffect(s.statusFilter, s.sortName) { s.viewStore?.save(s.statusFilter, s.sortName) }
    s.filterStatus = s.statusFilter?.let { ProjectStatus.fromWire(it) }
    s.filterSort = ProjectSort.entries.firstOrNull { it.name == s.sortName } ?: ProjectSort.RECENT
    s.favoriteIds = remember(s.projects, s.metaVersion) { s.metaStore?.favorites() ?: emptySet() }
    s.allTags = remember(s.projects) { s.metaStore?.allTags() ?: emptySet() }
    s.allViews = s.savedViews + s.extensionViews
    s.statusLabels = ProjectStatus.entries.associateWith { projectStatusLabel(it) }
    s.filteredProjects = remember(s.projects, s.statusFilter, s.sortName, s.recentIds, s.favoritesOnly, s.favoriteIds, s.activeCollection, s.allTags) {
                var base = if (s.favoritesOnly) s.projects.filter { it.project.id in s.favoriteIds } else s.projects
        if (s.tagFilter != null) base = base.filter { s.tagFilter in (s.metaStore?.tags(it.project.id) ?: emptySet()) }
        val collection = s.activeCollection
        if (collection != null && s.smartStore != null && s.metaStore != null) {
            base = base.filter { s.smartStore.matches(collection, it, s.metaStore) }
        }
        ProjectSorter.sort(
            ProjectFilter.apply(base, s.filterStatus),
            s.filterSort,
            priorityIds = if (s.filterSort == ProjectSort.RECENT) s.recentIds else emptyList()
        )
    }
    s.groupedProjects = remember(s.filteredProjects, s.groupMode, s.statusLabels) {
                when (s.groupMode) {
            "pack" -> s.filteredProjects.groupBy { it.project.refs.basePackId }.toList()
            "status" -> s.filteredProjects.groupBy { s.statusLabels[it.project.status] ?: it.project.status.wire }.toList()
            "tag" -> s.filteredProjects.groupBy { entry ->
                s.metaStore?.tags(entry.project.id)?.sorted()?.firstOrNull()
                    ?: s.context.getString(dev.ninfenz.mobile.R.string.library_untagged)
            }.toList()
            else -> listOf("" to s.filteredProjects)
        }
    }
    Box(modifier = Modifier.fillMaxSize().imePadding(), contentAlignment = Alignment.TopCenter) {
        LibraryHomeColumn(s)
        LibraryHomeUndoBar(s, Modifier.align(Alignment.BottomCenter))
    }
    LibraryHomeSaveViewDialog(s)
    LibraryHomeDeleteArchiveDialog(s)
}

@Composable
internal fun SeedLine(seed: SeedResult?) {
    when (seed) {
        is SeedResult.Installed -> Text(
            stringResource(dev.ninfenz.mobile.R.string.library_seed_ready, seed.id, seed.version),
            style = NfType.meta,
            color = MaterialTheme.colorScheme.primary
        )
        is SeedResult.AlreadyPresent -> Text(
            stringResource(dev.ninfenz.mobile.R.string.library_seed_exists, seed.id, seed.version),
            style = NfType.meta,
            color = MaterialTheme.colorScheme.primary
        )
        is SeedResult.Failed -> Text(
            seed.message,
            style = NfType.meta,
            color = MaterialTheme.colorScheme.error
        )
        null -> Unit
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun CreateScreen(
    projects: List<ProjectEntry>,
    packs: List<PackEntry>,
    onImport: () -> Unit,
    onCreateProject: () -> Unit,
    onOpenProject: (ProjectEntry) -> Unit,
    onGoLibrary: () -> Unit,
    onLoadSample: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = stringResource(dev.ninfenz.mobile.R.string.nav_create))
        if (packs.isEmpty()) {
            CreateNoPackState(onLoadSample, onImport)
        } else {
            LazyColumn(
                contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = NfSpacing.l),
                verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
            ) {
                item { CreateNewProjectCard(onCreateProject) }
                if (projects.isEmpty()) {
                    item { CreateNoProjectState(onCreateProject, onGoLibrary) }
                } else {
                    stickyHeader(key = "create-projects-header") { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.create_section_projects)) }
                    items(projects.size) { index ->
                        val entry = projects[index]
                        CreateProjectCard(entry, onOpenProject)
                    }
                }
            }
        }
    }
}
