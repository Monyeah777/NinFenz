package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.ui.design.NfType

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.ui.components.NfCard
import dev.ninfenz.mobile.ui.components.NfEmptyState
import dev.ninfenz.mobile.ui.components.NfSectionHeader
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.theme.NfSpacing

/** 新建项目向导（W2）：选 Pack → 标题 → 创建（core canonical + project-validate）。 */
@Composable
fun NewProjectScreen(
    packs: List<PackEntry>,
    creating: Boolean,
    error: String?,
    onBack: () -> Unit,
    onLoadSample: () -> Unit,
    onCreate: (PackEntry, String) -> Unit
) {
    var selectedKey by rememberSaveable { mutableStateOf<String?>(null) }
    val selected = packs.firstOrNull { selectedKey == it.id + "@" + it.version } ?: packs.firstOrNull()
    var title by rememberSaveable { mutableStateOf("") }
    var packQuery by rememberSaveable { mutableStateOf("") }

    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = stringResource(dev.ninfenz.mobile.R.string.new_project_title), onBack = onBack)
        if (packs.isEmpty()) {
            NfEmptyState(
                icon = Icons.Filled.Add,
                title = stringResource(dev.ninfenz.mobile.R.string.new_project_no_pack_title),
                message = stringResource(dev.ninfenz.mobile.R.string.new_project_no_pack_body),
                actionLabel = stringResource(dev.ninfenz.mobile.R.string.new_project_load_sample),
                onAction = onLoadSample
            )
        } else {
            LazyColumn(
                contentPadding = androidx.compose.foundation.layout.PaddingValues(NfSpacing.page),
                verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
            ) {
                item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.new_project_select_pack)) }
                item {
                    OutlinedTextField(
                        value = packQuery,
                        onValueChange = { packQuery = it },
                        label = { Text(stringResource(dev.ninfenz.mobile.R.string.pack_search)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
                val filteredPacks = packs.filter { packQuery.isBlank() || it.title.contains(packQuery, true) || it.id.contains(packQuery, true) }
                items(filteredPacks.size) { index ->
                    val pack = filteredPacks[index]
                    NfCard(onClick = { selectedKey = pack.id + "@" + pack.version }) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                            RadioButton(selected = selected?.id == pack.id && selected?.version == pack.version, onClick = { selectedKey = pack.id + "@" + pack.version })
                            Column(modifier = Modifier.weight(1f)) {
                                Text(pack.title, style = NfType.itemTitle)
                                Text(
                                    pack.id + " · " + pack.version + " · " + stringResource(dev.ninfenz.mobile.R.string.pack_item_count, pack.itemCount),
                                    style = NfType.meta,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                    }
                }
                item {
                    OutlinedTextField(
                        value = title,
                        onValueChange = { title = it },
                        label = { Text(stringResource(dev.ninfenz.mobile.R.string.new_project_field_title)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        supportingText = { Text(stringResource(dev.ninfenz.mobile.R.string.new_project_field_hint)) }
                    )
                }
                if (error != null) {
                    item {
                        Surface(color = MaterialTheme.colorScheme.errorContainer, shape = MaterialTheme.shapes.medium) {
                            Column(modifier = Modifier.padding(NfSpacing.m), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                                Text(
                                    error,
                                    style = NfType.meta,
                                    color = MaterialTheme.colorScheme.onErrorContainer
                                )
                                Text(
                                    stringResource(dev.ninfenz.mobile.R.string.new_project_error_kept),
                                    style = NfType.meta,
                                    color = MaterialTheme.colorScheme.onErrorContainer
                                )
                            }
                        }
                    }
                }
                item {
                    val unnamedTitle = stringResource(dev.ninfenz.mobile.R.string.unnamed_project)
                    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s), verticalAlignment = Alignment.CenterVertically) {
                        Button(
                            onClick = { selected?.let { onCreate(it, title.ifBlank { unnamedTitle }) } },
                            enabled = selected != null && !creating
                        ) {
                            if (creating) {
                                CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                            } else {
                                Text(stringResource(dev.ninfenz.mobile.R.string.new_project_create))
                            }
                        }
                        TextButton(onClick = onBack) { Text(stringResource(dev.ninfenz.mobile.R.string.new_project_cancel)) }
                    }
                }
            }
        }
    }
}
