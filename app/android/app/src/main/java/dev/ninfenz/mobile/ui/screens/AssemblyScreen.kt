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
fun AssemblyScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var plan by remember { mutableStateOf<AssemblyPlan?>(null) }
    var spec by remember { mutableStateOf<MdSpec?>(null) }
    var rawPlan by remember { mutableStateOf<JsonObject?>(null) }
    var rawSpec by remember { mutableStateOf<JsonObject?>(null) }
    var inputs by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    var markdown by remember { mutableStateOf<String?>(null) }
    var metaSummary by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var report by remember { mutableStateOf<ValidateReport?>(null) }
    var manifest by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var assembleRepro by remember { mutableStateOf<String?>(null) }
    var validateRepro by remember { mutableStateOf<String?>(null) }
    var extraSlots by remember { mutableStateOf<List<String>>(emptyList()) }
    var newSlot by remember { mutableStateOf("") }
    var showBrowse by remember { mutableStateOf(false) }
    val reqInput = remember { BringIntoViewRequester() }
    val reqSlots = remember { BringIntoViewRequester() }
    val reqAssemble = remember { BringIntoViewRequester() }
    val reqExport = remember { BringIntoViewRequester() }

    val planPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val text = FileAccess.readText(context, uri)
                val obj = J.parseObject(text, "nf-assembly-plan/1")
                plan = PlanModel.parse(obj)
                rawPlan = obj
                inputs = plan?.slots?.associate { it to "" } ?: emptyMap()
                error = null
            } catch (e: Exception) {
                error = CoreResponse.failure(
                    "NF-ASM-003",
                    context.getString(dev.ninfenz.mobile.R.string.assembly_plan_failed, e.message ?: e.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.assembly_plan_failed_fix),
                    1
                ).error
            }
        }
    }
    val specPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val text = FileAccess.readText(context, uri)
                val obj = J.parseObject(text, "nf-md-spec/1")
                spec = SpecModel.parse(obj)
                rawSpec = obj
                error = null
            } catch (e: Exception) {
                error = CoreResponse.failure(
                    "NF-SPC-001",
                    context.getString(dev.ninfenz.mobile.R.string.assembly_spec_failed, e.message ?: e.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.assembly_spec_failed_fix),
                    1
                ).error
            }
        }
    }

    NfScaffold(title = stringResource(dev.ninfenz.mobile.R.string.assembly_title), onBack = onBack) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(2.dp)) {
            val steps = listOf(
                stringResource(dev.ninfenz.mobile.R.string.assembly_input),
                stringResource(dev.ninfenz.mobile.R.string.assembly_slots),
                stringResource(dev.ninfenz.mobile.R.string.assembly_assemble),
                stringResource(dev.ninfenz.mobile.R.string.assembly_export)
            )
            val reqs = listOf(reqInput, reqSlots, reqAssemble, reqExport)
            steps.forEachIndexed { i, label ->
                TextButton(onClick = { scope.launch { reqs[i].bringIntoView() } }) {
                    Text((i + 1).toString() + " · " + label, style = MaterialTheme.typography.labelMedium)
                }
            }
        }
        if (showBrowse) {
            AlertDialog(
                onDismissRequest = { showBrowse = false },
                title = { Text(stringResource(dev.ninfenz.mobile.R.string.assembly_browse)) },
                text = {
                    androidx.compose.foundation.layout.Column(
                        verticalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        Text("plan: " + (plan?.pipelineId ?: "-") + " · " + (plan?.steps?.size ?: 0) + " steps", style = MaterialTheme.typography.labelMedium)
                        plan?.steps?.forEach { s -> Text("• " + s.id + " · " + s.node + " · " + s.module, style = MaterialTheme.typography.bodySmall) }
                        Text("spec: " + (spec?.id ?: "-") + " · " + (spec?.sections?.size ?: 0) + " sections", style = MaterialTheme.typography.labelMedium)
                        spec?.sections?.forEach { s -> Text("• " + s.title + " · " + s.slots.size + " slots", style = MaterialTheme.typography.bodySmall) }
                        Text("slots: " + (plan?.slots?.size ?: 0) + " + temp " + extraSlots.size, style = MaterialTheme.typography.labelMedium)
                    }
                },
                confirmButton = { TextButton(onClick = { showBrowse = false }) { Text(stringResource(android.R.string.ok)) } }
            )
        }
        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.assembly_input), modifier = Modifier.bringIntoViewRequester(reqInput)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { planPicker.launch(arrayOf("application/json", "text/plain")) }) { Text(stringResource(dev.ninfenz.mobile.R.string.assembly_open_plan)) }
                OutlinedButton(onClick = { specPicker.launch(arrayOf("application/json", "text/plain")) }) { Text(stringResource(dev.ninfenz.mobile.R.string.assembly_open_spec)) }
            }
            KeyValue("plan", plan?.let { it.pipelineId + " · steps " + it.steps.size + " · slots " + it.slots.size } ?: context.getString(dev.ninfenz.mobile.R.string.assembly_not_loaded))
            KeyValue("spec", spec?.let { it.id + " · sections " + it.sections.size + " · slots " + it.slots.size } ?: context.getString(dev.ninfenz.mobile.R.string.assembly_not_loaded))
            TextButton(onClick = { showBrowse = true }, enabled = plan != null || spec != null) {
                Text(stringResource(dev.ninfenz.mobile.R.string.assembly_browse))
            }
            spec?.let { s ->
                val issues = SpecModel.formIssues(s)
                if (issues.isEmpty()) Notice(context.getString(dev.ninfenz.mobile.R.string.assembly_spec_local_ok), Tone.INFO)
                for (issue in issues) Notice(issue.code + "：" + issue.message, Tone.WARN)
            }
            plan?.let { p ->
                val issues = PlanModel.formIssues(p)
                if (issues.isEmpty()) Notice(context.getString(dev.ninfenz.mobile.R.string.assembly_plan_local_ok), Tone.INFO)
                for (issue in issues) Notice(issue.code + "：" + issue.message, Tone.WARN)
            }
        }

        error?.let { ErrorNotice(it) }

        val p = plan
        val s = spec
        if (p == null || s == null) {
            EmptyState(stringResource(dev.ninfenz.mobile.R.string.assembly_need_plan))
        } else {
            CardBox(title = stringResource(dev.ninfenz.mobile.R.string.assembly_slots), modifier = Modifier.bringIntoViewRequester(reqSlots)) {
                val allSlots = p.slots + extraSlots
                if (allSlots.isEmpty()) EmptyState(stringResource(dev.ninfenz.mobile.R.string.assembly_no_slots))
                for (slot in allSlots) {
                    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                        FormTextField(
                            label = slot,
                            value = inputs[slot] ?: "",
                            onValueChange = { v -> inputs = inputs + (slot to v) },
                            singleLine = false,
                            modifier = Modifier.weight(1f)
                        )
                        if (slot in extraSlots) {
                            TextButton(onClick = {
                                extraSlots = extraSlots - slot
                                inputs = inputs - slot
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.assembly_remove_slot)) }
                        }
                    }
                }
                Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    FormTextField(
                        label = stringResource(dev.ninfenz.mobile.R.string.assembly_new_slot),
                        value = newSlot,
                        onValueChange = { newSlot = it },
                        singleLine = true,
                        modifier = Modifier.weight(1f)
                    )
                    OutlinedButton(onClick = {
                        val name = newSlot.trim()
                        if (name.isNotEmpty() && name !in allSlots) {
                            extraSlots = extraSlots + name
                            inputs = inputs + (name to "")
                            newSlot = ""
                        }
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.assembly_add_slot)) }
                }
            }

            CardBox(title = stringResource(dev.ninfenz.mobile.R.string.assembly_assemble), modifier = Modifier.bringIntoViewRequester(reqAssemble)) {
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(enabled = !busy, onClick = {
                        val rawP = rawPlan ?: return@Button
                        val rawS = rawSpec ?: return@Button
                        scope.launch {
                            busy = true
                            error = null
                            markdown = null
                            metaSummary = null
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
                                            assembleRepro = if (offset == null) {
                                                context.getString(dev.ninfenz.mobile.R.string.repro_stable)
                                            } else {
                                                context.getString(dev.ninfenz.mobile.R.string.repro_diff, offset)
                                            }
                                        }
                                    }
                                    markdown = result?.let { J.optString(it, "markdown") }
                                    val meta = result?.let { J.optChild(it, "meta") }
                                    metaSummary = meta?.let {
                                        "plan digest=" + (J.optString(it, "plan_digest") ?: "-") +
                                            " · spec digest=" + (J.optString(it, "spec_digest") ?: "-") +
                                            " · missing=" + J.optStringList(it, "missing_slots").joinToString(",")
                                    }
                                } else {
                                    error = response.error
                                }
                            } finally {
                                busy = false
                            }
                        }
                    }) { Text(if (busy) context.getString(dev.ninfenz.mobile.R.string.assembly_busy) else "assemble") }
                    OutlinedButton(enabled = !busy, onClick = {
                        val md = markdown ?: return@OutlinedButton
                        val rawS = rawSpec ?: return@OutlinedButton
                        val rawP = rawPlan ?: return@OutlinedButton
                        scope.launch {
                            busy = true
                            error = null
                            report = null
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
                                    report = ReportModel.parse(result)
                                    val second = safeCall("validate", payload)
                                    val secondResult = second.resultObject()
                                    if (second.ok && secondResult != null) {
                                        val offset = dev.ninfenz.mobile.data.ReproChecker.firstDifference(
                                            result.toString().toByteArray(Charsets.UTF_8),
                                            secondResult.toString().toByteArray(Charsets.UTF_8)
                                        )
                                        validateRepro = if (offset == null) {
                                            context.getString(dev.ninfenz.mobile.R.string.repro_stable)
                                        } else {
                                            context.getString(dev.ninfenz.mobile.R.string.repro_diff, offset)
                                        }
                                    }
                                }
                                if (!response.ok) error = response.error
                            } finally {
                                busy = false
                            }
                        }
                    }) { Text(if (busy) context.getString(dev.ninfenz.mobile.R.string.assembly_validating) else "validate L1") }
                }
                metaSummary?.let { MonoText(it) }
                assembleRepro?.let { MonoText(it) }
                validateRepro?.let { MonoText(it) }
            }

            CardBox(title = stringResource(dev.ninfenz.mobile.R.string.assembly_export), modifier = Modifier.bringIntoViewRequester(reqExport)) {
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(enabled = !busy && markdown != null, onClick = {
                        val md = markdown ?: return@Button
                        scope.launch {
                            busy = true
                            error = null
                            try {
                                val outDir = File(context.filesDir, "exports").apply { mkdirs() }
                                val payload = buildJsonObject {
                                    put("markdown", md)
                                    put("format", "md")
                                    put("out_dir", outDir.absolutePath)
                                    put("manifest", true)
                                }
                                val response = safeCall("export", payload)
                                if (response.ok) {
                                    manifest = response.result?.toString()
                                } else {
                                    error = response.error
                                }
                            } finally {
                                busy = false
                            }
                        }
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.assembly_export_md)) }
                    Button(enabled = !busy && markdown != null, onClick = {
                        val md = markdown ?: return@Button
                        scope.launch {
                            busy = true
                            error = null
                            try {
                                val outDir = File(context.filesDir, "exports").apply { mkdirs() }
                                val payload = buildJsonObject {
                                    put("markdown", md)
                                    put("format", "zip")
                                    put("out_dir", outDir.absolutePath)
                                    put("manifest", true)
                                }
                                val response = safeCall("export", payload)
                                if (response.ok) {
                                    manifest = response.result?.toString()
                                } else {
                                    error = response.error
                                }
                            } finally {
                                busy = false
                            }
                        }
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.assembly_export_zip)) }
                    OutlinedButton(enabled = !busy && markdown != null, onClick = {
                        val md = markdown ?: return@OutlinedButton
                        val intent = ShareExporter.shareMarkdown(context, "nf-assembly", md)
                        ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.assembly_share_title))
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.assembly_share_md)) }
                }
                manifest?.let { MonoText(it) }
            }

            report?.let { r ->
                CardBox(title = stringResource(dev.ninfenz.mobile.R.string.assembly_report)) {
                    KeyValue("verdict", ReportModel.line(r))
                    KeyValue("target", r.target.kind + " · " + r.target.ref)
                    for (issue in r.issues) {
                        Notice(issue.code + " " + (issue.path ?: "-") + "：" + issue.message + context.getString(dev.ninfenz.mobile.R.string.error_fix_suffix) + issue.fix,
                            if (issue.severity == "error") Tone.ERROR else Tone.WARN)
                    }
                }
            }

            CardBox(title = stringResource(dev.ninfenz.mobile.R.string.assembly_preview)) {
                val md = markdown
                if (md == null) {
                    EmptyState(stringResource(dev.ninfenz.mobile.R.string.assembly_not_assembled))
                } else {
                    MonoText(md)
                }
            }
        }
    }
}
