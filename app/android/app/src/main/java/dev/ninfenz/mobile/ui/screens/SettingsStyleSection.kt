package dev.ninfenz.mobile.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import dev.ninfenz.mobile.R
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.data.StyleTemplateStore
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.design.NfType
import dev.ninfenz.mobile.ui.theme.NfSpacing
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** W8 样式模板：导入 DOCX 并保存 OOXML 片段；不声称完整语义逆向。 */
@Composable
fun SettingsStyleSection() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val store = remember { StyleTemplateStore(context.filesDir) }
    var items by remember { mutableStateOf(store.list()) }
    var note by remember { mutableStateOf<String?>(null) }

    val launchPicker = rememberStylePicker(
        context = context,
        scope = scope,
        store = store,
        onRefreshed = { items = store.list() },
        onNote = { note = it }
    )

    StyleTemplateContent(
        items = items,
        note = note,
        onPick = { launchPicker(arrayOf("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/pdf")) },
        onDelete = { style ->
            store.delete(style.id)
            items = store.list()
        }
    )
}

@Composable
private fun rememberStylePicker(
    context: android.content.Context,
    scope: kotlinx.coroutines.CoroutineScope,
    store: StyleTemplateStore,
    onRefreshed: () -> Unit,
    onNote: (String?) -> Unit
): (Array<String>) -> Unit {
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            runCatching {
                val meta = FileAccess.meta(context, uri)
                val file = withContext(Dispatchers.IO) { FileAccess.copyToCache(context, uri, meta.name) }
                val name = meta.name.substringBeforeLast('.')
                val saved = withContext(Dispatchers.IO) {
                    if (meta.mime == "application/pdf" || meta.name.endsWith(".pdf", ignoreCase = true)) {
                        store.fromPdf(file, name, context)
                    } else {
                        store.fromDocx(file, name)
                    }
                }
                onRefreshed()
                onNote(context.getString(R.string.settings_styles_imported, saved.name))
            }.onFailure {
                onNote(context.getString(R.string.settings_styles_failed, it.message ?: it.javaClass.simpleName))
            }
        }
    }
    return { input -> picker.launch(input) }
}

@Composable
private fun StyleTemplateContent(
    items: List<StyleTemplateStore.StyleTemplate>,
    note: String?,
    onPick: () -> Unit,
    onDelete: (StyleTemplateStore.StyleTemplate) -> Unit
) {
    CardBox(title = stringResource(R.string.settings_styles_title)) {
        Text(
            stringResource(R.string.settings_styles_hint),
            style = NfType.meta,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
            TextButton(onClick = onPick) {
                Text(stringResource(R.string.settings_styles_import))
            }
        }
        if (items.isEmpty()) {
            Text(
                stringResource(R.string.settings_styles_empty),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        items.forEach { style ->
            Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(style.name, style = NfType.body)
                    Text(
                        stringResource(R.string.settings_styles_meta, style.sourceFormat, style.digest.take(12)),
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                TextButton(onClick = { onDelete(style) }) { Text(stringResource(R.string.settings_styles_delete)) }
            }
        }
        note?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary) }
    }
}
