package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.util.orNullLogged
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.data.AuthorArtifacts
import dev.ninfenz.mobile.data.EpubExporter
import dev.ninfenz.mobile.data.HtmlExporter
import dev.ninfenz.mobile.data.PdfExporter
import dev.ninfenz.mobile.data.ExportHistoryStore
import dev.ninfenz.mobile.data.DocxHeadingAudit
import dev.ninfenz.mobile.data.DocxStyleAudit
import dev.ninfenz.mobile.data.StyleTemplateStore
import dev.ninfenz.mobile.model.FidelityReconciler
import dev.ninfenz.mobile.model.MarkdownBlocks
import dev.ninfenz.mobile.model.PlanModel
import dev.ninfenz.mobile.model.ProjectStatus
import dev.ninfenz.mobile.ui.safeCall
import java.io.File
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

internal fun DeliveryUiState.exportPayload(md: String, dir: File, format: String): JsonObject = buildJsonObject {
    put("markdown", md)
    put("format", format)
    put("out_dir", dir.absolutePath)
    put("manifest", true)
    put("title", project.title)
    put("project_id", project.id)
    if (format == "docx") {
        docxStyles?.let { put("docx_styles", it) }
        docxSectPr?.let { put("docx_sect_pr", it) }
        docxTheme?.let { put("docx_theme", it) }
        docxNumbering?.let { put("docx_numbering", it) }
        docxHeader?.let { put("docx_header", it) }
        docxFooter?.let { put("docx_footer", it) }
    }
}

internal suspend fun DeliveryUiState.exportViaCore(md: String, dir: File, format: String, failures: MutableList<String>, fallbackName: String): File? =
    runCatching {
        val response = safeCall("export", exportPayload(md, dir, format))
        if (!response.ok) throw IllegalStateException(response.error?.message ?: "export failed")
        val raw = response.resultObject()?.get("files")?.toString().orEmpty()
        val name = Regex("\"name\":\"([^\"]+)\"").find(raw)?.groupValues?.getOrNull(1) ?: fallbackName
        File(dir, name)
    }.onFailure { failures += format + ":" + (it.message ?: it.javaClass.simpleName) }.orNullLogged("DeliveryScreen")

internal suspend fun DeliveryUiState.exportPreservation(md: String, dir: File, failures: MutableList<String>): File? {
    if (!audit) return null
    return runCatching {
        val lineage = dev.ninfenz.mobile.data.PreservationLineageStore(context.filesDir)
        val created = dev.ninfenz.mobile.data.PreservationExporter.export(
            md, project.title, project.id, dir,
            dev.ninfenz.mobile.data.PreservationOptions(
                dev.ninfenz.mobile.data.ContractStore(context.filesDir).raw(project.id),
                grant.toJson().toString(),
                lineage.load(project.id)
            )
        )
        val reproDir = File(context.cacheDir, "repro-preserve-batch").apply { deleteRecursively(); mkdirs() }
        val second = dev.ninfenz.mobile.data.PreservationExporter.export(
            md, project.title, project.id, reproDir,
            dev.ninfenz.mobile.data.PreservationOptions(
                dev.ninfenz.mobile.data.ContractStore(context.filesDir).raw(project.id),
                grant.toJson().toString(),
                lineage.load(project.id)
            )
        )
        val reproReport = dev.ninfenz.mobile.data.ReproChecker.check(created.file, second.file)
        reproDir.deleteRecursively()
        if (!reproReport.stable) throw IllegalStateException("repro diff " + (reproReport.firstDiff ?: -1))
        val digest = java.security.MessageDigest.getInstance("SHA-256")
            .digest(created.file.readBytes())
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }
        lineage.save(project.id, digest)
        created.file
    }.onFailure { failures += "preservation:" + (it.message ?: it.javaClass.simpleName) }.orNullLogged("DeliveryScreen")
}

internal fun DeliveryUiState.attemptExport(failures: MutableList<String>, label: String, block: () -> File): File? =
    try {
        block()
    } catch (t: Throwable) {
        failures += label + ":" + (t.message ?: t.javaClass.simpleName)
        null
    }


internal suspend fun DeliveryUiState.runExportAll(md: String) {
    try {
        val dir = File(File(context.filesDir, "exports/delivery"), "batch-" + System.currentTimeMillis()).apply { mkdirs() }
        val failures = mutableListOf<String>()
        val docxFile = exportViaCore(md, dir, "docx", failures, "result.docx")
        val zipFile = exportViaCore(md, dir, "zip", failures, "result.zip")
        val skillFile = exportViaCore(md, dir, "skill", failures, "result-skill.zip")
        val preserveFile = exportPreservation(md, dir, failures)
        val files = buildList {
            add(File(dir, "result.md").apply { writeText(md, Charsets.UTF_8) })
            docxFile?.let { add(it) }
            zipFile?.let { add(it) }
            skillFile?.let { add(it) }
            preserveFile?.let { add(it) }
            attemptExport(failures, "epub") { dev.ninfenz.mobile.data.EpubExporter.export(md, project.title, dir, epubAuthor, epubLanguage, dev.ninfenz.mobile.data.OutputNaming.resolve(selectedOutputTemplate, project.title, "epub")).file }?.let { add(it) }
            attemptExport(failures, "html") { dev.ninfenz.mobile.data.HtmlExporter.export(md, project.title, dir, dev.ninfenz.mobile.data.OutputNaming.resolve(selectedOutputTemplate, project.title, "html")).file }?.let { add(it) }
            attemptExport(failures, "pdf") { dev.ninfenz.mobile.data.PdfExporter.export(md, project.title, dir, pdfPageSize, pdfIncludeTitle, dev.ninfenz.mobile.data.OutputNaming.resolve(selectedOutputTemplate, project.title, "pdf")).file }?.let { add(it) }
            attemptExport(failures, "nfdoc") { dev.ninfenz.mobile.data.NfDocExporter.export(md, project.title, project.id, dir).file }?.let { add(it) }
        }
        afterExportAll(files, failures, md)
    } catch (t: Throwable) {
        error = CoreError("NF-EXP-002", context.getString(dev.ninfenz.mobile.R.string.export_pdf_failed, t.message ?: t.javaClass.simpleName), context.getString(dev.ninfenz.mobile.R.string.export_failed_fix), null, 1)
    } finally {
        busy = false
    }
}

internal fun DeliveryUiState.startExportAll(md: String) {
    busy = true
    error = null
    batchFiles = emptyList()
    exportBatchNote = null
    scope.launch { runExportAll(md) }
}

internal fun DeliveryUiState.handleExportDone(format: String, file: File?, manifest: String?, report: dev.ninfenz.mobile.data.ReproChecker.Report?, exportMarkdown: String?) {
    exportedFile = file
    val manifestDirect = format in setOf("epub", "pdf", "html", "preserve", "nf-doc", "pdf-ua")
    if (format == "pdf-ua") {
        manifestText = null
        reproOk = report?.stable
        reproText = context.getString(dev.ninfenz.mobile.R.string.delivery_pdfua_note)
    } else if (manifestDirect) {
        manifestText = null
        reproOk = report?.stable
        reproText = report?.let { reproTextStable(it, context) }
    } else {
        manifestText = manifest
        reproOk = report?.stable
        reproText = reproTextFor(report, context)
    }
    recordExport(format, file, if (manifestDirect) null else manifest)
    if (format == "docx") {
        file?.let { exported ->
            docxStyles?.let { applied -> docxStyleAudit = DocxStyleAudit.check(applied, exported) }
            docxHeadingAudit = DocxHeadingAudit.check(exportMarkdown.orEmpty(), exported)
        }
    }
    if (format == "md") {
        scope.launch { advanceStatus(ProjectStatus.EXPORTED, allowAuditSkip = !audit) }
    }
}

internal fun DeliveryUiState.openStyleTemplates() {
    styleTemplates = styleStore.list()
    showStyleTemplates = true
}

internal fun DeliveryUiState.pickStyleTemplate(template: StyleTemplateStore.StyleTemplate) {
    if (!template.sourceFormat.equals("docx", ignoreCase = true)) return
    docxStyles = template.stylesXml
    docxSectPr = template.sectPr.takeIf { it.isNotBlank() }
    docxTheme = template.themeXml.takeIf { it.isNotBlank() }
    docxNumbering = template.numberingXml.takeIf { it.isNotBlank() }
    showStyleTemplates = false
}

internal fun DeliveryUiState.packEvidence(latest: ExportHistoryStore.Entry) {
    val md = markdown ?: return
    evidenceBusy = true
    evidenceNote = null
    scope.launch {
        val result = dev.ninfenz.mobile.data.HardTechEvidence.pack(context, md, File(latest.path))
        evidenceNote = result.message
        evidenceBusy = false
    }
}

internal fun DeliveryUiState.openPreviewEditor(md: String) {
    val parsed = MarkdownBlocks.parse(md)
    previewBlocks = parsed
    previewBaseline = parsed
    previewHistory = emptyList()
    previewRedo = emptyList()
    previewDirty = false
    editingPreview = true
}

internal suspend fun DeliveryUiState.compilePlan(art: AuthorArtifacts) {
    busy = true
    error = null
    val response = safeCall("graph-compile", buildJsonObject {
        put("graph", art.graphJson)
        put("spec", art.specJson)
    })
    val obj = response.resultObject()
    if (response.ok && obj != null) {
        try {
            val parsed = PlanModel.parse(obj)
            plan = parsed
            rawPlan = obj
            inputs = parsed.slots.associate { slot ->
                val restored = restoredInputs[slot]
                slot to (if (!restored.isNullOrBlank()) restored else contractValues[slot] ?: slotPrefill[slot] ?: "")
            }
            draftStore.save(project.id, inputs, obj)
            draftNote = if (restoredInputs.isNotEmpty()) context.getString(dev.ninfenz.mobile.R.string.delivery_draft_restored) else null
            markdown = null
            report = null
            needsRevalidate = false
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
