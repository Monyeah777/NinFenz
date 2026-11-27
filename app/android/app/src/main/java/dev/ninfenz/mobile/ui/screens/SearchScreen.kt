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
        applySearchFilters(ApplySearchFiltersArgs(results, filterKind, ui.selectedPackId, ui.selectedProjectId, ui.favoritesOnly, ui.scopeTag, metaStore))
    }
    SearchEffects(ui, index, fts, filterStore, focusRequester, filtered)
    val displayed = remember(filtered, ui.visibleCount) { filtered.take(ui.visibleCount) }
    val rows = remember(displayed) { searchRows(displayed) }

    SearchScreenBody(SearchScreenBodyArgs(ui = ui,
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
        projects = projects))
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

internal data class SearchScreenBodyArgs(
    val ui: SearchUiState,
    val filterKind: SearchKind?,
    val results: List<SearchHit>,
    val filtered: List<SearchHit>,
    val displayed: List<SearchHit>,
    val rows: List<SearchRow>,
    val metaStore: LibraryMetaStore,
    val historyStore: SearchHistoryStore,
    val focusRequester: FocusRequester,
    val listState: androidx.compose.foundation.lazy.LazyListState,
    val onBack: () -> Unit,
    val onOpenPack: (String, String) -> Unit,
    val onOpenProject: (String) -> Unit,
    val packIds: List<String>,
    val projects: List<ProjectEntry>,
)

@Composable
private fun SearchScreenBody(args: SearchScreenBodyArgs) = with(args) {
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
        SearchFilterArea(SearchFilterAreaArgs(ui.query, results, ui.all, filterKind, ui.filterName, packIds, ui.selectedPackId,
            projects, ui.selectedProjectId, ui.favoritesOnly, ui.scopeTag, metaStore,
            onFilterNameChange = { ui.filterName = it }, onPackChange = { ui.selectedPackId = it },
            onProjectChange = { ui.selectedProjectId = it }, onFavoritesChange = { ui.favoritesOnly = it },
            onScopeTagChange = { ui.scopeTag = it }))
        SearchResultsArea(SearchResultsAreaArgs(ui.query, filtered, ui.history, ui.all, rows, ui.selected, ui.visibleCount, listState,
            showClearFilters = ui.filterName != null || ui.selectedPackId != null || ui.selectedProjectId != null,
            onQueryChange = { ui.query = it }, onOpenHit = { openHit(it) },
            onPickHistory = { ui.query = it }, onClearHistory = { historyStore.clear(); ui.history = emptyList() },
            onVisibleCountChange = { ui.visibleCount = it },
            onClearFilters = { ui.filterName = null; ui.selectedPackId = null; ui.selectedProjectId = null }))
    }
}

internal data class ApplySearchFiltersArgs(
    val results: List<SearchHit>,
    val filterKind: SearchKind?,
    val selectedPackId: String?,
    val selectedProjectId: String?,
    val favoritesOnly: Boolean,
    val scopeTag: String?,
    val metaStore: LibraryMetaStore,
)

private fun applySearchFilters(args: ApplySearchFiltersArgs): List<SearchHit> {
    with(args) {
    var scoped = SearchFilter.apply(results, filterKind, selectedPackId, selectedProjectId)
    if (favoritesOnly) scoped = scoped.filter { hit -> hit.projectId?.let { metaStore.isFavorite(it) } == true }
    if (scopeTag != null) scoped = scoped.filter { hit -> hit.projectId?.let { scopeTag in metaStore.tags(it) } == true }
    return scoped

    }
}
