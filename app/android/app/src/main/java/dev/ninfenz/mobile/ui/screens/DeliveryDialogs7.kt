package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.TextButton
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import dev.ninfenz.mobile.ui.components.MarkdownPreview
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.BatchChunksDialog() {
    if (batchChunks.isNotEmpty()) {
        val slots = plan?.slots.orEmpty()
        AlertDialog(
            onDismissRequest = { batchChunks = emptyList() },
            title = { Text(pluralStringResource(dev.ninfenz.mobile.R.plurals.delivery_slot_batch_title, batchChunks.size, batchChunks.size, slots.size)) },
            text = { BatchChunksBody() },
            confirmButton = {
                TextButton(onClick = { applyBatch(onlyEmpty = true) }) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_batch_fill_empty))
                }
            },
            dismissButton = {
                Row {
                    TextButton(onClick = { applyBatch(onlyEmpty = false) }) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_batch_replace_all))
                    }
                    TextButton(onClick = { batchChunks = emptyList() }) { Text(stringResource(android.R.string.cancel)) }
                }
            }
        )
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.BatchChunksBody() {
    val slots = plan?.slots.orEmpty()
    Column(
        modifier = Modifier
            .heightIn(max = 420.dp)
            .verticalScroll(rememberScrollState())
    ) {
        Text(
            stringResource(dev.ninfenz.mobile.R.string.delivery_slot_batch_meta, batchSource),
            style = NfType.meta
        )
        Text(
            stringResource(dev.ninfenz.mobile.R.string.delivery_slot_batch_preview_note),
            style = NfType.meta,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        slots.forEachIndexed { index, slot ->
            val chunk = batchChunks.getOrNull(index)
            if (chunk != null) {
                val existing = inputs[slot].orEmpty()
                Text("$slot ← " + chunk.text.replace('\n', ' ').take(48), style = NfType.meta)
                Text(
                    stringResource(
                        if (existing.isBlank()) dev.ninfenz.mobile.R.string.delivery_slot_batch_preview_fill
                        else dev.ninfenz.mobile.R.string.delivery_slot_batch_preview_overwrite
                    ),
                    style = NfType.meta,
                    color = if (existing.isBlank()) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
                )
            }
        }
        if (batchChunks.size > slots.size) {
            Text(
                pluralStringResource(dev.ninfenz.mobile.R.plurals.delivery_slot_batch_overflow, batchChunks.size - slots.size, batchChunks.size - slots.size),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.error
            )
        }
    }
}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.FullPreviewDialog() {
    if (showFullPreview) {
        val md = markdown
        if (md != null) {
            Dialog(
                onDismissRequest = { showFullPreview = false },
                properties = DialogProperties(usePlatformDefaultWidth = false)
            ) {
                Surface(modifier = Modifier.fillMaxSize()) {
                    Column(modifier = Modifier.fillMaxSize().statusBarsPadding()) {
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page, vertical = NfSpacing.s),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                stringResource(dev.ninfenz.mobile.R.string.delivery_preview),
                                style = NfType.screenTitle,
                                modifier = Modifier.weight(1f)
                            )
                            TextButton(onClick = { showFullPreview = false }) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.preview_close))
                            }
                        }
                        HorizontalDivider()
                        Column(
                            modifier = Modifier
                                .fillMaxSize()
                                .verticalScroll(rememberScrollState())
                                .padding(NfSpacing.page)
                        ) {
                            MarkdownPreview(md)
                        }
                    }
                }
            }
        }
    }
}
