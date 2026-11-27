package dev.ninfenz.mobile.ui.screens

import android.content.Context
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.AuthorArtifacts
import dev.ninfenz.mobile.data.EpubValidator
import dev.ninfenz.mobile.data.HtmlValidator
import dev.ninfenz.mobile.data.PdfValidator
import dev.ninfenz.mobile.data.ExportHistoryStore
import dev.ninfenz.mobile.data.ExportVerifier
import dev.ninfenz.mobile.data.AssemblyArtifact
import dev.ninfenz.mobile.data.StatusAdvanceResult
import dev.ninfenz.mobile.model.CorrectionPrompt
import dev.ninfenz.mobile.model.ProjectStatus
import dev.ninfenz.mobile.model.ReportModel
import dev.ninfenz.mobile.model.SlotInput
import dev.ninfenz.mobile.model.SlotBatchImporter
import dev.ninfenz.mobile.model.SlotTextAdapter
import dev.ninfenz.mobile.model.ValidateReport
import dev.ninfenz.mobile.share.ShareExporter
import dev.ninfenz.mobile.ui.safeCall
import java.io.File
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

internal fun DeliveryUiState.trashAndRemove(entry: dev.ninfenz.mobile.data.ExportHistoryStore.Entry) {
    runCatching {
        val source = File(entry.path)
        if (source.isFile) {
            val trash = File(File(context.filesDir, "exports"), "trash").apply { mkdirs() }
            val target = File(trash, System.currentTimeMillis().toString() + "-" + source.name)
            if (source.renameTo(target)) {
                File(target.absolutePath + ".restore").writeText(entry.path, Charsets.UTF_8)
            }
        }
    }
    exportHistory.remove(entry.path)
    exportEntries = exportHistory.load()
}

internal fun DeliveryUiState.pasteSlot(slot: String) {
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

internal fun DeliveryUiState.openSlotPicker(slot: String) {
    slotImportTarget = slot
    launchSlotPicker(arrayOf("*/*"))
}

internal fun DeliveryUiState.shouldVerify(format: String): Boolean {
    val profile = selectedPreflight ?: return true
    val flag = profile.config[format]?.toString()?.trim('"')?.toBooleanStrictOrNull() ?: return true
    return flag
}


internal fun DeliveryUiState.applyBatch(onlyEmpty: Boolean) {
    val slots = plan?.slots ?: return
    if (slots.isEmpty() || batchChunks.isEmpty()) return
    val before = inputs
    val result = SlotBatchImporter.apply(batchChunks, slots, inputs, onlyEmpty)
    batchUndo = before
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

internal fun DeliveryUiState.fillTemplateSlots() {
    val parsed = parsedTemplateSlots
    val next = inputs.toMutableMap()
    var filled = 0
    parsed.forEach { (id, value) ->
        if (!next[id].isNullOrBlank() || requireNotNull(plan).slots.none { it == id }) return@forEach
        val meta = specMeta?.slots?.firstOrNull { it.id == id }
        if (!templateValueAllowed(meta, value)) return@forEach
        next[id] = dev.ninfenz.mobile.model.SlotInput.sanitize(meta?.kind, value)
        filled++
    }
    inputs = next
    android.widget.Toast.makeText(
        context,
        context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.delivery_template_filled, filled, filled),
        android.widget.Toast.LENGTH_SHORT
    ).show()
}

internal fun DeliveryUiState.assemblePayloadOf(raw: JsonObject, current: AuthorArtifacts): JsonObject = buildJsonObject {
    put("plan", raw)
    put("spec", current.specJson)
    put("inputs", buildJsonObject { for ((k, v) in inputs) put(k, v) })
}

internal suspend fun DeliveryUiState.advanceStatus(target: ProjectStatus, assembly: AssemblyArtifact? = null, allowAuditSkip: Boolean = false) {
    when (val advanced = statusStore.advance(project, target, assembly, allowAuditSkip)) {
        is StatusAdvanceResult.Advanced -> {
            status = advanced.to
            statusNote = context.getString(dev.ninfenz.mobile.R.string.delivery_status_note, statusText(context, advanced.to))
            onStatusChanged()
        }
        is StatusAdvanceResult.Failure -> statusNote = context.getString(dev.ninfenz.mobile.R.string.delivery_status_fail, advanced.message)
    }
}

internal suspend fun DeliveryUiState.assembleRepro(md: String, payload: JsonObject) {
    val second = safeCall("assemble", payload)
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
}

internal fun DeliveryUiState.parseReport(result: JsonObject) {
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

internal suspend fun DeliveryUiState.validateForAssemble(md: String, raw: JsonObject, current: AuthorArtifacts) {
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
    if (result != null) parseReport(result)
    if (!response.ok) error = response.error
    if (report?.verdict == "pass") {
        needsRevalidate = false
        advanceStatus(ProjectStatus.VALIDATED)
    }
}

internal suspend fun DeliveryUiState.runAssemble(raw: JsonObject, current: AuthorArtifacts) {
    val payload = assemblePayloadOf(raw, current)
    val response = safeCall("assemble", payload)
    val result = response.resultObject()
    val md = result?.let { J.optString(it, "markdown") }
    if (response.ok && !md.isNullOrBlank()) {
        assembleRepro(md, payload)
        markdown = md
        versionStore.save(project.id, md)
        report = null
        needsRevalidate = false
        advanceStatus(ProjectStatus.ASSEMBLED, AssemblyArtifact(md.toByteArray(Charsets.UTF_8)))
        validateForAssemble(md, raw, current)
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

internal fun DeliveryUiState.startAssemble(current: AuthorArtifacts) {
    val raw = rawPlan ?: return
    busy = true
    error = null
    markdown = null
    report = null
    exportedFile = null
    exportVerify = null
    manifestText = null
    scope.launch { runAssemble(raw, current) }
}

internal suspend fun DeliveryUiState.runValidate(md: String, raw: JsonObject, current: AuthorArtifacts) {
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
    if (result != null) parseReport(result)
    if (!response.ok) error = response.error
    if (report?.verdict == "pass") advanceStatus(ProjectStatus.VALIDATED)
    busy = false
}

internal fun DeliveryUiState.startValidate(current: AuthorArtifacts) {
    val md = markdown ?: return
    val raw = rawPlan ?: return
    busy = true
    error = null
    scope.launch { runValidate(md, raw, current) }
}

internal fun DeliveryUiState.shareFixPrompt(r: ValidateReport) {
    val md = markdown ?: return
    val prompt = CorrectionPrompt.build(md, r)
    val intent = ShareExporter.shareMarkdown(context, "nf-fix-prompt", prompt)
    ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.delivery_share_fix))
}

internal fun DeliveryUiState.signContract(checks: List<Pair<String, Boolean>>) {
    val at = java.time.Instant.now().toString()
    val digest = exportedFile?.let { sha256File(it) }
    runCatching {
        contractStore.sign(project.id, checks.filter { it.second }.map { it.first }, at, digest)
    }.onFailure { statusNote = it.message ?: it.javaClass.simpleName }
    signoff = contractStore.load(project.id)
}
