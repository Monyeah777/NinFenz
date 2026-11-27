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
internal fun LibraryHomeHeader(s: LibraryHomeState) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .statusBarsPadding()
            .padding(horizontal = NfSpacing.page, vertical = NfSpacing.s)
    ) {
        LibraryHomeHeaderTitle(s)
        LibraryHomeHeaderPrimaryActions(s)
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun LibraryHomeHeaderTitle(s: LibraryHomeState) {
            val titleBlock: @Composable () -> Unit = {
                Column {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.library_header_title),
                        style = NfType.screenTitle,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Text(
                        pluralStringResource(dev.ninfenz.mobile.R.plurals.library_header_projects, s.projects.size, s.projects.size) + " · " +
                            pluralStringResource(dev.ninfenz.mobile.R.plurals.library_header_packs, s.packs.size, s.packs.size),
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            val actions: @Composable () -> Unit = {
                TextButton(onClick = s.onCommands, modifier = Modifier.heightIn(min = 48.dp)) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.action_commands))
                }
                IconButton(onClick = s.onSearch, modifier = Modifier.size(48.dp)) { Icon(Icons.Filled.Search, contentDescription = stringResource(dev.ninfenz.mobile.R.string.action_search)) }
                IconButton(onClick = s.onSettings, modifier = Modifier.size(48.dp)) { Icon(Icons.Filled.Settings, contentDescription = stringResource(dev.ninfenz.mobile.R.string.action_settings)) }
            }
            if (LocalDensity.current.fontScale >= 1.4f) {
                Column {
                    titleBlock()
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) { actions() }
                }
            } else {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(modifier = Modifier.weight(1f)) { titleBlock() }
                    Row(horizontalArrangement = Arrangement.End) { actions() }
                }
            }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun LibraryHomeHeaderPrimaryActions(s: LibraryHomeState) {
            Row(
                modifier = Modifier.padding(top = NfSpacing.s),
                horizontalArrangement = Arrangement.spacedBy(NfSpacing.s),
                verticalAlignment = Alignment.CenterVertically
            ) {
                if (s.projects.isEmpty()) {
                    OutlinedButton(onClick = s.onNewProject, modifier = Modifier.heightIn(min = 48.dp)) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.create_action_new))
                    }
                } else {
                    Button(onClick = s.onNewProject, modifier = Modifier.heightIn(min = 48.dp)) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.create_action_new))
                    }
                }
                TextButton(onClick = s.onImport, modifier = Modifier.heightIn(min = 48.dp)) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.library_import))
                }
            }
            SeedLine(s.seedState)
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun LibraryHomeColumn(s: LibraryHomeState) {
    Column(modifier = Modifier.fillMaxSize().widthIn(max = NfLayout.contentMaxWidth)) {
        LibraryHomeHeader(s)
        LibraryHomeRefreshArea(s)
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun LibraryHomeRefreshArea(s: LibraryHomeState) {
    PullToRefreshBox(
        isRefreshing = s.refreshing,
        onRefresh = s.onRefresh,
        modifier = Modifier.fillMaxSize()
    ) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.l)
        ) {
            LibraryHomeDailyCard(s)
            LibraryHomeProjectsBlock(s)
            LibraryHomeEmptyBlock(s)
            LibraryHomeFilteredBlock(s)
            LibraryHomePacksBlock(s)
            LibraryHomeArchiveBlock(s)
            LibraryHomeErrorsBlock(s)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
internal fun LazyListScope.LibraryHomeDailyCard(s: LibraryHomeState) {
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
                            value = s.dailyText,
                            onValueChange = { s.dailyText = it },
                            modifier = Modifier.fillMaxWidth(),
                            placeholder = { Text(stringResource(dev.ninfenz.mobile.R.string.daily_hint)) },
                            minLines = 3,
                            maxLines = 6
                        )
                        OutlinedButton(
                            enabled = s.dailyText.isNotBlank(),
                            onClick = {
                                val text = s.dailyText.trim()
                                if (text.isNotEmpty()) {
                                    s.onDailyText(text)
                                    s.dailyText = ""
                                }
                            },
                            modifier = Modifier.heightIn(min = 48.dp)
                        ) { Text(stringResource(dev.ninfenz.mobile.R.string.daily_action)) }
                    }
                }
            }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
internal fun LazyListScope.LibraryHomeProjectsBlock(s: LibraryHomeState) {
    if (s.projects.isNotEmpty()) {
        LibraryHomeQuickCard(s)
        LibraryHomeProjectsCard(s)
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
internal fun LazyListScope.LibraryHomeQuickCard(s: LibraryHomeState) {
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
                                OutlinedButton(onClick = s.onQuickPaste, modifier = Modifier.heightIn(min = 48.dp)) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.library_quick_paste))
                                }
                            }
                        }
                    }
                }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
internal fun LazyListScope.LibraryHomeProjectsCard(s: LibraryHomeState) {
    item {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            LibraryHomeFilterStrip(s, Modifier.weight(1f))
            LibraryHomeViewActions(s)
            LibraryHomeSortControls(s)
        }
    }
}

