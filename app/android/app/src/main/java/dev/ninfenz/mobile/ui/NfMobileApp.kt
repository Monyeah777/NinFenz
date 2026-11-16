package dev.ninfenz.mobile.ui

import dev.ninfenz.mobile.ui.theme.NfMotion
import dev.ninfenz.mobile.ui.theme.NfSpacing

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.material3.VerticalDivider
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.res.stringResource
import dev.ninfenz.mobile.model.CommandPalette
import androidx.compose.ui.platform.LocalContext
import dev.ninfenz.mobile.core.Core
import dev.ninfenz.mobile.data.AppPrefs
import dev.ninfenz.mobile.data.CommandHistoryStore
import dev.ninfenz.mobile.data.LibraryStore
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.PackSnapshot
import dev.ninfenz.mobile.data.PackStore
import dev.ninfenz.mobile.data.CreateProjectResult
import dev.ninfenz.mobile.data.ProjectCreator
import dev.ninfenz.mobile.data.ProjectArchiver
import dev.ninfenz.mobile.data.ProjectDuplicator
import dev.ninfenz.mobile.data.ProjectEntry
import dev.ninfenz.mobile.data.SampleSeeder
import dev.ninfenz.mobile.data.SeedResult
import dev.ninfenz.mobile.data.LanguageMode
import dev.ninfenz.mobile.data.ThemeMode
import dev.ninfenz.mobile.share.ShareHandoff
import dev.ninfenz.mobile.ui.components.NfEmptyState
import dev.ninfenz.mobile.ui.screens.AssemblyScreen
import dev.ninfenz.mobile.ui.screens.AuthorScreen
import dev.ninfenz.mobile.ui.screens.CcosScreen
import dev.ninfenz.mobile.ui.screens.CreateScreen
import dev.ninfenz.mobile.ui.screens.DeliveryScreen
import dev.ninfenz.mobile.ui.screens.ErrorCodesScreen
import dev.ninfenz.mobile.ui.screens.DeliverScreen
import dev.ninfenz.mobile.ui.screens.GraphScreen
import dev.ninfenz.mobile.ui.screens.ImportScreen
import dev.ninfenz.mobile.ui.screens.LibraryHomeScreen
import dev.ninfenz.mobile.ui.screens.MeScreen
import dev.ninfenz.mobile.ui.screens.NewProjectScreen
import dev.ninfenz.mobile.ui.screens.OnboardingScreen
import dev.ninfenz.mobile.ui.screens.PackCenterScreen
import dev.ninfenz.mobile.ui.screens.PackDetailScreen
import dev.ninfenz.mobile.ui.screens.PackUpdateScreen
import dev.ninfenz.mobile.ui.screens.ProjectDetailScreen
import dev.ninfenz.mobile.ui.screens.ProtocolScreen
import dev.ninfenz.mobile.ui.screens.SearchScreen
import dev.ninfenz.mobile.ui.screens.SettingsScreen
import dev.ninfenz.mobile.ui.shell.Detail
import dev.ninfenz.mobile.ui.shell.ShellState
import dev.ninfenz.mobile.ui.shell.ShellStateCodec
import dev.ninfenz.mobile.ui.shell.TopDestination
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private val ShellStateSaver = Saver<ShellState, List<String>>(
    save = { ShellStateCodec.encode(it) },
    restore = { ShellStateCodec.decode(it) }
)

/**
 * v0.02 应用外壳：四目的地（库/创作/交付/我的）+ 自适应底部栏/rail + FAB 导入 + 单层详情。
 * 旧的 8 个功能页保留在详情层，保证 v1 能力可达；首启示例与引导在 W1 接入。
 */
@Composable
fun NfMobileApp(
    prefs: AppPrefs,
    themeMode: ThemeMode,
    onThemeMode: (ThemeMode) -> Unit,
    languageMode: LanguageMode = LanguageMode.SYSTEM,
    onLanguageMode: (LanguageMode) -> Unit = {},
    dynamicColor: Boolean = false,
    onDynamicColor: (Boolean) -> Unit = {},
    shortcut: String? = null,
    onShortcutConsumed: () -> Unit = {}
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val library = remember { LibraryStore(context.filesDir) }
    val packStore = remember { PackStore(context.filesDir) }
    val seeder = remember { SampleSeeder(context, context.filesDir, prefs) }
    val projectCreator = remember { ProjectCreator(context.filesDir) }
    val commandHistory = remember { CommandHistoryStore(context.filesDir) }
    var recentCommands by remember { mutableStateOf(commandHistory.load()) }

    var shell by rememberSaveable(stateSaver = ShellStateSaver) { mutableStateOf(ShellState()) }
    var packs by remember { mutableStateOf<PackSnapshot>(PackSnapshot(emptyList(), emptyList())) }
    var projects by remember { mutableStateOf<List<ProjectEntry>>(emptyList()) }
    var archivedProjects by remember { mutableStateOf<List<File>>(emptyList()) }
    var projectErrors by remember { mutableStateOf<List<String>>(emptyList()) }
    var seedState by remember { mutableStateOf<SeedResult?>(null) }
    var seeding by remember { mutableStateOf(false) }
    var refreshing by remember { mutableStateOf(false) }
    var sharedPrefill by remember { mutableStateOf<dev.ninfenz.mobile.share.SharePayload?>(null) }
    var onboardingDone by remember { mutableStateOf(prefs.onboardingDone) }
    var showAbout by remember { mutableStateOf(false) }
    var showCommands by rememberSaveable { mutableStateOf(false) }
    LaunchedEffect(Unit) {
        CommandBus.requests.collect { showCommands = true }
    }
    var storageText by remember { mutableStateOf("计算中…") }
    var nativeReady by remember { mutableStateOf(false) }
    var creatingProject by remember { mutableStateOf(false) }
    var createError by remember { mutableStateOf<String?>(null) }
    var demoTried by remember { mutableStateOf(false) }
    var abi by remember { mutableStateOf<String?>(null) }

    fun refresh() {
        refreshing = true
        scope.launch {
            val packSnapshot = withContext(Dispatchers.IO) { packStore.scan() }
            val projectSnapshot = withContext(Dispatchers.IO) { library.loadProjects() }
            val size = withContext(Dispatchers.IO) { dirSize(context.filesDir) }
            val diag = runCatching { withContext(Dispatchers.IO) { Core.diagnostics() } }.getOrNull()
            packs = packSnapshot
            projects = projectSnapshot.projects
            archivedProjects = withContext(Dispatchers.IO) { ProjectArchiver.list(context.filesDir) }
            projectErrors = projectSnapshot.errors
            storageText = humanSize(size)
            nativeReady = diag?.nativeReady == true
            abi = diag?.abiVersion
            refreshing = false
        }
    }

    fun runSeed() {
        if (seeding) return
        seeding = true
        scope.launch {
            seedState = seeder.seed()
            seeding = false
            refresh()
        }
    }

    fun runCommand(id: String) {
        showCommands = false
        commandHistory.record(id)
        recentCommands = commandHistory.load()
        when (id) {
            "import" -> shell = shell.open(Detail.Import)
            "new_project" -> shell = shell.open(Detail.NewProject)
            "search" -> shell = shell.open(Detail.Search)
            "pack_center" -> shell = shell.open(Detail.PackCenter)
            "pack_update" -> shell = shell.open(Detail.PackUpdate)
            "ccos" -> shell = shell.open(Detail.Ccos)
            "settings" -> shell = shell.open(Detail.Settings)
            "error_codes" -> shell = shell.open(Detail.ErrorCodes)
        }
    }

    fun createProject(pack: PackEntry, title: String) {
        if (creatingProject) return
        creatingProject = true
        createError = null
        scope.launch {
            when (val result = projectCreator.create(pack, title)) {
                is CreateProjectResult.Success -> {
                    refresh()
                    shell = shell.open(Detail.Project(result.project.id))
                }
                is CreateProjectResult.Failure -> {
                    createError = "[" + result.code + "] " + result.message + "；修复：" + result.fix
                }
            }
            creatingProject = false
        }
    }

    LaunchedEffect(Unit) {
        val pending = ShareHandoff.consume()
        if (pending != null) {
            sharedPrefill = pending
            shell = shell.open(Detail.Import)
        }
        refresh()
    }

    // 示例载入且核心可用时，自动生成演示项目（失败不阻断，库页仍可手动新建）。
    LaunchedEffect(nativeReady, packs.packs.size, projects.size) {
        if (!demoTried && nativeReady && projects.isEmpty() && packs.packs.isNotEmpty()) {
            demoTried = true
            val pack = packs.packs.first()
            when (val result = projectCreator.create(pack, "演示项目", "demo-project")) {
                is CreateProjectResult.Success -> refresh()
                is CreateProjectResult.Failure -> Unit
            }
        }
    }

    if (!onboardingDone) {
        OnboardingScreen(
            seedState = seedState,
            seeding = seeding,
            onSeed = ::runSeed,
            onDone = {
                prefs.onboardingDone = true
                onboardingDone = true
                refresh()
            },
            onSkip = {
                prefs.onboardingDone = true
                onboardingDone = true
            }
        )
        return
    }

    LaunchedEffect(shortcut, onboardingDone) {
        if (onboardingDone && shortcut != null) {
            when (shortcut) {
                "import" -> shell = shell.open(Detail.Import)
                "new_project" -> shell = shell.open(Detail.NewProject)
                "search" -> shell = shell.open(Detail.Search)
            }
            onShortcutConsumed()
        }
    }

    val layout = layoutClassFor(LocalConfiguration.current.screenWidthDp)
    val compact = layout == LayoutClass.COMPACT

    BackHandler(enabled = shell.detail != null || shell.destination != TopDestination.LIBRARY) {
        val next = shell.back()
        shell = next ?: shell.select(TopDestination.LIBRARY)
    }

    val topLevelContent: @Composable () -> Unit = {
        when (shell.destination) {

                        TopDestination.LIBRARY -> LibraryHomeScreen(
                            packs = packs.packs,
                            projects = projects,
                            errors = packs.errors + projectErrors,
                            seedState = seedState,
                            seeding = seeding,
                            onSeed = ::runSeed,
                            onImport = { shell = shell.open(Detail.Import) },
                            onOpenPack = { shell = shell.open(Detail.Pack(it.id, it.version)) },
                            onOpenProject = { shell = shell.open(Detail.Project(it.project.id)) },
                            onSearch = { shell = shell.open(Detail.Search) },
                            onPackCenter = { shell = shell.open(Detail.PackCenter) },
                            onSettings = { shell = shell.open(Detail.Settings) },
                            onCommands = { showCommands = true },
                            archived = archivedProjects,
                            onRestoreArchive = { file ->
                                scope.launch {
                                    val restored = withContext(Dispatchers.IO) {
                                        ProjectArchiver.restore(file, context.filesDir)
                                    }
                                    refresh()
                                    shell = shell.open(
                                        Detail.Project(restored.name.removeSuffix(".nfproject.json"))
                                    )
                                }
                            },
                            refreshing = refreshing,
                            onRefresh = { refresh() }
                        )
                        TopDestination.CREATE -> CreateScreen(
                            projects = projects,
                            packs = packs.packs,
                            onImport = { shell = shell.open(Detail.Import) },
                            onCreateProject = { shell = shell.open(Detail.NewProject) },
                            onOpenProject = { shell = shell.open(Detail.Project(it.project.id)) },
                            onGoLibrary = { shell = shell.select(TopDestination.LIBRARY) },
                            onLoadSample = ::runSeed
                        )
                        TopDestination.DELIVER -> DeliverScreen(
                            projects = projects,
                            onOpenProject = { shell = shell.open(Detail.Project(it.project.id)) },
                            onOpenDelivery = { shell = shell.open(Detail.Delivery(it.project.id)) },
                            onGoCreate = { shell = shell.select(TopDestination.CREATE) },
                            onPackUpdate = { shell = shell.open(Detail.PackCenter) },
                            onCcos = { shell = shell.open(Detail.Ccos) }
                        )
                        TopDestination.ME -> MeScreen(
                            themeMode = themeMode,
                            onThemeMode = onThemeMode,
                            languageMode = languageMode,
                            onLanguageMode = onLanguageMode,
                            dynamicColor = dynamicColor,
                            onDynamicColor = onDynamicColor,
                            storageText = storageText,
                            nativeReady = nativeReady,
                            abi = abi,
                            onSettings = { shell = shell.open(Detail.Settings) },
                            onAbout = { showAbout = true }
                        )
                    
        }
    }
    val detailContent: @Composable () -> Unit = {
        when (val detail = shell.detail) {
            null -> Unit
is Detail.Import -> ImportScreen(
                        prefill = sharedPrefill,
                        store = library,
                        onBack = {
                            sharedPrefill = null
                            shell = shell.back() ?: shell
                        },
                        onPrefillConsumed = { sharedPrefill = null }
                    )
                    is Detail.NewProject -> NewProjectScreen(
                        packs = packs.packs,
                        creating = creatingProject,
                        error = createError,
                        onBack = { shell = shell.back() ?: shell },
                        onLoadSample = {
                            shell = shell.select(TopDestination.LIBRARY)
                            runSeed()
                        },
                        onCreate = { pack, title -> createProject(pack, title) }
                    )
                    is Detail.Search -> SearchScreen(
                        onBack = { shell = shell.back() ?: shell },
                        onOpenPack = { id, version -> shell = shell.open(Detail.Pack(id, version)) },
                        onOpenProject = { id -> shell = shell.open(Detail.Project(id)) }
                    )
                    is Detail.Settings -> SettingsScreen(
                        onBack = { shell = shell.back() ?: shell },
                        onErrorCodes = { shell = shell.open(Detail.ErrorCodes) }
                    )
                    is Detail.ErrorCodes -> ErrorCodesScreen(onBack = { shell = shell.back() ?: shell })
                    is Detail.Author -> {
                        val entry = projects.firstOrNull { it.project.id == detail.id }
                        if (entry == null) {
                            NfEmptyState(
                                icon = Icons.Filled.Edit,
                                title = "项目不存在",
                                message = "可能已被删除或文件损坏。",
                                actionLabel = "返回库",
                                onAction = { shell = shell.back() ?: shell }
                            )
                        } else {
                            val pack = packs.packs.firstOrNull {
                                it.id == entry.project.refs.basePackId && it.version == entry.project.refs.basePackVersion
                            }
                            AuthorScreen(
                                project = entry.project,
                                pack = pack,
                                onBack = { shell = shell.back() ?: shell },
                                onAssembly = { shell = shell.open(Detail.Delivery(entry.project.id)) },
                                onSaved = { refresh() }
                            )
                        }
                    }
                    is Detail.Protocol -> ProtocolScreen(onBack = { shell = shell.back() ?: shell })
                    is Detail.Graph -> GraphScreen(store = library, onBack = { shell = shell.back() ?: shell })
                    is Detail.Delivery -> {
                        val entry = projects.firstOrNull { it.project.id == detail.id }
                        if (entry == null) {
                            NfEmptyState(
                                icon = Icons.Filled.Info,
                                title = "项目不存在",
                                message = "可能已被删除或文件损坏。",
                                actionLabel = "返回库",
                                onAction = { shell = shell.back() ?: shell }
                            )
                        } else {
                            val pack = packs.packs.firstOrNull {
                                it.id == entry.project.refs.basePackId && it.version == entry.project.refs.basePackVersion
                            }
                            DeliveryScreen(project = entry.project, pack = pack, onBack = { shell = shell.back() ?: shell }, onStatusChanged = { refresh() })
                        }
                    }
                    is Detail.Assembly -> AssemblyScreen(onBack = { shell = shell.back() ?: shell })
                    is Detail.PackCenter -> PackCenterScreen(
                        packs = packs.packs,
                        onBack = { shell = shell.back() ?: shell },
                        onOpenPack = { pack -> shell = shell.open(Detail.Pack(pack.id, pack.version)) },
                        onUpdatePlan = { shell = shell.open(Detail.PackUpdate) },
                        onLoadSample = ::runSeed,
                        refreshing = refreshing,
                        onRefresh = { refresh() }
                    )
                    is Detail.PackUpdate -> PackUpdateScreen(store = library, onBack = { shell = shell.back() ?: shell })
                    is Detail.Ccos -> CcosScreen(onBack = { shell = shell.back() ?: shell })
                    is Detail.Pack -> {
                        val pack = packs.packs.firstOrNull { it.id == detail.id && it.version == detail.version }
                        if (pack == null) {
                            NfEmptyState(
                                icon = Icons.Filled.Home,
                                title = "Pack 不存在",
                                message = "可能已被删除或版本变化。",
                                actionLabel = "返回库",
                                onAction = { shell = shell.back() ?: shell }
                            )
                        } else {
                            PackDetailScreen(pack, onBack = { shell = shell.back() ?: shell }, onUpdate = { shell = shell.open(Detail.PackUpdate) })
                        }
                    }
                    is Detail.Project -> {
                        val entry = projects.firstOrNull { it.project.id == detail.id }
                        if (entry == null) {
                            NfEmptyState(
                                icon = Icons.Filled.Edit,
                                title = "项目不存在",
                                message = "可能已被删除或文件损坏。",
                                actionLabel = "返回库",
                                onAction = { shell = shell.back() ?: shell }
                            )
                        } else {
                            ProjectDetailScreen(
                                project = entry.project,
                                onBack = { shell = shell.back() ?: shell },
                                onAuthor = { shell = shell.open(Detail.Author(entry.project.id)) },
                                onAssembly = { shell = shell.open(Detail.Delivery(entry.project.id)) },
                                onArchive = {
                                    scope.launch {
                                        withContext(Dispatchers.IO) { ProjectArchiver.archive(entry.file, context.filesDir) }
                                        refresh()
                                        shell = shell.select(TopDestination.LIBRARY)
                                    }
                                },
                                onDuplicate = {
                                    scope.launch {
                                        val copy = withContext(Dispatchers.IO) {
                                            ProjectDuplicator.duplicate(entry.file, context.filesDir)
                                        }
                                        refresh()
                                        shell = shell.open(Detail.Project(copy.name.removeSuffix(".nfproject.json")))
                                    }
                                }
                            )
                        }
                    }
                
        }
    }

    Scaffold(
        contentWindowInsets = WindowInsets(0),
        bottomBar = {
            if (compact && shell.detail == null) {
                NfBottomBar(shell.destination) { shell = shell.select(it) }
            }
        },
        floatingActionButton = {
            if (shell.detail == null && shell.destination == TopDestination.LIBRARY) {
                FloatingActionButton(onClick = { shell = shell.open(Detail.Import) }) {
                    Icon(Icons.Filled.Add, contentDescription = stringResource(dev.ninfenz.mobile.R.string.action_import))
                }
            }
        }
    ) { padding ->
        Row(modifier = Modifier.fillMaxSize()) {
            if (!compact) {
                NfRail(shell.destination) { shell = shell.select(it) }
            }
            Box(modifier = Modifier.weight(1f).padding(padding)) {
                Crossfade(
                    targetState = shell.detail,
                    animationSpec = tween(durationMillis = NfMotion.MEDIUM_MS),
                    label = "nf-shell"
                ) { detail ->
                    if (detail == null) {
                        topLevelContent()
                    } else if (!compact && LocalConfiguration.current.screenWidthDp >= 840) {
                        Row(modifier = Modifier.fillMaxSize()) {
                            Box(modifier = Modifier.width(380.dp).fillMaxHeight()) { topLevelContent() }
                            VerticalDivider()
                            Box(modifier = Modifier.weight(1f)) { detailContent() }
                        }
                    } else {
                        detailContent()
                    }
                }
            }
        }
    }

    if (showAbout) {
        AlertDialog(
            onDismissRequest = { showAbout = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.about_title)) },
            text = {
                Text("NF Mobile 0.2.0（v0.02）\n本地处理 · 无网络权限 · 无遥测\nMIT License · 详见仓库 app/docs/LEGAL.md")
            },
            confirmButton = { TextButton(onClick = { showAbout = false }) { Text(stringResource(dev.ninfenz.mobile.R.string.action_close)) } }
        )
    }

    if (showCommands) {
        val items = listOf(
            CommandPalette.Item("import", stringResource(dev.ninfenz.mobile.R.string.action_import)),
            CommandPalette.Item("new_project", stringResource(dev.ninfenz.mobile.R.string.new_project_title)),
            CommandPalette.Item("search", stringResource(dev.ninfenz.mobile.R.string.search_title)),
            CommandPalette.Item("pack_center", stringResource(dev.ninfenz.mobile.R.string.deliver_pack_center_title)),
            CommandPalette.Item("pack_update", stringResource(dev.ninfenz.mobile.R.string.pack_detail_update)),
            CommandPalette.Item("ccos", stringResource(dev.ninfenz.mobile.R.string.ccos_title)),
            CommandPalette.Item("settings", stringResource(dev.ninfenz.mobile.R.string.settings_title)),
            CommandPalette.Item("error_codes", stringResource(dev.ninfenz.mobile.R.string.error_codes_title))
        )
        CommandPaletteDialog(CommandPalette.order(items, recentCommands), onDismiss = { showCommands = false }, onRun = ::runCommand)
    }
}

@Composable
private fun CommandPaletteDialog(
    items: List<CommandPalette.Item>,
    onDismiss: () -> Unit,
    onRun: (String) -> Unit
) {
    var query by rememberSaveable { mutableStateOf("") }
    val filtered = CommandPalette.filter(items, query)
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(dev.ninfenz.mobile.R.string.commands_title)) },
        text = {
            Column {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text(stringResource(dev.ninfenz.mobile.R.string.commands_placeholder)) },
                    singleLine = true
                )
                if (filtered.isEmpty()) {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.commands_no_result),
                        modifier = Modifier.padding(NfSpacing.m)
                    )
                } else {
                    LazyColumn(modifier = Modifier.heightIn(max = 360.dp)) {
                        items(filtered, key = { it.id }) { item ->
                            Text(
                                item.title,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { onRun(item.id) }
                                    .padding(horizontal = NfSpacing.m, vertical = 12.dp)
                            )
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text(stringResource(dev.ninfenz.mobile.R.string.action_close)) }
        }
    )
}

@Composable
private fun NfBottomBar(current: TopDestination, onSelect: (TopDestination) -> Unit) {
    NavigationBar {
        TopDestination.entries.forEach { destination ->
            NavigationBarItem(
                selected = destination == current,
                onClick = { onSelect(destination) },
                icon = { Icon(destinationIcon(destination), contentDescription = null) },
                label = { Text(stringResource(destination.labelRes)) }
            )
        }
    }
}

@Composable
private fun NfRail(current: TopDestination, onSelect: (TopDestination) -> Unit) {
    NavigationRail {
        TopDestination.entries.forEach { destination ->
            NavigationRailItem(
                selected = destination == current,
                onClick = { onSelect(destination) },
                icon = { Icon(destinationIcon(destination), contentDescription = null) },
                label = { Text(stringResource(destination.labelRes)) }
            )
        }
    }
}

private fun destinationIcon(destination: TopDestination) = when (destination) {
    TopDestination.LIBRARY -> Icons.Filled.Home
    TopDestination.CREATE -> Icons.Filled.Edit
    TopDestination.DELIVER -> Icons.AutoMirrored.Filled.List
    TopDestination.ME -> Icons.Filled.Person
}

private fun dirSize(dir: File): Long {
    if (!dir.exists()) return 0L
    return dir.walkTopDown().filter { it.isFile }.sumOf { it.length() }
}

private fun humanSize(bytes: Long): String = when {
    bytes < 1024 -> bytes.toString() + " B"
    bytes < 1024 * 1024 -> (bytes / 1024).toString() + " KB"
    else -> String.format("%.1f MB", bytes / 1024.0 / 1024.0)
}
