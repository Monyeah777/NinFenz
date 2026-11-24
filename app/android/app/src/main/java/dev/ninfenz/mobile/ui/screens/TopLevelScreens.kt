package dev.ninfenz.mobile.ui.screens

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
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.PackTrustStore
import dev.ninfenz.mobile.data.PackVerifier
import dev.ninfenz.mobile.data.ProjectArchiver
import dev.ninfenz.mobile.data.ProjectEntry
import dev.ninfenz.mobile.data.RecentProjectStore
import dev.ninfenz.mobile.data.SeedResult
import dev.ninfenz.mobile.data.LanguageMode
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
import dev.ninfenz.mobile.ui.components.NfCard
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
    val viewFilesDir = remember { runCatching { context.filesDir }.getOrNull() }
    val viewStore = remember(viewFilesDir) { viewFilesDir?.let { LibraryViewStore(it) } }
    val savedView = remember { viewStore?.load() }
    var pendingDeleteArchive by remember { mutableStateOf<File?>(null) }
    var undoArchive by remember { mutableStateOf<File?>(null) }
    val snackbarScope = rememberCoroutineScope()
    var dailyText by rememberSaveable { mutableStateOf("") }
    var statusFilter by rememberSaveable { mutableStateOf(savedView?.status) }
    var sortName by rememberSaveable { mutableStateOf(savedView?.sort ?: ProjectSort.RECENT.name) }
    var sortMenuOpen by remember { mutableStateOf(false) }
    var projectsExpanded by rememberSaveable { mutableStateOf(true) }
    val recentStore = remember(viewFilesDir) { viewFilesDir?.let { RecentProjectStore(it) } }
    var recentIds by remember { mutableStateOf(recentStore?.load() ?: emptyList()) }
    LaunchedEffect(statusFilter, sortName) {
        viewStore?.save(statusFilter, sortName)
    }
    val filterStatus = statusFilter?.let { ProjectStatus.fromWire(it) }
    val filterSort = ProjectSort.entries.firstOrNull { it.name == sortName } ?: ProjectSort.RECENT
    val filteredProjects = remember(projects, statusFilter, sortName, recentIds) {
        ProjectSorter.sort(
            ProjectFilter.apply(projects, filterStatus),
            filterSort,
            priorityIds = if (filterSort == ProjectSort.RECENT) recentIds else emptyList()
        )
    }
    fun openWithPriority(entry: ProjectEntry) {
        recentIds = recentStore?.record(entry.project.id) ?: recentIds
        onOpenProject(entry)
    }

    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.TopCenter) {
    Column(modifier = Modifier.fillMaxSize().widthIn(max = NfLayout.contentMaxWidth)) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .statusBarsPadding()
                .padding(horizontal = NfSpacing.page, vertical = NfSpacing.s)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.library_header_title),
                        style = NfType.screenTitle
                    )
                    Text(
                        pluralStringResource(dev.ninfenz.mobile.R.plurals.library_header_projects, projects.size, projects.size) + " · " +
                            pluralStringResource(dev.ninfenz.mobile.R.plurals.library_header_packs, packs.size, packs.size),
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                TextButton(onClick = onCommands, modifier = Modifier.heightIn(min = 48.dp)) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.action_commands))
                }
                IconButton(onClick = onSearch, modifier = Modifier.size(48.dp)) { Icon(Icons.Filled.Search, contentDescription = stringResource(dev.ninfenz.mobile.R.string.action_search)) }
                IconButton(onClick = onSettings, modifier = Modifier.size(48.dp)) { Icon(Icons.Filled.Settings, contentDescription = stringResource(dev.ninfenz.mobile.R.string.action_settings)) }
            }
            Row(
                modifier = Modifier.padding(top = NfSpacing.s),
                horizontalArrangement = Arrangement.spacedBy(NfSpacing.s),
                verticalAlignment = Alignment.CenterVertically
            ) {
                if (projects.isEmpty()) {
                    OutlinedButton(onClick = onNewProject, modifier = Modifier.heightIn(min = 48.dp)) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.create_action_new))
                    }
                } else {
                    Button(onClick = onNewProject, modifier = Modifier.heightIn(min = 48.dp)) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.create_action_new))
                    }
                }
                TextButton(onClick = onImport, modifier = Modifier.heightIn(min = 48.dp)) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.library_import))
                }
            }
            SeedLine(seedState)
        }
        PullToRefreshBox(
            isRefreshing = refreshing,
            onRefresh = onRefresh,
            modifier = Modifier.fillMaxSize()
        ) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.l)
        ) {
            item {
                Surface(
                    shape = MaterialTheme.shapes.large,
                    color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.35f),
                    modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page)
                ) {
                    Column(
                        modifier = Modifier.padding(NfSpacing.l),
                        verticalArrangement = Arrangement.spacedBy(NfSpacing.s)
                    ) {
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.daily_title),
                            style = NfType.sectionTitle
                        )
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.daily_helper),
                            style = NfType.secondary,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        OutlinedTextField(
                            value = dailyText,
                            onValueChange = { dailyText = it },
                            modifier = Modifier.fillMaxWidth(),
                            placeholder = { Text(stringResource(dev.ninfenz.mobile.R.string.daily_hint)) },
                            minLines = 3,
                            maxLines = 6
                        )
                        OutlinedButton(
                            enabled = dailyText.isNotBlank(),
                            onClick = {
                                val text = dailyText.trim()
                                if (text.isNotEmpty()) {
                                    onDailyText(text)
                                    dailyText = ""
                                }
                            },
                            modifier = Modifier.heightIn(min = 48.dp)
                        ) { Text(stringResource(dev.ninfenz.mobile.R.string.daily_action)) }
                    }
                }
            }
            if (projects.isNotEmpty()) {
                item {
                    Surface(
                        shape = MaterialTheme.shapes.large,
                        color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.35f),
                        modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page)
                    ) {
                        Column(
                            modifier = Modifier.padding(NfSpacing.l),
                            verticalArrangement = Arrangement.spacedBy(NfSpacing.s)
                        ) {
                            Text(
                                stringResource(dev.ninfenz.mobile.R.string.library_quick_title),
                                style = NfType.sectionTitle
                            )
                            Text(
                                stringResource(dev.ninfenz.mobile.R.string.library_quick_body),
                                style = NfType.secondary,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                                OutlinedButton(onClick = onQuickPaste, modifier = Modifier.heightIn(min = 48.dp)) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.library_quick_paste))
                                }
                            }
                        }
                    }
                }
                item {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        LazyRow(
                            modifier = Modifier.weight(1f),
                            contentPadding = androidx.compose.foundation.layout.PaddingValues(start = NfSpacing.page, end = NfSpacing.s),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            item {
                                FilterChip(
                                    selected = filterStatus == null,
                                    onClick = { statusFilter = null },
                                    label = { Text(stringResource(dev.ninfenz.mobile.R.string.search_filter_all)) }
                                )
                            }
                            items(ProjectStatus.entries) { status ->
                                FilterChip(
                                    selected = filterStatus == status,
                                    onClick = { statusFilter = status.wire },
                                    label = { Text(projectStatusLabel(status)) }
                                )
                            }
                        }
                        val sortLabel = stringResource(dev.ninfenz.mobile.R.string.library_sort_label) + "：" +
                            when (filterSort) {
                                ProjectSort.RECENT -> stringResource(dev.ninfenz.mobile.R.string.library_sort_recent)
                                ProjectSort.TITLE -> stringResource(dev.ninfenz.mobile.R.string.library_sort_title)
                                ProjectSort.STATUS -> stringResource(dev.ninfenz.mobile.R.string.library_sort_status)
                            }
                        Box {
                            IconButton(
                                onClick = { sortMenuOpen = true },
                                modifier = Modifier
                                    .size(48.dp)
                                    .semantics { contentDescription = sortLabel }
                            ) {
                                Text("⇅", style = NfType.screenTitle)
                            }
                            androidx.compose.material3.DropdownMenu(
                                expanded = sortMenuOpen,
                                onDismissRequest = { sortMenuOpen = false }
                            ) {
                                ProjectSort.entries.forEach { mode ->
                                    androidx.compose.material3.DropdownMenuItem(
                                        text = {
                                            Text(
                                                when (mode) {
                                                    ProjectSort.RECENT -> stringResource(dev.ninfenz.mobile.R.string.library_sort_recent)
                                                    ProjectSort.TITLE -> stringResource(dev.ninfenz.mobile.R.string.library_sort_title)
                                                    ProjectSort.STATUS -> stringResource(dev.ninfenz.mobile.R.string.library_sort_status)
                                                }
                                            )
                                        },
                                        onClick = {
                                            sortName = mode.name
                                            sortMenuOpen = false
                                        }
                                    )
                                }
                            }
                        }
                    }
                }
            }
            if (packs.isEmpty() && projects.isEmpty()) {
                item {
                    NfEmptyState(
                        icon = Icons.Filled.Home,
                        title = stringResource(dev.ninfenz.mobile.R.string.library_empty_title),
                        message = stringResource(dev.ninfenz.mobile.R.string.library_empty_body),
                        actionLabel = stringResource(dev.ninfenz.mobile.R.string.library_action_load_sample),
                        onAction = onSeed,
                        secondaryLabel = stringResource(dev.ninfenz.mobile.R.string.library_action_import_file),
                        onSecondary = onImport
                    )
                }
            }
            if (filteredProjects.isNotEmpty()) {
                stickyHeader(key = "library-projects-header") {
                    val projectChevron by animateFloatAsState(
                        targetValue = if (projectsExpanded) 180f else 0f,
                        animationSpec = tween(durationMillis = NfMotion.MEDIUM_MS),
                        label = "library-projects-chevron"
                    )
                    NfSectionHeader(
                        stringResource(dev.ninfenz.mobile.R.string.library_section_projects),
                        action = {
                            IconButton(
                                onClick = { projectsExpanded = !projectsExpanded },
                                modifier = Modifier.size(48.dp)
                            ) {
                                Icon(
                                    Icons.Filled.KeyboardArrowDown,
                                    contentDescription = stringResource(
                                        if (projectsExpanded) dev.ninfenz.mobile.R.string.action_collapse
                                        else dev.ninfenz.mobile.R.string.action_expand
                                    ),
                                    modifier = Modifier.rotate(projectChevron)
                                )
                            }
                        }
                    )
                }
                item {
                    androidx.compose.animation.AnimatedVisibility(
                        visible = projectsExpanded,
                        enter = fadeIn(tween(NfMotion.SHORT_MS)) + expandVertically(
                            animationSpec = spring(dampingRatio = 0.82f, stiffness = 420f),
                            expandFrom = Alignment.Top
                        ),
                        exit = fadeOut(tween(NfMotion.SHORT_MS)) + shrinkVertically(
                            animationSpec = spring(dampingRatio = 0.9f, stiffness = 500f),
                            shrinkTowards = Alignment.Top
                        )
                    ) {
                        Column(
                            modifier = Modifier.padding(horizontal = NfSpacing.page),
                            verticalArrangement = Arrangement.spacedBy(NfSpacing.l)
                        ) {
                            filteredProjects.forEachIndexed { index, entry ->
                                SwipeableProjectCard(
                                    entry = entry,
                                    index = index,
                                    onOpen = { openWithPriority(entry) },
                                    onFlow = { onOpenFlow(entry) },
                                    onDelete = {
                                        snackbarScope.launch {
                                            val archived = runCatching {
                                                ProjectArchiver.archive(entry.file, context.filesDir)
                                            }.getOrNull()
                                            if (archived != null) {
                                                undoArchive = archived
                                                onRefresh()
                                            }
                                        }
                                    }
                                )
                            }
                        }
                    }
                }
            } else if (projects.isNotEmpty()) {
                item {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.library_filter_empty),
                            style = NfType.secondary,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.weight(1f)
                        )
                        TextButton(onClick = { statusFilter = null }) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.library_clear_filter))
                        }
                    }
                }
            }
            if (packs.isNotEmpty()) {
                stickyHeader(key = "library-packs-header") {
                    NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.library_section_packs), action = {
                        TextButton(onClick = onPackCenter) { Text(stringResource(dev.ninfenz.mobile.R.string.library_manage)) }
                    })
                }
                items(packs.size) { index ->
                    val pack = packs[index]
                    NfCard(
                        modifier = Modifier.padding(horizontal = NfSpacing.page),
                        onClick = { onOpenPack(pack) }
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(pack.title, style = NfType.itemTitle)
                                Text(
                                    pack.id + " · " + pack.version + " · " + context.getString(dev.ninfenz.mobile.R.string.pack_item_count, pack.itemCount),
                                    style = NfType.meta,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                            NfStatusChip(stringResource(dev.ninfenz.mobile.R.string.packcenter_installed))
                        }
                    }
                }
            }
            if (archived.isNotEmpty()) {
                stickyHeader(key = "library-archive-header") { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.library_section_archive)) }
                items(archived.size) { index ->
                    val file = archived[index]
                    NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(file.name, style = NfType.meta, modifier = Modifier.weight(1f))
                            TextButton(onClick = { onRestoreArchive(file) }) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.project_archive_restore))
                            }
                            TextButton(onClick = { pendingDeleteArchive = file }) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.project_archive_delete))
                            }
                        }
                    }
                }
            }
            if (errors.isNotEmpty()) {
                item {
                    Surface(
                        color = MaterialTheme.colorScheme.errorContainer,
                        shape = MaterialTheme.shapes.medium,
                        modifier = Modifier.padding(horizontal = NfSpacing.page)
                    ) {
                        Column(modifier = Modifier.padding(NfSpacing.m)) {
                            Text(pluralStringResource(dev.ninfenz.mobile.R.plurals.library_errors, errors.size, errors.size), style = NfType.itemTitle)
                            errors.take(3).forEach { Text(it, style = NfType.meta) }
                        }
                    }
                }
            }
        }
        }
    }
    androidx.compose.animation.AnimatedVisibility(
        visible = undoArchive != null,
        modifier = Modifier.align(Alignment.BottomCenter),
        enter = fadeIn(tween(NfMotion.SHORT_MS)) + slideInVertically(tween(NfMotion.MEDIUM_MS)) { it / 2 },
        exit = fadeOut(tween(NfMotion.SHORT_MS)) + slideOutVertically(tween(NfMotion.SHORT_MS)) { it / 2 }
    ) {
        undoArchive?.let { archived ->
            Surface(
                modifier = Modifier.padding(horizontal = NfSpacing.page, vertical = NfSpacing.m),
                shape = MaterialTheme.shapes.large,
                tonalElevation = 6.dp
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = NfSpacing.m, vertical = NfSpacing.xs),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
                ) {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.library_project_archived),
                        style = NfType.secondary,
                        modifier = Modifier.weight(1f)
                    )
                    TextButton(onClick = {
                        runCatching { ProjectArchiver.restore(archived, context.filesDir) }
                        undoArchive = null
                        onRefresh()
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.library_project_undo)) }
                    TextButton(onClick = { undoArchive = null }) {
                        Text(stringResource(android.R.string.cancel))
                    }
                }
            }
        }
    }
    }

    pendingDeleteArchive?.let { file ->
        AlertDialog(
            onDismissRequest = { pendingDeleteArchive = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.project_archive_delete)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.project_archive_delete_body, file.name)) },
            confirmButton = {
                TextButton(onClick = {
                    ProjectArchiver.delete(file, context.filesDir)
                    pendingDeleteArchive = null
                    onRefresh()
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.project_archive_delete)) }
            },
            dismissButton = {
                TextButton(onClick = { pendingDeleteArchive = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}

@Composable
private fun SeedLine(seed: SeedResult?) {
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
            NfEmptyState(
                icon = Icons.Filled.Edit,
                title = stringResource(dev.ninfenz.mobile.R.string.create_no_pack_title),
                message = stringResource(dev.ninfenz.mobile.R.string.create_no_pack_body),
                actionLabel = stringResource(dev.ninfenz.mobile.R.string.create_action_load_sample),
                onAction = onLoadSample,
                secondaryLabel = stringResource(dev.ninfenz.mobile.R.string.create_action_import),
                onSecondary = onImport
            )
        } else {
            LazyColumn(
                contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = NfSpacing.l),
                verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
            ) {
                item {
                    NfCard(
                        modifier = Modifier.padding(horizontal = NfSpacing.page),
                        onClick = onCreateProject
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
                            Icon(Icons.Filled.Add, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                            Column(modifier = Modifier.weight(1f)) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.create_from_pack), style = NfType.itemTitle)
                                Text(
                                    stringResource(dev.ninfenz.mobile.R.string.create_from_pack_subtitle),
                                    style = NfType.meta,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                    }
                }
                if (projects.isEmpty()) {
                    item {
                        NfEmptyState(
                            icon = Icons.Filled.Edit,
                            title = stringResource(dev.ninfenz.mobile.R.string.create_no_project_title),
                            message = stringResource(dev.ninfenz.mobile.R.string.create_no_project_body),
                            actionLabel = stringResource(dev.ninfenz.mobile.R.string.create_action_new),
                            onAction = onCreateProject,
                            secondaryLabel = stringResource(dev.ninfenz.mobile.R.string.create_action_library),
                            onSecondary = onGoLibrary
                        )
                    }
                } else {
                    stickyHeader(key = "create-projects-header") { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.create_section_projects)) }
                    items(projects.size) { index ->
                        val entry = projects[index]
                        NfCard(
                            modifier = Modifier.padding(horizontal = NfSpacing.page),
                            onClick = { onOpenProject(entry) }
                        ) {
                            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(entry.project.title, style = NfType.itemTitle, modifier = Modifier.weight(1f))
                                    NfStatusChip(projectStatusLabel(entry.project))
                                }
                                Text(
                                    "Pack " + entry.project.refs.basePackId + " · " + entry.project.refs.basePackVersion,
                                    style = NfType.meta,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun DeliverScreen(
    projects: List<ProjectEntry>,
    onOpenProject: (ProjectEntry) -> Unit,
    onOpenDelivery: (ProjectEntry) -> Unit,
    onGoCreate: () -> Unit,
    onPackUpdate: () -> Unit,
    onCcos: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = stringResource(dev.ninfenz.mobile.R.string.nav_deliver))
        if (projects.isEmpty()) {
            NfEmptyState(
                icon = Icons.AutoMirrored.Filled.List,
                title = stringResource(dev.ninfenz.mobile.R.string.deliver_empty_title),
                message = stringResource(dev.ninfenz.mobile.R.string.deliver_empty_body),
                actionLabel = stringResource(dev.ninfenz.mobile.R.string.deliver_action_create),
                onAction = onGoCreate,
                secondaryLabel = stringResource(dev.ninfenz.mobile.R.string.deliver_action_pack_update),
                onSecondary = onPackUpdate
            )
        } else {
            LazyColumn(
                contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = NfSpacing.l),
                verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
            ) {
                stickyHeader(key = "deliver-projects-header") { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.create_section_projects)) }
                items(projects.size) { index ->
                    val entry = projects[index]
                    NfCard(
                        modifier = Modifier.padding(horizontal = NfSpacing.page),
                        onClick = { onOpenProject(entry) }
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(entry.project.title, style = NfType.itemTitle)
                                Text(
                                    stringResource(dev.ninfenz.mobile.R.string.project_flow_label),
                                    style = NfType.meta,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                            Button(onClick = { onOpenDelivery(entry) }) { Text(stringResource(dev.ninfenz.mobile.R.string.deliver_action_go)) }
                        }
                    }
                }
                item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.deliver_section_more)) }
                item {
                    NfListRow(
                        title = stringResource(dev.ninfenz.mobile.R.string.deliver_pack_center_title),
                        subtitle = stringResource(dev.ninfenz.mobile.R.string.deliver_pack_center_subtitle),
                        leading = Icons.Filled.Refresh,
                        onClick = onPackUpdate
                    )
                }
                item {
                    NfListRow(
                        title = stringResource(dev.ninfenz.mobile.R.string.deliver_ccos_title),
                        subtitle = stringResource(dev.ninfenz.mobile.R.string.deliver_ccos_subtitle),
                        leading = Icons.Filled.Info,
                        onClick = onCcos
                    )
                }
            }
        }
    }
}

@Composable
fun MeScreen(
    themeMode: ThemeMode,
    onThemeMode: (ThemeMode) -> Unit,
    languageMode: LanguageMode = LanguageMode.SYSTEM,
    onLanguageMode: (LanguageMode) -> Unit = {},
    dynamicColor: Boolean = false,
    onDynamicColor: (Boolean) -> Unit = {},
    storageText: String,
    nativeReady: Boolean,
    abi: String?,
    onSettings: () -> Unit,
    onAbout: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = stringResource(dev.ninfenz.mobile.R.string.nav_me))
        LazyColumn(
            contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = NfSpacing.l),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
        ) {
            item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.me_section_appearance)) }
            item {
                Row(
                    modifier = Modifier.padding(horizontal = NfSpacing.page),
                    horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
                ) {
                    ThemeMode.entries.forEach { mode ->
                        FilterChip(
                            selected = mode == themeMode,
                            onClick = { onThemeMode(mode) },
                            label = { Text(themeModeLabel(mode)) }
                        )
                    }
                }
            }
            item {
                Row(
                    modifier = Modifier.padding(horizontal = NfSpacing.page),
                    horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
                ) {
                    FilterChip(
                        selected = dynamicColor,
                        onClick = { onDynamicColor(!dynamicColor) },
                        label = { Text(stringResource(dev.ninfenz.mobile.R.string.me_dynamic_color)) }
                    )
                }
            }
            item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.me_section_language)) }
            item {
                Row(
                    modifier = Modifier.padding(horizontal = NfSpacing.page),
                    horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
                ) {
                    LanguageMode.entries.forEach { mode ->
                        FilterChip(
                            selected = mode == languageMode,
                            onClick = { onLanguageMode(mode) },
                            label = {
                                Text(
                                    when (mode) {
                                        LanguageMode.SYSTEM -> stringResource(dev.ninfenz.mobile.R.string.me_language_system)
                                        LanguageMode.ZH -> stringResource(dev.ninfenz.mobile.R.string.me_language_zh)
                                        LanguageMode.EN -> stringResource(dev.ninfenz.mobile.R.string.me_language_en)
                                    }
                                )
                            }
                        )
                    }
                }
            }
            item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.me_section_storage)) }
            item {
                NfListRow(
                    title = stringResource(dev.ninfenz.mobile.R.string.me_storage_title),
                    subtitle = storageText,
                    leading = Icons.Filled.Home,
                    trailing = "›",
                    onClick = onSettings
                )
            }
            item {
                NfListRow(
                    title = stringResource(dev.ninfenz.mobile.R.string.me_diagnostic_title),
                    subtitle = if (nativeReady) stringResource(dev.ninfenz.mobile.R.string.me_diag_ok, abi ?: "") else stringResource(dev.ninfenz.mobile.R.string.me_diag_missing),
                    leading = Icons.Filled.Refresh,
                    trailing = "›",
                    onClick = onSettings
                )
            }
            item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.me_section_about)) }
            item {
                NfListRow(
                    title = stringResource(dev.ninfenz.mobile.R.string.me_about_title),
                    subtitle = stringResource(dev.ninfenz.mobile.R.string.me_about_subtitle),
                    leading = Icons.Filled.Info,
                    trailing = "›",
                    onClick = onAbout
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProjectDetailScreen(
    project: Project,
    onBack: () -> Unit,
    onAuthor: () -> Unit,
    onAssembly: () -> Unit,
    onDuplicate: () -> Unit = {},
    onArchive: () -> Unit = {},
    onRename: (String) -> Unit = {},
    onReview: (Boolean, String, String) -> Unit = { _, _, _ -> },
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
    var showArchive by remember { mutableStateOf(false) }
    var diffReport by remember { mutableStateOf<ProjectDiff.Report?>(null) }
    var diffError by remember { mutableStateOf<String?>(null) }
    var showComparePicker by remember { mutableStateOf(false) }
    var compareQuery by remember { mutableStateOf("") }
    var showDelete by remember { mutableStateOf(false) }
    var showRename by remember { mutableStateOf(false) }
    var renameText by remember(project.title) { mutableStateOf(project.title) }
    var showReview by remember { mutableStateOf(false) }
    var showMoreActions by remember { mutableStateOf(false) }
    var showRemoveOverride by remember { mutableStateOf(false) }
    var showTemplateReference by remember { mutableStateOf(false) }
    var historyExpanded by rememberSaveable(project.id) { mutableStateOf(false) }
    var hasSpecOverride by remember(project.id) {
        mutableStateOf(java.io.File(java.io.File(java.io.File(context.filesDir, "projects"), project.id), "authoring/spec-override.json").isFile)
    }
    val templateReference = remember(project.id, hasSpecOverride) {
        java.io.File(java.io.File(java.io.File(context.filesDir, "projects"), project.id), "authoring/template.md")
            .takeIf { it.isFile }?.readText(Charsets.UTF_8)
    }
    val canApprove = project.status in setOf(ProjectStatus.VALIDATED, ProjectStatus.EXPORTED, ProjectStatus.REVIEWED)
    var reviewStale by remember { mutableStateOf(false) }
    LaunchedEffect(project.id, project.review.state, project.review.subjectDigest) {
        reviewStale = runCatching {
            withContext(Dispatchers.IO) {
                dev.ninfenz.mobile.data.ProjectReviewStore(context.filesDir).isStale(
                    java.io.File(java.io.File(context.filesDir, "projects"), project.id + ".nfproject.json")
                )
            }
        }.getOrDefault(false)
    }
    var reviewer by rememberSaveable { mutableStateOf("") }
    var reviewNote by rememberSaveable { mutableStateOf("") }
    val diffPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: android.net.Uri? ->
        if (uri != null) {
            diffScope.launch {
                diffError = null
                try {
                    val text = withContext(Dispatchers.IO) {
                        context.contentResolver.openInputStream(uri)?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }
                    }
                    if (text == null) {
                        diffError = context.getString(dev.ninfenz.mobile.R.string.project_diff_read_failed)
                    } else {
                        diffReport = ProjectDiff.compare(project, ProjectModel.parse(text))
                    }
                } catch (t: Throwable) {
                    diffError = context.getString(dev.ninfenz.mobile.R.string.project_parse_failed, t.message ?: t.javaClass.simpleName)
                }
            }
        }
    }
    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(
            title = project.title,
            onBack = onBack,
            actions = {
                IconButton(onClick = { showMoreActions = true }) {
                    Icon(
                        Icons.Filled.MoreVert,
                        contentDescription = stringResource(dev.ninfenz.mobile.R.string.action_more)
                    )
                }
            }
        )
        LazyColumn(
            contentPadding = androidx.compose.foundation.layout.PaddingValues(NfSpacing.page),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
        ) {
            item {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = NfSpacing.page),
                    verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        NfStatusChip(projectStatusLabel(project))
                        if (project.historyCount > 0) {
                            Text(
                                stringResource(dev.ninfenz.mobile.R.string.project_detail_history, project.historyCount),
                                style = NfType.meta,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.weight(1f),
                                textAlign = androidx.compose.ui.text.style.TextAlign.End
                            )
                        }
                    }
                    Text(project.id, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    if (templateReference != null) {
                        NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_template_ref), null, Icons.Filled.Search, "›") {
                            showTemplateReference = true
                        }
                    }
                    if (hasSpecOverride) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                stringResource(dev.ninfenz.mobile.R.string.template_override_active),
                                style = NfType.meta,
                                color = MaterialTheme.colorScheme.primary,
                                modifier = Modifier.weight(1f)
                            )
                            TextButton(onClick = { showRemoveOverride = true }) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.template_override_remove))
                            }
                        }
                    }
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.project_detail_pack, project.refs.basePackId, project.refs.basePackVersion) +
                            " · " + stringResource(dev.ninfenz.mobile.R.string.project_detail_protocol, project.refs.protocolId.ifBlank { stringResource(dev.ninfenz.mobile.R.string.not_bound) }),
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            item {
                NfCard {
                    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.project_detail_next_step),
                            style = NfType.label,
                            color = MaterialTheme.colorScheme.primary
                        )
                        val nextIsAuthor = project.status == ProjectStatus.DRAFT || project.status == ProjectStatus.AUTHORING
                        Text(
                            stringResource(if (nextIsAuthor) dev.ninfenz.mobile.R.string.flow_action_author else dev.ninfenz.mobile.R.string.flow_action_delivery),
                            style = NfType.screenTitle
                        )
                        Text(
                            stringResource(if (nextIsAuthor) dev.ninfenz.mobile.R.string.project_detail_author_subtitle else dev.ninfenz.mobile.R.string.project_detail_delivery_subtitle),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Button(
                            onClick = { if (nextIsAuthor) onAuthor() else onAssembly() },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.flow_action_continue))
                        }
                    }
                }
            }
            item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.project_detail_info)) }
            item {
                NfCard {
                    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        Row {
                            Text("Pack", style = NfType.meta, modifier = Modifier.width(72.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(project.refs.basePackId + " · " + project.refs.basePackVersion, style = NfType.meta)
                        }
                        Row {
                            Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_protocol_label), style = NfType.meta, modifier = Modifier.width(72.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(project.refs.protocolId.ifBlank { stringResource(dev.ninfenz.mobile.R.string.not_bound) }, style = NfType.meta)
                        }
                        Row {
                            Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_review), style = NfType.meta, modifier = Modifier.width(72.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(project.review.state + " · " + (project.review.reviewer ?: "-"), style = NfType.meta)
                        }
                        if (reviewStale) {
                            Text(
                                stringResource(dev.ninfenz.mobile.R.string.project_review_stale),
                                style = NfType.meta,
                                color = MaterialTheme.colorScheme.error
                            )
                        }
                    }
                }
            }
            if (project.historyCount > 0 || project.history.isNotEmpty()) {
            item {
                NfListRow(
                    title = stringResource(dev.ninfenz.mobile.R.string.project_history_title),
                    subtitle = stringResource(dev.ninfenz.mobile.R.string.project_detail_history, project.historyCount),
                    leading = Icons.AutoMirrored.Filled.List,
                    trailing = stringResource(if (historyExpanded) dev.ninfenz.mobile.R.string.project_history_collapse else dev.ninfenz.mobile.R.string.project_history_expand),
                    onClick = { historyExpanded = !historyExpanded }
                )
            }
            }
            if (historyExpanded && (project.historyCount > 0 || project.history.isNotEmpty())) {
                item {
                    NfCard {
                        Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    stringResource(dev.ninfenz.mobile.R.string.project_history_title),
                                    style = NfType.itemTitle,
                                    modifier = Modifier.weight(1f)
                                )
                                TextButton(onClick = {
                                    val md = ProjectHistoryExport.toMarkdown(project)
                                    val intent = ShareExporter.shareMarkdown(context, "nf-history-" + project.id, md)
                                    ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.project_history_share))
                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.project_history_share)) }
                            }
                            if (project.history.isEmpty()) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_history, project.historyCount), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            } else {
                                project.history.takeLast(20).forEach { h ->
                                    Text(
                                        h.op + (h.digest?.let { " · " + it.take(12) } ?: "") + (h.at?.let { " · " + it } ?: ""),
                                        style = NfType.meta,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    if (showTemplateReference && templateReference != null) {
        AlertDialog(
            onDismissRequest = { showTemplateReference = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.author_template_ref)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        TextButton(onClick = { clipboard.setText(androidx.compose.ui.text.AnnotatedString(templateReference)) }) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.author_template_copy))
                        }
                        TextButton(onClick = {
                            val intent = dev.ninfenz.mobile.share.ShareExporter.shareMarkdown(context, "nf-template", templateReference)
                            dev.ninfenz.mobile.share.ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.author_template_share))
                        }) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.author_template_share))
                        }
                    }
                    Column(modifier = Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState())) {
                        dev.ninfenz.mobile.ui.components.MarkdownPreview(templateReference, limitBlocks = 40)
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showTemplateReference = false }) { Text(stringResource(android.R.string.ok)) }
            }
        )
    }

    if (showRemoveOverride) {
        AlertDialog(
            onDismissRequest = { showRemoveOverride = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.template_override_remove_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.template_override_remove_body)) },
            confirmButton = {
                TextButton(onClick = {
                    dev.ninfenz.mobile.data.DraftProjectBinder.clearSpec(context.filesDir, project.id)
                    hasSpecOverride = false
                    showRemoveOverride = false
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.template_override_remove)) }
            },
            dismissButton = {
                TextButton(onClick = { showRemoveOverride = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

    if (showMoreActions) {
        ModalBottomSheet(onDismissRequest = { showMoreActions = false }) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = NfSpacing.page)
                    .padding(bottom = NfSpacing.xl),
                verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)
            ) {
                Text(stringResource(dev.ninfenz.mobile.R.string.project_more_actions), style = NfType.screenTitle)
                Text(project.title, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                HorizontalDivider(modifier = Modifier.padding(vertical = NfSpacing.s))
                Text(stringResource(dev.ninfenz.mobile.R.string.project_actions_manage), style = NfType.label, color = MaterialTheme.colorScheme.onSurfaceVariant)
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_detail_rename), null, Icons.Filled.Edit, "›") {
                    showMoreActions = false
                    renameText = project.title
                    showRename = true
                }
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_detail_review), null, Icons.Filled.Info, "›") {
                    showMoreActions = false
                    showReview = true
                }
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_detail_duplicate), null, Icons.Filled.Add, "›") {
                    showMoreActions = false
                    onDuplicate()
                }
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.flow_title), null, Icons.AutoMirrored.Filled.List, "›") {
                    showMoreActions = false
                    onFlow()
                }
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_detail_archive), null, Icons.Filled.Info, "›") {
                    showMoreActions = false
                    showArchive = true
                }
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_detail_diff), null, Icons.AutoMirrored.Filled.List, "›") {
                    showMoreActions = false
                    diffPicker.launch(arrayOf("application/json", "*/*"))
                }
                if (compareCandidates.isNotEmpty()) {
                    NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_diff_library), null, Icons.AutoMirrored.Filled.List, "›") {
                        showMoreActions = false
                        showComparePicker = true
                    }
                }
                HorizontalDivider(modifier = Modifier.padding(vertical = NfSpacing.s))
                Text(stringResource(dev.ninfenz.mobile.R.string.project_actions_share), style = NfType.label, color = MaterialTheme.colorScheme.onSurfaceVariant)
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_detail_share), null, Icons.Filled.Search, "›") {
                    showMoreActions = false
                    onShare()
                }
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_detail_share_full), null, Icons.Filled.Search, "›") {
                    showMoreActions = false
                    onShareFull()
                }
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_save_template), null, Icons.Filled.Search, "›") {
                    showMoreActions = false
                    onSaveAsTemplate()
                }
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_export_template), null, Icons.Filled.Search, "›") {
                    showMoreActions = false
                    onExportTemplatePackage()
                }
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_copy_id), null, Icons.Filled.Search, "›") {
                    showMoreActions = false
                    clipboard.setText(androidx.compose.ui.text.AnnotatedString(project.id))
                    android.widget.Toast.makeText(context, context.getString(dev.ninfenz.mobile.R.string.project_copy_id), android.widget.Toast.LENGTH_SHORT).show()
                }
                HorizontalDivider(modifier = Modifier.padding(vertical = NfSpacing.s))
                Text(stringResource(dev.ninfenz.mobile.R.string.project_actions_danger), style = NfType.label, color = MaterialTheme.colorScheme.onSurfaceVariant)
                TextButton(
                    onClick = {
                        showMoreActions = false
                        showDelete = true
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_delete), color = MaterialTheme.colorScheme.error)
                }
            }
        }
    }

    if (showDelete) {
        AlertDialog(
            onDismissRequest = { showDelete = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.project_delete_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.project_delete_body, project.title)) },
            confirmButton = {
                TextButton(onClick = {
                    showDelete = false
                    onDelete()
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.project_delete_confirm)) }
            },
            dismissButton = {
                TextButton(onClick = { showDelete = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

    if (showReview) {
        AlertDialog(
            onDismissRequest = { showReview = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_review)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.project_review_current, project.review.state), style = NfType.meta)
                    OutlinedTextField(
                        value = reviewer,
                        onValueChange = { reviewer = it },
                        singleLine = true,
                        label = { Text(stringResource(dev.ninfenz.mobile.R.string.project_review_reviewer)) }
                    )
                    OutlinedTextField(
                        value = reviewNote,
                        onValueChange = { reviewNote = it },
                        label = { Text(stringResource(dev.ninfenz.mobile.R.string.project_review_note)) }
                    )
                    if (!canApprove) {
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.project_review_need_validate),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.error
                        )
                    }
                }
            },
            confirmButton = {
                TextButton(
                    enabled = canApprove && reviewer.isNotBlank() && reviewNote.isNotBlank(),
                    onClick = {
                        showReview = false
                        onReview(true, reviewer, reviewNote)
                    }
                ) { Text(stringResource(dev.ninfenz.mobile.R.string.project_review_approve)) }
            },
            dismissButton = {
                TextButton(
                    enabled = reviewer.isNotBlank() && reviewNote.isNotBlank(),
                    onClick = {
                        showReview = false
                        onReview(false, reviewer, reviewNote)
                    }
                ) { Text(stringResource(dev.ninfenz.mobile.R.string.project_review_reject)) }
            }
        )
    }

    if (showRename) {
        AlertDialog(
            onDismissRequest = { showRename = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_rename)) },
            text = {
                OutlinedTextField(
                    value = renameText,
                    onValueChange = { renameText = it },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    label = { Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_rename_label)) }
                )
            },
            confirmButton = {
                TextButton(
                    enabled = renameText.isNotBlank(),
                    onClick = {
                        showRename = false
                        onRename(renameText.trim())
                    }
                ) { Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_rename_confirm)) }
            },
            dismissButton = {
                TextButton(onClick = { showRename = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

    if (showComparePicker) {
        AlertDialog(
            onDismissRequest = { showComparePicker = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.project_diff_library)) },
            text = {
                Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                    OutlinedTextField(
                        value = compareQuery,
                        onValueChange = { compareQuery = it },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        placeholder = { Text(stringResource(dev.ninfenz.mobile.R.string.project_diff_search)) }
                    )
                    compareCandidates.filter {
                        it.project.id != project.id &&
                            (compareQuery.isBlank() || it.project.title.contains(compareQuery, ignoreCase = true) || it.project.id.contains(compareQuery, ignoreCase = true))
                    }.forEach { candidate ->
                        TextButton(onClick = {
                            showComparePicker = false
                            diffScope.launch {
                                try {
                                    val text = withContext(Dispatchers.IO) { candidate.file.readText(Charsets.UTF_8) }
                                    diffReport = ProjectDiff.compare(project, ProjectModel.parse(text))
                                } catch (t: Throwable) {
                                    diffError = context.getString(dev.ninfenz.mobile.R.string.project_parse_failed, t.message ?: t.javaClass.simpleName)
                                }
                            }
                        }) {
                            Text(
                                candidate.project.title + " · " + candidate.project.id + " · " +
                                    projectStatusLabel(candidate.project) + " · " +
                                    SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()).format(Date(candidate.file.lastModified()))
                            )
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showComparePicker = false }) { Text(stringResource(dev.ninfenz.mobile.R.string.action_close)) }
            }
        )
    }

    diffError?.let { message ->
        AlertDialog(
            onDismissRequest = { diffError = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_diff)) },
            text = { Text(message) },
            confirmButton = { TextButton(onClick = { diffError = null }) { Text(stringResource(dev.ninfenz.mobile.R.string.action_close)) } }
        )
    }

    diffReport?.let { report ->
        AlertDialog(
            onDismissRequest = { diffReport = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_diff)) },
            text = {
                Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                    if (!report.hasChanges) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.project_diff_same))
                    } else {
                        report.changes.forEach { change ->
                            Text(change.field + ": " + change.before + " → " + change.after, style = NfType.meta)
                        }
                        report.historyOnlyBefore.forEach { Text("history -: " + it, style = NfType.meta) }
                        report.historyOnlyAfter.forEach { Text("history +: " + it, style = NfType.meta) }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { diffReport = null }) { Text(stringResource(dev.ninfenz.mobile.R.string.action_close)) } }
        )
    }

    if (showArchive) {
        AlertDialog(
            onDismissRequest = { showArchive = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.project_archive_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.project_archive_body)) },
            confirmButton = {
                TextButton(onClick = {
                    showArchive = false
                    onArchive()
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.project_archive_confirm)) }
            },
            dismissButton = {
                TextButton(onClick = { showArchive = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}

@Composable
fun PackDetailScreen(pack: PackEntry, onBack: () -> Unit, onUpdate: () -> Unit) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
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
                NfCard {
                    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        Text(pack.id + " · " + pack.version, style = NfType.itemTitle)
                        Text(pack.description, style = NfType.secondary)
                        Text(stringResource(dev.ninfenz.mobile.R.string.pack_detail_items, pack.itemCount), style = NfType.meta)
                        Text(stringResource(dev.ninfenz.mobile.R.string.pack_detail_tree, pack.tree.take(16) + "…"), style = NfType.meta)
                        Text(stringResource(dev.ninfenz.mobile.R.string.pack_detail_dir, pack.dir.absolutePath), style = NfType.meta)
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
                            TextButton(onClick = {
                                if (pinnedTree != null && trustMatches) {
                                    trustStore.clear(pack.id, pack.version)
                                } else {
                                    trustStore.pin(pack.id, pack.version, pack.tree)
                                }
                                pinnedTree = trustStore.pinnedTree(pack.id, pack.version)
                            }) {
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
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    Button(
                        onClick = {
                            if (verifying) return@Button
                            verifying = true
                            errorText = null
                            report = null
                            scope.launch {
                                val response = PackVerifier().verify(pack)
                                val result = response.resultObject()
                                val verdict = result?.get("verdict")?.let { it.toString().trim('"') }
                                val issues = result?.get("issues")?.toString() ?: ""
                                if (response.ok) {
                                    report = context.getString(dev.ninfenz.mobile.R.string.validate_passed, verdict ?: "pass") + (if (issues == "[]") "" else " · issues=" + issues)
                                } else {
                                    val err = response.error
                                    errorText = "[" + (err?.code ?: "NF-VAL-001") + "] " +
                                        (err?.message ?: context.getString(dev.ninfenz.mobile.R.string.validate_failed)) +
                                        context.getString(dev.ninfenz.mobile.R.string.error_fix_suffix) +
                                        (err?.fix ?: context.getString(dev.ninfenz.mobile.R.string.view_diagnostics))
                                }
                                verifying = false
                            }
                        },
                        enabled = !verifying
                    ) { Text(if (verifying) context.getString(dev.ninfenz.mobile.R.string.validating) else context.getString(dev.ninfenz.mobile.R.string.validate_pack)) }
                    Button(onClick = onUpdate) { Text(stringResource(dev.ninfenz.mobile.R.string.pack_detail_update)) }
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
fun projectStatusLabel(project: Project): String = projectStatusLabel(project.status)

@Composable
fun projectStatusLabel(status: dev.ninfenz.mobile.model.ProjectStatus): String = when (status) {
    dev.ninfenz.mobile.model.ProjectStatus.DRAFT -> stringResource(dev.ninfenz.mobile.R.string.status_draft)
    dev.ninfenz.mobile.model.ProjectStatus.AUTHORING -> stringResource(dev.ninfenz.mobile.R.string.status_authoring)
    dev.ninfenz.mobile.model.ProjectStatus.ASSEMBLED -> stringResource(dev.ninfenz.mobile.R.string.status_assembled)
    dev.ninfenz.mobile.model.ProjectStatus.VALIDATED -> stringResource(dev.ninfenz.mobile.R.string.status_validated)
    dev.ninfenz.mobile.model.ProjectStatus.EXPORTED -> stringResource(dev.ninfenz.mobile.R.string.status_exported)
    dev.ninfenz.mobile.model.ProjectStatus.REVIEWED -> stringResource(dev.ninfenz.mobile.R.string.status_reviewed)
}

@Composable
fun themeModeLabel(mode: ThemeMode): String = when (mode) {
    ThemeMode.SYSTEM -> stringResource(dev.ninfenz.mobile.R.string.theme_system)
    ThemeMode.LIGHT -> stringResource(dev.ninfenz.mobile.R.string.theme_light)
    ThemeMode.DARK -> stringResource(dev.ninfenz.mobile.R.string.theme_dark)
}
