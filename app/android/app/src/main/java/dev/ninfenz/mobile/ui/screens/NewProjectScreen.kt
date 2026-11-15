package dev.ninfenz.mobile.ui.screens

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
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
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
    var selected by remember(packs) { mutableStateOf(packs.firstOrNull()) }
    var title by remember { mutableStateOf("") }

    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = "新建项目", onBack = onBack)
        if (packs.isEmpty()) {
            NfEmptyState(
                icon = Icons.Filled.Add,
                title = "还没有可用的 Pack",
                message = "先载入内置示例 Pack，或从文件管理器导入一个 Pack。",
                actionLabel = "载入示例 Pack",
                onAction = onLoadSample
            )
        } else {
            LazyColumn(
                contentPadding = androidx.compose.foundation.layout.PaddingValues(NfSpacing.page),
                verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
            ) {
                item { NfSectionHeader("选择 Pack") }
                items(packs.size) { index ->
                    val pack = packs[index]
                    NfCard(onClick = { selected = pack }) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                            RadioButton(selected = selected?.id == pack.id, onClick = { selected = pack })
                            Column(modifier = Modifier.weight(1f)) {
                                Text(pack.title, style = MaterialTheme.typography.titleMedium)
                                Text(
                                    pack.id + " · " + pack.version + " · " + pack.itemCount + " 项",
                                    style = MaterialTheme.typography.bodySmall,
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
                        label = { Text("项目标题") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        supportingText = { Text("留空则使用「未命名项目」") }
                    )
                }
                if (error != null) {
                    item {
                        Surface(color = MaterialTheme.colorScheme.errorContainer, shape = MaterialTheme.shapes.medium) {
                            Text(
                                error,
                                modifier = Modifier.padding(NfSpacing.m),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onErrorContainer
                            )
                        }
                    }
                }
                item {
                    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s), verticalAlignment = Alignment.CenterVertically) {
                        Button(
                            onClick = { selected?.let { onCreate(it, title.ifBlank { "未命名项目" }) } },
                            enabled = selected != null && !creating
                        ) {
                            if (creating) {
                                CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                            } else {
                                Text("创建项目")
                            }
                        }
                        TextButton(onClick = onBack) { Text("取消") }
                    }
                }
            }
        }
    }
}
