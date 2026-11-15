package dev.ninfenz.mobile.ui.screens

import android.content.Intent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import android.content.Context
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.AuthorArtifacts
import dev.ninfenz.mobile.data.AuthorArtifactsLoader
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.ProjectStatusStore
import dev.ninfenz.mobile.data.StatusAdvanceResult
import dev.ninfenz.mobile.model.AssemblyPlan
import dev.ninfenz.mobile.model.PlanModel
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ProjectStatus
import dev.ninfenz.mobile.model.ReportModel
import dev.ninfenz.mobile.model.ValidateReport
import dev.ninfenz.mobile.share.ShareExporter
import dev.ninfenz.mobile.ui.components.NfCard
import dev.ninfenz.mobile.ui.components.NfEmptyState
import dev.ninfenz.mobile.ui.components.NfErrorCard
import dev.ninfenz.mobile.ui.components.NfLoadingState
import dev.ninfenz.mobile.ui.components.NfSectionHeader
import dev.ninfenz.mobile.ui.components.NfStatusChip
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.theme.NfSpacing
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/**
 * W5 交付台：项目 → graph-compile 计划 → 槽位输入 → assemble → validate L1 → 导出 md/zip/docx → 分享。
 * 项目状态写回与 PDF 内核仍未接（PDF=平台打印，OPEN）。
 */
@Composable
fun DeliveryScreen(project: Project, pack: PackEntry?, onBack: () -> Unit, onStatusChanged: () -> Unit = {}) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val statusStore = remember { ProjectStatusStore(context.filesDir) }
    var status by remember(project.id) { mutableStateOf(project.status) }
    var statusNote by remember { mutableStateOf<String?>(null) }
    var artifacts by remember { mutableStateOf<AuthorArtifacts?>(null) }
    var loadError by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }

    var plan by remember { mutableStateOf<AssemblyPlan?>(null) }
    var rawPlan by remember { mutableStateOf<JsonObject?>(null) }
    var inputs by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    var markdown by remember { mutableStateOf<String?>(null) }
    var report by remember { mutableStateOf<ValidateReport?>(null) }
    var manifestText by remember { mutableStateOf<String?>(null) }
    var exportedFile by remember { mutableStateOf<File?>(null) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var busy by remember { mutableStateOf(false) }

    LaunchedEffect(pack?.dir?.absolutePath) {
        loading = true
        loadError = null
        try {
            if (pack != null) artifacts = withContext(Dispatchers.IO) { AuthorArtifactsLoader.load(pack) }
        } catch (t: Throwable) {
            loadError = t.message ?: t.javaClass.simpleName
        }
        loading = false
    }

    if (pack == null) {
        Column(modifier = Modifier.fillMaxSize()) {
            NfTopAppBar(title = project.title, onBack = onBack)
            NfEmptyState(
                icon = Icons.Filled.Info,
                title = stringResource(dev.ninfenz.mobile.R.string.delivery_pack_missing_title),
                message = stringResource(dev.ninfenz.mobile.R.string.delivery_pack_missing_body, project.refs.basePackId),
                actionLabel = stringResource(dev.ninfenz.mobile.R.string.delivery_back),
                onAction = onBack
            )
        }
        return
    }

    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = stringResource(dev.ninfenz.mobile.R.string.delivery_title, project.title), onBack = onBack)
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
        ) {
            NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(project.title, style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f))
                        NfStatusChip(statusText(context, status))
                    }
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.delivery_pack_label, project.refs.basePackId, project.refs.basePackVersion),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_note), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            statusNote?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
            if (loading) NfLoadingState()
            if (loadError != null) {
                NfErrorCard("NF-PCK-003", stringResource(dev.ninfenz.mobile.R.string.delivery_load_error, loadError!!), stringResource(dev.ninfenz.mobile.R.string.delivery_load_fix), modifier = Modifier.padding(horizontal = NfSpacing.page))
            }
            error?.let { err -> NfErrorCard(err.code, err.message, err.fix, modifier = Modifier.padding(horizontal = NfSpacing.page)) }

            val current = artifacts
            if (current != null) {
                NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.delivery_plan))
                Button(
                    enabled = !busy,
                    modifier = Modifier.padding(horizontal = NfSpacing.page),
                    onClick = {
                        busy = true
                        error = null
                        scope.launch {
                            val response = safeCall("graph-compile", buildJsonObject {
                                put("graph", current.graphJson)
                                put("spec", current.specJson)
                            })
                            val obj = response.resultObject()
                            if (response.ok && obj != null) {
                                try {
                                    val parsed = PlanModel.parse(obj)
                                    plan = parsed
                                    rawPlan = obj
                                    inputs = parsed.slots.associate { it to "" }
                                    markdown = null
                                    report = null
                                    exportedFile = null
                                    manifestText = null
                                } catch (t: Throwable) {
                                    error = CoreResponse.failure("NF-ASM-003", "plan 解析失败：" + (t.message ?: t.javaClass.simpleName), "检查核心 graph-compile 输出", 1).error
                                }
                            } else {
                                error = response.error
                            }
                            busy = false
                        }
                    }
                ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.delivery_compiling) else stringResource(dev.ninfenz.mobile.R.string.delivery_compile)) }
                plan?.let { p ->
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.delivery_plan_summary, p.steps.size, p.slots.size),
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(horizontal = NfSpacing.page)
                    )
                }

                NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.delivery_slots))
                if (plan == null) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_compile_first), style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(horizontal = NfSpacing.page))
                } else if (plan!!.slots.isEmpty()) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_no_slots), style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(horizontal = NfSpacing.page))
                } else {
                    for (slot in plan!!.slots) {
                        Column(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                            Text(slot, style = MaterialTheme.typography.labelLarge)
                            OutlinedTextField(
                                value = inputs[slot] ?: "",
                                onValueChange = { inputs = inputs + (slot to it) },
                                singleLine = false,
                                modifier = Modifier.fillMaxWidth()
                            )
                        }
                    }
                }

                NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.delivery_assemble_validate))
                Row(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    Button(
                        enabled = !busy && rawPlan != null,
                        onClick = {
                            val raw = rawPlan ?: return@Button
                            busy = true
                            error = null
                            scope.launch {
                                val response = safeCall("assemble", buildJsonObject {
                                    put("plan", raw)
                                    put("spec", current.specJson)
                                    put("inputs", buildJsonObject { for ((k, v) in inputs) put(k, v) })
                                })
                                val result = response.resultObject()
                                val md = result?.let { J.optString(it, "markdown") }
                                if (response.ok && !md.isNullOrBlank()) {
                                    markdown = md
                                    report = null
                                    when (val advanced = statusStore.advance(project, ProjectStatus.ASSEMBLED)) {
                                        is StatusAdvanceResult.Advanced -> {
                                            status = advanced.to
                                            statusNote = context.getString(dev.ninfenz.mobile.R.string.delivery_status_note, statusText(context, advanced.to))
                                            onStatusChanged()
                                        }
                                        is StatusAdvanceResult.Failure -> statusNote = context.getString(dev.ninfenz.mobile.R.string.delivery_status_fail, advanced.message)
                                    }
                                } else {
                                    error = response.error ?: CoreResponse.failure("NF-ASM-002", "装配未返回 markdown", "检查槽位输入", 1).error
                                }
                                busy = false
                            }
                        }
                    ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.delivery_assembling) else stringResource(dev.ninfenz.mobile.R.string.delivery_assemble)) }
                    Button(
                        enabled = !busy && markdown != null && rawPlan != null,
                        onClick = {
                            val md = markdown ?: return@Button
                            val raw = rawPlan ?: return@Button
                            busy = true
                            error = null
                            scope.launch {
                                val response = safeCall("validate", buildJsonObject {
                                    put("markdown", md)
                                    put("spec", current.specJson)
                                    put("plan", raw)
                                    put("level", "L1")
                                })
                                val result = response.resultObject()
                                if (result != null) {
                                    try {
                                        report = ReportModel.parse(result)
                                    } catch (t: Throwable) {
                                        error = CoreResponse.failure("NF-VAL-001", "报告解析失败：" + (t.message ?: t.javaClass.simpleName), "检查核心输出", 1).error
                                    }
                                }
                                if (!response.ok) error = response.error
                                if (report?.verdict == "pass") {
                                    when (val advanced = statusStore.advance(project, ProjectStatus.VALIDATED)) {
                                        is StatusAdvanceResult.Advanced -> {
                                            status = advanced.to
                                            statusNote = context.getString(dev.ninfenz.mobile.R.string.delivery_status_note, statusText(context, advanced.to))
                                            onStatusChanged()
                                        }
                                        is StatusAdvanceResult.Failure -> statusNote = context.getString(dev.ninfenz.mobile.R.string.delivery_status_fail, advanced.message)
                                    }
                                }
                                busy = false
                            }
                        }
                    ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.delivery_validating) else stringResource(dev.ninfenz.mobile.R.string.delivery_validate)) }
                }
                report?.let { r ->
                    Text(ReportModel.line(r), style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(horizontal = NfSpacing.page))
                    for (issue in r.issues.take(20)) {
                        Text(
                            issue.code + " " + (issue.path ?: "-") + "：" + issue.message + "；修复：" + issue.fix,
                            style = MaterialTheme.typography.bodySmall,
                            color = if (issue.severity == "error") MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(horizontal = NfSpacing.page)
                        )
                    }
                }

                NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.delivery_export_section))
                Row(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    ExportButton("md", "text/markdown", markdown, project, context, scope, { busy = it }, { error = it }) { file, manifest ->
                        exportedFile = file
                        manifestText = manifest
                        scope.launch {
                            when (val advanced = statusStore.advance(project, ProjectStatus.EXPORTED)) {
                                is StatusAdvanceResult.Advanced -> {
                                    status = advanced.to
                                    statusNote = context.getString(dev.ninfenz.mobile.R.string.delivery_status_note, statusText(context, advanced.to))
                                    onStatusChanged()
                                }
                                is StatusAdvanceResult.Failure -> statusNote = context.getString(dev.ninfenz.mobile.R.string.delivery_status_fail, advanced.message)
                            }
                        }
                    }
                    ExportButton("zip", "application/zip", markdown, project, context, scope, { busy = it }, { error = it }) { file, manifest ->
                        exportedFile = file
                        manifestText = manifest
                    }
                    ExportButton("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", markdown, project, context, scope, { busy = it }, { error = it }) { file, manifest ->
                        exportedFile = file
                        manifestText = manifest
                    }
                }
                Row(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    OutlinedButton(
                        enabled = markdown != null,
                        onClick = {
                            val md = markdown ?: return@OutlinedButton
                            val intent = ShareExporter.shareMarkdown(context, "nf-" + project.id, md)
                            context.startActivity(Intent.createChooser(intent, context.getString(dev.ninfenz.mobile.R.string.delivery_share_md)))
                        }
                    ) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_share_md)) }
                    OutlinedButton(
                        enabled = exportedFile != null,
                        onClick = {
                            val file = exportedFile ?: return@OutlinedButton
                            val mime = when (file.extension.lowercase()) {
                                "md" -> "text/markdown"
                                "zip" -> "application/zip"
                                "docx" -> "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                                else -> "application/octet-stream"
                            }
                            val intent = ShareExporter.shareFileIntent(context, file, mime, project.title)
                            context.startActivity(Intent.createChooser(intent, context.getString(dev.ninfenz.mobile.R.string.delivery_share_file)))
                        }
                    ) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_share_file)) }
                }
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_pdf_note), style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(horizontal = NfSpacing.page))
                manifestText?.let { Text(it, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(horizontal = NfSpacing.page)) }

                NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.delivery_preview))
                markdown?.let { md ->
                    Text(md.take(4000), style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(horizontal = NfSpacing.page))
                } ?: Text(stringResource(dev.ninfenz.mobile.R.string.delivery_not_assembled), style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(horizontal = NfSpacing.page))
            }
        }
    }
}

private fun statusText(context: Context, status: ProjectStatus): String = when (status) {
    ProjectStatus.DRAFT -> context.getString(dev.ninfenz.mobile.R.string.delivery_status_draft)
    ProjectStatus.AUTHORING -> context.getString(dev.ninfenz.mobile.R.string.delivery_status_authoring)
    ProjectStatus.ASSEMBLED -> context.getString(dev.ninfenz.mobile.R.string.delivery_status_assembled)
    ProjectStatus.VALIDATED -> context.getString(dev.ninfenz.mobile.R.string.delivery_status_validated)
    ProjectStatus.EXPORTED -> context.getString(dev.ninfenz.mobile.R.string.delivery_status_exported)
    ProjectStatus.REVIEWED -> context.getString(dev.ninfenz.mobile.R.string.delivery_status_reviewed)
}

@Composable
private fun ExportButton(
    format: String,
    mime: String,
    markdown: String?,
    project: Project,
    context: android.content.Context,
    scope: kotlinx.coroutines.CoroutineScope,
    setBusy: (Boolean) -> Unit,
    setError: (CoreError?) -> Unit,
    onDone: (File?, String?) -> Unit
) {
    Button(
        enabled = markdown != null,
        onClick = {
            val md = markdown ?: return@Button
            setBusy(true)
            setError(null)
            scope.launch {
                try {
                    val outDir = File(File(context.filesDir, "exports"), "delivery").apply { mkdirs() }
                    val payload = buildJsonObject {
                        put("markdown", md)
                        put("format", format)
                        put("out_dir", outDir.absolutePath)
                        put("manifest", true)
                        put("title", project.title)
                        put("project_id", project.id)
                    }
                    val response = safeCall("export", payload)
                    if (response.ok) {
                        val manifest = response.resultObject()
                        val name = manifest?.get("files")?.toString()?.let { raw ->
                            Regex("\"name\":\"([^\"]+)\"").find(raw)?.groupValues?.getOrNull(1)
                        }
                        val file = name?.let { File(outDir, it) }
                        onDone(file, manifest?.toString())
                    } else {
                        setError(response.error)
                    }
                } finally {
                    setBusy(false)
                }
            }
        }
    ) { Text(context.getString(dev.ninfenz.mobile.R.string.delivery_export, format)) }
}
