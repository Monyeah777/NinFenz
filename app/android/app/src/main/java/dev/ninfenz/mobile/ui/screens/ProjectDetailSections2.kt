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
internal fun LazyListScope.ProjectDetailHistoryCard(s: ProjectDetailState) {
            if (s.historyExpanded && (s.project.historyCount > 0 || s.project.history.isNotEmpty())) {
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
                                    val md = ProjectHistoryExport.toMarkdown(s.project)
                                    val intent = ShareExporter.shareMarkdown(s.context, "nf-history-" + s.project.id, md)
                                    ShareExporter.launchChooser(s.context, intent, s.context.getString(dev.ninfenz.mobile.R.string.project_history_share))
                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.project_history_share)) }
                            }
                            if (s.project.history.isEmpty()) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_history, s.project.historyCount), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            } else {
                                s.project.history.takeLast(20).forEach { h ->
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

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ProjectDetailTemplateRefDialog(s: ProjectDetailState) {
    val templateRef = s.templateReference ?: return
    if (s.showTemplateReference) {
        AlertDialog(
            onDismissRequest = { s.showTemplateReference = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.author_template_ref)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        TextButton(onClick = { s.clipboard.setText(androidx.compose.ui.text.AnnotatedString(templateRef)) }) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.author_template_copy))
                        }
                        TextButton(onClick = {
                            val intent = dev.ninfenz.mobile.share.ShareExporter.shareMarkdown(s.context, "nf-template", templateRef)
                            dev.ninfenz.mobile.share.ShareExporter.launchChooser(s.context, intent, s.context.getString(dev.ninfenz.mobile.R.string.author_template_share))
                        }) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.author_template_share))
                        }
                    }
                    Column(modifier = Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState())) {
                        dev.ninfenz.mobile.ui.components.MarkdownPreview(templateRef, limitBlocks = 40)
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { s.showTemplateReference = false }) { Text(stringResource(android.R.string.ok)) }
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ProjectDetailRemoveOverrideDialog(s: ProjectDetailState) {
    if (s.showRemoveOverride) {
        AlertDialog(
            onDismissRequest = { s.showRemoveOverride = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.template_override_remove_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.template_override_remove_body)) },
            confirmButton = {
                TextButton(onClick = {
                    dev.ninfenz.mobile.data.DraftProjectBinder.clearSpec(s.context.filesDir, s.project.id)
                    s.hasSpecOverride = false
                    s.showRemoveOverride = false
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.template_override_remove)) }
            },
            dismissButton = {
                TextButton(onClick = { s.showRemoveOverride = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ProjectDetailMoreActionsSheet(s: ProjectDetailState) {
    if (s.showMoreActions) {
        ModalBottomSheet(onDismissRequest = { s.showMoreActions = false }) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = NfSpacing.page)
                    .padding(bottom = NfSpacing.xl),
                verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)
            ) {
                ProjectDetailMoreActionsManage(s)
                ProjectDetailMoreActionsShare(s)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ProjectDetailMoreActionsManage(s: ProjectDetailState) {
                Text(stringResource(dev.ninfenz.mobile.R.string.project_more_actions), style = NfType.screenTitle)
                Text(s.project.title, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                HorizontalDivider(modifier = Modifier.padding(vertical = NfSpacing.s))
                Text(stringResource(dev.ninfenz.mobile.R.string.project_actions_manage), style = NfType.label, color = MaterialTheme.colorScheme.onSurfaceVariant)
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_detail_rename), null, Icons.Filled.Edit, "›") {
                    s.showMoreActions = false
                    s.renameText = s.project.title
                    s.showRename = true
                }
                if (s.showAudit) {
                    NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_detail_review), null, Icons.Filled.Info, "›") {
                        s.showMoreActions = false
                        s.showReview = true
                    }
                    NfListRow(stringResource(dev.ninfenz.mobile.R.string.review_blocks_title), null, Icons.Filled.Search, "›") {
                        s.showMoreActions = false
                        s.onReviewBlocks()
                    }
                }
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_tags), null, Icons.Filled.Search, "›") {
                    s.showMoreActions = false
                    s.tagText = ""
                    s.showTags = true
                }
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_detail_duplicate), null, Icons.Filled.Add, "›") {
                    s.showMoreActions = false
                    s.onDuplicate()
                }
                if (s.packs.isNotEmpty()) {
                    NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_change_pack), null, Icons.Filled.Add, "›") {
                        s.showMoreActions = false
                        s.showChangePack = true
                    }
                }
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.flow_title), null, Icons.AutoMirrored.Filled.List, "›") {
                    s.showMoreActions = false
                    s.onFlow()
                }
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_detail_archive), null, Icons.Filled.Info, "›") {
                    s.showMoreActions = false
                    s.showArchive = true
                }
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_detail_diff), null, Icons.AutoMirrored.Filled.List, "›") {
                    s.showMoreActions = false
                    s.launchDiffPicker(arrayOf("application/json", "*/*"))
                }
                if (s.compareCandidates.isNotEmpty()) {
                    NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_diff_library), null, Icons.AutoMirrored.Filled.List, "›") {
                        s.showMoreActions = false
                        s.showComparePicker = true
                    }
                }
                HorizontalDivider(modifier = Modifier.padding(vertical = NfSpacing.s))
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ProjectDetailMoreActionsShare(s: ProjectDetailState) {
                Text(stringResource(dev.ninfenz.mobile.R.string.project_actions_share), style = NfType.label, color = MaterialTheme.colorScheme.onSurfaceVariant)
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_detail_share), null, Icons.Filled.Search, "›") {
                    s.showMoreActions = false
                    s.onShare()
                }
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_detail_share_full), null, Icons.Filled.Search, "›") {
                    s.showMoreActions = false
                    s.onShareFull()
                }
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_save_template), null, Icons.Filled.Search, "›") {
                    s.showMoreActions = false
                    s.onSaveAsTemplate()
                }
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_export_template), null, Icons.Filled.Search, "›") {
                    s.showMoreActions = false
                    s.onExportTemplatePackage()
                }
                NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_copy_id), null, Icons.Filled.Search, "›") {
                    s.showMoreActions = false
                    s.clipboard.setText(androidx.compose.ui.text.AnnotatedString(s.project.id))
                    android.widget.Toast.makeText(s.context, s.context.getString(dev.ninfenz.mobile.R.string.project_copy_id), android.widget.Toast.LENGTH_SHORT).show()
                }
                HorizontalDivider(modifier = Modifier.padding(vertical = NfSpacing.s))
                Text(stringResource(dev.ninfenz.mobile.R.string.project_actions_danger), style = NfType.label, color = MaterialTheme.colorScheme.onSurfaceVariant)
                TextButton(
                    onClick = {
                        s.showMoreActions = false
                        s.showDelete = true
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_delete), color = MaterialTheme.colorScheme.error)
                }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ProjectDetailTagsDialog(s: ProjectDetailState) {
    if (s.showTags) {
        AlertDialog(
            onDismissRequest = { s.showTags = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.project_tags)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    if (s.tags.isEmpty()) Text(stringResource(dev.ninfenz.mobile.R.string.project_tag_empty), style = NfType.meta)
                    s.tags.sorted().forEach { tag ->
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Text("#" + tag, style = NfType.meta)
                            TextButton(onClick = { s.tags = s.metaStore.removeTag(s.project.id, tag); s.onFavoriteChanged() }) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.inbox_remove))
                            }
                        }
                    }
                    OutlinedTextField(
                        value = s.tagText,
                        onValueChange = { s.tagText = it },
                        label = { Text(stringResource(dev.ninfenz.mobile.R.string.project_tag_hint)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            },
            confirmButton = {
                TextButton(enabled = s.tagText.isNotBlank(), onClick = {
                    s.tags = s.metaStore.addTag(s.project.id, s.tagText)
                    s.tagText = ""
                    s.onFavoriteChanged()
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.project_tag_add)) }
            },
            dismissButton = { TextButton(onClick = { s.showTags = false }) { Text(stringResource(android.R.string.ok)) } }
        )
    }
}

