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
import androidx.compose.runtime.MutableState
import androidx.compose.foundation.lazy.LazyListScope

internal class LibraryHomeState(
    val context: android.content.Context,
    val clipboard: androidx.compose.ui.platform.ClipboardManager,
    val snackbarScope: kotlinx.coroutines.CoroutineScope,
    var packs: List<PackEntry>,
    var projects: List<ProjectEntry>,
    var errors: List<String>,
    var seedState: SeedResult?,
    var seeding: Boolean,
    var archived: List<File>,
    var refreshing: Boolean,
    var onSeed: () -> Unit,
    var onImport: () -> Unit,
    var onQuickPaste: () -> Unit,
    var onDailyText: (String) -> Unit,
    var onNewProject: () -> Unit,
    var onOpenPack: (PackEntry) -> Unit,
    var onOpenProject: (ProjectEntry) -> Unit,
    var onOpenFlow: (ProjectEntry) -> Unit,
    var onSearch: () -> Unit,
    var onPackCenter: () -> Unit,
    var onSettings: () -> Unit,
    var onCommands: () -> Unit,
    var onRestoreArchive: (File) -> Unit,
    var onRefresh: () -> Unit,
    dailyTextState: androidx.compose.runtime.MutableState<String>,
    statusFilterState: androidx.compose.runtime.MutableState<String?>,
    favoritesOnlyState: androidx.compose.runtime.MutableState<Boolean>,
    viewNameState: androidx.compose.runtime.MutableState<String>,
    tagFilterState: androidx.compose.runtime.MutableState<String?>,
    sortNameState: androidx.compose.runtime.MutableState<String>,
    projectsExpandedState: androidx.compose.runtime.MutableState<Boolean>,
    groupModeState: androidx.compose.runtime.MutableState<String>,
    selectionModeState: androidx.compose.runtime.MutableState<Boolean>,
) {
    val viewFilesDir = runCatching { context.filesDir }.orNullLogged("TopLevelScreens")

    val viewStore = viewFilesDir?.let { LibraryViewStore(it) }

    val savedView = viewStore?.load()

    var pendingDeleteArchive by mutableStateOf<File?>(null)

    var undoArchive by mutableStateOf<File?>(null)

    val audit = dev.ninfenz.mobile.data.FeatureGate.auditEnabled()

    val savedViewStore = viewFilesDir?.let { SavedViewStore(it) }

    var savedViews by mutableStateOf(savedViewStore?.load() ?: emptyList())

    val extensionViews = runCatching {
                    ExtensionStore(context.filesDir).contributions(setOf("saved_view")).mapNotNull { c ->
                        savedViewStore?.fromExtension(c.id, c.config)
                    }
                }.getOrDefault(emptyList())

    val smartStore = viewFilesDir?.let { SmartCollectionStore(it) }

    val smartCollections = (smartStore?.load() ?: emptyList()) + runCatching {
                    ExtensionStore(context.filesDir).contributions(setOf("smart_collection")).mapNotNull { c ->
                        smartStore?.fromExtension(c.id, c.config)
                    }
                }.getOrDefault(emptyList())

    var activeCollection by mutableStateOf<SmartCollectionStore.Collection?>(null)

    var showSaveView by mutableStateOf(false)

    val metaStore = viewFilesDir?.let { LibraryMetaStore(it) }

    var metaVersion by mutableIntStateOf(0)

    var sortMenuOpen by mutableStateOf(false)

    var selectedIds by mutableStateOf<Set<String>>(emptySet())

    val recentStore = viewFilesDir?.let { RecentProjectStore(it) }

    var recentIds by mutableStateOf(recentStore?.load() ?: emptyList())

    var dailyText by dailyTextState

    var statusFilter by statusFilterState

    var favoritesOnly by favoritesOnlyState

    var viewName by viewNameState

    var tagFilter by tagFilterState

    var sortName by sortNameState

    var projectsExpanded by projectsExpandedState

    var groupMode by groupModeState

    var selectionMode by selectionModeState

    var filterStatus: ProjectStatus? = null
    var filterSort: ProjectSort = ProjectSort.RECENT
    var favoriteIds: Set<String> = emptySet()
    var allTags: Set<String> = emptySet()
    var allViews: List<SavedViewStore.View> = emptyList()
    var filteredProjects: List<ProjectEntry> = emptyList()
    var statusLabels: Map<ProjectStatus, String> = emptyMap()
    var groupedProjects: List<Pair<String, List<ProjectEntry>>> = emptyList()

    fun openWithPriority(entry: ProjectEntry) {
                recentIds = recentStore?.record(entry.project.id) ?: recentIds
        onOpenProject(entry)
    }
}

