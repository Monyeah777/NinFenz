package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.TextButton
import androidx.compose.foundation.layout.heightIn
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.model.SlotInput
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.ManualTransformDialog() {
    if (showManualTransform) {
        AlertDialog(
            onDismissRequest = { showManualTransform = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.preview_manual_transform)) },
            text = { ManualTransformBody() },
            confirmButton = {
                val valid = when (manualKind) {
                    "truncate" -> (manualA.toIntOrNull() ?: 0) > 0
                    "prefix", "suffix", "replace" -> manualA.isNotEmpty()
                    else -> true
                }
                TextButton(enabled = valid, onClick = {
                    val transform = dev.ninfenz.mobile.model.FlashFillModel.Transform(manualKind, manualA, manualB)
                    previewHistory = previewHistory + listOf(previewBlocks)
                    previewRedo = emptyList()
                    previewBlocks = previewBlocks.map { it.copy(text = transform.apply(it.text)) }
                    previewDirty = true
                    inferredTransform = transform
                    showManualTransform = false
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_manual_apply)) }
            },
            dismissButton = {
                TextButton(onClick = { showManualTransform = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.ManualTransformBody() {
    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
        Text(stringResource(dev.ninfenz.mobile.R.string.preview_manual_hint), style = NfType.meta)
        Row(
            horizontalArrangement = Arrangement.spacedBy(NfSpacing.xs),
            modifier = Modifier.horizontalScroll(rememberScrollState())
        ) {
            listOf("lower", "upper", "trim", "collapse", "prefix", "suffix", "replace", "truncate").forEach { kind ->
                FilterChip(
                    selected = manualKind == kind,
                    onClick = { manualKind = kind },
                    label = { Text(dev.ninfenz.mobile.model.FlashFillModel.Transform(kind).describe()) }
                )
            }
        }
        if (manualKind in listOf("truncate", "prefix", "suffix", "replace")) {
            OutlinedTextField(
                value = manualA,
                onValueChange = { manualA = it },
                label = {
                    Text(
                        if (manualKind == "truncate") "N" else stringResource(dev.ninfenz.mobile.R.string.preview_bulk_value)
                    )
                },
                modifier = Modifier.fillMaxWidth()
            )
        }
        if (manualKind == "replace") {
            OutlinedTextField(
                value = manualB,
                onValueChange = { manualB = it },
                label = { Text(stringResource(dev.ninfenz.mobile.R.string.preview_bulk_to)) },
                modifier = Modifier.fillMaxWidth()
            )
        }
        val valid = when (manualKind) {
            "truncate" -> (manualA.toIntOrNull() ?: 0) > 0
            "prefix", "suffix", "replace" -> manualA.isNotEmpty()
            else -> true
        }
        if (!valid) {
            Text(
                stringResource(dev.ninfenz.mobile.R.string.preview_manual_invalid),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.error
            )
        }
    }
}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.AssignBlockTextDialog() {
    assignBlockText?.let { text ->
        AlertDialog(
            onDismissRequest = { assignBlockText = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.preview_assign_title)) },
            text = {
                Column(modifier = Modifier.heightIn(max = 360.dp).verticalScroll(rememberScrollState())) {
                    specMeta?.slots?.forEach { slot ->
                        val clean = dev.ninfenz.mobile.model.SlotInput.sanitize(slot.kind, text).let { v ->
                            slot.maxChars?.let { v.take(it) } ?: v
                        }
                        val issues = buildList {
                            if (slot.nonEmpty && clean.isBlank()) add(context.getString(dev.ninfenz.mobile.R.string.slot_required))
                            if (slot.minChars != null && clean.length < slot.minChars) add(context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.slot_min_chars, slot.minChars, slot.minChars))
                            slot.startsWith?.let { if (!clean.startsWith(it)) add(context.getString(dev.ninfenz.mobile.R.string.slot_prefix, it)) }
                            slot.endsWith?.let { if (!clean.endsWith(it)) add(context.getString(dev.ninfenz.mobile.R.string.slot_suffix, it)) }
                            slot.pattern?.let { p ->
                                val matches = runCatching { Regex(p).matches(clean) }.getOrDefault(false)
                                if (!matches) add(context.getString(dev.ninfenz.mobile.R.string.slot_pattern, p))
                            }
                        }
                        TextButton(
                            enabled = issues.isEmpty(),
                            onClick = {
                                inputs = inputs + (slot.id to clean)
                                assignBlockText = null
                            }
                        ) {
                            Text(
                                slot.id + " · " + slot.name + (slot.maxChars?.let { " · " + text.length + "/" + it } ?: "") + (if (issues.isEmpty()) "" else " · " + issues.joinToString("；")),
                                color = if (issues.isEmpty()) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.error
                            )
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { assignBlockText = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.DiscardPreviewDialog() {
    if (showDiscardPreview) {
        AlertDialog(
            onDismissRequest = { showDiscardPreview = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.preview_discard_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.preview_discard_body)) },
            confirmButton = {
                TextButton(onClick = {
                    showDiscardPreview = false
                    editingPreview = false
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_discard)) }
            },
            dismissButton = {
                TextButton(onClick = { showDiscardPreview = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.BulkDialog() {
    if (showBulk) {
        AlertDialog(
            onDismissRequest = { showBulk = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.preview_bulk)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        listOf("replace" to dev.ninfenz.mobile.R.string.preview_bulk_replace, "prefix" to dev.ninfenz.mobile.R.string.preview_bulk_prefix, "suffix" to dev.ninfenz.mobile.R.string.preview_bulk_suffix, "truncate" to dev.ninfenz.mobile.R.string.preview_bulk_truncate).forEach { (mode, label) ->
                            FilterChip(selected = bulkMode == mode, onClick = { bulkMode = mode; bulkError = null }, label = { Text(stringResource(label)) })
                        }
                    }
                    OutlinedTextField(value = bulkFrom, onValueChange = { bulkFrom = it; bulkError = null }, label = { Text(stringResource(if (bulkMode == "replace") dev.ninfenz.mobile.R.string.preview_bulk_from else if (bulkMode == "truncate") dev.ninfenz.mobile.R.string.preview_bulk_length else dev.ninfenz.mobile.R.string.preview_bulk_value)) }, modifier = Modifier.fillMaxWidth())
                    if (bulkMode == "replace") {
                        OutlinedTextField(value = bulkTo, onValueChange = { bulkTo = it }, label = { Text(stringResource(dev.ninfenz.mobile.R.string.preview_bulk_to)) }, modifier = Modifier.fillMaxWidth())
                    }
                    Text(pluralStringResource(dev.ninfenz.mobile.R.plurals.preview_bulk_count, previewBlocks.count { bulkApply(it.text) != it.text }, previewBlocks.count { bulkApply(it.text) != it.text }), style = NfType.meta)
                    bulkError?.let { Text(it, color = MaterialTheme.colorScheme.error, style = NfType.meta) }
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    val bad = bulkFrom.isBlank() || (bulkMode == "truncate" && (bulkFrom.toIntOrNull() ?: 0) <= 0)
                    if (bad) {
                        bulkError = context.getString(dev.ninfenz.mobile.R.string.preview_bulk_empty)
                    } else {
                        previewHistory = previewHistory + listOf(previewBlocks)
                        previewRedo = emptyList()
                        previewBlocks = previewBlocks.map { it.copy(text = bulkApply(it.text)) }
                        previewDirty = true
                        showBulk = false
                    }
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_bulk_apply)) }
            },
            dismissButton = {
                TextButton(onClick = { showBulk = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}
