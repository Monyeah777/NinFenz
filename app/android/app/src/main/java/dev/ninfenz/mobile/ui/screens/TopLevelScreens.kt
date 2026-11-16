package dev.ninfenz.mobile.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.padding
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
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.PackTrustStore
import dev.ninfenz.mobile.data.PackVerifier
import dev.ninfenz.mobile.data.ProjectEntry
import dev.ninfenz.mobile.data.SeedResult
import dev.ninfenz.mobile.data.LanguageMode
import dev.ninfenz.mobile.data.ThemeMode
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ProjectFilter
import dev.ninfenz.mobile.model.ProjectDiff
import dev.ninfenz.mobile.model.ProjectHistoryExport
import dev.ninfenz.mobile.model.ProjectModel
import dev.ninfenz.mobile.model.ProjectStatus
import dev.ninfenz.mobile.share.ShareExporter
import dev.ninfenz.mobile.ui.components.NfCard
import dev.ninfenz.mobile.ui.components.NfEmptyState
import dev.ninfenz.mobile.ui.components.NfGradientHero
import dev.ninfenz.mobile.ui.components.NfListRow
import dev.ninfenz.mobile.ui.components.NfSectionHeader
import dev.ninfenz.mobile.ui.components.NfStatusChip
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.theme.NfSpacing
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LibraryHomeScreen(
    packs: List<PackEntry>,
    projects: List<ProjectEntry>,
    errors: List<String>,
    seedState: SeedResult?,
    seeding: Boolean,
    onSeed: () -> Unit,
    onImport: () -> Unit,
    onOpenPack: (PackEntry) -> Unit,
    onOpenProject: (ProjectEntry) -> Unit,
    onSearch: () -> Unit,
    onPackCenter: () -> Unit,
    onSettings: () -> Unit,
    onCommands: () -> Unit = {},
    archived: List<File> = emptyList(),
    onRestoreArchive: (File) -> Unit = {},
    refreshing: Boolean = false,
    onRefresh: () -> Unit = {}
) {
    var statusFilter by rememberSaveable { mutableStateOf<String?>(null) }
    val filterStatus = statusFilter?.let { ProjectStatus.fromWire(it) }
    val filteredProjects = remember(projects, statusFilter) { ProjectFilter.apply(projects, filterStatus) }

    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(
            title = stringResource(dev.ninfenz.mobile.R.string.nav_library),
            actions = {
                TextButton(onClick = onCommands, modifier = Modifier.heightIn(min = 48.dp)) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.action_commands))
                }
                IconButton(onClick = onSearch, modifier = Modifier.size(48.dp)) { Icon(Icons.Filled.Search, contentDescription = stringResource(dev.ninfenz.mobile.R.string.action_search)) }
                IconButton(onClick = onSettings, modifier = Modifier.size(48.dp)) { Icon(Icons.Filled.Settings, contentDescription = stringResource(dev.ninfenz.mobile.R.string.action_settings)) }
            }
        )
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
                NfGradientHero(
                    title = stringResource(dev.ninfenz.mobile.R.string.library_hero_title),
                    subtitle = stringResource(dev.ninfenz.mobile.R.string.library_hero_subtitle),
                    modifier = Modifier.padding(horizontal = NfSpacing.page)
                ) {
                    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        Button(onClick = onImport, modifier = Modifier.heightIn(min = 48.dp)) { Text(stringResource(dev.ninfenz.mobile.R.string.library_import)) }
                        TextButton(onClick = onSeed, enabled = !seeding, modifier = Modifier.heightIn(min = 48.dp)) {
                            Text(if (seeding) stringResource(dev.ninfenz.mobile.R.string.library_loading_sample) else stringResource(dev.ninfenz.mobile.R.string.library_load_sample))
                        }
                    }
                    SeedLine(seedState)
                }
            }
            if (projects.isNotEmpty()) {
                item {
                    LazyRow(
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = NfSpacing.page),
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
                item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.library_section_projects)) }
                items(filteredProjects.size) { index ->
                    val entry = filteredProjects[index]
                    NfCard(
                        modifier = Modifier.padding(horizontal = NfSpacing.page),
                        onClick = { onOpenProject(entry) }
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(entry.project.title, style = MaterialTheme.typography.titleMedium)
                                Text(entry.project.id, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            NfStatusChip(projectStatusLabel(entry.project))
                        }
                    }
                }
            } else if (projects.isNotEmpty()) {
                item {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.library_filter_empty),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(horizontal = NfSpacing.page)
                    )
                }
            }
            if (packs.isNotEmpty()) {
                item {
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
                                Text(pack.title, style = MaterialTheme.typography.titleMedium)
                                Text(
                                    pack.id + " · " + pack.version + " · " + pack.itemCount + " 项",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                            NfStatusChip(stringResource(dev.ninfenz.mobile.R.string.packcenter_installed))
                        }
                    }
                }
            }
            if (archived.isNotEmpty()) {
                item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.library_section_archive)) }
                items(archived.size) { index ->
                    val file = archived[index]
                    NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(file.name, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
                            TextButton(onClick = { onRestoreArchive(file) }) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.project_archive_restore))
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
                            Text(stringResource(dev.ninfenz.mobile.R.string.library_errors, errors.size), style = MaterialTheme.typography.titleMedium)
                            errors.take(3).forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
                        }
                    }
                }
            }
        }
        }
    }
}

@Composable
private fun SeedLine(seed: SeedResult?) {
    when (seed) {
        is SeedResult.Installed -> Text(
            stringResource(dev.ninfenz.mobile.R.string.library_seed_ready, seed.id, seed.version),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.primary
        )
        is SeedResult.AlreadyPresent -> Text(
            stringResource(dev.ninfenz.mobile.R.string.library_seed_exists, seed.id, seed.version),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.primary
        )
        is SeedResult.Failed -> Text(
            seed.message,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.error
        )
        null -> Unit
    }
}

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
                                Text(stringResource(dev.ninfenz.mobile.R.string.create_from_pack), style = MaterialTheme.typography.titleMedium)
                                Text(
                                    stringResource(dev.ninfenz.mobile.R.string.create_from_pack_subtitle),
                                    style = MaterialTheme.typography.bodySmall,
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
                    item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.create_section_projects)) }
                    items(projects.size) { index ->
                        val entry = projects[index]
                        NfCard(
                            modifier = Modifier.padding(horizontal = NfSpacing.page),
                            onClick = { onOpenProject(entry) }
                        ) {
                            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(entry.project.title, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                                    NfStatusChip(projectStatusLabel(entry.project))
                                }
                                Text(
                                    "Pack " + entry.project.refs.basePackId + " · " + entry.project.refs.basePackVersion,
                                    style = MaterialTheme.typography.bodySmall,
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
                item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.create_section_projects)) }
                items(projects.size) { index ->
                    val entry = projects[index]
                    NfCard(
                        modifier = Modifier.padding(horizontal = NfSpacing.page),
                        onClick = { onOpenProject(entry) }
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(entry.project.title, style = MaterialTheme.typography.titleMedium)
                                Text(
                                    "装配 / 校验 / 导出",
                                    style = MaterialTheme.typography.bodySmall,
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

@Composable
fun ProjectDetailScreen(
    project: Project,
    onBack: () -> Unit,
    onAuthor: () -> Unit,
    onAssembly: () -> Unit,
    onDuplicate: () -> Unit = {},
    onArchive: () -> Unit = {},
    compareCandidates: List<ProjectEntry> = emptyList()
) {
    val context = LocalContext.current
    val diffScope = rememberCoroutineScope()
    var showArchive by remember { mutableStateOf(false) }
    var diffReport by remember { mutableStateOf<ProjectDiff.Report?>(null) }
    var diffError by remember { mutableStateOf<String?>(null) }
    var showComparePicker by remember { mutableStateOf(false) }
    var compareQuery by remember { mutableStateOf("") }
    val diffPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: android.net.Uri? ->
        if (uri != null) {
            diffScope.launch {
                diffError = null
                try {
                    val text = withContext(Dispatchers.IO) {
                        context.contentResolver.openInputStream(uri)?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }
                    }
                    if (text == null) {
                        diffError = "无法读取所选项目文件"
                    } else {
                        diffReport = ProjectDiff.compare(project, ProjectModel.parse(text))
                    }
                } catch (t: Throwable) {
                    diffError = "项目解析失败：" + (t.message ?: t.javaClass.simpleName)
                }
            }
        }
    }
    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = project.title, onBack = onBack)
        LazyColumn(
            contentPadding = androidx.compose.foundation.layout.PaddingValues(NfSpacing.page),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
        ) {
            item {
                NfCard {
                    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_status), style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
                            NfStatusChip(projectStatusLabel(project))
                        }
                        Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_id, project.id), style = MaterialTheme.typography.bodySmall)
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.project_detail_pack, project.refs.basePackId, project.refs.basePackVersion),
                            style = MaterialTheme.typography.bodySmall
                        )
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.project_detail_protocol, project.refs.protocolId.ifBlank { "未绑定" }),
                            style = MaterialTheme.typography.bodySmall
                        )
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.project_detail_history, project.historyCount),
                            style = MaterialTheme.typography.bodySmall
                        )
                        TextButton(onClick = onDuplicate) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_duplicate))
                        }
                        TextButton(onClick = { showArchive = true }) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_archive))
                        }
                        TextButton(onClick = { diffPicker.launch(arrayOf("application/json", "*/*")) }) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_diff))
                        }
                        if (compareCandidates.isNotEmpty()) {
                            TextButton(onClick = { showComparePicker = true }) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.project_diff_library))
                            }
                        }
                    }
                }
            }
            if (project.history.isNotEmpty()) {
                item {
                    NfCard {
                        Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    stringResource(dev.ninfenz.mobile.R.string.project_history_title),
                                    style = MaterialTheme.typography.titleMedium,
                                    modifier = Modifier.weight(1f)
                                )
                                TextButton(onClick = {
                                    val md = ProjectHistoryExport.toMarkdown(project)
                                    val intent = ShareExporter.shareMarkdown(context, "nf-history-" + project.id, md)
                                    ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.project_history_share))
                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.project_history_share)) }
                            }
                            project.history.takeLast(20).forEach { h ->
                                Text(
                                    h.op + (h.digest?.let { " · " + it.take(12) } ?: "") + (h.at?.let { " · " + it } ?: ""),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                    }
                }
            }
            item {
                NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.project_detail_section_continue))
            }
            item { NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_detail_author), stringResource(dev.ninfenz.mobile.R.string.project_detail_author_subtitle), Icons.Filled.Edit, "›", onAuthor) }
            item { NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_detail_delivery), stringResource(dev.ninfenz.mobile.R.string.project_detail_delivery_subtitle), Icons.Filled.Info, "›", onAssembly) }
        }
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
                                    diffError = "项目解析失败：" + (t.message ?: t.javaClass.simpleName)
                                }
                            }
                        }) { Text(candidate.project.title + " · " + candidate.project.id) }
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
                            Text(change.field + ": " + change.before + " → " + change.after, style = MaterialTheme.typography.bodySmall)
                        }
                        report.historyOnlyBefore.forEach { Text("history -: " + it, style = MaterialTheme.typography.bodySmall) }
                        report.historyOnlyAfter.forEach { Text("history +: " + it, style = MaterialTheme.typography.bodySmall) }
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
                        Text(pack.id + " · " + pack.version, style = MaterialTheme.typography.titleMedium)
                        Text(pack.description, style = MaterialTheme.typography.bodyMedium)
                        Text(stringResource(dev.ninfenz.mobile.R.string.pack_detail_items, pack.itemCount), style = MaterialTheme.typography.bodySmall)
                        Text(stringResource(dev.ninfenz.mobile.R.string.pack_detail_tree, pack.tree.take(16) + "…"), style = MaterialTheme.typography.bodySmall)
                        Text(stringResource(dev.ninfenz.mobile.R.string.pack_detail_dir, pack.dir.absolutePath), style = MaterialTheme.typography.bodySmall)
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                when {
                                    pinnedTree == null -> stringResource(dev.ninfenz.mobile.R.string.pack_trust_unpinned)
                                    trustMatches -> stringResource(dev.ninfenz.mobile.R.string.pack_trust_pinned)
                                    else -> stringResource(dev.ninfenz.mobile.R.string.pack_trust_mismatch)
                                },
                                style = MaterialTheme.typography.bodySmall,
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
                                    report = "校验通过：verdict=" + (verdict ?: "pass") + (if (issues == "[]") "" else " · issues=" + issues)
                                } else {
                                    val err = response.error
                                    errorText = "[" + (err?.code ?: "NF-VAL-001") + "] " + (err?.message ?: "校验失败") + "；修复：" + (err?.fix ?: "查看诊断")
                                }
                                verifying = false
                            }
                        },
                        enabled = !verifying
                    ) { Text(if (verifying) "校验中…" else "校验 Pack") }
                    Button(onClick = onUpdate) { Text(stringResource(dev.ninfenz.mobile.R.string.pack_detail_update)) }
                }
            }
            if (report != null) {
                item {
                    Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = MaterialTheme.shapes.medium) {
                        Text(report!!, modifier = Modifier.padding(NfSpacing.m), style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            if (errorText != null) {
                item {
                    Surface(color = MaterialTheme.colorScheme.errorContainer, shape = MaterialTheme.shapes.medium) {
                        Text(errorText!!, modifier = Modifier.padding(NfSpacing.m), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onErrorContainer)
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
