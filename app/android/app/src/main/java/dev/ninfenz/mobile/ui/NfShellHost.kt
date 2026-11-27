package dev.ninfenz.mobile.ui

import android.content.Context
import android.net.Uri
import androidx.compose.runtime.MutableState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import dev.ninfenz.mobile.MainActivity
import dev.ninfenz.mobile.core.Core
import dev.ninfenz.mobile.data.AppPrefs
import dev.ninfenz.mobile.data.CommandHistoryStore
import dev.ninfenz.mobile.data.CreateProjectResult
import dev.ninfenz.mobile.data.LanguageMode
import dev.ninfenz.mobile.data.LibraryStore
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.PackSnapshot
import dev.ninfenz.mobile.data.PackStore
import dev.ninfenz.mobile.data.ProjectArchiver
import dev.ninfenz.mobile.data.ProjectCreator
import dev.ninfenz.mobile.data.ProjectEntry
import dev.ninfenz.mobile.data.ProjectPackageImporter
import dev.ninfenz.mobile.data.RecentProjectShortcuts
import dev.ninfenz.mobile.data.SampleSeeder
import dev.ninfenz.mobile.data.SeedResult
import dev.ninfenz.mobile.data.ThemeMode
import dev.ninfenz.mobile.data.UriIo
import dev.ninfenz.mobile.model.ProjectSort
import dev.ninfenz.mobile.model.ProjectSorter
import dev.ninfenz.mobile.share.SharePayload
import dev.ninfenz.mobile.ui.shell.Detail
import dev.ninfenz.mobile.ui.shell.ShellState
import dev.ninfenz.mobile.ui.shell.TopDestination
import dev.ninfenz.mobile.util.orNullLogged
import java.io.File
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * 应用外壳运行时宿主：集中持有 NfMobileApp 的界面状态、导航与后台动作，
 * 让壳层/路由 Composable 只保留结构；行为与拆分前一致。
 */
internal class NfShellHost(
    val context: Context,
    val scope: CoroutineScope,
    val prefs: AppPrefs
) {
    val library = LibraryStore(context.filesDir)
    val packStore = PackStore(context.filesDir)
    val seeder = SampleSeeder(context, context.filesDir, prefs)
    val projectCreator = ProjectCreator(context.filesDir)
    val commandHistory = CommandHistoryStore(context.filesDir)

    private var shellState: MutableState<ShellState> = mutableStateOf(ShellState())
    private var showCommandsState: MutableState<Boolean> = mutableStateOf(false)
    private var recentCommandsState: MutableState<List<String>> = mutableStateOf(commandHistory.load())

    var shell: ShellState
        get() = shellState.value
        set(value) {
            shellState.value = value
        }

    var showCommands: Boolean
        get() = showCommandsState.value
        set(value) {
            showCommandsState.value = value
        }

    var recentCommands: List<String>
        get() = recentCommandsState.value
        set(value) {
            recentCommandsState.value = value
        }

    var packs by mutableStateOf(PackSnapshot(emptyList(), emptyList()))
    var projects by mutableStateOf<List<ProjectEntry>>(emptyList())
    var archivedProjects by mutableStateOf<List<File>>(emptyList())
    var projectErrors by mutableStateOf<List<String>>(emptyList())
    var seedState by mutableStateOf<SeedResult?>(null)
    var seeding by mutableStateOf(false)
    var refreshing by mutableStateOf(false)
    var sharedPrefill by mutableStateOf<SharePayload?>(null)
    var quickPasteImport by mutableStateOf(false)
    var onboardingDone by mutableStateOf(prefs.onboardingDone)
    var showAbout by mutableStateOf(false)
    var missingPackWarning by mutableStateOf<Pair<String, String>?>(null)
    var storageText by mutableStateOf(context.getString(dev.ninfenz.mobile.R.string.storage_calculating))
    var nativeReady by mutableStateOf(false)
    var creatingProject by mutableStateOf(false)
    var createError by mutableStateOf<String?>(null)
    var demoTried by mutableStateOf(false)
    var abi by mutableStateOf<String?>(null)

    var themeMode: ThemeMode = ThemeMode.SYSTEM
    var onThemeMode: (ThemeMode) -> Unit = {}
    var languageMode: LanguageMode = LanguageMode.SYSTEM
    var onLanguageMode: (LanguageMode) -> Unit = {}
    var dynamicColor: Boolean = false
    var onDynamicColor: (Boolean) -> Unit = {}
    var launchProjectImport: () -> Unit = {}

    fun bind(shell: MutableState<ShellState>, showCommands: MutableState<Boolean>) {
        shellState = shell
        showCommandsState = showCommands
    }

    fun refresh() {
        refreshing = true
        scope.launch {
            val packSnapshot = withContext(Dispatchers.IO) { packStore.scan() }
            val projectSnapshot = withContext(Dispatchers.IO) { library.loadProjects() }
            val size = withContext(Dispatchers.IO) { dirSize(context.filesDir) }
            val diag = runCatching { withContext(Dispatchers.IO) { Core.diagnostics() } }.orNullLogged("NfMobileApp")
            packs = packSnapshot
            projects = projectSnapshot.projects
            RecentProjectShortcuts.publish(context, ProjectSorter.sort(projectSnapshot.projects, ProjectSort.RECENT), MainActivity::class.java)
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
            "import" -> open(Detail.Import)
            "inbox" -> open(Detail.Inbox)
            "new_project" -> open(Detail.NewProject)
            "search" -> open(Detail.Search)
            "pack_center" -> open(Detail.PackCenter)
            "pack_update" -> open(Detail.PackUpdate)
            "ccos" -> open(Detail.Ccos)
            "settings" -> open(Detail.Settings)
            "error_codes" -> open(Detail.ErrorCodes)
            "project_import" -> launchProjectImport()
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
                    open(Detail.Project(result.project.id))
                }
                is CreateProjectResult.Failure -> {
                    createError = context.getString(dev.ninfenz.mobile.R.string.error_with_fix, result.code, result.message, result.fix)
                }
            }
            creatingProject = false
        }
    }

    fun importProject(uri: Uri) {
        scope.launch {
            val result = runCatching {
                val temp = File(File(context.cacheDir, "imports").apply { mkdirs() }, "project.zip")
                withContext(Dispatchers.IO) {
                    UriIo.copyTo(context, uri, temp)
                    ProjectPackageImporter.import(context.filesDir, temp).also { temp.delete() }
                }
            }
            result.onSuccess { imported ->
                if (imported.packId.isNotBlank() && packs.packs.none { it.id == imported.packId && it.version == imported.packVersion }) {
                    missingPackWarning = imported.packId to imported.packVersion
                }
                refresh()
                open(Detail.Project(imported.id))
            }.onFailure {
                toast(context.getString(dev.ninfenz.mobile.R.string.project_package_import_failed, it.message ?: it.javaClass.simpleName))
            }
        }
    }

    fun openProjectImported(id: String, packId: String, packVersion: String) {
        if (packId.isNotBlank() && packs.packs.none { it.id == packId && it.version == packVersion }) {
            missingPackWarning = packId to packVersion
        }
        refresh()
        open(Detail.Project(id))
    }

    fun onBundleImported() {
        refresh()
        select(TopDestination.LIBRARY)
    }

    fun open(detail: Detail) {
        shell = shell.open(detail)
    }

    fun select(destination: TopDestination) {
        shell = shell.select(destination)
    }

    fun back() {
        shell = shell.back() ?: shell
    }

    fun backToLibrary() {
        shell = shell.back() ?: shell.select(TopDestination.LIBRARY)
    }

    fun toast(message: String, length: Int = android.widget.Toast.LENGTH_LONG) {
        android.widget.Toast.makeText(context, message, length).show()
    }
}

private fun dirSize(dir: File): Long {
    if (!dir.exists()) return 0L
    return dir.walkTopDown().filter { it.isFile }.sumOf { it.length() }
}

private fun humanSize(bytes: Long): String = when {
    bytes < 1024 -> bytes.toString() + " B"
    bytes < 1024 * 1024 -> (bytes / 1024).toString() + " KB"
    else -> String.format(java.util.Locale.US, "%.1f MB", bytes / 1024.0 / 1024.0)
}
