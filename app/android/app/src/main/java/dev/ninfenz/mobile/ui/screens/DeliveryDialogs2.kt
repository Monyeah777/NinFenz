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
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.model.DiffKind
import dev.ninfenz.mobile.model.MacroRunner
import dev.ninfenz.mobile.model.TextDiff
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType
import kotlinx.coroutines.launch

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.VersionsDialog() {
    if (showVersions) {
        val versions = remember(showVersions) { versionStore.load(project.id) }
        AlertDialog(
            onDismissRequest = { showVersions = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_versions)) },
            text = {
                Column(modifier = Modifier.heightIn(max = 480.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    if (versions.isEmpty()) Text(stringResource(dev.ninfenz.mobile.R.string.delivery_versions_empty), style = NfType.meta)
                    versions.forEachIndexed { index, version ->
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                "#" + (versions.size - index) + " · " + java.text.SimpleDateFormat("MM-dd HH:mm", java.util.Locale.getDefault()).format(java.util.Date(version.at)),
                                style = NfType.meta
                            )
                            Row {
                                TextButton(onClick = {
                                    compareVersionText = version.markdown
                                    compareVersionLabel = "#" + (versions.size - index)
                                    showVersions = false
                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_compare)) }
                                TextButton(onClick = {
                                    markdown = version.markdown
                                    needsRevalidate = true
                                    activeStep = if (audit) 2 else 3
                                    showVersions = false
                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_restore_version)) }
                            }
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showVersions = false }) { Text(stringResource(android.R.string.ok)) } }
        )
    }

}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.CompareVersionDialog() {
    compareVersionText?.let { oldText ->
        val report = TextDiff.diff(oldText, markdown.orEmpty())
        val visible = report.lines.take(400)
        AlertDialog(
            onDismissRequest = { compareVersionText = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_compare) + " " + compareVersionLabel) },
            text = {
                Column(modifier = Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    if (report.changed == 0) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_compare_empty), style = NfType.meta)
                    }
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.delivery_compare_summary, report.added, report.removed),
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    if (report.degraded) {
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.delivery_compare_degraded),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.error
                        )
                    }
                    visible.forEach { line ->
                        val prefix = when (line.kind) {
                            DiffKind.ADD -> "+ "
                            DiffKind.REMOVE -> "- "
                            DiffKind.EQUAL -> "  "
                        }
                        Text(
                            prefix + line.text,
                            style = NfType.meta,
                            color = when (line.kind) {
                                DiffKind.ADD -> MaterialTheme.colorScheme.primary
                                DiffKind.REMOVE -> MaterialTheme.colorScheme.error
                                DiffKind.EQUAL -> MaterialTheme.colorScheme.onSurfaceVariant
                            }
                        )
                    }
                    if (report.lines.size > visible.size) {
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.delivery_compare_truncated, visible.size),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            },
            confirmButton = { TextButton(onClick = { compareVersionText = null }) { Text(stringResource(android.R.string.ok)) } }
        )
    }

}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.MacrosDialog() {
    if (showMacros) {
        AlertDialog(
            onDismissRequest = { showMacros = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_run_macro)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    if (macroItems.isEmpty()) {
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.delivery_macro_none),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    macroItems.forEach { macro ->
                        TextButton(onClick = {
                            macroSelected = macro
                            macroParams = MacroRunner.placeholders(macro.json).associateWith { "" }
                            showMacroParams = true
                        }) { Text(macro.title.ifBlank { macro.id }) }
                    }
                    if (macroItems.isNotEmpty()) {
                        TextButton(onClick = {
                            showMacros = false
                            showMacroBatchConfirm = true
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_macro_batch_run)) }
                    }
                    macroBatchResult?.let { batch ->
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.delivery_macro_batch_status, batch.status, batch.failures),
                            style = NfType.meta,
                            color = if (batch.failures == 0) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
                        )
                        batch.runs.forEachIndexed { index, run ->
                            Text("#" + (index + 1) + " · " + run.status + " · " + run.failures, style = NfType.meta)
                        }
                    }
                    macroResult?.let { run ->
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.delivery_macro_done, run.status, run.failures),
                            style = NfType.meta,
                            color = if (run.failures == 0) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
                        )
                        run.steps.forEach { step ->
                            Text(
                                step.id + " " + step.action + " · " + step.status +
                                    (if (step.message.isBlank()) "" else " · " + step.message),
                                style = NfType.meta,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showMacros = false }) { Text(stringResource(android.R.string.cancel)) } }
        )
    }

}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.MacroSelectedDialog() {
    macroSelected?.let { macro ->
        if (showMacroParams) {
            AlertDialog(
                onDismissRequest = { showMacroParams = false },
                title = { Text(macro.title.ifBlank { macro.id }) },
                text = {
                    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                        if (macroParams.isEmpty()) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.delivery_macro_no_params), style = NfType.meta)
                        }
                        macroParams.keys.forEach { key ->
                            OutlinedTextField(
                                value = macroParams[key].orEmpty(),
                                onValueChange = { value -> macroParams = macroParams + (key to value) },
                                label = { Text(key) },
                                singleLine = true,
                                modifier = Modifier.fillMaxWidth()
                            )
                        }
                    }
                },
                confirmButton = {
                    TextButton(onClick = {
                        scope.launch {
                            executeMacro(macro, macroParams)
                            showMacroParams = false
                            macroSelected = null
                            showMacros = true
                        }
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_macro_run_selected)) }
                },
                dismissButton = {
                    TextButton(onClick = { showMacroParams = false }) { Text(stringResource(android.R.string.cancel)) }
                }
            )
        }
    }

}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.MacroBatchConfirmDialog() {
    if (showMacroBatchConfirm) {
        AlertDialog(
            onDismissRequest = { showMacroBatchConfirm = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_macro_batch_run)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_macro_batch_confirm)) },
            confirmButton = {
                TextButton(onClick = {
                    scope.launch {
                        executeMacroBatch()
                        showMacroBatchConfirm = false
                        showMacros = true
                    }
                }) { Text(stringResource(android.R.string.ok)) }
            },
            dismissButton = {
                TextButton(onClick = { showMacroBatchConfirm = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.FidelityDialog() {
    fidelityResult?.let { result ->
        AlertDialog(
            onDismissRequest = { fidelityResult = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_fidelity)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.delivery_fidelity_score, result.score, result.matched, result.expected),
                        style = NfType.meta,
                        color = if (result.score == 100) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
                    )
                    if (result.missing.isNotEmpty()) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_fidelity_missing, result.missing.joinToString("、")), style = NfType.meta)
                    }
                    if (result.extra.isNotEmpty()) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_fidelity_extra, result.extra.joinToString("、")), style = NfType.meta)
                    }
                }
            },
            confirmButton = { TextButton(onClick = { fidelityResult = null }) { Text(stringResource(android.R.string.ok)) } }
        )
    }

}
