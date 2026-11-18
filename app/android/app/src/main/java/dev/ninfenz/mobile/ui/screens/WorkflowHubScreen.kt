package dev.ninfenz.mobile.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.data.ProjectEntry
import dev.ninfenz.mobile.data.RecentProjectStore
import dev.ninfenz.mobile.model.ProjectStatus
import dev.ninfenz.mobile.model.ProjectSorter
import dev.ninfenz.mobile.model.ProjectSort
import dev.ninfenz.mobile.ui.components.NfCard
import dev.ninfenz.mobile.ui.components.NfEmptyState

import dev.ninfenz.mobile.ui.components.NfSectionHeader
import dev.ninfenz.mobile.ui.components.NfStatusChip
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.theme.NfSpacing

/** 工作台：把「创作」与「交付」合成一个入口；按项目状态给唯一下一步。 */
@Composable
fun WorkflowHubScreen(
    projects: List<ProjectEntry>,
    onOpenProject: (ProjectEntry) -> Unit,
    onAuthor: (ProjectEntry) -> Unit,
    onDelivery: (ProjectEntry) -> Unit,
    onNewProject: () -> Unit,
    onImport: () -> Unit
) {
    var filter by rememberSaveable { mutableStateOf("active") }
    var projectsExpanded by rememberSaveable { mutableStateOf(true) }
    val context = LocalContext.current
    val recentStore = remember { runCatching { RecentProjectStore(context.filesDir) }.getOrNull() }
    var recentIds by remember { mutableStateOf(recentStore?.load() ?: emptyList()) }
    val visible = ProjectSorter.sort(
        projects.filter {
            when (filter) {
                "done" -> it.project.status == ProjectStatus.EXPORTED || it.project.status == ProjectStatus.REVIEWED
                "all" -> true
                else -> it.project.status == ProjectStatus.DRAFT ||
                    it.project.status == ProjectStatus.AUTHORING ||
                    it.project.status == ProjectStatus.ASSEMBLED ||
                    it.project.status == ProjectStatus.VALIDATED
            }
        },
        ProjectSort.RECENT,
        priorityIds = recentIds
    )

    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = stringResource(dev.ninfenz.mobile.R.string.nav_flow))
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.l)
        ) {
            item {
                Column(
                    modifier = Modifier.padding(horizontal = NfSpacing.page, vertical = NfSpacing.s),
                    verticalArrangement = Arrangement.spacedBy(NfSpacing.s)
                ) {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.flow_header_summary, projects.size, projects.count { it.project.status != dev.ninfenz.mobile.model.ProjectStatus.EXPORTED && it.project.status != dev.ninfenz.mobile.model.ProjectStatus.REVIEWED }),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        Button(onClick = onNewProject) { Text(stringResource(dev.ninfenz.mobile.R.string.create_action_new)) }
                        TextButton(onClick = onImport) { Text(stringResource(dev.ninfenz.mobile.R.string.library_import)) }
                    }
                }
            }
            item {
                LazyRow(
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = NfSpacing.page),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    item { FilterChip(selected = filter == "active", onClick = { filter = "active" }, label = { Text(stringResource(dev.ninfenz.mobile.R.string.flow_filter_active)) }) }
                    item { FilterChip(selected = filter == "done", onClick = { filter = "done" }, label = { Text(stringResource(dev.ninfenz.mobile.R.string.flow_filter_done)) }) }
                    item { FilterChip(selected = filter == "all", onClick = { filter = "all" }, label = { Text(stringResource(dev.ninfenz.mobile.R.string.search_filter_all)) }) }
                }
            }
            if (visible.isEmpty()) {
                item {
                    NfEmptyState(
                        icon = Icons.Filled.Add,
                        title = stringResource(dev.ninfenz.mobile.R.string.flow_empty_title),
                        message = stringResource(dev.ninfenz.mobile.R.string.flow_empty_body),
                        actionLabel = stringResource(dev.ninfenz.mobile.R.string.create_action_new),
                        onAction = onNewProject,
                        secondaryLabel = stringResource(dev.ninfenz.mobile.R.string.library_import),
                        onSecondary = onImport
                    )
                }
            } else {
                item {
                    val chevron by animateFloatAsState(
                        targetValue = if (projectsExpanded) 180f else 0f,
                        animationSpec = tween(durationMillis = 220),
                        label = "workhub-projects-chevron"
                    )
                    NfSectionHeader(
                        stringResource(dev.ninfenz.mobile.R.string.library_section_projects),
                        action = {
                            androidx.compose.material3.IconButton(
                                onClick = { projectsExpanded = !projectsExpanded },
                                modifier = Modifier.size(48.dp)
                            ) {
                                androidx.compose.material3.Icon(
                                    Icons.Filled.KeyboardArrowDown,
                                    contentDescription = stringResource(
                                        if (projectsExpanded) dev.ninfenz.mobile.R.string.action_collapse
                                        else dev.ninfenz.mobile.R.string.action_expand
                                    ),
                                    modifier = Modifier.rotate(chevron)
                                )
                            }
                        }
                    )
                }
                item {
                    AnimatedVisibility(
                        visible = projectsExpanded,
                        enter = fadeIn(tween(180)) + expandVertically(
                            animationSpec = spring(dampingRatio = 0.82f, stiffness = 420f),
                            expandFrom = Alignment.Top
                        ),
                        exit = fadeOut(tween(120)) + shrinkVertically(
                            animationSpec = spring(dampingRatio = 0.9f, stiffness = 500f),
                            shrinkTowards = Alignment.Top
                        )
                    ) {
                        Column(
                            modifier = Modifier.padding(horizontal = NfSpacing.page),
                            verticalArrangement = Arrangement.spacedBy(NfSpacing.l)
                        ) {
                            visible.forEach { entry ->
                                val status = entry.project.status
                                val nextAuthor = status == ProjectStatus.DRAFT || status == ProjectStatus.AUTHORING
                                NfCard(onClick = {
                                    recentIds = recentStore?.record(entry.project.id) ?: recentIds
                                    onOpenProject(entry)
                                }) {
                                    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                                        Row(verticalAlignment = Alignment.CenterVertically) {
                                            Column(modifier = Modifier.weight(1f)) {
                                                Text(
                                                    entry.project.title,
                                                    style = MaterialTheme.typography.titleMedium,
                                                    maxLines = 2,
                                                    overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis
                                                )
                                                Text(entry.project.id, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                            }
                                            NfStatusChip(projectStatusLabel(entry.project))
                                        }
                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            horizontalArrangement = Arrangement.SpaceBetween,
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            TextButton(onClick = { if (nextAuthor) onAuthor(entry) else onDelivery(entry) }) {
                                                Text(
                                                    stringResource(
                                                        if (nextAuthor) dev.ninfenz.mobile.R.string.flow_action_author
                                                        else dev.ninfenz.mobile.R.string.flow_action_delivery
                                                    )
                                                )
                                            }
                                            Text("›", style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
