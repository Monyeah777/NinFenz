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
import androidx.compose.foundation.lazy.LazyListState
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


@Composable
internal fun SearchModuleDisabled(onBack: () -> Unit) {
    Column(Modifier.fillMaxSize()) {
        NfTopAppBar(title = stringResource(dev.ninfenz.mobile.R.string.search_title), onBack = onBack)
        Text(
            stringResource(dev.ninfenz.mobile.R.string.search_module_disabled),
            modifier = Modifier.padding(NfSpacing.page),
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
internal fun SearchQueryField(
    query: String,
    filtered: List<SearchHit>,
    selected: Int,
    focusRequester: FocusRequester,
    onQueryChange: (String) -> Unit,
    onSelect: (Int) -> Unit,
    onOpenHit: (SearchHit) -> Unit
) {
    OutlinedTextField(
        value = query,
        onValueChange = onQueryChange,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = NfSpacing.page)
            .focusRequester(focusRequester)
            .onPreviewKeyEvent { event ->
                if (event.type != KeyEventType.KeyDown) return@onPreviewKeyEvent false
                when (event.key) {
                    Key.DirectionDown -> { onSelect(1); true }
                    Key.DirectionUp -> { onSelect(-1); true }
                    Key.Enter, Key.NumPadEnter -> {
                        val hit = filtered.getOrNull(selected)
                        if (hit != null) { onOpenHit(hit); true } else false
                    }
                    Key.Escape -> {
                        if (query.isNotEmpty()) { onQueryChange(""); true } else false
                    }
                    else -> false
                }
            },
        placeholder = { Text(stringResource(dev.ninfenz.mobile.R.string.search_placeholder_short)) },
        leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
        trailingIcon = {
            if (query.isNotEmpty()) {
                IconButton(onClick = { onQueryChange("") }) {
                    Icon(Icons.Filled.Close, contentDescription = stringResource(dev.ninfenz.mobile.R.string.search_clear))
                }
            }
        },
        singleLine = true
    )
}

@Composable
internal fun SearchFilterArea(
    query: String,
    results: List<SearchHit>,
    all: List<SearchHit>,
    filterKind: SearchKind?,
    filterName: String?,
    packIds: List<String>,
    selectedPackId: String?,
    projects: List<ProjectEntry>,
    selectedProjectId: String?,
    favoritesOnly: Boolean,
    scopeTag: String?,
    metaStore: LibraryMetaStore,
    onFilterNameChange: (String?) -> Unit,
    onPackChange: (String?) -> Unit,
    onProjectChange: (String?) -> Unit,
    onFavoritesChange: (Boolean) -> Unit,
    onScopeTagChange: (String?) -> Unit
) {
    if (query.isNotBlank() && results.isNotEmpty()) {
        SearchFilterRow(filterKind) { kind ->
            onFilterNameChange(kind?.name)
        }
        if (packIds.isNotEmpty()) {
            PackFilterRow(packIds, selectedPackId) { onPackChange(it) }
        }
        if (projects.isNotEmpty()) {
            ProjectFilterRow(projects, selectedProjectId) { onProjectChange(it) }
        }
        val scopeTags = metaStore.allTags().sorted()
        if (all.any { it.projectId != null }) {
            SearchScopeRow(scopeTags, favoritesOnly, scopeTag, onFavoritesChange, onScopeTagChange)
        }
        Text(
            stringResource(dev.ninfenz.mobile.R.string.search_keyboard_hint),
            style = NfType.meta,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(horizontal = NfSpacing.page, vertical = 4.dp)
        )
    }
}

@Composable
private fun SearchScopeRow(
    scopeTags: List<String>,
    favoritesOnly: Boolean,
    scopeTag: String?,
    onFavoritesChange: (Boolean) -> Unit,
    onScopeTagChange: (String?) -> Unit
) {
    LazyRow(
        contentPadding = PaddingValues(horizontal = NfSpacing.page),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        item {
            FilterChip(
                selected = favoritesOnly,
                onClick = { onFavoritesChange(!favoritesOnly) },
                label = { Text(stringResource(dev.ninfenz.mobile.R.string.search_scope_favorites)) }
            )
        }
        item {
            FilterChip(
                selected = scopeTag == null,
                onClick = { onScopeTagChange(null) },
                label = { Text(stringResource(dev.ninfenz.mobile.R.string.search_scope_all_tags)) }
            )
        }
        items(scopeTags) { tag ->
            FilterChip(
                selected = scopeTag == tag,
                onClick = { onScopeTagChange(if (scopeTag == tag) null else tag) },
                label = { Text("#" + tag) }
            )
        }
    }
}

@Composable
private fun SearchNoResult(
    showClearFilters: Boolean,
    onQueryChange: (String) -> Unit,
    onClearFilters: () -> Unit
) {
    Column(modifier = Modifier.padding(NfSpacing.page)) {
        Text(
            stringResource(dev.ninfenz.mobile.R.string.search_no_result),
            style = NfType.secondary,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        TextButton(onClick = { onQueryChange("") }) {
            Text(stringResource(dev.ninfenz.mobile.R.string.search_clear))
        }
        if (showClearFilters) {
            TextButton(onClick = onClearFilters) { Text(stringResource(dev.ninfenz.mobile.R.string.search_clear_filters)) }
        }
    }
}

@Composable
internal fun SearchResultsArea(
    query: String,
    filtered: List<SearchHit>,
    history: List<String>,
    all: List<SearchHit>,
    rows: List<SearchRow>,
    selected: Int,
    visibleCount: Int,
    listState: LazyListState,
    showClearFilters: Boolean,
    onQueryChange: (String) -> Unit,
    onOpenHit: (SearchHit) -> Unit,
    onPickHistory: (String) -> Unit,
    onClearHistory: () -> Unit,
    onVisibleCountChange: (Int) -> Unit,
    onClearFilters: () -> Unit
) {
    LaunchedEffect(selected, rows) {
        val itemIndex = rows.indexOfFirst { it.hit != null && it.flatIndex == selected }
        if (itemIndex >= 0) listState.animateScrollToItem(itemIndex)
    }
    when {
        query.isBlank() -> SearchHistoryPanel(history, all.size, onPickHistory, onClearHistory)
        filtered.isEmpty() -> SearchNoResult(showClearFilters, onQueryChange, onClearFilters)
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
                    hit != null -> ResultRow(hit, selected == row.flatIndex) { onOpenHit(hit) }
                }
            }
            if (filtered.size > visibleCount) {
                item {
                    TextButton(onClick = { onVisibleCountChange(visibleCount + 200) }) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.search_show_more, filtered.size - visibleCount))
                    }
                }
            }
        }
    }
}
