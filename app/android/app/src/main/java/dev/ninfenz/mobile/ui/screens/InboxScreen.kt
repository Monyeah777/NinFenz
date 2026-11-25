package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import dev.ninfenz.mobile.share.InboxStore
import dev.ninfenz.mobile.share.SharePayload
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.components.EmptyState
import dev.ninfenz.mobile.ui.components.NfScaffold
import dev.ninfenz.mobile.ui.design.NfType
import dev.ninfenz.mobile.ui.theme.NfSpacing

@Composable
fun InboxScreen(onBack: () -> Unit, onImport: (SharePayload) -> Unit) {
    val context = LocalContext.current
    val store = remember { InboxStore(context.filesDir) }
    var entries by remember { mutableStateOf(store.load()) }
    NfScaffold(title = stringResource(dev.ninfenz.mobile.R.string.inbox_title), onBack = onBack) {
        if (entries.isEmpty()) {
            EmptyState(stringResource(dev.ninfenz.mobile.R.string.inbox_empty))
        } else {
            Row(modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.End) {
                TextButton(onClick = { store.clear(); entries = emptyList() }) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.inbox_clear))
                }
            }
            Column(modifier = Modifier.fillMaxWidth().verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
                entries.forEach { entry ->
                    CardBox(title = entry.payload.kind + " · " + entry.payload.count) {
                        Text(
                            entry.payload.summary(
                                itemLabel = stringResource(dev.ninfenz.mobile.R.string.inbox_items, entry.payload.count),
                                processLabel = entry.payload.processText?.let { stringResource(dev.ninfenz.mobile.R.string.inbox_chars, it.length) }
                            ),
                            style = NfType.secondary
                        )
                        Text(
                            java.text.SimpleDateFormat("MM-dd HH:mm", java.util.Locale.getDefault()).format(java.util.Date(entry.at)),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                            TextButton(onClick = { onImport(entry.payload) }) { Text(stringResource(dev.ninfenz.mobile.R.string.inbox_import)) }
                            TextButton(onClick = { store.remove(entry.id); entries = store.load() }) { Text(stringResource(dev.ninfenz.mobile.R.string.inbox_remove)) }
                        }
                    }
                }
            }
        }
    }
}
