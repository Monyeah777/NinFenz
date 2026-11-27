package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.TextButton
import androidx.compose.foundation.layout.heightIn
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.model.MarkdownBlock
import dev.ninfenz.mobile.model.MarkdownBlocks
import dev.ninfenz.mobile.model.SlotInput
import dev.ninfenz.mobile.ui.components.NfExpandableText
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.EditingPreviewDialog() {
    if (editingPreview) {
        AlertDialog(
            onDismissRequest = {
                if (previewDirty) showDiscardPreview = true else editingPreview = false
            },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.preview_edit_title)) },
            text = { PreviewEditorContent() },
            confirmButton = {
                TextButton(onClick = {
                    markdown = MarkdownBlocks.render(previewBlocks)
                    versionStore.save(project.id, markdown ?: "")
                    previewDirty = false
                    needsRevalidate = true
                    activeStep = if (audit) 2 else 3
                    draftStore.save(project.id, inputs, rawPlan, markdown)
                    report = null
                    validateRepro = null
                    exportedFile = null
                    exportVerify = null
                    editingPreview = false
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_save)) }
            },
            dismissButton = {
                TextButton(onClick = {
                    if (previewDirty) showDiscardPreview = true else editingPreview = false
                }) {
                    Text(stringResource(android.R.string.cancel))
                }
            }
        )
    }

}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.PreviewEditorContent() {
    Column(
        modifier = Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(NfSpacing.s)
    ) {
        PreviewEditorToolbar()
        PreviewBlocks()
        PreviewEditorAddBlock()
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.PreviewEditorToolbar() {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(
            stringResource(dev.ninfenz.mobile.R.string.preview_edit_note),
            style = NfType.meta,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.weight(1f)
        )
        PreviewUndoRedoButtons()
        PreviewToolbarActions()
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.PreviewUndoRedoButtons() {
    TextButton(
        enabled = previewHistory.isNotEmpty(),
        onClick = {
            previewRedo = previewRedo + listOf(previewBlocks)
            previewBlocks = previewHistory.last()
            previewHistory = previewHistory.dropLast(1)
        }
    ) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_undo)) }
    TextButton(
        enabled = previewRedo.isNotEmpty(),
        onClick = {
            previewHistory = previewHistory + listOf(previewBlocks)
            previewBlocks = previewRedo.last()
            previewRedo = previewRedo.dropLast(1)
        }
    ) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_redo)) }
    TextButton(onClick = { showBulk = true }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_bulk)) }
    TextButton(onClick = { showManualTransform = true }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_manual_transform)) }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.PreviewToolbarActions() {
    TextButton(onClick = {
        val base = previewBaseline
        val changed = if (base.size == previewBlocks.size) {
            base.indices.filter { base[it].text != previewBlocks[it].text }
        } else emptyList()
        val transform = if (changed.isNotEmpty()) {
            dev.ninfenz.mobile.model.FlashFillModel.infer(
                changed.map { i -> base[i].text to previewBlocks[i].text }
            )
        } else null
        if (transform == null) {
            android.widget.Toast.makeText(context, context.getString(dev.ninfenz.mobile.R.string.preview_infer_failed), android.widget.Toast.LENGTH_SHORT).show()
        } else {
            previewHistory = previewHistory + listOf(previewBlocks)
            previewRedo = emptyList()
            previewBlocks = previewBlocks.map { it.copy(text = transform.apply(it.text)) }
            previewDirty = true
            inferredTransform = transform
            android.widget.Toast.makeText(context, context.getString(dev.ninfenz.mobile.R.string.preview_infer_done, transform.describe()), android.widget.Toast.LENGTH_SHORT).show()
        }
    }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_infer)) }
    inferredTransform?.let { t ->
        TextButton(onClick = {
            dev.ninfenz.mobile.data.TransformStore(context.filesDir).save(project.id, t)
            savedTransform = t
            android.widget.Toast.makeText(context, context.getString(dev.ninfenz.mobile.R.string.preview_transform_saved), android.widget.Toast.LENGTH_SHORT).show()
        }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_save_transform)) }
    }
    savedTransform?.let { t ->
        TextButton(onClick = {
            previewHistory = previewHistory + listOf(previewBlocks)
            previewRedo = emptyList()
            previewBlocks = previewBlocks.map { it.copy(text = t.apply(it.text)) }
            previewDirty = true
        }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_apply_saved)) }
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.PreviewBlocks() {
    previewBlocks.forEachIndexed { index, block ->
        PreviewBlockEditor(index, block)
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.PreviewBlockEditor(index: Int, block: MarkdownBlock) {
    Text(block.kind, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
    OutlinedTextField(
        value = block.text,
        onValueChange = { value ->
            previewHistory = previewHistory + listOf(previewBlocks)
            previewRedo = emptyList()
            previewDirty = true
            previewBlocks = previewBlocks.toMutableList().also { it[index] = block.copy(text = value) }
        },
        modifier = Modifier.fillMaxWidth(),
        minLines = 2
    )
    if (block.kind in setOf("paragraph", "quote") && block.text.isNotBlank() && block.text.length <= 80 && index !in ignoredHints) {
        PreviewBlockSuggestion(index, block)
    }
    PreviewBlockActions(index, block)
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.PreviewBlockSuggestion(index: Int, block: MarkdownBlock) {
    val heading = previewBlocks.take(index).lastOrNull { it.kind == "heading" }?.text
    val suggestion = dev.ninfenz.mobile.model.FormalizationSuggester.suggest(
        block.text,
        heading,
        specMeta?.slots.orEmpty(),
        inputs.filterValues { it.isNotBlank() }.keys
    )

    val applySuggestion: (String, String) -> Unit = { slotId, text -> inputs = inputs + (slotId to text) }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(
            if (suggestion != null) {
                stringResource(dev.ninfenz.mobile.R.string.preview_suggest_slot, suggestion.slotId, suggestion.slotName)
            } else {
                stringResource(dev.ninfenz.mobile.R.string.preview_formalize_hint)
            },
            style = NfType.meta,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.weight(1f)
        )
        if (suggestion != null) PreviewSuggestionApplyButton(suggestion.slotId, block.text, applySuggestion)
        TextButton(onClick = { assignBlockText = block.text }) {
            Text(stringResource(dev.ninfenz.mobile.R.string.preview_formalize))
        }
        TextButton(onClick = { ignoredHints = ignoredHints + index }) {
            Text(stringResource(dev.ninfenz.mobile.R.string.preview_ignore))
        }
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.PreviewBlockActions(index: Int, block: MarkdownBlock) {
    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
        TextButton(
            enabled = index > 0,
            onClick = {
                previewHistory = previewHistory + listOf(previewBlocks)
                previewBlocks = previewBlocks.toMutableList().also {
                    val item = it.removeAt(index)
                    it.add(index - 1, item)
                }
            }
        ) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_block_up)) }
        TextButton(
            enabled = index < previewBlocks.lastIndex,
            onClick = {
                previewHistory = previewHistory + listOf(previewBlocks)
                previewBlocks = previewBlocks.toMutableList().also {
                    val item = it.removeAt(index)
                    it.add(index + 1, item)
                }
            }
        ) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_block_down)) }
        TextButton(onClick = {
            previewHistory = previewHistory + listOf(previewBlocks)
            previewBlocks = previewBlocks.filterIndexed { i, _ -> i != index }
        }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_block_delete)) }
        TextButton(onClick = { assignBlockText = block.text }) {
            Text(stringResource(dev.ninfenz.mobile.R.string.preview_assign_slot))
        }
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.PreviewEditorAddBlock() {
    TextButton(onClick = {
        previewHistory = previewHistory + listOf(previewBlocks)
        previewBlocks = previewBlocks + MarkdownBlock(
            id = (previewBlocks.maxOfOrNull { it.id } ?: 0) + 1,
            text = ""
        )
    }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_block_add)) }
}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.SlotImportTargetDialog() {
    slotImportTarget?.let { target ->
        AlertDialog(
            onDismissRequest = { slotImportTarget = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_import_title, target)) },
            text = {
                Column(
                    modifier = Modifier
                        .heightIn(max = 420.dp)
                        .verticalScroll(rememberScrollState())
                ) {
                    Text(
                        pluralStringResource(
                            dev.ninfenz.mobile.R.plurals.delivery_slot_import_meta,
                            slotImportAdapted,
                            slotImportSource,
                            slotImportFormat,
                            slotImportOriginal,
                            slotImportAdapted
                        ),
                        style = NfType.meta
                    )
                    NfExpandableText(slotImportText, collapsedLines = 10)
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    val meta = specMeta?.slots?.firstOrNull { it.id == target }
                    val clean = SlotInput.sanitize(meta?.kind, slotImportText).let { value ->
                        meta?.maxChars?.let { value.take(it) } ?: value
                    }
                    inputs = inputs + (target to clean)
                    slotImportTarget = null
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_replace)) }
            },
            dismissButton = {
                Row {
                    TextButton(onClick = {
                        val meta = specMeta?.slots?.firstOrNull { it.id == target }
                        val old = inputs[target].orEmpty().trim()
                        val merged = if (old.isBlank()) slotImportText else old + "\n\n" + slotImportText
                        val clean = SlotInput.sanitize(meta?.kind, merged).let { value ->
                            meta?.maxChars?.let { value.take(it) } ?: value
                        }
                        inputs = inputs + (target to clean)
                        slotImportTarget = null
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_append)) }
                    TextButton(onClick = { slotImportTarget = null }) { Text(stringResource(android.R.string.cancel)) }
                }
            }
        )
    }
}
