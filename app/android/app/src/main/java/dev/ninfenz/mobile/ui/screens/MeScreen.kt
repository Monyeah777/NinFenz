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

@Composable
internal fun CreateNoPackState(onLoadSample: () -> Unit, onImport: () -> Unit) {
    NfEmptyState(
        icon = Icons.Filled.Edit,
        title = stringResource(dev.ninfenz.mobile.R.string.create_no_pack_title),
        message = stringResource(dev.ninfenz.mobile.R.string.create_no_pack_body),
        actionLabel = stringResource(dev.ninfenz.mobile.R.string.create_action_load_sample),
        onAction = onLoadSample,
        secondaryLabel = stringResource(dev.ninfenz.mobile.R.string.create_action_import),
        onSecondary = onImport
    )
}

@Composable
internal fun CreateNewProjectCard(onCreateProject: () -> Unit) {
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

@Composable
internal fun CreateNoProjectState(onCreateProject: () -> Unit, onGoLibrary: () -> Unit) {
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

@Composable
internal fun CreateProjectCard(entry: ProjectEntry, onOpenProject: (ProjectEntry) -> Unit) {
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
            DeliverEmptyState(onGoCreate, onPackUpdate)
        } else {
            LazyColumn(
                contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = NfSpacing.l),
                verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
            ) {
                stickyHeader(key = "deliver-projects-header") { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.create_section_projects)) }
                items(projects.size) { index ->
                    val entry = projects[index]
                    DeliverProjectCard(entry, onOpenProject, onOpenDelivery)
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
internal fun DeliverEmptyState(onGoCreate: () -> Unit, onPackUpdate: () -> Unit) {
    NfEmptyState(
        icon = Icons.AutoMirrored.Filled.List,
        title = stringResource(dev.ninfenz.mobile.R.string.deliver_empty_title),
        message = stringResource(dev.ninfenz.mobile.R.string.deliver_empty_body),
        actionLabel = stringResource(dev.ninfenz.mobile.R.string.deliver_action_create),
        onAction = onGoCreate,
        secondaryLabel = stringResource(dev.ninfenz.mobile.R.string.deliver_action_pack_update),
        onSecondary = onPackUpdate
    )
}

@Composable
internal fun DeliverProjectCard(
    entry: ProjectEntry,
    onOpenProject: (ProjectEntry) -> Unit,
    onOpenDelivery: (ProjectEntry) -> Unit
) {
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

@OptIn(ExperimentalFoundationApi::class)
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
            stickyHeader(key = "me-appearance") { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.me_section_appearance)) }
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
            stickyHeader(key = "me-language") { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.me_section_language)) }
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
                                        LanguageMode.PSEUDO -> stringResource(dev.ninfenz.mobile.R.string.me_language_pseudo)
                                    }
                                )
                            }
                        )
                    }
                }
            }
            stickyHeader(key = "me-storage") { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.me_section_storage)) }
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
            stickyHeader(key = "me-about") { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.me_section_about)) }
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
