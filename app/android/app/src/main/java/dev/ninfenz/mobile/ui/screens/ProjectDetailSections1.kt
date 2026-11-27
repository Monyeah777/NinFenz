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
internal fun ProjectDetailContent(s: ProjectDetailState) {
    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = s.project.title,
            onBack = s.onBack,
            actions = {
                IconButton(onClick = {
                    s.isFavorite = s.metaStore.toggle(s.project.id)
                    s.onFavoriteChanged()
                }) {
                    Icon(
                        if (s.isFavorite) Icons.Filled.Star else Icons.Outlined.StarOutlined,
                        contentDescription = stringResource(if (s.isFavorite) dev.ninfenz.mobile.R.string.library_unfavorite else dev.ninfenz.mobile.R.string.library_favorite)
                    )
                }
                IconButton(onClick = { s.showMoreActions = true }) {
                    Icon(
                        Icons.Filled.MoreVert,
                        contentDescription = stringResource(dev.ninfenz.mobile.R.string.action_more)
                    )
                }
            })
        LazyColumn(
            contentPadding = androidx.compose.foundation.layout.PaddingValues(NfSpacing.page),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
        ) {
            ProjectDetailHeaderCard(s)
            ProjectDetailNextStepCard(s)
            item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.project_detail_info)) }
            ProjectDetailInfoCard(s)
            ProjectDetailHistoryToggle(s)
            ProjectDetailHistoryCard(s)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
internal fun LazyListScope.ProjectDetailHeaderCard(s: ProjectDetailState) {
            item {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = NfSpacing.page),
                    verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        NfStatusChip(projectStatusLabel(s.project))
                        if (s.project.historyCount > 0) {
                            Text(
                                stringResource(dev.ninfenz.mobile.R.string.project_detail_history, s.project.historyCount),
                                style = NfType.meta,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.weight(1f),
                                textAlign = androidx.compose.ui.text.style.TextAlign.End
                            )
                        }
                    }
                    Text(s.project.id, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    if (s.tags.isNotEmpty()) {
                        Text("#" + s.tags.sorted().joinToString(" #"), style = NfType.meta, color = MaterialTheme.colorScheme.primary)
                    }
                    if (s.templateReference != null) {
                        NfListRow(stringResource(dev.ninfenz.mobile.R.string.project_template_ref), null, Icons.Filled.Search, "›") {
                            s.showTemplateReference = true
                        }
                    }
                    if (s.hasSpecOverride) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                stringResource(dev.ninfenz.mobile.R.string.template_override_active),
                                style = NfType.meta,
                                color = MaterialTheme.colorScheme.primary,
                                modifier = Modifier.weight(1f)
                            )
                            TextButton(onClick = { s.showRemoveOverride = true }) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.template_override_remove))
                            }
                        }
                    }
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.project_detail_pack, s.project.refs.basePackId, s.project.refs.basePackVersion) +
                            " · " + stringResource(dev.ninfenz.mobile.R.string.project_detail_protocol, s.project.refs.protocolId.ifBlank { stringResource(dev.ninfenz.mobile.R.string.not_bound) }),
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
internal fun LazyListScope.ProjectDetailNextStepCard(s: ProjectDetailState) {
            item {
                NfCard {
                    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.project_detail_next_step),
                            style = NfType.label,
                            color = MaterialTheme.colorScheme.primary
                        )
                        val nextIsAuthor = s.project.status == ProjectStatus.DRAFT || s.project.status == ProjectStatus.AUTHORING
                        Text(
                            stringResource(if (nextIsAuthor) dev.ninfenz.mobile.R.string.flow_action_author else dev.ninfenz.mobile.R.string.flow_action_delivery),
                            style = NfType.screenTitle
                        )
                        Text(
                            stringResource(if (nextIsAuthor) dev.ninfenz.mobile.R.string.project_detail_author_subtitle else dev.ninfenz.mobile.R.string.project_detail_delivery_subtitle),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Button(
                            onClick = { if (nextIsAuthor) s.onAuthor() else s.onAssembly() },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.flow_action_continue))
                        }
                    }
                }
            }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
internal fun LazyListScope.ProjectDetailInfoCard(s: ProjectDetailState) {
    item {
        NfCard {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                ProjectDetailInfoRows1(s)
                ProjectDetailInfoRows2(s)
                ProjectDetailInfoRows3(s)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ProjectDetailInfoRows1(s: ProjectDetailState) {
                        Row {
                            Text("Pack", style = NfType.meta, modifier = Modifier.width(72.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(s.project.refs.basePackId + " · " + s.project.refs.basePackVersion, style = NfType.meta)
                        }
                        val otherVersions = s.packs.filter {
                            it.id == s.project.refs.basePackId && it.version != s.project.refs.basePackVersion
                        }.map { it.version }.distinct().sorted()
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.project_change_pack_note),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        if (otherVersions.isNotEmpty()) {
                            Text(
                                stringResource(dev.ninfenz.mobile.R.string.project_pack_other_versions, otherVersions.joinToString(", ")),
                                style = NfType.meta,
                                color = MaterialTheme.colorScheme.primary
                            )
                        }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ProjectDetailInfoRows2(s: ProjectDetailState) {
                        val lockCheck = s.packLockStore.verify(s.project, s.packs)
                        val lockStatus = when (lockCheck.status) {
                            PackLockStore.Status.OK -> stringResource(dev.ninfenz.mobile.R.string.project_pack_lock_ok)
                            PackLockStore.Status.MISSING -> stringResource(dev.ninfenz.mobile.R.string.project_pack_lock_missing)
                            PackLockStore.Status.PROJECT_CHANGED -> stringResource(dev.ninfenz.mobile.R.string.project_pack_lock_changed)
                            PackLockStore.Status.PACK_MISSING -> stringResource(dev.ninfenz.mobile.R.string.project_pack_lock_pack_missing)
                            PackLockStore.Status.TREE_MISMATCH -> stringResource(dev.ninfenz.mobile.R.string.project_pack_lock_mismatch)
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                stringResource(dev.ninfenz.mobile.R.string.project_pack_lock) + " · " + lockStatus,
                                style = NfType.meta,
                                color = if (lockCheck.status == PackLockStore.Status.OK) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.weight(1f)
                            )
                            TextButton(onClick = {
                                s.packLock = s.packLockStore.lock(s.project)
                                s.packLockNote = s.context.getString(dev.ninfenz.mobile.R.string.project_pack_locked)
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.project_pack_lock_now)) }
                            if (s.packLock != null) {
                                TextButton(onClick = {
                                    s.packLockStore.unlock(s.project.id)
                                    s.packLock = null
                                    s.packLockNote = s.context.getString(dev.ninfenz.mobile.R.string.project_pack_unlocked)
                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.project_pack_lock_clear)) }
                            }
                        }
                        s.packLockNote?.let {
                            Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary)
                        }
                        Row {
                            Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_protocol_label), style = NfType.meta, modifier = Modifier.width(72.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(s.project.refs.protocolId.ifBlank { stringResource(dev.ninfenz.mobile.R.string.not_bound) }, style = NfType.meta)
                        }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ProjectDetailInfoRows3(s: ProjectDetailState) {
                        if (s.showAudit) {
                        Row {
                            Text(stringResource(dev.ninfenz.mobile.R.string.project_detail_review), style = NfType.meta, modifier = Modifier.width(72.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(s.project.review.state + " · " + (s.project.review.reviewer ?: "-"), style = NfType.meta)
                        }
                        }
                        if (s.showAudit && s.reviewStale) {
                            Text(
                                stringResource(dev.ninfenz.mobile.R.string.project_review_stale),
                                style = NfType.meta,
                                color = MaterialTheme.colorScheme.error
                            )
                        }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
internal fun LazyListScope.ProjectDetailHistoryToggle(s: ProjectDetailState) {
            if (s.showAudit && (s.project.historyCount > 0 || s.project.history.isNotEmpty())) {
            item {
                NfListRow(
                    title = stringResource(dev.ninfenz.mobile.R.string.project_history_title),
                    subtitle = stringResource(dev.ninfenz.mobile.R.string.project_detail_history, s.project.historyCount),
                    leading = Icons.AutoMirrored.Filled.List,
                    trailing = stringResource(if (s.historyExpanded) dev.ninfenz.mobile.R.string.project_history_collapse else dev.ninfenz.mobile.R.string.project_history_expand),
                    onClick = { s.historyExpanded = !s.historyExpanded }
                )
            }
            }
}

