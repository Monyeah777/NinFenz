package dev.ninfenz.mobile.ui.screens

import android.content.Intent
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.model.AssemblyPlan
import dev.ninfenz.mobile.model.MdSpec
import dev.ninfenz.mobile.model.PlanModel
import dev.ninfenz.mobile.model.ReportModel
import dev.ninfenz.mobile.model.SpecModel
import dev.ninfenz.mobile.model.ValidateReport
import dev.ninfenz.mobile.share.ShareExporter
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.components.EmptyState
import dev.ninfenz.mobile.ui.components.ErrorNotice
import dev.ninfenz.mobile.ui.components.FormTextField
import dev.ninfenz.mobile.ui.components.KeyValue
import dev.ninfenz.mobile.ui.components.MonoText
import dev.ninfenz.mobile.ui.components.NfScaffold
import dev.ninfenz.mobile.ui.components.Notice
import dev.ninfenz.mobile.ui.components.Tone
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.io.File

@Composable
internal fun AssemblySlotsCard(
    plan: AssemblyPlan,
    inputs: Map<String, String>,
    extraSlots: List<String>,
    newSlot: String,
    modifier: Modifier = Modifier,
    onInputsChange: (Map<String, String>) -> Unit,
    onExtraSlotsChange: (List<String>) -> Unit,
    onNewSlotChange: (String) -> Unit,
    onRemoveSlot: (String) -> Unit
) {
    CardBox(title = stringResource(dev.ninfenz.mobile.R.string.assembly_slots), modifier = modifier) {
        val allSlots = plan.slots + extraSlots
        if (allSlots.isEmpty()) EmptyState(stringResource(dev.ninfenz.mobile.R.string.assembly_no_slots))
        for (slot in allSlots) {
            Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                FormTextField(
                    label = slot,
                    value = inputs[slot] ?: "",
                    onValueChange = { v -> onInputsChange(inputs + (slot to v)) },
                    singleLine = false,
                    modifier = Modifier.weight(1f)
                )
                if (slot in extraSlots) {
                    TextButton(onClick = {
                        onRemoveSlot(slot)
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.assembly_remove_slot)) }
                }
            }
        }
        Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
            FormTextField(
                label = stringResource(dev.ninfenz.mobile.R.string.assembly_new_slot),
                value = newSlot,
                onValueChange = onNewSlotChange,
                singleLine = true,
                modifier = Modifier.weight(1f)
            )
            OutlinedButton(onClick = {
                val name = newSlot.trim()
                if (name.isNotEmpty() && name !in allSlots) {
                    onExtraSlotsChange(extraSlots + name)
                    onInputsChange(inputs + (name to ""))
                    onNewSlotChange("")
                }
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.assembly_add_slot)) }
        }
    }
}

@Composable
internal fun AssemblyAssembleCard(
    rawPlan: JsonObject?,
    rawSpec: JsonObject?,
    inputs: Map<String, String>,
    busy: Boolean,
    markdown: String?,
    metaSummary: String?,
    assembleRepro: String?,
    validateRepro: String?,
    modifier: Modifier = Modifier,
    onBusyChange: (Boolean) -> Unit,
    onErrorChange: (CoreError?) -> Unit,
    onMarkdownChange: (String?) -> Unit,
    onMetaSummaryChange: (String?) -> Unit,
    onAssembleReproChange: (String?) -> Unit,
    onValidateReproChange: (String?) -> Unit,
    onReportChange: (ValidateReport?) -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    CardBox(title = stringResource(dev.ninfenz.mobile.R.string.assembly_assemble), modifier = modifier) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(enabled = !busy, onClick = {
                val rawP = rawPlan ?: return@Button
                val rawS = rawSpec ?: return@Button
                scope.launch {
                    runAssemble(context, rawP, rawS, inputs, onBusyChange, onErrorChange,
                        onMarkdownChange, onMetaSummaryChange, onAssembleReproChange)
                }
            }) { Text(if (busy) context.getString(dev.ninfenz.mobile.R.string.assembly_busy) else "assemble") }
            OutlinedButton(enabled = !busy, onClick = {
                val md = markdown ?: return@OutlinedButton
                val rawS = rawSpec ?: return@OutlinedButton
                val rawP = rawPlan ?: return@OutlinedButton
                scope.launch {
                    runValidate(context, md, rawS, rawP, onBusyChange, onErrorChange, onReportChange, onValidateReproChange)
                }
            }) { Text(if (busy) context.getString(dev.ninfenz.mobile.R.string.assembly_validating) else "validate L1") }
        }
        metaSummary?.let { MonoText(it) }
        assembleRepro?.let { MonoText(it) }
        validateRepro?.let { MonoText(it) }
    }
}

@Composable
internal fun AssemblyExportCard(
    markdown: String?,
    busy: Boolean,
    manifest: String?,
    modifier: Modifier = Modifier,
    onBusyChange: (Boolean) -> Unit,
    onErrorChange: (CoreError?) -> Unit,
    onManifestChange: (String?) -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    CardBox(title = stringResource(dev.ninfenz.mobile.R.string.assembly_export), modifier = modifier) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(enabled = !busy && markdown != null, onClick = {
                val md = markdown ?: return@Button
                scope.launch { runExport(context, md, "md", onBusyChange, onErrorChange, onManifestChange) }
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.assembly_export_md)) }
            Button(enabled = !busy && markdown != null, onClick = {
                val md = markdown ?: return@Button
                scope.launch { runExport(context, md, "zip", onBusyChange, onErrorChange, onManifestChange) }
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.assembly_export_zip)) }
            OutlinedButton(enabled = !busy && markdown != null, onClick = {
                val md = markdown ?: return@OutlinedButton
                val intent = ShareExporter.shareMarkdown(context, "nf-assembly", md)
                ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.assembly_share_title))
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.assembly_share_md)) }
        }
        manifest?.let { MonoText(it) }
    }
}

@Composable
internal fun AssemblyWorkspace(
    plan: AssemblyPlan,
    rawPlan: JsonObject?,
    rawSpec: JsonObject?,
    inputs: Map<String, String>,
    markdown: String?,
    metaSummary: String?,
    report: ValidateReport?,
    manifest: String?,
    busy: Boolean,
    assembleRepro: String?,
    validateRepro: String?,
    extraSlots: List<String>,
    newSlot: String,
    reqSlots: BringIntoViewRequester,
    reqAssemble: BringIntoViewRequester,
    reqExport: BringIntoViewRequester,
    onInputsChange: (Map<String, String>) -> Unit,
    onExtraSlotsChange: (List<String>) -> Unit,
    onNewSlotChange: (String) -> Unit,
    onRemoveSlot: (String) -> Unit,
    onBusyChange: (Boolean) -> Unit,
    onErrorChange: (CoreError?) -> Unit,
    onMarkdownChange: (String?) -> Unit,
    onMetaSummaryChange: (String?) -> Unit,
    onAssembleReproChange: (String?) -> Unit,
    onValidateReproChange: (String?) -> Unit,
    onReportChange: (ValidateReport?) -> Unit,
    onManifestChange: (String?) -> Unit
) {
    AssemblySlotsCard(plan, inputs, extraSlots, newSlot,
        modifier = Modifier.bringIntoViewRequester(reqSlots),
        onInputsChange = onInputsChange, onExtraSlotsChange = onExtraSlotsChange,
        onNewSlotChange = onNewSlotChange, onRemoveSlot = onRemoveSlot)
    AssemblyAssembleCard(rawPlan, rawSpec, inputs, busy, markdown, metaSummary, assembleRepro, validateRepro,
        modifier = Modifier.bringIntoViewRequester(reqAssemble),
        onBusyChange = onBusyChange, onErrorChange = onErrorChange,
        onMarkdownChange = onMarkdownChange, onMetaSummaryChange = onMetaSummaryChange,
        onAssembleReproChange = onAssembleReproChange, onValidateReproChange = onValidateReproChange,
        onReportChange = onReportChange)
    AssemblyExportCard(markdown, busy, manifest,
        modifier = Modifier.bringIntoViewRequester(reqExport),
        onBusyChange = onBusyChange, onErrorChange = onErrorChange, onManifestChange = onManifestChange)
    AssemblyReportCard(report = report)
    AssemblyPreviewCard(markdown = markdown)
}

private suspend fun runAssemble(
    context: android.content.Context,
    rawP: JsonObject,
    rawS: JsonObject,
    inputs: Map<String, String>,
    onBusyChange: (Boolean) -> Unit,
    onErrorChange: (CoreError?) -> Unit,
    onMarkdownChange: (String?) -> Unit,
    onMetaSummaryChange: (String?) -> Unit,
    onAssembleReproChange: (String?) -> Unit
) {
    onBusyChange(true)
    onErrorChange(null)
    onMarkdownChange(null)
    onMetaSummaryChange(null)
    try {
        val outDir = File(context.filesDir, "exports/assemble").apply { mkdirs() }
        val payload = buildJsonObject {
            put("plan", rawP)
            put("spec", rawS)
            put("inputs", buildJsonObject {
                for ((k, v) in inputs) put(k, v)
            })
            put("out_dir", outDir.absolutePath)
        }
        val response = safeCall("assemble", payload)
        if (response.ok) {
            val result = response.resultObject()
            if (result != null) {
                val second = safeCall("assemble", payload)
                val secondResult = second.resultObject()
                if (second.ok && secondResult != null) {
                    val offset = dev.ninfenz.mobile.data.ReproChecker.firstDifference(
                        result.toString().toByteArray(Charsets.UTF_8),
                        secondResult.toString().toByteArray(Charsets.UTF_8)
                    )
                    onAssembleReproChange(if (offset == null) {
                        context.getString(dev.ninfenz.mobile.R.string.repro_stable)
                    } else {
                        context.getString(dev.ninfenz.mobile.R.string.repro_diff, offset)
                    })
                }
            }
            onMarkdownChange(result?.let { J.optString(it, "markdown") })
            val meta = result?.let { J.optChild(it, "meta") }
            onMetaSummaryChange(meta?.let {
                "plan digest=" + (J.optString(it, "plan_digest") ?: "-") +
                    " · spec digest=" + (J.optString(it, "spec_digest") ?: "-") +
                    " · missing=" + J.optStringList(it, "missing_slots").joinToString(",")
            })
        } else {
            onErrorChange(response.error)
        }
    } finally {
        onBusyChange(false)
    }
}

private suspend fun runValidate(
    context: android.content.Context,
    md: String,
    rawS: JsonObject,
    rawP: JsonObject,
    onBusyChange: (Boolean) -> Unit,
    onErrorChange: (CoreError?) -> Unit,
    onReportChange: (ValidateReport?) -> Unit,
    onValidateReproChange: (String?) -> Unit
) {
    onBusyChange(true)
    onErrorChange(null)
    onReportChange(null)
    try {
        val payload = buildJsonObject {
            put("markdown", md)
            put("spec", rawS)
            put("plan", rawP)
            put("level", "L1")
        }
        val response = safeCall("validate", payload)
        if (response.resultObject() != null) {
            val result = response.resultObject()!!
            onReportChange(ReportModel.parse(result))
            val second = safeCall("validate", payload)
            val secondResult = second.resultObject()
            if (second.ok && secondResult != null) {
                val offset = dev.ninfenz.mobile.data.ReproChecker.firstDifference(
                    result.toString().toByteArray(Charsets.UTF_8),
                    secondResult.toString().toByteArray(Charsets.UTF_8)
                )
                onValidateReproChange(if (offset == null) {
                    context.getString(dev.ninfenz.mobile.R.string.repro_stable)
                } else {
                    context.getString(dev.ninfenz.mobile.R.string.repro_diff, offset)
                })
            }
        }
        if (!response.ok) onErrorChange(response.error)
    } finally {
        onBusyChange(false)
    }
}

private suspend fun runExport(
    context: android.content.Context,
    md: String,
    format: String,
    onBusyChange: (Boolean) -> Unit,
    onErrorChange: (CoreError?) -> Unit,
    onManifestChange: (String?) -> Unit
) {
    onBusyChange(true)
    onErrorChange(null)
    try {
        val outDir = File(context.filesDir, "exports").apply { mkdirs() }
        val payload = buildJsonObject {
            put("markdown", md)
            put("format", format)
            put("out_dir", outDir.absolutePath)
            put("manifest", true)
        }
        val response = safeCall("export", payload)
        if (response.ok) {
            onManifestChange(response.result?.toString())
        } else {
            onErrorChange(response.error)
        }
    } finally {
        onBusyChange(false)
    }
}
