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
import dev.ninfenz.mobile.data.ProjectEntry
import dev.ninfenz.mobile.data.SearchHit
import dev.ninfenz.mobile.data.SearchHistoryStore
import dev.ninfenz.mobile.data.SearchFilterStore
import dev.ninfenz.mobile.data.SearchIndex
import dev.ninfenz.mobile.data.SearchKind
import dev.ninfenz.mobile.model.SearchFilter
import dev.ninfenz.mobile.model.SearchKeyboard
import dev.ninfenz.mobile.ui.components.NfTopAppBar
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
    val index = remember { SearchIndex(context.filesDir) }
    var all by remember { mutableStateOf<List<SearchHit>>(emptyList()) }
    var query by rememberSaveable { mutableStateOf("") }
    var selected by remember { mutableIntStateOf(0) }
    val filterStore = remember { SearchFilterStore(context.filesDir) }
    val savedFilter = remember { filterStore.load() }
    var filterName by rememberSaveable { mutableStateOf(savedFilter?.kind) }
    var selectedPackId by rememberSaveable {
        mutableStateOf(savedFilter?.packId?.takeIf { it in packIds })
    }
    var selectedProjectId by rememberSaveable {
        mutableStateOf(savedFilter?.projectId?.takeIf { id -> projects.any { it.project.id == id } })
    }
    val filterKind = filterName?.let { name -> SearchKind.entries.firstOrNull { it.name == name } }
    val historyStore = remember { SearchHistoryStore(context.filesDir) }
    var history by remember { mutableStateOf(historyStore.load()) }
    val focusRequester = remember { FocusRequester() }
    val listState = rememberLazyListState()

    LaunchedEffect(Unit) {
        all = withContext(Dispatchers.IO) { index.build() }
    }
    LaunchedEffect(filterName, selectedPackId, selectedProjectId) {
        filterStore.save(filterName, selectedPackId, selectedProjectId)
    }
    LaunchedEffect(Unit) {
        focusRequester.requestFocus()
    }
    val results = remember(query, all) { index.search(all, query) }
    val filtered = remember(results, filterName, selectedPackId, selectedProjectId) {
        SearchFilter.apply(results, filterKind, selectedPackId, selectedProjectId)
    }
    LaunchedEffect(filtered) { selected = 0 }
    val rows = remember(filtered) {
        val out = mutableListOf<SearchRow>()
        var flat = 0
        SearchKind.entries.forEach { kind ->
            val hits = filtered.filter { it.kind == kind }
            if (hits.isNotEmpty()) {
                out.add(SearchRow(kind = kind))
                hits.forEach { hit ->
                    out.add(SearchRow(hit = hit, flatIndex = flat))
                    flat++
                }
            }
        }
        out
    }
    fun openHit(hit: SearchHit) {
        historyStore.record(query)
        history = historyStore.load()
        when {
            hit.kind == SearchKind.PROJECT && hit.projectId != null -> onOpenProject(hit.projectId)
            hit.packId != null && hit.packVersion != null -> onOpenPack(hit.packId, hit.packVersion)
        }
    }
    fun select(delta: Int) {
        selected = SearchKeyboard.move(selected, filtered.size, delta)
    }
    LaunchedEffect(selected, rows) {
        val itemIndex = rows.indexOfFirst { it.hit != null && it.flatIndex == selected }
        if (itemIndex >= 0) listState.animateScrollToItem(itemIndex)
    }

    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = stringResource(dev.ninfenz.mobile.R.string.search_title), onBack = onBack)
        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = NfSpacing.page)
                .focusRequester(focusRequester)
                .onPreviewKeyEvent { event ->
                    if (event.type != KeyEventType.KeyDown) return@onPreviewKeyEvent false
                    when (event.key) {
                        Key.DirectionDown -> { select(1); true }
                        Key.DirectionUp -> { select(-1); true }
                        Key.Enter, Key.NumPadEnter -> {
                            val hit = filtered.getOrNull(selected)
                            if (hit != null) { openHit(hit); true } else false
                        }
                        Key.Escape -> {
                            if (query.isNotEmpty()) { query = ""; true } else false
                        }
                        else -> false
                    }
                },
            placeholder = { Text(stringResource(dev.ninfenz.mobile.R.string.search_placeholder_short)) },
            leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
            trailingIcon = {
                if (query.isNotEmpty()) {
                    IconButton(onClick = { query = "" }) {
                        Icon(Icons.Filled.Close, contentDescription = stringResource(dev.ninfenz.mobile.R.string.search_clear))
                    }
                }
            },
            singleLine = true
        )
        if (query.isNotBlank() && results.isNotEmpty()) {
            SearchFilterRow(filterKind) { kind ->
                filterName = kind?.name
            }
            if (packIds.isNotEmpty()) {
                PackFilterRow(packIds, selectedPackId) { selectedPackId = it }
            }
            if (projects.isNotEmpty()) {
                ProjectFilterRow(projects, selectedProjectId) { selectedProjectId = it }
            }
            Text(
                stringResource(dev.ninfenz.mobile.R.string.search_keyboard_hint),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = NfSpacing.page, vertical = 4.dp)
            )
        }
        when {
            query.isBlank() -> SearchHistoryPanel(
                history = history,
                total = all.size,
                onPick = { query = it },
                onClear = { historyStore.clear(); history = emptyList() }
            )
            filtered.isEmpty() -> Column(modifier = Modifier.padding(NfSpacing.page)) {
                Text(
                    stringResource(dev.ninfenz.mobile.R.string.search_no_result),
                    style = NfType.secondary,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                TextButton(onClick = { query = "" }) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.search_clear))
                }
            }
            else -> LazyColumn(
                state = listState,
                contentPadding = PaddingValues(bottom = 96.dp),
                verticalArrangement = Arrangement.spacedBy(2.dp)
            ) {
                itemsIndexed(rows) { _, row ->
                    val kind = row.kind
                    val hit = row.hit
                    when {
                        kind != null -> SectionLabel(kindLabel(kind))
                        hit != null -> ResultRow(hit, selected == row.flatIndex) { openHit(hit) }
                    }
                }
            }
        }
    }
}

private data class SearchRow(
    val kind: SearchKind? = null,
    val hit: SearchHit? = null,
    val flatIndex: Int = -1
)

@Composable
private fun PackFilterRow(packIds: List<String>, selected: String?, onPick: (String?) -> Unit) {
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
private fun ProjectFilterRow(projects: List<ProjectEntry>, selected: String?, onPick: (String?) -> Unit) {
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
private fun kindLabel(kind: SearchKind): String = when (kind) {
    SearchKind.PROJECT -> stringResource(dev.ninfenz.mobile.R.string.search_kind_project)
    SearchKind.PACK -> stringResource(dev.ninfenz.mobile.R.string.search_kind_pack)
    SearchKind.CLAUSE -> stringResource(dev.ninfenz.mobile.R.string.search_kind_clause)
    SearchKind.FIELD -> stringResource(dev.ninfenz.mobile.R.string.search_kind_field)
    SearchKind.NODE -> stringResource(dev.ninfenz.mobile.R.string.search_kind_node)
    SearchKind.SECTION -> stringResource(dev.ninfenz.mobile.R.string.search_kind_section)
    SearchKind.SLOT -> stringResource(dev.ninfenz.mobile.R.string.search_kind_slot)
}


@Composable
private fun SearchHistoryPanel(
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
private fun SearchFilterRow(selected: SearchKind?, onPick: (SearchKind?) -> Unit) {
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
private fun SectionLabel(text: String) {
    Text(
        text,
        style = NfType.itemTitle,
        modifier = Modifier.padding(start = NfSpacing.page, end = NfSpacing.page, top = NfSpacing.m, bottom = NfSpacing.xs)
    )
}

@Composable
private fun ResultRow(hit: SearchHit, selected: Boolean, onClick: () -> Unit) {
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
