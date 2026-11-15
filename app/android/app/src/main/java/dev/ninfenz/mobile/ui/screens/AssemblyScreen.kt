package dev.ninfenz.mobile.ui.screens

import android.content.Intent
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
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
                error = CoreResponse.failure("NF-ASM-003", "plan 解析失败：" + (e.message ?: e.javaClass.simpleName), "按 app/schema/nf-assembly-plan.schema.json 修正", 1).error
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
                error = CoreResponse.failure("NF-SPC-001", "spec 解析失败：" + (e.message ?: e.javaClass.simpleName), "按 app/schema/nf-md-spec.schema.json 修正", 1).error
            }
        }
    }

    NfScaffold(title = stringResource(dev.ninfenz.mobile.R.string.assembly_title), onBack = onBack) {
        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.assembly_input)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { planPicker.launch(arrayOf("application/json", "text/plain")) }) { Text(stringResource(dev.ninfenz.mobile.R.string.assembly_open_plan)) }
                OutlinedButton(onClick = { specPicker.launch(arrayOf("application/json", "text/plain")) }) { Text(stringResource(dev.ninfenz.mobile.R.string.assembly_open_spec)) }
            }
            KeyValue("plan", plan?.let { it.pipelineId + " · steps " + it.steps.size + " · slots " + it.slots.size } ?: "未加载")
            KeyValue("spec", spec?.let { it.id + " · sections " + it.sections.size + " · slots " + it.slots.size } ?: "未加载")
            spec?.let { s ->
                val issues = SpecModel.formIssues(s)
                if (issues.isEmpty()) Notice("spec 本地检查通过", Tone.INFO)
                for (issue in issues) Notice(issue.code + "：" + issue.message, Tone.WARN)
            }
            plan?.let { p ->
                val issues = PlanModel.formIssues(p)
                if (issues.isEmpty()) Notice("plan 本地检查通过", Tone.INFO)
                for (issue in issues) Notice(issue.code + "：" + issue.message, Tone.WARN)
            }
        }

        error?.let { ErrorNotice(it) }

        val p = plan
        val s = spec
        if (p == null || s == null) {
            EmptyState(stringResource(dev.ninfenz.mobile.R.string.assembly_need_plan))
        } else {
            CardBox(title = stringResource(dev.ninfenz.mobile.R.string.assembly_slots)) {
                if (p.slots.isEmpty()) EmptyState(stringResource(dev.ninfenz.mobile.R.string.assembly_no_slots))
                for (slot in p.slots) {
                    FormTextField(
                        label = slot,
                        value = inputs[slot] ?: "",
                        onValueChange = { v -> inputs = inputs + (slot to v) },
                        singleLine = false
                    )
                }
            }

            CardBox(title = stringResource(dev.ninfenz.mobile.R.string.assembly_assemble)) {
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
                    }) { Text(if (busy) "装配中…" else "assemble") }
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
                                    report = ReportModel.parse(response.resultObject()!!)
                                }
                                if (!response.ok) error = response.error
                            } finally {
                                busy = false
                            }
                        }
                    }) { Text(if (busy) "校验中…" else "validate L1") }
                }
                metaSummary?.let { MonoText(it) }
            }

            CardBox(title = stringResource(dev.ninfenz.mobile.R.string.assembly_export)) {
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
                        ShareExporter.launchChooser(context, intent, "分享装配结果")
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.assembly_share_md)) }
                }
                manifest?.let { MonoText(it) }
            }

            report?.let { r ->
                CardBox(title = stringResource(dev.ninfenz.mobile.R.string.assembly_report)) {
                    KeyValue("verdict", ReportModel.line(r))
                    KeyValue("target", r.target.kind + " · " + r.target.ref)
                    for (issue in r.issues) {
                        Notice(issue.code + " " + (issue.path ?: "-") + "：" + issue.message + "；修复：" + issue.fix,
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
