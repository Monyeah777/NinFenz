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
import androidx.compose.foundation.lazy.LazyListScope

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun LibraryHomeFilterStrip(s: LibraryHomeState, modifier: Modifier) {
                        LazyRow(
                            modifier = modifier,
                            contentPadding = androidx.compose.foundation.layout.PaddingValues(start = NfSpacing.page, end = NfSpacing.s),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            item {
                                FilterChip(
                                    selected = s.favoritesOnly,
                                    onClick = { s.favoritesOnly = !s.favoritesOnly },
                                    label = { Text(stringResource(dev.ninfenz.mobile.R.string.library_favorites)) }
                                )
                            }
                            items(s.allTags.sorted()) { tag ->
                                FilterChip(
                                    selected = s.tagFilter == tag,
                                    onClick = { s.tagFilter = if (s.tagFilter == tag) null else tag },
                                    label = { Text("#" + tag) }
                                )
                            }
                            items(s.allViews, key = { it.id }) { view ->
                                FilterChip(
                                    selected = s.favoritesOnly == view.favoritesOnly &&
                                        s.tagFilter == view.tag &&
                                        s.statusFilter == view.status &&
                                        s.sortName == view.sort,
                                    onClick = {
                                        s.favoritesOnly = view.favoritesOnly
                                        s.tagFilter = view.tag
                                        s.statusFilter = view.status
                                        s.sortName = view.sort
                                    },
                                    label = { Text(view.name) }
                                )
                            }
                            items(s.smartCollections, key = { it.id }) { collection ->
                                FilterChip(
                                    selected = s.activeCollection?.id == collection.id,
                                    onClick = { s.activeCollection = if (s.activeCollection?.id == collection.id) null else collection },
                                    label = { Text(collection.name) }
                                )
                            }
                            item {
                                FilterChip(
                                    selected = s.filterStatus == null,
                                    onClick = { s.statusFilter = null },
                                    label = { Text(stringResource(dev.ninfenz.mobile.R.string.search_filter_all)) }
                                )
                            }
                            items(ProjectStatus.entries.filter { s.audit || (it != ProjectStatus.VALIDATED && it != ProjectStatus.REVIEWED) }) { status ->
                                FilterChip(
                                    selected = s.filterStatus == status,
                                    onClick = { s.statusFilter = status.wire },
                                    label = { Text(projectStatusLabel(status)) }
                                )
                            }
                        }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun LibraryHomeViewActions(s: LibraryHomeState) {
                        if (s.savedViewStore != null) {
                            TextButton(onClick = { s.viewName = ""; s.showSaveView = true }) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.library_save_view))
                            }
                        }
                        TextButton(onClick = {
                            s.groupMode = when (s.groupMode) {
                                "none" -> "pack"
                                "pack" -> "status"
                                "status" -> "tag"
                                else -> "none"
                            }
                        }) {
                            Text(stringResource(when (s.groupMode) {
                                "pack" -> dev.ninfenz.mobile.R.string.library_group_pack
                                "status" -> dev.ninfenz.mobile.R.string.library_group_status
                                "tag" -> dev.ninfenz.mobile.R.string.library_group_tag
                                else -> dev.ninfenz.mobile.R.string.library_group_none
                            }))
                        }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun LibraryHomeSortControls(s: LibraryHomeState) {
                        val sortLabel = stringResource(dev.ninfenz.mobile.R.string.library_sort_label) + "：" +
                            when (s.filterSort) {
                                ProjectSort.RECENT -> stringResource(dev.ninfenz.mobile.R.string.library_sort_recent)
                                ProjectSort.TITLE -> stringResource(dev.ninfenz.mobile.R.string.library_sort_title)
                                ProjectSort.STATUS -> stringResource(dev.ninfenz.mobile.R.string.library_sort_status)
                            }
                        Box {
                            IconButton(
                                onClick = { s.sortMenuOpen = true },
                                modifier = Modifier
                                    .size(48.dp)
                                    .semantics { contentDescription = sortLabel }
                            ) {
                                Text("⇅", style = NfType.screenTitle)
                            }
                            androidx.compose.material3.DropdownMenu(
                                expanded = s.sortMenuOpen,
                                onDismissRequest = { s.sortMenuOpen = false }
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
                                            s.sortName = mode.name
                                            s.sortMenuOpen = false
                                        }
                                    )
                                }
                            }
                        }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
internal fun LazyListScope.LibraryHomeEmptyBlock(s: LibraryHomeState) {
            if (s.packs.isEmpty() && s.projects.isEmpty()) {
                item {
                    NfEmptyState(
                        icon = Icons.Filled.Home,
                        title = stringResource(dev.ninfenz.mobile.R.string.library_empty_title),
                        message = stringResource(dev.ninfenz.mobile.R.string.library_empty_body),
                        actionLabel = stringResource(dev.ninfenz.mobile.R.string.library_action_load_sample),
                        onAction = s.onSeed,
                        secondaryLabel = stringResource(dev.ninfenz.mobile.R.string.library_action_import_file),
                        onSecondary = s.onImport
                    )
                }
            }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
internal fun LazyListScope.LibraryHomeFilteredBlock(s: LibraryHomeState) {
    if (s.filteredProjects.isNotEmpty()) {
        LibraryHomeProjectsSticky(s)
        LibraryHomeProjectsAnimated(s)
    } else if (s.projects.isNotEmpty()) {
        LibraryHomeNoMatchCard(s)
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
internal fun LazyListScope.LibraryHomeProjectsSticky(s: LibraryHomeState) {
                stickyHeader(key = "library-projects-header") {
                    val projectChevron by animateFloatAsState(
                        targetValue = if (s.projectsExpanded) 180f else 0f,
                        animationSpec = tween(durationMillis = NfMotion.MEDIUM_MS),
                        label = "library-projects-chevron"
                    )
                    NfSectionHeader(
                        stringResource(dev.ninfenz.mobile.R.string.library_section_projects),
                        action = {
                            TextButton(onClick = {
                                s.selectionMode = !s.selectionMode
                                if (!s.selectionMode) s.selectedIds = emptySet()
                            }) {
                                Text(stringResource(if (s.selectionMode) dev.ninfenz.mobile.R.string.library_bulk_cancel else dev.ninfenz.mobile.R.string.library_bulk_select))
                            }
                            IconButton(
                                onClick = { s.projectsExpanded = !s.projectsExpanded },
                                modifier = Modifier.size(48.dp)
                            ) {
                                Icon(
                                    Icons.Filled.KeyboardArrowDown,
                                    contentDescription = stringResource(
                                        if (s.projectsExpanded) dev.ninfenz.mobile.R.string.action_collapse
                                        else dev.ninfenz.mobile.R.string.action_expand
                                    ),
                                    modifier = Modifier.rotate(projectChevron)
                                )
                            }
                        }
                    )
                }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
internal fun LazyListScope.LibraryHomeProjectsAnimated(s: LibraryHomeState) {
    item {
        androidx.compose.animation.AnimatedVisibility(
            visible = s.projectsExpanded,
            enter = nfExpandableEnter(),
            exit = nfExpandableExit()
        ) {
            Column(
                modifier = Modifier.padding(horizontal = NfSpacing.page),
                verticalArrangement = Arrangement.spacedBy(NfSpacing.l)
            ) {
                LibraryHomeSelectionBar(s)
                LibraryHomeGroupedProjects(s)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
internal fun LazyListScope.LibraryHomeNoMatchCard(s: LibraryHomeState) {
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
                        TextButton(onClick = { s.statusFilter = null }) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.library_clear_filter))
                        }
                    }
                }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun LibraryHomeSelectionBar(s: LibraryHomeState) {
                            if (s.selectionMode) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(
                                        stringResource(dev.ninfenz.mobile.R.string.library_bulk_selected, s.selectedIds.size),
                                        style = NfType.meta,
                                        modifier = Modifier.weight(1f)
                                    )
                                    TextButton(enabled = s.selectedIds.isNotEmpty(), onClick = {
                                        s.selectedIds.forEach { s.metaStore?.toggle(it) }
                                        s.metaVersion++
                                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.library_bulk_favorite)) }
                                    TextButton(enabled = s.selectedIds.isNotEmpty(), onClick = {
                                        val chosen = s.projects.filter { it.project.id in s.selectedIds }
                                        s.snackbarScope.launch {
                                            chosen.forEach { runCatching { ProjectArchiver.archive(it.file, s.context.filesDir) } }
                                            s.selectedIds = emptySet()
                                            s.selectionMode = false
                                            s.onRefresh()
                                        }
                                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.library_bulk_archive)) }
                                }
                            }
}

