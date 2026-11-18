package dev.ninfenz.mobile.ui.screens

import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.TextButton
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.Surface
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
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.AuthorArtifacts
import dev.ninfenz.mobile.data.AuthorArtifactsLoader
import dev.ninfenz.mobile.data.DeliveryDraftStore
import dev.ninfenz.mobile.data.DocxReferenceStyles
import dev.ninfenz.mobile.data.EpubExporter
import dev.ninfenz.mobile.data.FileAccess
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
import dev.ninfenz.mobile.model.MarkdownBlock
import dev.ninfenz.mobile.model.MarkdownBlocks
import dev.ninfenz.mobile.model.SpecModel
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
import dev.ninfenz.mobile.ui.components.NfStepStrip
import dev.ninfenz.mobile.ui.components.NfStatusChip
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.components.MarkdownPreview
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
 * 项目状态写回已接；PDF 优先 WebView HTML/CSS（WebPdfExporter），失败回退本地基础文本（PdfExporter）。
 */
@Composable
fun DeliveryScreen(project: Project, pack: PackEntry?, onBack: () -> Unit, onStatusChanged: () -> Unit = {}) {
    val context = LocalContext.current
    val focusManager = LocalFocusManager.current
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
    var showFullPreview by remember { mutableStateOf(false) }
    var editingPreview by remember { mutableStateOf(false) }
    var previewBlocks by remember { mutableStateOf<List<MarkdownBlock>>(emptyList()) }
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
    var reproText by remember { mutableStateOf<String?>(null) }
    var reproOk by remember { mutableStateOf<Boolean?>(null) }
    var validateRepro by remember { mutableStateOf<String?>(null) }
    var docxStyles by remember { mutableStateOf<String?>(null) }
    var docxSectPr by remember { mutableStateOf<String?>(null) }
    var docxTheme by remember { mutableStateOf<String?>(null) }
    var docxNumbering by remember { mutableStateOf<String?>(null) }
    var docxHeader by remember { mutableStateOf<String?>(null) }
    var docxFooter by remember { mutableStateOf<String?>(null) }
    val referencePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            scope.launch {
                val file = runCatching { FileAccess.copyToCache(context, uri, "reference.docx") }.getOrNull()
                val styles = file?.let { DocxReferenceStyles.extract(it) }
                val sectPr = file?.let { DocxReferenceStyles.extractSectPr(it) }
                val theme = file?.let { DocxReferenceStyles.extractTheme(it) }
                val numbering = file?.let { DocxReferenceStyles.extractNumbering(it) }
                val header = file?.let { DocxReferenceStyles.extractHeader(it) }
                val footer = file?.let { DocxReferenceStyles.extractFooter(it) }
                file?.delete()
                docxStyles = styles
                docxSectPr = sectPr
                docxTheme = theme
                docxNumbering = numbering
                docxHeader = header
                docxFooter = footer
                if (styles == null) {
                    error = CoreError(
                        "NF-EXP-002",
                        context.getString(dev.ninfenz.mobile.R.string.docx_reference_failed),
                        context.getString(dev.ninfenz.mobile.R.string.docx_reference_failed_fix),
                        null,
                        2
                    )
                }
            }
        }
    }
    val restoredInputs = remember(project.id) { draftStore.load(project.id) }
    val restoredPlan = remember(project.id) { draftStore.loadPlan(project.id) }
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
    LaunchedEffect(project.id, plan, rawPlan, inputs) {
        if (plan != null) {
            delay(500)
            withContext(Dispatchers.IO) { draftStore.save(project.id, inputs, rawPlan) }
        }
    }
    LaunchedEffect(project.id, restoredPlan) {
        val raw = restoredPlan ?: return@LaunchedEffect
        runCatching { PlanModel.parse(raw) }.onSuccess { parsed ->
            rawPlan = raw
            plan = parsed
            inputs = parsed.slots.associate { it to (restoredInputs[it] ?: "") }
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

    val step = when {
        exportedFile != null -> 3
        markdown != null || report != null -> 2
        plan != null -> 1
        else -> 0
    }
    val specMeta = remember(artifacts?.specJson) {
        artifacts?.let { runCatching { SpecModel.parse(it.specJson) }.getOrNull() }
    }
    Column(modifier = Modifier.fillMaxSize().imePadding()) {
        NfTopAppBar(title = stringResource(dev.ninfenz.mobile.R.string.delivery_title, project.title), onBack = onBack)
        NfStepStrip(
            steps = listOf(
                stringResource(dev.ninfenz.mobile.R.string.delivery_plan),
                stringResource(dev.ninfenz.mobile.R.string.delivery_slots),
                stringResource(dev.ninfenz.mobile.R.string.delivery_assemble_validate),
                stringResource(dev.ninfenz.mobile.R.string.delivery_export_section)
            ),
            current = step
        )
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
        ) {
            Column(
                modifier = Modifier.padding(horizontal = NfSpacing.page),
                verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    NfStatusChip(statusText(context, status))
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.delivery_pack_label, project.refs.basePackId, project.refs.basePackVersion),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.weight(1f),
                        textAlign = androidx.compose.ui.text.style.TextAlign.End
                    )
                }
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_note), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
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
                                    draftStore.save(project.id, inputs, obj)
                                    draftNote = if (restoredInputs.isNotEmpty()) context.getString(dev.ninfenz.mobile.R.string.delivery_draft_restored) else null
                                    markdown = null
                                    report = null
                                    exportedFile = null
                                    manifestText = null
                                    batchChunks = emptyList()
                                    batchNote = null
                                } catch (t: Throwable) {
                                    error = CoreResponse.failure(
                                        "NF-ASM-003",
                                        context.getString(dev.ninfenz.mobile.R.string.delivery_plan_failed, t.message ?: t.javaClass.simpleName),
                                        context.getString(dev.ninfenz.mobile.R.string.delivery_plan_failed_fix),
                                        1
                                    ).error
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
                                val slotMeta = specMeta?.slots?.firstOrNull { it.id == slot }
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text(slot, style = MaterialTheme.typography.labelLarge)
                                        slotMeta?.let {
                                            Text(it.name, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                            Text(
                                                stringResource(if (it.required) dev.ninfenz.mobile.R.string.delivery_slot_required else dev.ninfenz.mobile.R.string.delivery_slot_optional),
                                                style = MaterialTheme.typography.labelSmall,
                                                color = if (it.required) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
                                            )
                                        }
                                    }
                                    Row {
                                        TextButton(onClick = { pasteSlot(slot) }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_paste)) }
                                        TextButton(onClick = { openSlotPicker(slot) }) { Text(stringResource(dev.ninfenz.mobile.R.string.action_import)) }
                                    }
                                }
                                val lastSlot = plan?.slots?.lastOrNull() == slot
                                OutlinedTextField(
                                    value = inputs[slot] ?: "",
                                    onValueChange = { inputs = inputs + (slot to it) },
                                    singleLine = false,
                                    minLines = 2,
                                    maxLines = 6,
                                    keyboardOptions = KeyboardOptions(
                                        imeAction = if (lastSlot) ImeAction.Done else ImeAction.Next
                                    ),
                                    keyboardActions = KeyboardActions(
                                        onDone = { focusManager.clearFocus() },
                                        onNext = { focusManager.moveFocus(FocusDirection.Down) }
                                    ),
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
                            markdown = null
                            report = null
                            exportedFile = null
                            exportVerify = null
                            manifestText = null
                            scope.launch {
                                val assemblePayload = buildJsonObject {
                                    put("plan", raw)
                                    put("spec", current.specJson)
                                    put("inputs", buildJsonObject { for ((k, v) in inputs) put(k, v) })
                                }
                                val response = safeCall("assemble", assemblePayload)
                                val result = response.resultObject()
                                val md = result?.let { J.optString(it, "markdown") }
                                if (response.ok && !md.isNullOrBlank()) {
                                    val second = safeCall("assemble", assemblePayload)
                                    val secondMd = second.resultObject()?.let { J.optString(it, "markdown") }
                                    if (second.ok && !secondMd.isNullOrBlank()) {
                                        val offset = dev.ninfenz.mobile.data.ReproChecker.firstDifference(
                                            md.toByteArray(Charsets.UTF_8),
                                            secondMd.toByteArray(Charsets.UTF_8)
                                        )
                                        reproOk = offset == null
                                        reproText = if (offset == null) {
                                            context.getString(dev.ninfenz.mobile.R.string.repro_stable)
                                        } else {
                                            context.getString(dev.ninfenz.mobile.R.string.repro_diff, offset)
                                        }
                                    }
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
                                    error = response.error ?: CoreResponse.failure(
                                        "NF-ASM-002",
                                        context.getString(dev.ninfenz.mobile.R.string.delivery_no_markdown),
                                        context.getString(dev.ninfenz.mobile.R.string.delivery_no_markdown_fix),
                                        1
                                    ).error
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
                                val validatePayload = buildJsonObject {
                                    put("markdown", md)
                                    put("spec", current.specJson)
                                    put("plan", raw)
                                    put("level", "L1")
                                }
                                val response = safeCall("validate", validatePayload)
                                val result = response.resultObject()
                                if (response.ok && result != null) {
                                    val second = safeCall("validate", validatePayload)
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
                                if (result != null) {
                                    try {
                                        report = ReportModel.parse(result)
                                    } catch (t: Throwable) {
                                        error = CoreResponse.failure(
                                            "NF-VAL-001",
                                            context.getString(dev.ninfenz.mobile.R.string.delivery_report_failed, t.message ?: t.javaClass.simpleName),
                                            context.getString(dev.ninfenz.mobile.R.string.delivery_report_failed_fix),
                                            1
                                        ).error
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
                    validateRepro?.let {
                        Text(it, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(horizontal = NfSpacing.page))
                    }
                    for (issue in r.issues.take(20)) {
                        Text(
                            issue.code + " " + (issue.path ?: "-") + "：" + issue.message + context.getString(dev.ninfenz.mobile.R.string.error_fix_suffix) + issue.fix,
                            style = MaterialTheme.typography.bodySmall,
                            color = if (issue.severity == "error") MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(horizontal = NfSpacing.page)
                        )
                    }
                }

                NfCollapsibleSection(title = stringResource(dev.ninfenz.mobile.R.string.delivery_export_section), initiallyExpanded = true) {
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_export_group_docs), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(start = NfSpacing.page, end = NfSpacing.page, top = NfSpacing.s))
                Row(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    ExportButton("md", "text/markdown", markdown, project, context, scope, { busy = it }, { error = it }, busy) { file, manifest, report ->
                        exportedFile = file
                        manifestText = manifest
                        reproOk = report?.stable
                        reproText = when {
                            report == null -> null
                            report.stable -> context.getString(dev.ninfenz.mobile.R.string.repro_stable)
                            else -> context.getString(dev.ninfenz.mobile.R.string.repro_diff, report.firstDiff ?: -1)
                        }
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
                    ExportButton("zip", "application/zip", markdown, project, context, scope, { busy = it }, { error = it }, busy) { file, manifest, report ->
                        exportedFile = file
                        manifestText = manifest
                        reproOk = report?.stable
                        reproText = when {
                            report == null -> null
                            report.stable -> context.getString(dev.ninfenz.mobile.R.string.repro_stable)
                            else -> context.getString(dev.ninfenz.mobile.R.string.repro_diff, report.firstDiff ?: -1)
                        }
                        recordExport("zip", file, manifest)
                    }
                    ExportButton("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", markdown, project, context, scope, { busy = it }, { error = it }, busy, docxStyles = docxStyles, docxSectPr = docxSectPr, docxTheme = docxTheme, docxNumbering = docxNumbering, docxHeader = docxHeader, docxFooter = docxFooter) { file, manifest, report ->
                        exportedFile = file
                        manifestText = manifest
                        reproOk = report?.stable
                        reproText = when {
                            report == null -> null
                            report.stable -> context.getString(dev.ninfenz.mobile.R.string.repro_stable)
                            else -> context.getString(dev.ninfenz.mobile.R.string.repro_diff, report.firstDiff ?: -1)
                        }
                        recordExport("docx", file, manifest)
                    }
                }
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_export_group_data), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(start = NfSpacing.page, end = NfSpacing.page, top = NfSpacing.s))
                Row(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    ExportButton("json", "application/json", markdown, project, context, scope, { busy = it }, { error = it }, busy) { file, manifest, report ->
                        exportedFile = file
                        manifestText = manifest
                        reproOk = report?.stable
                        reproText = when {
                            report == null -> null
                            report.stable -> context.getString(dev.ninfenz.mobile.R.string.repro_stable)
                            else -> context.getString(dev.ninfenz.mobile.R.string.repro_diff, report.firstDiff ?: -1)
                        }
                        recordExport("json", file, manifest)
                    }
                    ExportButton("skill", "application/zip", markdown, project, context, scope, { busy = it }, { error = it }, busy) { file, manifest, report ->
                        exportedFile = file
                        manifestText = manifest
                        reproOk = report?.stable
                        reproText = when {
                            report == null -> null
                            report.stable -> context.getString(dev.ninfenz.mobile.R.string.repro_stable)
                            else -> context.getString(dev.ninfenz.mobile.R.string.repro_diff, report.firstDiff ?: -1)
                        }
                        recordExport("skill", file, manifest)
                    }
                }
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_export_group_reading), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(start = NfSpacing.page, end = NfSpacing.page, top = NfSpacing.s))
                Row(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    EpubExportButton(markdown, project, context, scope, { busy = it }, { error = it }, busy) { file, report ->
                        exportedFile = file
                        manifestText = null
                        reproOk = report.stable
                        reproText = if (report.stable) {
                            context.getString(dev.ninfenz.mobile.R.string.repro_stable)
                        } else {
                            context.getString(dev.ninfenz.mobile.R.string.repro_diff, report.firstDiff ?: -1)
                        }
                        recordExport("epub", file, null)
                    }
                    PdfExportButton(markdown, project, context, scope, { busy = it }, { error = it }, busy) { file, report ->
                        exportedFile = file
                        manifestText = null
                        reproOk = report.stable
                        reproText = if (report.stable) {
                            context.getString(dev.ninfenz.mobile.R.string.repro_stable)
                        } else {
                            context.getString(dev.ninfenz.mobile.R.string.repro_diff, report.firstDiff ?: -1)
                        }
                        recordExport("pdf", file, null)
                    }
                    HtmlExportButton(markdown, project, context, scope, { busy = it }, { error = it }, busy) { file, report ->
                        exportedFile = file
                        manifestText = null
                        reproOk = report.stable
                        reproText = if (report.stable) {
                            context.getString(dev.ninfenz.mobile.R.string.repro_stable)
                        } else {
                            context.getString(dev.ninfenz.mobile.R.string.repro_diff, report.firstDiff ?: -1)
                        }
                        recordExport("html", file, null)
                    }
                }
                Row(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    OutlinedButton(
                        enabled = markdown != null && !busy,
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
                Row(
                    modifier = Modifier.padding(horizontal = NfSpacing.page),
                    horizontalArrangement = Arrangement.spacedBy(NfSpacing.s),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    OutlinedButton(onClick = {
                        referencePicker.launch(arrayOf("application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.docx_reference_pick)) }
                    Text(
                        stringResource(
                            if (docxStyles != null) dev.ninfenz.mobile.R.string.docx_reference_loaded
                            else dev.ninfenz.mobile.R.string.docx_reference_none
                        ),
                        style = MaterialTheme.typography.bodySmall
                    )
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
                reproText?.let {
                    Text(
                        it,
                        style = MaterialTheme.typography.bodySmall,
                        color = if (reproOk == true) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
                        modifier = Modifier.padding(horizontal = NfSpacing.page)
                    )
                }
                if (exportEntries.isNotEmpty()) {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.delivery_recent_exports),
                            style = MaterialTheme.typography.titleSmall
                        )
                        TextButton(onClick = {
                            exportHistory.clear()
                            exportEntries = emptyList()
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_clear_exports)) }
                    }
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
                        Column(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                            MarkdownPreview(md, limitBlocks = 8)
                            Row {
                                TextButton(onClick = {
                                    previewBlocks = MarkdownBlocks.parse(md)
                                    editingPreview = true
                                }) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.preview_edit))
                                }
                                TextButton(onClick = { showFullPreview = true }) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.preview_full))
                                }
                            }
                        }
                    } ?: Text(stringResource(dev.ninfenz.mobile.R.string.delivery_not_assembled), style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(horizontal = NfSpacing.page))
                }
            }
        }
    }

    if (editingPreview) {
        AlertDialog(
            onDismissRequest = { editingPreview = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.preview_edit_title)) },
            text = {
                Column(
                    modifier = Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(NfSpacing.s)
                ) {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.preview_edit_note),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    previewBlocks.forEachIndexed { index, block ->
                        OutlinedTextField(
                            value = block.text,
                            onValueChange = { value ->
                                previewBlocks = previewBlocks.toMutableList().also { it[index] = block.copy(text = value) }
                            },
                            modifier = Modifier.fillMaxWidth(),
                            minLines = 2
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                            TextButton(
                                enabled = index > 0,
                                onClick = {
                                    previewBlocks = previewBlocks.toMutableList().also {
                                        val item = it.removeAt(index)
                                        it.add(index - 1, item)
                                    }
                                }
                            ) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_block_up)) }
                            TextButton(
                                enabled = index < previewBlocks.lastIndex,
                                onClick = {
                                    previewBlocks = previewBlocks.toMutableList().also {
                                        val item = it.removeAt(index)
                                        it.add(index + 1, item)
                                    }
                                }
                            ) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_block_down)) }
                            TextButton(onClick = {
                                previewBlocks = previewBlocks.filterIndexed { i, _ -> i != index }
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_block_delete)) }
                        }
                    }
                    TextButton(onClick = {
                        previewBlocks = previewBlocks + MarkdownBlock(
                            id = (previewBlocks.maxOfOrNull { it.id } ?: 0) + 1,
                            text = ""
                        )
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_block_add)) }
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    markdown = MarkdownBlocks.render(previewBlocks)
                    report = null
                    validateRepro = null
                    exportedFile = null
                    exportVerify = null
                    editingPreview = false
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_save)) }
            },
            dismissButton = {
                TextButton(onClick = { editingPreview = false }) {
                    Text(stringResource(android.R.string.cancel))
                }
            }
        )
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
                                style = MaterialTheme.typography.titleLarge,
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
    busy: Boolean,
    docxStyles: String? = null,
    docxSectPr: String? = null,
    docxTheme: String? = null,
    docxNumbering: String? = null,
    docxHeader: String? = null,
    docxFooter: String? = null,
    onDone: (File?, String?, dev.ninfenz.mobile.data.ReproChecker.Report?) -> Unit
) {
    Button(
        enabled = markdown != null && !busy,
        onClick = {
            val md = markdown ?: return@Button
            setBusy(true)
            setError(null)
            scope.launch {
                try {
                    val outDir = File(File(context.filesDir, "exports"), "delivery").apply { mkdirs() }
                    fun payloadFor(dir: File) = buildJsonObject {
                        put("markdown", md)
                        put("format", format)
                        put("out_dir", dir.absolutePath)
                        put("manifest", true)
                        put("title", project.title)
                        put("project_id", project.id)
                        if (format == "docx" && docxStyles != null) put("docx_styles", docxStyles)
                        if (format == "docx" && docxSectPr != null) put("docx_sect_pr", docxSectPr)
                        if (format == "docx" && docxTheme != null) put("docx_theme", docxTheme)
                        if (format == "docx" && docxNumbering != null) put("docx_numbering", docxNumbering)
                        if (format == "docx" && docxHeader != null) put("docx_header", docxHeader)
                        if (format == "docx" && docxFooter != null) put("docx_footer", docxFooter)
                    }
                    fun fileFor(dir: File, manifest: kotlinx.serialization.json.JsonObject?): File? {
                        val name = manifest?.get("files")?.toString()?.let { raw ->
                            Regex("\"name\":\"([^\"]+)\"").find(raw)?.groupValues?.getOrNull(1)
                        }
                        return name?.let { File(dir, it) }
                    }
                    val response = safeCall("export", payloadFor(outDir))
                    if (response.ok) {
                        val manifest = response.resultObject()
                        val file = fileFor(outDir, manifest)
                        var report: dev.ninfenz.mobile.data.ReproChecker.Report? = null
                        if (file != null) {
                            val reproDir = File(context.cacheDir, "repro-core-" + format).apply { deleteRecursively(); mkdirs() }
                            val second = safeCall("export", payloadFor(reproDir))
                            if (second.ok) {
                                val secondFile = fileFor(reproDir, second.resultObject())
                                if (secondFile != null) {
                                    report = dev.ninfenz.mobile.data.ReproChecker.check(file, secondFile)
                                }
                            }
                            reproDir.deleteRecursively()
                        }
                        onDone(file, manifest?.toString(), report)
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
    busy: Boolean,
    onDone: (File, dev.ninfenz.mobile.data.ReproChecker.Report) -> Unit
) {
    Button(
        enabled = markdown != null && !busy,
        onClick = {
            val md = markdown ?: return@Button
            setBusy(true)
            setError(null)
            scope.launch {
                try {
                    val outDir = File(File(context.filesDir, "exports"), "delivery").apply { mkdirs() }
                    val created = EpubExporter.export(md, project.title, outDir)
                    val reproDir = File(context.cacheDir, "repro-epub").apply { deleteRecursively(); mkdirs() }
                    val second = EpubExporter.export(md, project.title, reproDir)
                    val report = dev.ninfenz.mobile.data.ReproChecker.check(created.file, second.file)
                    reproDir.deleteRecursively()
                    onDone(created.file, report)
                } catch (t: Throwable) {
                    setError(CoreError("NF-EXP-001", context.getString(dev.ninfenz.mobile.R.string.export_epub_failed, t.message ?: t.javaClass.simpleName), context.getString(dev.ninfenz.mobile.R.string.export_failed_fix), null, 1))
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
    busy: Boolean,
    onDone: (File, dev.ninfenz.mobile.data.ReproChecker.Report) -> Unit
) {
    Button(
        enabled = markdown != null && !busy,
        onClick = {
            val md = markdown ?: return@Button
            setBusy(true)
            setError(null)
            scope.launch {
                try {
                    val outDir = File(File(context.filesDir, "exports"), "delivery").apply { mkdirs() }
                    val rich = dev.ninfenz.mobile.data.WebPdfExporter.export(context, md, project.title, outDir)
                    val createdFile: File = rich?.file ?: PdfExporter.export(md, project.title, outDir).file
                    val reproDir = File(context.cacheDir, "repro-pdf").apply { deleteRecursively(); mkdirs() }
                    val secondFile: File = if (rich != null) {
                        dev.ninfenz.mobile.data.WebPdfExporter.export(context, md, project.title, reproDir)?.file
                            ?: PdfExporter.export(md, project.title, reproDir).file
                    } else {
                        PdfExporter.export(md, project.title, reproDir).file
                    }
                    val report = dev.ninfenz.mobile.data.ReproChecker.check(createdFile, secondFile)
                    reproDir.deleteRecursively()
                    onDone(createdFile, report)
                } catch (t: Throwable) {
                    setError(CoreError("NF-EXP-002", context.getString(dev.ninfenz.mobile.R.string.export_pdf_failed, t.message ?: t.javaClass.simpleName), context.getString(dev.ninfenz.mobile.R.string.export_failed_fix), null, 1))
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
    busy: Boolean,
    onDone: (File, dev.ninfenz.mobile.data.ReproChecker.Report) -> Unit
) {
    Button(
        enabled = markdown != null && !busy,
        onClick = {
            val md = markdown ?: return@Button
            setBusy(true)
            setError(null)
            scope.launch {
                try {
                    val outDir = File(File(context.filesDir, "exports"), "delivery").apply { mkdirs() }
                    val created = HtmlExporter.export(md, project.title, outDir)
                    val reproDir = File(context.cacheDir, "repro-html").apply { deleteRecursively(); mkdirs() }
                    val second = HtmlExporter.export(md, project.title, reproDir)
                    val report = dev.ninfenz.mobile.data.ReproChecker.check(created.file, second.file)
                    reproDir.deleteRecursively()
                    onDone(created.file, report)
                } catch (t: Throwable) {
                    setError(CoreError("NF-EXP-003", context.getString(dev.ninfenz.mobile.R.string.export_html_failed, t.message ?: t.javaClass.simpleName), context.getString(dev.ninfenz.mobile.R.string.export_failed_fix), null, 1))
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
