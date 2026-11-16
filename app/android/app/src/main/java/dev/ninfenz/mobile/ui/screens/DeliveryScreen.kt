package dev.ninfenz.mobile.ui.screens

import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.TextButton
import androidx.compose.foundation.layout.heightIn
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import kotlinx.coroutines.delay
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import android.content.Context
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.AuthorArtifacts
import dev.ninfenz.mobile.data.AuthorArtifactsLoader
import dev.ninfenz.mobile.data.DeliveryDraftStore
import dev.ninfenz.mobile.data.EpubExporter
import dev.ninfenz.mobile.data.EpubValidator
import dev.ninfenz.mobile.data.HtmlExporter
import dev.ninfenz.mobile.data.HtmlValidator
import dev.ninfenz.mobile.data.PdfExporter
import dev.ninfenz.mobile.data.PdfValidator
import dev.ninfenz.mobile.data.ExportHistoryStore
import dev.ninfenz.mobile.data.ExportVerifier
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.AssemblyArtifact
import dev.ninfenz.mobile.data.ProjectStatusStore
import dev.ninfenz.mobile.data.StatusAdvanceResult
import dev.ninfenz.mobile.model.AssemblyPlan
import dev.ninfenz.mobile.model.PlanModel
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ProjectStatus
import dev.ninfenz.mobile.model.ReportModel
import dev.ninfenz.mobile.model.SlotBatchImporter
import dev.ninfenz.mobile.model.SlotTextAdapter
import dev.ninfenz.mobile.model.ValidateReport
import dev.ninfenz.mobile.share.ShareExporter
import dev.ninfenz.mobile.ui.components.NfCard
import dev.ninfenz.mobile.ui.components.NfEmptyState
import dev.ninfenz.mobile.ui.components.NfCollapsibleSection
import dev.ninfenz.mobile.ui.components.NfExpandableText
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
 * 项目状态写回已接；PDF 为本地基础文本导出（PdfExporter），复杂排版/平台打印仍 OPEN。
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
    var slotImportTarget by remember { mutableStateOf<String?>(null) }
    var slotImportSource by remember { mutableStateOf("") }
    var slotImportFormat by remember { mutableStateOf("text") }
    var slotImportOriginal by remember { mutableStateOf(0) }
    var slotImportAdapted by remember { mutableStateOf(0) }
    var slotImportText by remember { mutableStateOf("") }
    var batchChunks by remember { mutableStateOf<List<SlotBatchImporter.Chunk>>(emptyList()) }
    var batchSource by remember { mutableStateOf("") }
    var batchNote by remember { mutableStateOf<String?>(null) }
    val draftStore = remember { DeliveryDraftStore(context.filesDir) }
    val exportHistory = remember { ExportHistoryStore(context.filesDir) }
    var exportEntries by remember { mutableStateOf(exportHistory.load()) }
    var exportVerify by remember { mutableStateOf<ExportVerifier.Result?>(null) }
    val restoredInputs = remember(project.id) { draftStore.load(project.id) }
    var draftNote by remember(project.id) {
        mutableStateOf(if (restoredInputs.isNotEmpty()) context.getString(dev.ninfenz.mobile.R.string.delivery_draft_restored) else null)
    }

    fun pasteSlot(slot: String) {
        val manager = context.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as? android.content.ClipboardManager
        val text = manager?.primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(context)?.toString()
        if (text.isNullOrBlank()) {
            error = CoreResponse.failure("NF-E-003", context.getString(dev.ninfenz.mobile.R.string.delivery_slot_import_empty), context.getString(dev.ninfenz.mobile.R.string.delivery_slot_import_empty_fix), 2).error
            return
        }
        val adapted = SlotTextAdapter.adapt(text, "clipboard.md")
        slotImportTarget = slot
        slotImportSource = "clipboard"
        slotImportFormat = adapted.format
        slotImportOriginal = adapted.original.length
        slotImportAdapted = adapted.adapted.length
        slotImportText = adapted.adapted
    }

    val slotPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri == null) { slotImportTarget = null; return@rememberLauncherForActivityResult }
        val target = slotImportTarget ?: return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val name = uri.lastPathSegment?.substringAfterLast('/') ?: "import"
                val raw = withContext(Dispatchers.IO) {
                    context.contentResolver.openInputStream(uri)?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: ""
                }
                if (raw.isBlank()) {
                    error = CoreResponse.failure("NF-E-003", context.getString(dev.ninfenz.mobile.R.string.delivery_slot_import_empty), context.getString(dev.ninfenz.mobile.R.string.delivery_slot_import_empty_fix), 2).error
                    slotImportTarget = null
                } else {
                    val adapted = SlotTextAdapter.adapt(raw, name)
                    slotImportSource = name
                    slotImportFormat = adapted.format
                    slotImportOriginal = adapted.original.length
                    slotImportAdapted = adapted.adapted.length
                    slotImportText = adapted.adapted
                }
            } catch (t: Throwable) {
                error = CoreResponse.failure("NF-E-003", context.getString(dev.ninfenz.mobile.R.string.delivery_slot_import_fail, t.message ?: t.javaClass.simpleName), context.getString(dev.ninfenz.mobile.R.string.delivery_slot_import_fail_fix), 2).error
                slotImportTarget = null
            }
        }
    }

    fun openSlotPicker(slot: String) {
        slotImportTarget = slot
        slotPicker.launch(arrayOf("*/*"))
    }

    val batchPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val name = uri.lastPathSegment?.substringAfterLast('/') ?: "batch"
                val raw = withContext(Dispatchers.IO) { readTextLimited(context, uri) }
                val chunks = SlotBatchImporter.chunks(raw, name)
                if (chunks.isEmpty()) {
                    error = CoreResponse.failure("NF-E-003", context.getString(dev.ninfenz.mobile.R.string.delivery_slot_batch_empty), context.getString(dev.ninfenz.mobile.R.string.delivery_slot_batch_empty_fix), 2).error
                } else {
                    batchSource = name
                    batchNote = null
                    batchChunks = chunks
                }
            } catch (t: Throwable) {
                error = CoreResponse.failure("NF-E-003", context.getString(dev.ninfenz.mobile.R.string.delivery_slot_import_fail, t.message ?: t.javaClass.simpleName), context.getString(dev.ninfenz.mobile.R.string.delivery_slot_import_fail_fix), 2).error
            }
        }
    }

    fun recordExport(format: String, file: File?, manifest: String?, verify: Boolean = true) {
        if (file == null) return
        val sha = manifest?.let { Regex("\"sha256\":\"([^\"]+)\"").find(it)?.groupValues?.getOrNull(1) }.orEmpty()
        val verdict = when {
            !verify -> null
            format == "epub" -> EpubValidator.inspect(file).let { ExportVerifier.Result(it.ok, it.message) }
            format == "pdf" -> PdfValidator.inspect(file).let { ExportVerifier.Result(it.ok, it.message) }
            format == "html" -> HtmlValidator.inspect(file).let { ExportVerifier.Result(it.ok, it.message) }
            else -> ExportVerifier.verify(file, manifest)
        }
        exportVerify = verdict
        exportHistory.record(format, file, sha, verdict?.ok, verdict?.message)
        exportEntries = exportHistory.load()
    }

    fun applyBatch(onlyEmpty: Boolean) {
        val slots = plan?.slots ?: return
        if (slots.isEmpty() || batchChunks.isEmpty()) return
        val result = SlotBatchImporter.apply(batchChunks, slots, inputs, onlyEmpty)
        inputs = result.values
        batchNote = context.getString(
            dev.ninfenz.mobile.R.string.delivery_slot_batch_done,
            result.filled,
            result.skipped,
            result.appended,
            result.dropped
        )
        batchChunks = emptyList()
    }

    var busy by remember { mutableStateOf(false) }

    val latestInputs by rememberUpdatedState(inputs)
    val latestPlan by rememberUpdatedState(plan)
    LaunchedEffect(project.id, plan, inputs) {
        if (plan != null) {
            delay(500)
            withContext(Dispatchers.IO) { draftStore.save(project.id, inputs) }
        }
    }
    DisposableEffect(project.id) {
        onDispose {
            if (latestPlan != null) draftStore.save(project.id, latestInputs)
        }
    }

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
                                    inputs = parsed.slots.associate { it to (restoredInputs[it] ?: "") }
                                    draftNote = if (restoredInputs.isNotEmpty()) context.getString(dev.ninfenz.mobile.R.string.delivery_draft_restored) else null
                                    markdown = null
                                    report = null
                                    exportedFile = null
                                    manifestText = null
                                    batchChunks = emptyList()
                                    batchNote = null
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

                NfCollapsibleSection(
                    title = stringResource(dev.ninfenz.mobile.R.string.delivery_slots),
                    subtitle = plan?.let { stringResource(dev.ninfenz.mobile.R.string.delivery_plan_summary, it.steps.size, it.slots.size) },
                    initiallyExpanded = true
                ) {
                    plan?.let { p ->
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_batch_hint), style = MaterialTheme.typography.bodySmall)
                            TextButton(onClick = { batchPicker.launch(arrayOf("*/*")) }) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_batch_import))
                            }
                        }
                        batchNote?.let {
                            Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page))
                        }
                        draftNote?.let {
                            Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(horizontal = NfSpacing.page))
                        }
                    }
                    if (plan == null) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_compile_first), style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(horizontal = NfSpacing.page))
                    } else if (plan!!.slots.isEmpty()) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_no_slots), style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(horizontal = NfSpacing.page))
                    } else {
                        for (slot in plan!!.slots) {
                            Column(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(slot, style = MaterialTheme.typography.labelLarge)
                                    Row {
                                        TextButton(onClick = { pasteSlot(slot) }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_paste)) }
                                        TextButton(onClick = { openSlotPicker(slot) }) { Text(stringResource(dev.ninfenz.mobile.R.string.action_import)) }
                                    }
                                }
                                OutlinedTextField(
                                    value = inputs[slot] ?: "",
                                    onValueChange = { inputs = inputs + (slot to it) },
                                    singleLine = false,
                                    minLines = 2,
                                    maxLines = 6,
                                    supportingText = { Text(pluralStringResource(dev.ninfenz.mobile.R.plurals.delivery_slot_chars, (inputs[slot] ?: "").length, (inputs[slot] ?: "").length)) },
                                    modifier = Modifier.fillMaxWidth()
                                )
                            }
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
                                    when (val advanced = statusStore.advance(project, ProjectStatus.ASSEMBLED, AssemblyArtifact(md.toByteArray(Charsets.UTF_8)))) {
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

                NfCollapsibleSection(title = stringResource(dev.ninfenz.mobile.R.string.delivery_export_section), initiallyExpanded = true) {
                Row(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    ExportButton("md", "text/markdown", markdown, project, context, scope, { busy = it }, { error = it }) { file, manifest ->
                        exportedFile = file
                        manifestText = manifest
                        recordExport("md", file, manifest)
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
                        recordExport("zip", file, manifest)
                    }
                    ExportButton("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", markdown, project, context, scope, { busy = it }, { error = it }) { file, manifest ->
                        exportedFile = file
                        manifestText = manifest
                        recordExport("docx", file, manifest)
                    }
                }
                Row(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    ExportButton("json", "application/json", markdown, project, context, scope, { busy = it }, { error = it }) { file, manifest ->
                        exportedFile = file
                        manifestText = manifest
                        recordExport("json", file, manifest)
                    }
                    ExportButton("skill", "application/zip", markdown, project, context, scope, { busy = it }, { error = it }) { file, manifest ->
                        exportedFile = file
                        manifestText = manifest
                        recordExport("skill", file, manifest)
                    }
                }
                Row(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    EpubExportButton(markdown, project, context, scope, { busy = it }, { error = it }) { file ->
                        exportedFile = file
                        manifestText = null
                        recordExport("epub", file, null)
                    }
                    PdfExportButton(markdown, project, context, scope, { busy = it }, { error = it }) { file ->
                        exportedFile = file
                        manifestText = null
                        recordExport("pdf", file, null)
                    }
                    HtmlExportButton(markdown, project, context, scope, { busy = it }, { error = it }) { file ->
                        exportedFile = file
                        manifestText = null
                        recordExport("html", file, null)
                    }
                }
                Row(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    OutlinedButton(
                        enabled = markdown != null,
                        onClick = {
                            val md = markdown ?: return@OutlinedButton
                            val intent = ShareExporter.shareMarkdown(context, "nf-" + project.id, md)
                            ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.delivery_share_md))
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
                            ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.delivery_share_file))
                        }
                    ) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_share_file)) }
                }
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_pdf_note), style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(horizontal = NfSpacing.page))
                manifestText?.let { Text(it, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
                exportVerify?.let {
                    Text(
                        it.message,
                        style = MaterialTheme.typography.bodySmall,
                        color = if (it.ok) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
                        modifier = Modifier.padding(horizontal = NfSpacing.page)
                    )
                }
                if (exportEntries.isNotEmpty()) {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.delivery_recent_exports),
                        style = MaterialTheme.typography.titleSmall,
                        modifier = Modifier.padding(horizontal = NfSpacing.page)
                    )
                    exportEntries.take(5).forEach { entry ->
                        Column(modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(entry.format + " · " + entry.name, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
                            entry.ok?.let { ok ->
                                Text(
                                    stringResource(if (ok) dev.ninfenz.mobile.R.string.export_verified else dev.ninfenz.mobile.R.string.export_verify_failed),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = if (ok) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
                                )
                            }
                            TextButton(onClick = {
                                val file = File(entry.path)
                                if (file.isFile) {
                                    val intent = ShareExporter.shareFileIntent(context, file, mimeFor(entry.format), entry.name)
                                    ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.delivery_share_file))
                                }
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_share_file)) }
                            TextButton(onClick = {
                                val file = File(entry.path)
                                if (file.isFile) {
                                    val intent = ShareExporter.viewFileIntent(context, file, mimeFor(entry.format))
                                    ShareExporter.launchView(context, intent, context.getString(dev.ninfenz.mobile.R.string.delivery_open_file))
                                }
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_open_file)) }
                        }
                        entry.message?.takeIf { entry.ok != true }?.let { message ->
                            Text(
                                message,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.error
                            )
                        }
                        }
                    }
                }
                }

                NfCollapsibleSection(title = stringResource(dev.ninfenz.mobile.R.string.delivery_preview), initiallyExpanded = true) {
                    markdown?.let { md ->
                        NfExpandableText(md, modifier = Modifier.padding(horizontal = NfSpacing.page))
                    } ?: Text(stringResource(dev.ninfenz.mobile.R.string.delivery_not_assembled), style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(horizontal = NfSpacing.page))
                }
            }
        }
    }

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
                        style = MaterialTheme.typography.bodySmall
                    )
                    NfExpandableText(slotImportText, collapsedLines = 10)
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    inputs = inputs + (target to slotImportText)
                    slotImportTarget = null
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_replace)) }
            },
            dismissButton = {
                Row {
                    TextButton(onClick = {
                        val old = inputs[target].orEmpty().trim()
                        inputs = inputs + (target to if (old.isBlank()) slotImportText else old + "\n\n" + slotImportText)
                        slotImportTarget = null
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_append)) }
                    TextButton(onClick = { slotImportTarget = null }) { Text(stringResource(android.R.string.cancel)) }
                }
            }
        )
    }

    if (batchChunks.isNotEmpty()) {
        val slots = plan?.slots.orEmpty()
        AlertDialog(
            onDismissRequest = { batchChunks = emptyList() },
            title = { Text(pluralStringResource(dev.ninfenz.mobile.R.plurals.delivery_slot_batch_title, batchChunks.size, batchChunks.size, slots.size)) },
            text = {
                Column(
                    modifier = Modifier
                        .heightIn(max = 420.dp)
                        .verticalScroll(rememberScrollState())
                ) {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.delivery_slot_batch_meta, batchSource),
                        style = MaterialTheme.typography.bodySmall
                    )
                    slots.forEachIndexed { index, slot ->
                        val chunk = batchChunks.getOrNull(index)
                        if (chunk != null) {
                            Text("$slot ← " + chunk.text.replace('\n', ' ').take(48), style = MaterialTheme.typography.bodySmall)
                        }
                    }
                    if (batchChunks.size > slots.size) {
                        Text(
                            pluralStringResource(dev.ninfenz.mobile.R.plurals.delivery_slot_batch_overflow, batchChunks.size - slots.size, batchChunks.size - slots.size),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.error
                        )
                    }
                }
            },
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

private const val MAX_IMPORT_CHARS = 1_048_576

private fun readTextLimited(context: Context, uri: android.net.Uri): String {
    val stream = context.contentResolver.openInputStream(uri) ?: return ""
    stream.use { input ->
        val reader = java.io.InputStreamReader(input, Charsets.UTF_8)
        val buffer = CharArray(8192)
        val out = StringBuilder()
        while (true) {
            val n = reader.read(buffer)
            if (n < 0) break
            out.append(buffer, 0, n)
            if (out.length > MAX_IMPORT_CHARS) {
                throw IllegalArgumentException(context.getString(dev.ninfenz.mobile.R.string.delivery_slot_import_too_large))
            }
        }
        return out.toString()
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

@Composable
private fun EpubExportButton(
    markdown: String?,
    project: Project,
    context: android.content.Context,
    scope: kotlinx.coroutines.CoroutineScope,
    setBusy: (Boolean) -> Unit,
    setError: (CoreError?) -> Unit,
    onDone: (File) -> Unit
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
                    val created = EpubExporter.export(md, project.title, outDir)
                    onDone(created.file)
                } catch (t: Throwable) {
                    setError(CoreError("NF-EXP-001", "EPUB 导出失败：" + (t.message ?: t.javaClass.simpleName), "检查存储空间", null, 1))
                } finally {
                    setBusy(false)
                }
            }
        }
    ) { Text(context.getString(dev.ninfenz.mobile.R.string.delivery_export, "epub")) }
}

@Composable
private fun PdfExportButton(
    markdown: String?,
    project: Project,
    context: android.content.Context,
    scope: kotlinx.coroutines.CoroutineScope,
    setBusy: (Boolean) -> Unit,
    setError: (CoreError?) -> Unit,
    onDone: (File) -> Unit
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
                    val created = PdfExporter.export(md, project.title, outDir)
                    onDone(created.file)
                } catch (t: Throwable) {
                    setError(CoreError("NF-EXP-002", "PDF 导出失败：" + (t.message ?: t.javaClass.simpleName), "检查存储空间", null, 1))
                } finally {
                    setBusy(false)
                }
            }
        }
    ) { Text(context.getString(dev.ninfenz.mobile.R.string.delivery_export, "pdf")) }
}

@Composable
private fun HtmlExportButton(
    markdown: String?,
    project: Project,
    context: android.content.Context,
    scope: kotlinx.coroutines.CoroutineScope,
    setBusy: (Boolean) -> Unit,
    setError: (CoreError?) -> Unit,
    onDone: (File) -> Unit
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
                    val created = HtmlExporter.export(md, project.title, outDir)
                    onDone(created.file)
                } catch (t: Throwable) {
                    setError(CoreError("NF-EXP-003", "HTML 导出失败：" + (t.message ?: t.javaClass.simpleName), "检查存储空间", null, 1))
                } finally {
                    setBusy(false)
                }
            }
        }
    ) { Text(context.getString(dev.ninfenz.mobile.R.string.delivery_export, "html")) }
}

private fun mimeFor(format: String): String = when (format) {
    "md" -> "text/markdown"
    "zip", "skill" -> "application/zip"
    "docx" -> "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    "json" -> "application/json"
    "epub" -> "application/epub+zip"
    "pdf" -> "application/pdf"
    "html" -> "text/html"
    else -> "application/octet-stream"
}
