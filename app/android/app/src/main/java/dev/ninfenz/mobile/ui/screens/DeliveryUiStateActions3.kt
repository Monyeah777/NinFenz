package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.util.orNullLogged
import kotlinx.coroutines.delay
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.UriIo
import dev.ninfenz.mobile.data.AuthorArtifactsLoader
import dev.ninfenz.mobile.data.ExtensionStore
import dev.ninfenz.mobile.data.ExportProfileStore
import dev.ninfenz.mobile.data.DocxReferenceStyles
import dev.ninfenz.mobile.data.EpubExporter
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.data.HtmlExporter
import dev.ninfenz.mobile.data.PdfExporter
import dev.ninfenz.mobile.data.MacroStore
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.model.MacroBatchResult
import dev.ninfenz.mobile.model.MacroRunResult
import dev.ninfenz.mobile.model.MacroRunner
import dev.ninfenz.mobile.model.PlanModel
import dev.ninfenz.mobile.model.SlotBatchImporter
import dev.ninfenz.mobile.model.SlotTextAdapter
import dev.ninfenz.mobile.ui.safeCall
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

internal fun DeliveryUiState.applyExportProfile(profile: dev.ninfenz.mobile.data.ExportProfileStore.Profile) {
    docxStyles = profile.styles
    docxSectPr = profile.sectPr
    docxTheme = profile.theme
    docxNumbering = profile.numbering
    docxHeader = profile.header
    docxFooter = profile.footer
    profile.epubAuthor?.let { epubAuthor = it }
    profile.epubLanguage?.let { epubLanguage = it }
    profile.pdfPageSize?.let { pdfPageSize = it }
    profile.pdfIncludeTitle?.let { pdfIncludeTitle = it }
    showExportProfiles = false
}

internal fun DeliveryUiState.removeExportProfile(profile: dev.ninfenz.mobile.data.ExportProfileStore.Profile) {
    exportProfileStore.remove(profile.id)
    exportProfiles = exportProfileStore.load()
}

internal fun DeliveryUiState.assembleAllVariants() {
    val raw = rawPlan ?: return
    val specJson = artifacts?.specJson ?: return
    busy = true
    scope.launch {
        var ok = 0
        var failed = 0
        for (variant in extensionVariants) {
            val variantInputs = inputs.toMutableMap()
            (variant.config["inputs"] as? JsonObject)?.forEach { (key, value) ->
                if (plan?.slots?.contains(key) == true) variantInputs[key] = value.jsonPrimitive.content
            }
            val response = runCatching {
                safeCall("assemble", buildJsonObject {
                    put("plan", raw)
                    put("spec", specJson)
                    put("inputs", buildJsonObject { for ((k, v) in variantInputs) put(k, v) })
                })
            }.orNullLogged("DeliveryScreen")
            val md = response?.resultObject()?.let { J.optString(it, "markdown") }
            if (response?.ok == true && !md.isNullOrBlank()) {
                versionStore.save(project.id, md)
                ok++
            } else {
                failed++
            }
        }
        variantNote = context.getString(dev.ninfenz.mobile.R.string.delivery_batch_assemble_done, ok, failed)
        busy = false
    }
}

internal fun DeliveryUiState.exportVariantFormats(md: String, outDir: File, safe: String, variantId: String): Int {
    var missing = 0
    runCatching {
        dev.ninfenz.mobile.data.HtmlExporter.export(md, project.title, outDir, safe + ".html")
    }.onFailure { missing++ }
    runCatching {
        dev.ninfenz.mobile.data.EpubExporter.export(
            md, project.title, outDir, epubAuthor, epubLanguage, safe + ".epub"
        )
    }.onFailure { missing++ }
    runCatching {
        dev.ninfenz.mobile.data.PdfExporter.export(
            md, project.title, outDir, pdfPageSize, pdfIncludeTitle, safe + ".pdf"
        )
    }.onFailure { missing++ }
    runCatching {
        val doc = dev.ninfenz.mobile.model.NfDocModel.fromMarkdown(
            project.title + " · " + variantId,
            project.id + "/" + variantId,
            md
        )
        File(outDir, safe + ".nfdoc.json").writeText(
            dev.ninfenz.mobile.model.NfDocModel.toJson(doc).toString() + "\n",
            Charsets.UTF_8
        )
    }.onFailure { missing++ }
    return missing
}

internal fun DeliveryUiState.exportAllVariants() {
    val raw = rawPlan ?: return
    val specJson = artifacts?.specJson ?: return
    busy = true
    scope.launch {
        val outDir = File(File(context.filesDir, "exports"), "variants").apply { mkdirs() }
        var ok = 0
        var failed = 0
        var missingFormats = 0
        for (variant in extensionVariants) {
            val variantInputs = inputs.toMutableMap()
            (variant.config["inputs"] as? JsonObject)?.forEach { (key, value) ->
                if (plan?.slots?.contains(key) == true) variantInputs[key] = value.jsonPrimitive.content
            }
            val response = runCatching {
                safeCall("assemble", buildJsonObject {
                    put("plan", raw)
                    put("spec", specJson)
                    put("inputs", buildJsonObject { for ((k, v) in variantInputs) put(k, v) })
                })
            }.orNullLogged("DeliveryScreen")
            val md = response?.resultObject()?.let { J.optString(it, "markdown") }
            if (response?.ok == true && !md.isNullOrBlank()) {
                val safe = variant.id.replace(Regex("[^A-Za-z0-9._-]"), "_")
                File(outDir, safe + ".md").writeText(md, Charsets.UTF_8)
                missingFormats += exportVariantFormats(md, outDir, safe, variant.id)
                ok++
            } else {
                failed++
            }
        }
        val suffix = if (missingFormats > 0) {
            context.getString(dev.ninfenz.mobile.R.string.delivery_batch_export_partial, missingFormats)
        } else ""
        variantNote = context.getString(dev.ninfenz.mobile.R.string.delivery_batch_export_done, ok, failed) + suffix
        busy = false
    }
}

internal fun DeliveryUiState.applyVariant(variant: dev.ninfenz.mobile.data.ExtensionStore.Contribution) {
    val objectInputs = variant.config["inputs"] as? JsonObject
    val before = inputs
    val next = inputs.toMutableMap()
    var applied = 0
    var skipped = 0
    objectInputs?.forEach { (key, value) ->
        val text = value.jsonPrimitive.content
        if (plan?.slots?.contains(key) == true) {
            next[key] = text
            applied++
        } else {
            skipped++
        }
    }
    if (applied > 0) {
        batchUndo = before
        inputs = next
        variantNote = context.getString(dev.ninfenz.mobile.R.string.delivery_variant_applied, variant.id) +
            if (skipped > 0) " · skipped=" + skipped else ""
        showVariants = false
    }
}

internal fun DeliveryUiState.macroExecutor(): DeliveryMacroExecutor = DeliveryMacroExecutor(
    context = context,
    projectId = project.id,
    spec = artifacts?.specJson,
    plan = rawPlan,
    inputs = inputs,
    markdownProvider = { markdown },
    onMarkdown = { next ->
        markdown = next
        needsRevalidate = true
    }
)

internal suspend fun DeliveryUiState.executeMacro(macro: MacroStore.Macro, values: Map<String, String>) {
    val bound = MacroRunner.bind(macro.json, values)
    val plan = MacroStore(context.filesDir).plan(bound).orNullLogged("DeliveryScreen")
    macroBatchResult = null
    macroResult = if (plan == null) {
        MacroRunResult("failed", emptyList(), 1)
    } else {
        val executor = macroExecutor()
        MacroRunner.run(plan) { action, params -> executor.run(action, params) }
    }
}

internal suspend fun DeliveryUiState.executeMacroBatch() {
    val plans = macroItems.mapNotNull { macro -> MacroStore(context.filesDir).plan(macro.json).orNullLogged("DeliveryScreen") }
    macroResult = null
    macroBatchResult = if (plans.isEmpty()) {
        MacroBatchResult("failed", emptyList(), 1)
    } else {
        val executor = macroExecutor()
        MacroRunner.runBatch(plans) { action, params -> executor.run(action, params) }
    }
}

internal fun DeliveryUiState.bulkApply(text: String): String = when (bulkMode) {
    "replace" -> text.replace(bulkFrom, bulkTo)
    "prefix" -> bulkFrom + text
    "suffix" -> text + bulkFrom
    "truncate" -> text.take(bulkFrom.toIntOrNull() ?: text.length)
    else -> text
}

internal fun DeliveryUiState.onReferencePicked(uri: android.net.Uri?) {
        if (uri != null) {
            scope.launch {
                val file = runCatching { FileAccess.copyToCache(context, uri, "reference.docx") }.orNullLogged("DeliveryScreen")
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


internal fun DeliveryUiState.onSlotPicked(uri: android.net.Uri?) {
        if (uri == null) { slotImportTarget = null; return }
        val target = slotImportTarget ?: return
        scope.launch {
            try {
                val name = uri.lastPathSegment?.substringAfterLast('/') ?: "import"
                val raw = withContext(Dispatchers.IO) { UriIo.readText(context, uri) ?: "" }
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


internal fun DeliveryUiState.onBatchPicked(uri: android.net.Uri?) {
        if (uri == null) return
        scope.launch {
            try {
                val name = uri.lastPathSegment?.substringAfterLast('/') ?: "batch"
                val raw = withContext(Dispatchers.IO) {
                    UriIo.readTextLimited(context, uri, MAX_IMPORT_CHARS, context.getString(dev.ninfenz.mobile.R.string.delivery_slot_import_too_large))
                }
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


internal suspend fun DeliveryUiState.effectSaveDraft() {
        if (plan != null) {
            delay(500)
            withContext(Dispatchers.IO) { draftStore.save(project.id, inputs, rawPlan, markdown) }
        }
    
}


internal suspend fun DeliveryUiState.effectRestorePlan() {
        val raw = restoredPlan ?: return
        runCatching { PlanModel.parse(raw) }.onSuccess { parsed ->
            rawPlan = raw
            plan = parsed
            inputs = parsed.slots.associate { slot ->
                val restored = restoredInputs[slot]
                slot to (if (!restored.isNullOrBlank()) restored else contractValues[slot] ?: slotPrefill[slot] ?: "")
            }
        }
    
}


internal suspend fun DeliveryUiState.effectLoadArtifacts(pack: PackEntry?) {
    val specOverride = dev.ninfenz.mobile.data.ProjectPaths.specOverride(context.filesDir, project.id)
        loading = true
        loadError = null
        try {
            if (pack != null) artifacts = withContext(Dispatchers.IO) { AuthorArtifactsLoader.load(pack, specOverride) }
        } catch (t: Throwable) {
            loadError = t.message ?: t.javaClass.simpleName
        }
        loading = false
    
}


internal fun DeliveryUiState.handleBack() {
        when {
            activeStep > 0 -> activeStep = if (!audit && activeStep == 3) 1 else activeStep - 1
            hasWork -> showLeaveConfirm = true
            else -> onBack()
        }
    
}
