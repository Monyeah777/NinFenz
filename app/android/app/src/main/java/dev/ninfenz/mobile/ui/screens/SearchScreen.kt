package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.FilterChip
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.data.Capability
import dev.ninfenz.mobile.data.CapabilityRegistry
import dev.ninfenz.mobile.data.LibraryMetaStore
import dev.ninfenz.mobile.data.ProjectEntry
import dev.ninfenz.mobile.data.SearchHit
import dev.ninfenz.mobile.data.SearchHistoryStore
import dev.ninfenz.mobile.data.SearchFilterStore
import dev.ninfenz.mobile.data.SearchIndex
import dev.ninfenz.mobile.data.SearchIndexStore
import dev.ninfenz.mobile.data.SearchKind
import dev.ninfenz.mobile.model.SearchFilter
import dev.ninfenz.mobile.model.SearchKeyboard
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.rememberCapabilityRevision
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** 库搜索（W2）：Pack 条款/字段/节点/章节/槽位 + 项目；本地内存索引，不联网。 */
@Composable
fun SearchScreen(
    onBack: () -> Unit,
    onOpenPack: (packId: String, version: String) -> Unit,
    onOpenProject: (projectId: String) -> Unit,
    packIds: List<String> = emptyList(),
    projects: List<ProjectEntry> = emptyList()
) {
    val context = LocalContext.current
    val capabilityRevision = rememberCapabilityRevision()
    if (capabilityRevision >= 0 && !CapabilityRegistry.isEnabled(Capability.SEARCH)) {
        SearchModuleDisabled(onBack = onBack)
        return
    }
    val ui = rememberSearchUiState(context, packIds, projects)
    val index = remember { SearchIndex(context.filesDir) }
    val fts = remember { SearchIndexStore(context) }
    val metaStore = remember { LibraryMetaStore(context.filesDir) }
    val filterStore = remember { SearchFilterStore(context.filesDir) }
    val historyStore = remember { SearchHistoryStore(context.filesDir) }
    val focusRequester = remember { FocusRequester() }
    val listState = rememberLazyListState()
    val filterKind = ui.filterName?.let { name -> SearchKind.entries.firstOrNull { it.name == name } }

    val results = remember(ui.query, ui.all, ui.ftsResults) { if (ui.query.isBlank()) emptyList() else ui.ftsResults }
    val filtered = remember(results, ui.filterName, ui.selectedPackId, ui.selectedProjectId, ui.favoritesOnly, ui.scopeTag) {
        applySearchFilters(results, filterKind, ui.selectedPackId, ui.selectedProjectId, ui.favoritesOnly, ui.scopeTag, metaStore)
    }
    SearchEffects(ui, index, fts, filterStore, focusRequester, filtered)
    val displayed = remember(filtered, ui.visibleCount) { filtered.take(ui.visibleCount) }
    val rows = remember(displayed) { searchRows(displayed) }

    SearchScreenBody(
        ui = ui,
        filterKind = filterKind,
        results = results,
        filtered = filtered,
        displayed = displayed,
        rows = rows,
        metaStore = metaStore,
        historyStore = historyStore,
        focusRequester = focusRequester,
        listState = listState,
        onBack = onBack,
        onOpenPack = onOpenPack,
        onOpenProject = onOpenProject,
        packIds = packIds,
        projects = projects
    )
}

internal class SearchUiState(
    queryState: androidx.compose.runtime.MutableState<String>,
    visibleCountState: androidx.compose.runtime.MutableState<Int>,
    filterNameState: androidx.compose.runtime.MutableState<String?>,
    selectedPackIdState: androidx.compose.runtime.MutableState<String?>,
    selectedProjectIdState: androidx.compose.runtime.MutableState<String?>,
    favoritesOnlyState: androidx.compose.runtime.MutableState<Boolean>,
    scopeTagState: androidx.compose.runtime.MutableState<String?>,
    historyState: androidx.compose.runtime.MutableState<List<String>>
) {
    var query by queryState
    var visibleCount by visibleCountState
    var filterName by filterNameState
    var selectedPackId by selectedPackIdState
    var selectedProjectId by selectedProjectIdState
    var favoritesOnly by favoritesOnlyState
    var scopeTag by scopeTagState
    var history by historyState
    var all by mutableStateOf<List<SearchHit>>(emptyList())
    var ftsResults by mutableStateOf<List<SearchHit>>(emptyList())
    var selected by mutableIntStateOf(0)
}

@Composable
private fun rememberSearchUiState(
    context: android.content.Context,
    packIds: List<String>,
    projects: List<ProjectEntry>
): SearchUiState {
    val savedFilter = remember { SearchFilterStore(context.filesDir).load() }
    val historyStore = remember { SearchHistoryStore(context.filesDir) }
    val queryState = rememberSaveable { mutableStateOf("") }
    val visibleCountState = rememberSaveable { mutableIntStateOf(200) }
    val filterNameState = rememberSaveable { mutableStateOf(savedFilter?.kind) }
    val selectedPackIdState = rememberSaveable { mutableStateOf(savedFilter?.packId?.takeIf { it in packIds }) }
    val selectedProjectIdState = rememberSaveable {
        mutableStateOf(savedFilter?.projectId?.takeIf { id -> projects.any { it.project.id == id } })
    }
    val favoritesOnlyState = rememberSaveable { mutableStateOf(false) }
    val scopeTagState = rememberSaveable { mutableStateOf<String?>(null) }
    val historyState = remember { mutableStateOf(historyStore.load()) }
    return remember {
        SearchUiState(
            queryState,
            visibleCountState,
            filterNameState,
            selectedPackIdState,
            selectedProjectIdState,
            favoritesOnlyState,
            scopeTagState,
            historyState
        )
    }
}

@Composable
private fun SearchEffects(
    ui: SearchUiState,
    index: SearchIndex,
    fts: SearchIndexStore,
    filterStore: SearchFilterStore,
    focusRequester: FocusRequester,
    filtered: List<SearchHit>
) {
    LaunchedEffect(Unit) {
        ui.all = withContext(Dispatchers.IO) { index.build() }
        withContext(Dispatchers.IO) { fts.rebuild(ui.all) }
    }
    LaunchedEffect(ui.query, ui.all) {
        ui.ftsResults = if (ui.query.isBlank()) emptyList() else withContext(Dispatchers.IO) {
            fts.search(ui.query).ifEmpty { index.search(ui.all, ui.query) }
        }
    }
    LaunchedEffect(ui.filterName, ui.selectedPackId, ui.selectedProjectId) {
        filterStore.save(ui.filterName, ui.selectedPackId, ui.selectedProjectId)
    }
    LaunchedEffect(Unit) {
        focusRequester.requestFocus()
    }
    LaunchedEffect(filtered) { ui.selected = 0; ui.visibleCount = 200 }
}

@Composable
private fun SearchScreenBody(
    ui: SearchUiState,
    filterKind: SearchKind?,
    results: List<SearchHit>,
    filtered: List<SearchHit>,
    displayed: List<SearchHit>,
    rows: List<SearchRow>,
    metaStore: LibraryMetaStore,
    historyStore: SearchHistoryStore,
    focusRequester: FocusRequester,
    listState: androidx.compose.foundation.lazy.LazyListState,
    onBack: () -> Unit,
    onOpenPack: (String, String) -> Unit,
    onOpenProject: (String) -> Unit,
    packIds: List<String>,
    projects: List<ProjectEntry>
) {
    fun openHit(hit: SearchHit) {
        historyStore.record(ui.query)
        ui.history = historyStore.load()
        when {
            hit.kind == SearchKind.PROJECT && hit.projectId != null -> onOpenProject(hit.projectId)
            hit.packId != null && hit.packVersion != null -> onOpenPack(hit.packId, hit.packVersion)
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = stringResource(dev.ninfenz.mobile.R.string.search_title), onBack = onBack)
        SearchQueryField(ui.query, filtered, ui.selected, focusRequester,
            onQueryChange = { ui.query = it },
            onSelect = { ui.selected = SearchKeyboard.move(ui.selected, displayed.size, it) },
            onOpenHit = { openHit(it) })
        SearchFilterArea(ui.query, results, ui.all, filterKind, ui.filterName, packIds, ui.selectedPackId,
            projects, ui.selectedProjectId, ui.favoritesOnly, ui.scopeTag, metaStore,
            onFilterNameChange = { ui.filterName = it }, onPackChange = { ui.selectedPackId = it },
            onProjectChange = { ui.selectedProjectId = it }, onFavoritesChange = { ui.favoritesOnly = it },
            onScopeTagChange = { ui.scopeTag = it })
        SearchResultsArea(ui.query, filtered, ui.history, ui.all, rows, ui.selected, ui.visibleCount, listState,
            showClearFilters = ui.filterName != null || ui.selectedPackId != null || ui.selectedProjectId != null,
            onQueryChange = { ui.query = it }, onOpenHit = { openHit(it) },
            onPickHistory = { ui.query = it }, onClearHistory = { historyStore.clear(); ui.history = emptyList() },
            onVisibleCountChange = { ui.visibleCount = it },
            onClearFilters = { ui.filterName = null; ui.selectedPackId = null; ui.selectedProjectId = null })
    }
}

private fun applySearchFilters(
    results: List<SearchHit>,
    filterKind: SearchKind?,
    selectedPackId: String?,
    selectedProjectId: String?,
    favoritesOnly: Boolean,
    scopeTag: String?,
    metaStore: LibraryMetaStore
): List<SearchHit> {
    var scoped = SearchFilter.apply(results, filterKind, selectedPackId, selectedProjectId)
    if (favoritesOnly) scoped = scoped.filter { hit -> hit.projectId?.let { metaStore.isFavorite(it) } == true }
    if (scopeTag != null) scoped = scoped.filter { hit -> hit.projectId?.let { scopeTag in metaStore.tags(it) } == true }
    return scoped
}

private fun searchRows(displayed: List<SearchHit>): List<SearchRow> {
    val out = mutableListOf<SearchRow>()
    var flat = 0
    SearchKind.entries.forEach { kind ->
        val hits = displayed.filter { it.kind == kind }
        if (hits.isNotEmpty()) {
            out.add(SearchRow(kind = kind))
            hits.forEach { hit ->
                out.add(SearchRow(hit = hit, flatIndex = flat))
                flat++
            }
        }
    }
    return out
}


internal data class SearchRow(
    val kind: SearchKind? = null,
    val hit: SearchHit? = null,
    val flatIndex: Int = -1
)

@Composable
internal fun PackFilterRow(packIds: List<String>, selected: String?, onPick: (String?) -> Unit) {
    LazyRow(
        contentPadding = PaddingValues(horizontal = NfSpacing.page),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        item {
            FilterChip(
                selected = selected == null,
                onClick = { onPick(null) },
                label = { Text(stringResource(dev.ninfenz.mobile.R.string.search_filter_all_packs)) }
            )
        }
        items(packIds) { id ->
            FilterChip(selected = selected == id, onClick = { onPick(id) }, label = { Text(id) })
        }
    }
}

@Composable
internal fun ProjectFilterRow(projects: List<ProjectEntry>, selected: String?, onPick: (String?) -> Unit) {
    LazyRow(
        contentPadding = PaddingValues(horizontal = NfSpacing.page),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        item {
            FilterChip(
                selected = selected == null,
                onClick = { onPick(null) },
                label = { Text(stringResource(dev.ninfenz.mobile.R.string.search_filter_all_projects)) }
            )
        }
        items(projects) { entry ->
            val id = entry.project.id
            FilterChip(
                selected = selected == id,
                onClick = { onPick(id) },
                label = { Text(entry.project.title.ifBlank { id }, maxLines = 1, overflow = TextOverflow.Ellipsis) }
            )
        }
    }
}

@Composable
internal fun kindLabel(kind: SearchKind): String = when (kind) {
    SearchKind.PROJECT -> stringResource(dev.ninfenz.mobile.R.string.search_kind_project)
    SearchKind.PACK -> stringResource(dev.ninfenz.mobile.R.string.search_kind_pack)
    SearchKind.CLAUSE -> stringResource(dev.ninfenz.mobile.R.string.search_kind_clause)
    SearchKind.FIELD -> stringResource(dev.ninfenz.mobile.R.string.search_kind_field)
    SearchKind.NODE -> stringResource(dev.ninfenz.mobile.R.string.search_kind_node)
    SearchKind.SECTION -> stringResource(dev.ninfenz.mobile.R.string.search_kind_section)
    SearchKind.SLOT -> stringResource(dev.ninfenz.mobile.R.string.search_kind_slot)
}


@Composable
internal fun SearchHistoryPanel(
    history: List<String>,
    total: Int,
    onPick: (String) -> Unit,
    onClear: () -> Unit
) {
    Column(modifier = Modifier.fillMaxWidth().padding(NfSpacing.page)) {
        Text(
            pluralStringResource(dev.ninfenz.mobile.R.plurals.search_hint, total, total),
            style = NfType.secondary,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        if (history.isNotEmpty()) {
            androidx.compose.foundation.layout.Row(
                modifier = Modifier.fillMaxWidth().padding(top = NfSpacing.m),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = androidx.compose.ui.Alignment.CenterVertically
            ) {
                Text(stringResource(dev.ninfenz.mobile.R.string.search_history_title), style = NfType.itemTitle)
                TextButton(onClick = onClear) { Text(stringResource(dev.ninfenz.mobile.R.string.search_history_clear)) }
            }
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(history) { q ->
                    FilterChip(selected = false, onClick = { onPick(q) }, label = { Text(q) })
                }
            }
        }
    }
}


@Composable
internal fun SearchFilterRow(selected: SearchKind?, onPick: (SearchKind?) -> Unit) {
    LazyRow(
        contentPadding = PaddingValues(horizontal = NfSpacing.page),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        item {
            FilterChip(
                selected = selected == null,
                onClick = { onPick(null) },
                label = { Text(stringResource(dev.ninfenz.mobile.R.string.search_filter_all)) }
            )
        }
        items(SearchKind.entries) { kind ->
            FilterChip(
                selected = selected == kind,
                onClick = { onPick(kind) },
                label = { Text(kindLabel(kind)) }
            )
        }
    }
}

@Composable
internal fun SectionLabel(text: String) {
    Text(
        text,
        style = NfType.itemTitle,
        modifier = Modifier.padding(start = NfSpacing.page, end = NfSpacing.page, top = NfSpacing.m, bottom = NfSpacing.xs)
    )
}

@Composable
internal fun ResultRow(hit: SearchHit, selected: Boolean, onClick: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(if (selected) MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surface)
            .clickable(onClick = onClick)
            .padding(horizontal = NfSpacing.page, vertical = 12.dp)
    ) {
        Text(hit.title, style = NfType.itemTitle, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Text(
            hit.detail,
            style = NfType.meta,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
    }
}
