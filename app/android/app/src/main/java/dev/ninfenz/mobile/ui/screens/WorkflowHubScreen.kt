package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.util.orNullLogged
import dev.ninfenz.mobile.ui.theme.NfMotion

import dev.ninfenz.mobile.ui.design.NfType

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
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.ui.components.nfExpandableEnter
import dev.ninfenz.mobile.ui.components.nfExpandableExit
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
    val recentStore = remember { runCatching { RecentProjectStore(context.filesDir) }.orNullLogged("WorkflowHubScreen") }
    var recentIds by remember { mutableStateOf(recentStore?.load() ?: emptyList()) }
    val visible = visibleProjects(projects, filter, recentIds)

    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = stringResource(dev.ninfenz.mobile.R.string.nav_flow))
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.l)
        ) {
            item {
                WorkflowHubHeader(
                    projects = projects,
                    onNewProject = onNewProject,
                    onImport = onImport
                )
            }
            item {
                WorkflowHubFilterRow(filter = filter, onFilterChange = { filter = it })
            }
            workflowHubSections(
                visible = visible,
                projectsExpanded = projectsExpanded,
                onToggleProjects = { projectsExpanded = !projectsExpanded },
                recentIds = recentIds,
                recentStore = recentStore,
                onRecentIdsChange = { recentIds = it },
                onOpenProject = onOpenProject,
                onAuthor = onAuthor,
                onDelivery = onDelivery,
                onNewProject = onNewProject,
                onImport = onImport
            )
        }
    }
}

private fun visibleProjects(
    projects: List<ProjectEntry>,
    filter: String,
    recentIds: List<String>
): List<ProjectEntry> = ProjectSorter.sort(
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

private fun androidx.compose.foundation.lazy.LazyListScope.workflowHubSections(
    visible: List<ProjectEntry>,
    projectsExpanded: Boolean,
    onToggleProjects: () -> Unit,
    recentIds: List<String>,
    recentStore: RecentProjectStore?,
    onRecentIdsChange: (List<String>) -> Unit,
    onOpenProject: (ProjectEntry) -> Unit,
    onAuthor: (ProjectEntry) -> Unit,
    onDelivery: (ProjectEntry) -> Unit,
    onNewProject: () -> Unit,
    onImport: () -> Unit
) {
    if (visible.isEmpty()) {
        item {
            WorkflowHubEmptyState(onNewProject = onNewProject, onImport = onImport)
        }
    } else {
        item {
            WorkflowHubProjectsHeader(
                projectsExpanded = projectsExpanded,
                onToggle = onToggleProjects
            )
        }
        item {
            WorkflowHubProjectList(
                visible = visible,
                projectsExpanded = projectsExpanded,
                recentIds = recentIds,
                recentStore = recentStore,
                onRecentIdsChange = onRecentIdsChange,
                onOpenProject = onOpenProject,
                onAuthor = onAuthor,
                onDelivery = onDelivery
            )
        }
    }
}

@Composable
private fun WorkflowHubHeader(
    projects: List<ProjectEntry>,
    onNewProject: () -> Unit,
    onImport: () -> Unit
) {
    Column(
        modifier = Modifier.padding(horizontal = NfSpacing.page, vertical = NfSpacing.s),
        verticalArrangement = Arrangement.spacedBy(NfSpacing.s)
    ) {
        Text(
            pluralStringResource(dev.ninfenz.mobile.R.plurals.flow_header_projects, projects.size, projects.size) + " · " +
                pluralStringResource(dev.ninfenz.mobile.R.plurals.flow_header_active, projects.count { it.project.status != dev.ninfenz.mobile.model.ProjectStatus.EXPORTED && it.project.status != dev.ninfenz.mobile.model.ProjectStatus.REVIEWED }, projects.count { it.project.status != dev.ninfenz.mobile.model.ProjectStatus.EXPORTED && it.project.status != dev.ninfenz.mobile.model.ProjectStatus.REVIEWED }),
            style = NfType.meta,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
            Button(onClick = onNewProject) { Text(stringResource(dev.ninfenz.mobile.R.string.create_action_new)) }
            TextButton(onClick = onImport) { Text(stringResource(dev.ninfenz.mobile.R.string.library_import)) }
        }
    }
}

@Composable
private fun WorkflowHubFilterRow(filter: String, onFilterChange: (String) -> Unit) {
    LazyRow(
        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = NfSpacing.page),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        item { FilterChip(selected = filter == "active", onClick = { onFilterChange("active") }, label = { Text(stringResource(dev.ninfenz.mobile.R.string.flow_filter_active)) }) }
        item { FilterChip(selected = filter == "done", onClick = { onFilterChange("done") }, label = { Text(stringResource(dev.ninfenz.mobile.R.string.flow_filter_done)) }) }
        item { FilterChip(selected = filter == "all", onClick = { onFilterChange("all") }, label = { Text(stringResource(dev.ninfenz.mobile.R.string.search_filter_all)) }) }
    }
}

@Composable
private fun WorkflowHubEmptyState(onNewProject: () -> Unit, onImport: () -> Unit) {
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

@Composable
private fun WorkflowHubProjectsHeader(
    projectsExpanded: Boolean,
    onToggle: () -> Unit
) {
    val chevron by animateFloatAsState(
        targetValue = if (projectsExpanded) 180f else 0f,
        animationSpec = tween(durationMillis = NfMotion.MEDIUM_MS),
        label = "workhub-projects-chevron"
    )
    NfSectionHeader(
        stringResource(dev.ninfenz.mobile.R.string.library_section_projects),
        action = {
            androidx.compose.material3.IconButton(
                onClick = { onToggle() },
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

@Composable
private fun WorkflowHubProjectList(
    visible: List<ProjectEntry>,
    projectsExpanded: Boolean,
    recentIds: List<String>,
    recentStore: RecentProjectStore?,
    onRecentIdsChange: (List<String>) -> Unit,
    onOpenProject: (ProjectEntry) -> Unit,
    onAuthor: (ProjectEntry) -> Unit,
    onDelivery: (ProjectEntry) -> Unit
) {
    AnimatedVisibility(
        visible = projectsExpanded,
        enter = nfExpandableEnter(),
        exit = nfExpandableExit()
    ) {
        Column(
            modifier = Modifier.padding(horizontal = NfSpacing.page),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.l)
        ) {
            visible.forEach { entry ->
                val status = entry.project.status
                val nextAuthor = status == ProjectStatus.DRAFT || status == ProjectStatus.AUTHORING
                NfCard(onClick = {
                    onRecentIdsChange(recentStore?.record(entry.project.id) ?: recentIds)
                    onOpenProject(entry)
                }) {
                    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    entry.project.title,
                                    style = NfType.itemTitle,
                                    maxLines = 2,
                                    overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis
                                )
                                Text(entry.project.id, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
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
                            Text("›", style = NfType.screenTitle, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
    }
}