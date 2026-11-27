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
internal fun LibraryHomeGroupedProjects(s: LibraryHomeState) {
                            var renderIndex = 0
                            s.groupedProjects.forEach { (label, entries) ->
                                if (s.groupMode != "none" && label.isNotBlank()) {
                                    NfSectionHeader(label)
                                }
                                entries.forEach { entry ->
                                    SwipeableProjectCard(
                                        entry = entry,
                                        index = renderIndex++,
                                        selectable = s.selectionMode,
                                        selected = entry.project.id in s.selectedIds,
                                        onOpen = {
                                            if (s.selectionMode) {
                                                s.selectedIds = if (entry.project.id in s.selectedIds) s.selectedIds - entry.project.id else s.selectedIds + entry.project.id
                                            } else {
                                                s.openWithPriority(entry)
                                            }
                                        },
                                        onFlow = { s.onOpenFlow(entry) },
                                        onDelete = {
                                            s.snackbarScope.launch {
                                                val archived = runCatching {
                                                    ProjectArchiver.archive(entry.file, s.context.filesDir)
                                                }.orNullLogged("TopLevelScreens")
                                                if (archived != null) {
                                                    s.undoArchive = archived
                                                    s.onRefresh()
                                                }
                                            }
                                        }
                                    )
                                }
                            }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
internal fun LazyListScope.LibraryHomePacksBlock(s: LibraryHomeState) {
            if (s.packs.isNotEmpty()) {
                stickyHeader(key = "library-packs-header") {
                    NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.library_section_packs), action = {
                        TextButton(onClick = s.onPackCenter) { Text(stringResource(dev.ninfenz.mobile.R.string.library_manage)) }
                    })
                }
                items(s.packs.size) { index ->
                    val pack = s.packs[index]
                    NfCard(
                        modifier = Modifier.padding(horizontal = NfSpacing.page),
                        onClick = { s.onOpenPack(pack) }
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(pack.title, style = NfType.itemTitle)
                                Text(
                                    pack.id + " · " + pack.version + " · " + s.context.getString(dev.ninfenz.mobile.R.string.pack_item_count, pack.itemCount),
                                    style = NfType.meta,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                            NfStatusChip(stringResource(dev.ninfenz.mobile.R.string.packcenter_installed))
                        }
                    }
                }
            }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
internal fun LazyListScope.LibraryHomeArchiveBlock(s: LibraryHomeState) {
            if (s.archived.isNotEmpty()) {
                stickyHeader(key = "library-archive-header") { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.library_section_archive)) }
                items(s.archived.size) { index ->
                    val file = s.archived[index]
                    NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(file.name, style = NfType.meta, modifier = Modifier.weight(1f))
                            TextButton(onClick = { s.onRestoreArchive(file) }) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.project_archive_restore))
                            }
                            TextButton(onClick = { s.pendingDeleteArchive = file }) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.project_archive_delete))
                            }
                        }
                    }
                }
            }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
internal fun LazyListScope.LibraryHomeErrorsBlock(s: LibraryHomeState) {
            if (s.errors.isNotEmpty()) {
                item {
                    Surface(
                        color = MaterialTheme.colorScheme.errorContainer,
                        shape = MaterialTheme.shapes.medium,
                        modifier = Modifier.padding(horizontal = NfSpacing.page)
                    ) {
                        Column(modifier = Modifier.padding(NfSpacing.m)) {
                            Text(pluralStringResource(dev.ninfenz.mobile.R.plurals.library_errors, s.errors.size, s.errors.size), style = NfType.itemTitle)
                            s.errors.take(3).forEach { Text(it, style = NfType.meta) }
                        }
                    }
                }
            }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun LibraryHomeUndoBar(s: LibraryHomeState, modifier: Modifier) {
    androidx.compose.animation.AnimatedVisibility(
        visible = s.undoArchive != null,
        modifier = modifier,
        enter = fadeIn(tween(NfMotion.SHORT_MS)) + slideInVertically(tween(NfMotion.MEDIUM_MS)) { it / 2 },
        exit = fadeOut(tween(NfMotion.SHORT_MS)) + slideOutVertically(tween(NfMotion.SHORT_MS)) { it / 2 }
    ) {
        s.undoArchive?.let { archived ->
            NfActionBarSurface {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.library_project_archived),
                        style = NfType.secondary,
                        modifier = Modifier.weight(1f)
                    )
                    TextButton(onClick = {
                        runCatching { ProjectArchiver.restore(archived, s.context.filesDir) }
                        s.undoArchive = null
                        s.onRefresh()
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.library_project_undo)) }
                    TextButton(onClick = { s.undoArchive = null }) {
                        Text(stringResource(android.R.string.cancel))
                    }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun LibraryHomeSaveViewDialog(s: LibraryHomeState) {
    if (s.showSaveView) {
        AlertDialog(
            onDismissRequest = { s.showSaveView = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.library_save_view)) },
            text = {
                OutlinedTextField(
                    value = s.viewName,
                    onValueChange = { s.viewName = it },
                    label = { Text(stringResource(dev.ninfenz.mobile.R.string.library_view_name)) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
            },
            confirmButton = {
                TextButton(enabled = s.viewName.isNotBlank() && s.savedViewStore != null, onClick = {
                    s.savedViews = s.savedViewStore?.save(SavedViewStore.View(
                        id = "v-" + System.nanoTime(),
                        name = s.viewName,
                        status = s.statusFilter,
                        sort = s.sortName,
                        favoritesOnly = s.favoritesOnly,
                        tag = s.tagFilter
                    )) ?: s.savedViews
                    s.showSaveView = false
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.library_view_saved)) }
            },
            dismissButton = { TextButton(onClick = { s.showSaveView = false }) { Text(stringResource(android.R.string.cancel)) } }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun LibraryHomeDeleteArchiveDialog(s: LibraryHomeState) {
    s.pendingDeleteArchive?.let { file ->
        AlertDialog(
            onDismissRequest = { s.pendingDeleteArchive = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.project_archive_delete)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.project_archive_delete_body, file.name)) },
            confirmButton = {
                TextButton(onClick = {
                    ProjectArchiver.delete(file, s.context.filesDir)
                    s.pendingDeleteArchive = null
                    s.onRefresh()
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.project_archive_delete)) }
            },
            dismissButton = {
                TextButton(onClick = { s.pendingDeleteArchive = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}

