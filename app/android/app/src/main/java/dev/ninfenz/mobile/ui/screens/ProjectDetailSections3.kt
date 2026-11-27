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
internal fun ProjectDetailChangePackSheet(s: ProjectDetailState) {
    if (s.showChangePack) {
        ModalBottomSheet(onDismissRequest = { s.showChangePack = false }) {
            Column(
                modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page).padding(bottom = NfSpacing.xl),
                verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)
            ) {
                Text(stringResource(dev.ninfenz.mobile.R.string.project_change_pack), style = NfType.screenTitle)
                Text(stringResource(dev.ninfenz.mobile.R.string.project_change_pack_note), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                OutlinedTextField(
                    value = s.packQuery,
                    onValueChange = { s.packQuery = it },
                    label = { Text(stringResource(dev.ninfenz.mobile.R.string.pack_search)) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                HorizontalDivider(modifier = Modifier.padding(vertical = NfSpacing.s))
                s.packs.filter { s.packQuery.isBlank() || it.title.contains(s.packQuery, true) || it.id.contains(s.packQuery, true) }.forEach { pack ->
                    NfListRow(
                        pack.title,
                        pack.id + " · " + pack.version + " · " + pack.itemCount + " items",
                        Icons.Filled.Add,
                        "›"
                    ) {
                        s.showChangePack = false
                        s.onChangePack(pack)
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ProjectDetailDeleteDialog(s: ProjectDetailState) {
    if (s.showDelete) {
        AlertDialog(
            onDismissRequest = { s.showDelete = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.project_delete_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.project_delete_body, s.project.title)) },
            confirmButton = {
                TextButton(onClick = {
                    s.showDelete = false
                    s.onDelete()
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.project_delete_confirm)) }
            },
            dismissButton = {
                TextButton(onClick = { s.showDelete = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ProjectDetailReviewDialog(s: ProjectDetailState) {
    if (s.showAudit && s.showReview) {
        AlertDialog(
            onDismissRequest = { s.showReview = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_review)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.project_review_current, s.project.review.state), style = NfType.meta)
                    OutlinedTextField(
                        value = s.reviewer,
                        onValueChange = { s.reviewer = it },
                        singleLine = true,
                        label = { Text(stringResource(dev.ninfenz.mobile.R.string.project_review_reviewer)) }
                    )
                    OutlinedTextField(
                        value = s.reviewNote,
                        onValueChange = { s.reviewNote = it },
                        label = { Text(stringResource(dev.ninfenz.mobile.R.string.project_review_note)) }
                    )
                    if (!s.canApprove) {
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
                    enabled = s.canApprove && s.reviewer.isNotBlank() && s.reviewNote.isNotBlank(),
                    onClick = {
                        s.showReview = false
                        s.onReview(true, s.reviewer, s.reviewNote)
                    }
                ) { Text(stringResource(dev.ninfenz.mobile.R.string.project_review_approve)) }
            },
            dismissButton = {
                TextButton(
                    enabled = s.reviewer.isNotBlank() && s.reviewNote.isNotBlank(),
                    onClick = {
                        s.showReview = false
                        s.onReview(false, s.reviewer, s.reviewNote)
                    }
                ) { Text(stringResource(dev.ninfenz.mobile.R.string.project_review_reject)) }
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ProjectDetailRenameDialog(s: ProjectDetailState) {
    if (s.showRename) {
        AlertDialog(
            onDismissRequest = { s.showRename = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_rename)) },
            text = {
                OutlinedTextField(
                    value = s.renameText,
                    onValueChange = { s.renameText = it },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    label = { Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_rename_label)) }
                )
            },
            confirmButton = {
                TextButton(
                    enabled = s.renameText.isNotBlank(),
                    onClick = {
                        s.showRename = false
                        s.onRename(s.renameText.trim())
                    }
                ) { Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_rename_confirm)) }
            },
            dismissButton = {
                TextButton(onClick = { s.showRename = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ProjectDetailComparePickerDialog(s: ProjectDetailState) {
    if (s.showComparePicker) {
        AlertDialog(
            onDismissRequest = { s.showComparePicker = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.project_diff_library)) },
            text = {
                Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                    OutlinedTextField(
                        value = s.compareQuery,
                        onValueChange = { s.compareQuery = it },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        placeholder = { Text(stringResource(dev.ninfenz.mobile.R.string.project_diff_search)) }
                    )
                    s.compareCandidates.filter {
                        it.project.id != s.project.id &&
                            (s.compareQuery.isBlank() || it.project.title.contains(s.compareQuery, ignoreCase = true) || it.project.id.contains(s.compareQuery, ignoreCase = true))
                    }.forEach { candidate ->
                        TextButton(onClick = {
                            s.showComparePicker = false
                            s.compareWith(candidate)
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
                TextButton(onClick = { s.showComparePicker = false }) { Text(stringResource(dev.ninfenz.mobile.R.string.action_close)) }
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ProjectDetailDiffErrorDialog(s: ProjectDetailState) {
    s.diffError?.let { message ->
        AlertDialog(
            onDismissRequest = { s.diffError = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_diff)) },
            text = { Text(message) },
            confirmButton = { TextButton(onClick = { s.diffError = null }) { Text(stringResource(dev.ninfenz.mobile.R.string.action_close)) } }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ProjectDetailDiffReportDialog(s: ProjectDetailState) {
    s.diffReport?.let { report ->
        AlertDialog(
            onDismissRequest = { s.diffReport = null },
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
            confirmButton = { TextButton(onClick = { s.diffReport = null }) { Text(stringResource(dev.ninfenz.mobile.R.string.action_close)) } }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ProjectDetailArchiveDialog(s: ProjectDetailState) {
    if (s.showArchive) {
        AlertDialog(
            onDismissRequest = { s.showArchive = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.project_archive_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.project_archive_body)) },
            confirmButton = {
                TextButton(onClick = {
                    s.showArchive = false
                    s.onArchive()
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.project_archive_confirm)) }
            },
            dismissButton = {
                TextButton(onClick = { s.showArchive = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}

