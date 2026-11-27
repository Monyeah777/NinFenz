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

internal fun searchRows(displayed: List<SearchHit>): List<SearchRow> {
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
