package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import dev.ninfenz.mobile.data.TemplateCandidateStore
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.components.EmptyState
import dev.ninfenz.mobile.ui.components.NfScaffold
import dev.ninfenz.mobile.ui.design.NfType
import dev.ninfenz.mobile.ui.theme.NfSpacing
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject

/** 本地模板候选画廊：浏览/复制/删除；不自动创建项目。 */
@Composable
fun TemplateGalleryScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val store = remember { TemplateCandidateStore(context.filesDir) }
    var items by remember { mutableStateOf(store.list()) }
    var note by remember { mutableStateOf<String?>(null) }

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
}
