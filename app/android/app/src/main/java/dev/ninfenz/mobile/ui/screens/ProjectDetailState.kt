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

internal class ProjectDetailState(
    var project: Project,
    val context: android.content.Context,
    val clipboard: androidx.compose.ui.platform.ClipboardManager,
    val diffScope: kotlinx.coroutines.CoroutineScope,
    var packs: List<PackEntry>,
    var compareCandidates: List<ProjectEntry>,
    val projects: List<ProjectEntry>,
    var onBack: () -> Unit,
    var onAuthor: () -> Unit,
    var onAssembly: () -> Unit,
    var onDuplicate: () -> Unit,
    var onChangePack: (PackEntry) -> Unit,
    var onArchive: () -> Unit,
    var onRename: (String) -> Unit,
    var onReview: (Boolean, String, String) -> Unit,
    var onReviewBlocks: () -> Unit,
    var onFavoriteChanged: () -> Unit,
    var onShare: () -> Unit,
    var onShareFull: () -> Unit,
    var onSaveAsTemplate: () -> Unit,
    var onExportTemplatePackage: () -> Unit,
    var onDelete: () -> Unit,
    var onFlow: () -> Unit,
    historyExpandedState: androidx.compose.runtime.MutableState<Boolean>,
    reviewerState: androidx.compose.runtime.MutableState<String>,
    reviewNoteState: androidx.compose.runtime.MutableState<String>,
) {
    val showAudit = dev.ninfenz.mobile.data.FeatureGate.auditEnabled()

    val metaStore = LibraryMetaStore(context.filesDir)

    val packLockStore = PackLockStore(context.filesDir)

    var packLock by mutableStateOf(packLockStore.load(project.id))

    var packLockNote by mutableStateOf<String?>(null)

    var isFavorite by mutableStateOf(metaStore.isFavorite(project.id))

    var tags by mutableStateOf(metaStore.tags(project.id))

    var showTags by mutableStateOf(false)

    var tagText by mutableStateOf("")

    var showArchive by mutableStateOf(false)

    var diffReport by mutableStateOf<ProjectDiff.Report?>(null)

    var diffError by mutableStateOf<String?>(null)

    var showComparePicker by mutableStateOf(false)

    var compareQuery by mutableStateOf("")

    var showDelete by mutableStateOf(false)

    var showRename by mutableStateOf(false)

    var renameText by mutableStateOf(project.title)

    var showReview by mutableStateOf(false)

    var showMoreActions by mutableStateOf(false)

    var showChangePack by mutableStateOf(false)

    var packQuery by mutableStateOf("")

    var showRemoveOverride by mutableStateOf(false)

    var showTemplateReference by mutableStateOf(false)

    var hasSpecOverride by mutableStateOf(dev.ninfenz.mobile.data.ProjectPaths.specOverride(context.filesDir, project.id).isFile)

    val canApprove = project.status in setOf(ProjectStatus.VALIDATED, ProjectStatus.EXPORTED, ProjectStatus.REVIEWED)

    var reviewStale by mutableStateOf(false)

    var templateReference: String? = null

    var historyExpanded by historyExpandedState

    var reviewer by reviewerState

    var reviewNote by reviewNoteState

    var projectId: String = project.id
    var launchDiffPicker: (Array<String>) -> Unit = {}

    fun resetForProject(project: Project) {
        this.project = project
        projectId = project.id
        packLock = packLockStore.load(project.id)
        packLockNote = null
        isFavorite = metaStore.isFavorite(project.id)
        tags = metaStore.tags(project.id)
        hasSpecOverride = dev.ninfenz.mobile.data.ProjectPaths.specOverride(context.filesDir, project.id).isFile
        renameText = project.title
    }

    fun onDiffPicked(uri: android.net.Uri?) {
        if (uri != null) {
            diffScope.launch {
                diffError = null
                try {
                    val text = withContext(Dispatchers.IO) {
                        UriIo.readText(context, uri)
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

    fun compareWith(candidate: ProjectEntry) {
        diffScope.launch {
            try {
                val text = withContext(Dispatchers.IO) { candidate.file.readText(Charsets.UTF_8) }
                diffReport = ProjectDiff.compare(project, ProjectModel.parse(text))
            } catch (t: Throwable) {
                diffError = context.getString(dev.ninfenz.mobile.R.string.project_parse_failed, t.message ?: t.javaClass.simpleName)
            }
        }
    }

    suspend fun refreshReviewStale() {
        reviewStale = runCatching {
            withContext(Dispatchers.IO) {
                dev.ninfenz.mobile.data.ProjectReviewStore(context.filesDir).isStale(
                    dev.ninfenz.mobile.data.ProjectPaths.projectJson(context.filesDir, project.id)
                )
            }
        }.getOrDefault(false)
    }
}
