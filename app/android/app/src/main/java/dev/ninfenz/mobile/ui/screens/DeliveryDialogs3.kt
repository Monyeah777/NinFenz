package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.TextButton
import androidx.compose.foundation.layout.heightIn
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.share.ShareExporter
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType
import java.io.File

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.LeaveConfirmDialog() {
    if (showLeaveConfirm) {
        AlertDialog(
            onDismissRequest = { showLeaveConfirm = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_leave_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_leave_body)) },
            confirmButton = {
                TextButton(onClick = { showLeaveConfirm = false; onBack() }) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_leave_confirm))
                }
            },
            dismissButton = {
                TextButton(onClick = { showLeaveConfirm = false }) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_leave_stay))
                }
            }
        )
    }

}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.PendingTrashDialog() {
    if (pendingTrash != null) {
        val entry = requireNotNull(pendingTrash)
        AlertDialog(
            onDismissRequest = { pendingTrash = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_trash_title)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    Text(entry.name, style = NfType.meta)
                    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_trash_body), style = NfType.meta)
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    trashAndRemove(entry)
                    pendingTrash = null
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_trash_confirm)) }
            },
            dismissButton = { TextButton(onClick = { pendingTrash = null }) { Text(stringResource(android.R.string.cancel)) } }
        )
    }

}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.TrashDialog() {
    if (showTrash) {
        val trashDir = File(File(context.filesDir, "exports"), "trash")
        val items = remember(showTrash) {
            trashDir.listFiles()?.filter { it.isFile && !it.name.endsWith(".restore") }?.sortedByDescending { it.lastModified() }.orEmpty()
        }
        AlertDialog(
            onDismissRequest = { showTrash = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_trash)) },
            text = {
                Column(modifier = Modifier.heightIn(max = 480.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    if (items.isEmpty()) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_trash_empty), style = NfType.meta)
                    }
                    items.forEach { file ->
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Text(file.name, style = NfType.meta, modifier = Modifier.weight(1f))
                            TextButton(onClick = {
                                val sidecar = File(file.absolutePath + ".restore")
                                val original = sidecar.takeIf { it.isFile }?.readText(Charsets.UTF_8)
                                    ?: File(File(File(context.filesDir, "exports"), "delivery"), file.name.substringAfter('-')).absolutePath
                                val target = File(original)
                                target.parentFile?.mkdirs()
                                if (file.renameTo(target)) sidecar.delete()
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_restore)) }
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showTrash = false }) { Text(stringResource(android.R.string.ok)) } }
        )
    }

}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.AllExportsDialog() {
    if (showAllExports) {
        AlertDialog(
            onDismissRequest = { showAllExports = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_all_exports)) },
            text = {
                Column(
                    modifier = Modifier.heightIn(max = 520.dp).verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)
                ) {
                    exportEntries.forEach { entry ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(entry.format + " · " + entry.name, style = NfType.meta, modifier = Modifier.weight(1f))
                            TextButton(onClick = {
                                val file = File(entry.path)
                                if (file.isFile) {
                                    ShareExporter.launchChooser(
                                        context,
                                        ShareExporter.shareFileIntent(context, file, mimeFor(entry.format), entry.name),
                                        context.getString(dev.ninfenz.mobile.R.string.delivery_share_file)
                                    )
                                }
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_share_file)) }
                            TextButton(onClick = { trashAndRemove(entry) }) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_remove_export))
                            }
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showAllExports = false }) { Text(stringResource(android.R.string.ok)) } }
        )
    }

}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.ResetConfirmDialog() {
    if (showResetConfirm) {
        AlertDialog(
            onDismissRequest = { showResetConfirm = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_reset_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_reset_body)) },
            confirmButton = {
                TextButton(onClick = {
                    plan = null
                    rawPlan = null
                    inputs = emptyMap()
                    markdown = null
                    report = null
                    exportedFile = null
                    manifestText = null
                    exportVerify = null
                    error = null
                    batchChunks = emptyList()
                    batchNote = null
                    previewBlocks = emptyList()
                    previewHistory = emptyList()
                    previewRedo = emptyList()
                    previewDirty = false
                    needsRevalidate = false
                    draftNote = null
                    reproOk = null
                    reproText = null
                    validateRepro = null
                    statusNote = null
                    draftStore.clear(project.id)
                    showResetConfirm = false
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_reset)) }
            },
            dismissButton = {
                TextButton(onClick = { showResetConfirm = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

}
