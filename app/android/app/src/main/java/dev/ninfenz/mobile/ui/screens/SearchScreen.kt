package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.data.SearchHit
import dev.ninfenz.mobile.data.SearchIndex
import dev.ninfenz.mobile.data.SearchKind
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.theme.NfSpacing
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** 库搜索（W2）：Pack 条款/字段/节点/章节/槽位 + 项目；本地内存索引，不联网。 */
@Composable
fun SearchScreen(
    onBack: () -> Unit,
    onOpenPack: (packId: String, version: String) -> Unit,
    onOpenProject: (projectId: String) -> Unit
) {
    val context = LocalContext.current
    val index = remember { SearchIndex(context.filesDir) }
    var all by remember { mutableStateOf<List<SearchHit>>(emptyList()) }
    var query by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        all = withContext(Dispatchers.IO) { index.build() }
    }
    val results = remember(query, all) { index.search(all, query) }

    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = stringResource(dev.ninfenz.mobile.R.string.search_title), onBack = onBack)
        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page),
            placeholder = { Text(stringResource(dev.ninfenz.mobile.R.string.search_placeholder)) },
            leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
            singleLine = true
        )
        when {
            query.isBlank() -> Text(
                stringResource(dev.ninfenz.mobile.R.string.search_hint, all.size),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(NfSpacing.page)
            )
            results.isEmpty() -> Text(
                stringResource(dev.ninfenz.mobile.R.string.search_no_result),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(NfSpacing.page)
            )
            else -> {
                val grouped = results.groupBy { it.kind }
                LazyColumn(
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 96.dp),
                    verticalArrangement = Arrangement.spacedBy(2.dp)
                ) {
                    SearchKind.entries.forEach { kind ->
                        val hits = grouped[kind] ?: return@forEach
                        if (hits.isEmpty()) return@forEach
                        item { SectionLabel(kind.label + " · " + hits.size) }
                        items(hits.size) { i ->
                            val hit = hits[i]
                            ResultRow(hit) {
                                when {
                                    hit.kind == SearchKind.PROJECT && hit.projectId != null -> onOpenProject(hit.projectId)
                                    hit.packId != null && hit.packVersion != null -> onOpenPack(hit.packId, hit.packVersion)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SectionLabel(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.titleMedium,
        modifier = Modifier.padding(start = NfSpacing.page, end = NfSpacing.page, top = NfSpacing.m, bottom = NfSpacing.xs)
    )
}

@Composable
private fun ResultRow(hit: SearchHit, onClick: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = NfSpacing.page, vertical = 10.dp)
    ) {
        Text(hit.title, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Text(
            hit.detail,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
    }
}
