package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.AnnotatedString
import dev.ninfenz.mobile.R
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.TemplateCandidateStore
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.components.EmptyState
import dev.ninfenz.mobile.ui.components.NfScaffold
import dev.ninfenz.mobile.ui.design.NfType
import dev.ninfenz.mobile.ui.theme.NfSpacing
import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject

/** 本地模板候选画廊：浏览/复制/删除/一键建项目；建项目前显式选 Pack。 */
@Composable
fun TemplateGalleryScreen(
    onBack: () -> Unit,
    packs: List<PackEntry> = emptyList(),
    onUse: (File, PackEntry, String) -> Unit = { _, _, _ -> }
) {
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val store = remember { TemplateCandidateStore(context.filesDir) }
    var items by remember { mutableStateOf(store.list()) }
    var note by remember { mutableStateOf<String?>(null) }
    var pendingUse by remember { mutableStateOf<File?>(null) }

    NfScaffold(title = stringResource(R.string.template_gallery_title), onBack = onBack) {
        if (items.isEmpty()) {
            EmptyState(stringResource(R.string.template_gallery_empty))
        } else {
            note?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
            LazyColumn(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                items(items, key = { it.absolutePath }) { file ->
                    val raw = remember(file) { runCatching { file.readText(Charsets.UTF_8) }.getOrNull() }
                    val obj = remember(raw) { raw?.let { runCatching { Json.parseToJsonElement(it).jsonObject }.getOrNull() } }
                    val sections = obj?.get("sections")?.jsonArray?.size ?: 0
                    val slots = obj?.get("slots")?.jsonArray?.size ?: 0
                    CardBox(title = store.titleOf(file)) {
                        Text(stringResource(R.string.template_gallery_meta, sections, slots), style = NfType.meta)
                        Text((raw ?: "").take(500), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Row(modifier = Modifier.fillMaxWidth()) {
                            TextButton(enabled = raw != null, onClick = {
                                clipboard.setText(AnnotatedString(raw.orEmpty()))
                                note = context.getString(R.string.template_gallery_copied)
                            }) { Text(stringResource(R.string.template_gallery_copy)) }
                            TextButton(
                                enabled = packs.isNotEmpty(),
                                onClick = { pendingUse = file }
                            ) { Text(stringResource(R.string.template_gallery_use)) }
                            TextButton(onClick = {
                                store.delete(file)
                                items = store.list()
                            }) { Text(stringResource(R.string.template_gallery_delete)) }
                        }
                    }
                }
            }
        }
    }

    pendingUse?.let { file ->
        val title = store.titleOf(file)
        AlertDialog(
            onDismissRequest = { pendingUse = null },
            title = { Text(stringResource(R.string.template_gallery_choose_pack)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    Text(title, style = NfType.sectionTitle)
                    if (packs.isEmpty()) {
                        Text(
                            stringResource(R.string.template_gallery_no_packs),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    } else {
                        packs.forEach { pack ->
                            Button(onClick = {
                                pendingUse = null
                                onUse(file, pack, title)
                            }) { Text(pack.id + " · " + pack.version) }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { pendingUse = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}
