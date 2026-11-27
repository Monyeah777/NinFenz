package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.util.orNullLogged
import dev.ninfenz.mobile.data.ImportSource

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.net.toUri
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.DraftLibrary
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.DocxImporter
import dev.ninfenz.mobile.data.EpubImporter
import dev.ninfenz.mobile.data.HtmlImporter
import dev.ninfenz.mobile.data.ProjectPackageImporter
import dev.ninfenz.mobile.data.TextEncoding
import dev.ninfenz.mobile.data.ShareQueueStore
import dev.ninfenz.mobile.data.ExtensionStore
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.data.ImportDraftStore
import dev.ninfenz.mobile.data.ZeroSliceReport
import dev.ninfenz.mobile.data.ZeroSliceStore
import dev.ninfenz.mobile.data.ImportHistoryStore
import dev.ninfenz.mobile.data.PromptSampleStore
import dev.ninfenz.mobile.data.TemplateCandidateStore
import dev.ninfenz.mobile.data.TemplatePackageBuilder
import dev.ninfenz.mobile.data.TemplatePackageImporter
import dev.ninfenz.mobile.data.LibraryStore
import dev.ninfenz.mobile.model.FidelityReport
import dev.ninfenz.mobile.model.ImportBatchState
import dev.ninfenz.mobile.model.ImportBatchStatus
import dev.ninfenz.mobile.model.ImportDoc
import dev.ninfenz.mobile.model.MarkdownBlocks
import dev.ninfenz.mobile.model.MarkdownSlicer
import dev.ninfenz.mobile.model.PromptPack
import dev.ninfenz.mobile.model.PromptProfile
import dev.ninfenz.mobile.model.SpecModel
import dev.ninfenz.mobile.model.TemplateCandidate
import dev.ninfenz.mobile.model.CsvTable
import dev.ninfenz.mobile.model.ImportModel
import dev.ninfenz.mobile.share.SharePayload
import dev.ninfenz.mobile.share.ShareExporter
import dev.ninfenz.mobile.share.SharedItem
import dev.ninfenz.mobile.ui.components.NfActionBarSurface
import dev.ninfenz.mobile.ui.components.NfCard
import dev.ninfenz.mobile.ui.components.NfEmptyState
import dev.ninfenz.mobile.ui.components.NfErrorCard
import dev.ninfenz.mobile.ui.components.MarkdownPreview
import dev.ninfenz.mobile.ui.components.NfStepStrip
import dev.ninfenz.mobile.ui.components.NfSectionHeader
import dev.ninfenz.mobile.ui.components.NfStatusChip
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.foundation.ExperimentalFoundationApi

internal suspend fun ImportUiState.effect1() {

        if (shareQueue.isEmpty()) shareQueueStore.clear() else shareQueueStore.save(shareQueue, shareCursor)
    
}

internal suspend fun ImportUiState.effect2() {

        if (cleared != null) {
            clearSeconds = 5
            while (clearSeconds > 0 && cleared != null) {
                delay(1000)
                clearSeconds -= 1
            }
            if (cleared != null) cleared = null
        }
    
}

internal fun ImportUiState.clearCurrentImport() {

        cleared = ImportClearSnapshot(
            doc = doc,
            rawResult = rawResult,
            savedName = savedName,
            acceptedMappings = acceptedMappings,
            prefillNote = prefillNote,
            notice = notice,
            suggestNote = suggestNote,
            shareQueue = shareQueue,
            shareCursor = shareCursor
        )
        doc = null
        rawResult = null
        savedName = null
        acceptedMappings = emptySet()
        prefillNote = null
        notice = null
        suggestNote = null
        error = null
        importDraftStore.clear()
        shareQueue = emptyList()
        shareCursor = 0
        showClearConfirm = false
    
}

internal suspend fun ImportUiState.importFromFile(file: File, sourceKind: String, name: String, mime: String?, size: Long) {

        zeroSlice = null
        zeroSliceNote = null
        zeroSliceStore.clear()
        val isZip = file.name.endsWith(".zip", ignoreCase = true) || (mime ?: "").contains("zip", ignoreCase = true)
        if (importProjectBundleIfPresent(context, file, isZip,
                onBusy = { busy = it }, onError = { error = it }, onNotice = { notice = it },
                onBundleImported = onBundleImported)) {
            return
        }
        if (importTemplatePackageIfPresent(context, file, isZip, packs,
                onBusy = { busy = it }, onError = { error = it }, onNotice = { notice = it },
                onCreateProjectFromTemplate = onCreateProjectFromTemplate)) {
            return
        }
        if (importProjectPackageIfPresent(context, file, isZip,
                onError = { error = it }, onNotice = { notice = it }, onProjectImported = onProjectImported)) {
            return
        }
        busy = true
        error = null
        notice = null
        doc = null
        rawResult = null
        savedName = null
        suggestNote = null
        acceptedMappings = emptySet()
        val kind = classifyImport(name, mime, file)
        val sourceFile = prepareImportSource(context, file, name, mime, kind,
            onError = { error = it }, onNotice = { notice = it }) ?: return
        val response = callCoreImport(sourceFile, sourceKind, name, mime, size)
        applyImportResponse(context, response, mappingThreshold, importHistory,
            onError = { error = it }, onDoc = { doc = it }, onRawResult = { rawResult = it },
            onAcceptedMappings = { acceptedMappings = it }, onNotice = { notice = it },
            onDuplicatePrompt = { duplicatePrompt = it }, onSuggestNote = { suggestNote = it },
            onRecentImports = { recentImports = it })
        rawResult?.let { importDraftStore.save(it.toString()) }
        if (sourceFile != file) sourceFile.delete()
        busy = false
    
}

internal fun ImportUiState.exportTemplatePackage(file: File) {

        val pack = packs.firstOrNull()
        if (pack == null) {
            error = CoreResponse.failure(
                "NF-PCK-002",
                context.getString(dev.ninfenz.mobile.R.string.import_template_export),
                context.getString(dev.ninfenz.mobile.R.string.import_template_export),
                2
            ).error
            return
        }
        val spec = runCatching {
            kotlinx.serialization.json.Json.parseToJsonElement(file.readText(Charsets.UTF_8)).jsonObject
        }.orNullLogged("ImportScreen")
        if (spec == null) return
        scope.launch {
            busy = true
            try {
                val prepared = TemplatePackageBuilder.prepare(context.cacheDir, pack, spec, templateStore.titleOf(file))
                val response = safeCall("pack-hash", buildJsonObject { put("root", prepared.dir.absolutePath) })
                val hashes = response.resultObject()?.get("hashes") as? kotlinx.serialization.json.JsonObject
                val tree = hashes?.get("tree")?.jsonPrimitive?.content
                val count = hashes?.get("count")?.jsonPrimitive?.content?.toIntOrNull()
                if (!response.ok || tree == null || count == null) {
                    error = response.error ?: CoreResponse.failure("NF-PCK-003", context.getString(dev.ninfenz.mobile.R.string.import_pack_hash_missing), context.getString(dev.ninfenz.mobile.R.string.import_pack_hash_missing_fix), 2).error
                } else {
                    val zip = TemplatePackageBuilder.finalize(prepared, tree, count, File(context.cacheDir, "template-export"))
                    val intent = ShareExporter.shareFileIntent(context, zip, "application/zip", templateStore.titleOf(file))
                    ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.import_template_export))
                }
            } catch (t: Throwable) {
                error = CoreResponse.failure(
                    "NF-E-005",
                    context.getString(dev.ninfenz.mobile.R.string.import_template_export) + ": " + (t.message ?: t.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.import_parse_failed_fix),
                    2
                ).error
            }
            busy = false
        }
    
}

internal fun ImportUiState.importCsv() {

        val manager = context.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as? android.content.ClipboardManager
        val text = manager?.primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(context)?.toString()
        if (text.isNullOrBlank()) {
            error = CoreResponse.failure(
                "NF-E-003",
                context.getString(dev.ninfenz.mobile.R.string.import_clipboard_empty),
                context.getString(dev.ninfenz.mobile.R.string.import_clipboard_empty_fix),
                2
            ).error
            return
        }
        val markdown = CsvTable.toMarkdown(text)
        scope.launch {
            if (text.toByteArray(Charsets.UTF_8).size > dev.ninfenz.mobile.data.FileAccess.MAX_IMPORT_BYTES) {
                error = CoreResponse.failure(
                    "NF-IMP-003",
                    context.getString(dev.ninfenz.mobile.R.string.import_file_too_large),
                    context.getString(dev.ninfenz.mobile.R.string.import_file_too_large_fix),
                    3
                ).error
                return@launch
            }
            val file = File(File(context.cacheDir, "imports").apply { mkdirs() }, "csv-table.md")
            file.writeText(markdown, Charsets.UTF_8)
            importFromFile(file, ImportSource.CLIPBOARD, "csv-table.md", "text/markdown", markdown.toByteArray(Charsets.UTF_8).size.toLong())
        }
    
}

internal fun ImportUiState.runZeroSlice() {

        val text = doc?.text
        if (text.isNullOrBlank()) {
            zeroSliceNote = context.getString(dev.ninfenz.mobile.R.string.import_zero_slice_failed, context.getString(dev.ninfenz.mobile.R.string.import_zero_slice_no_text))
            return
        }
        scope.launch {
            val pack = packs.firstOrNull()
            val spec = pack?.let { entry ->
                runCatching {
                    J.parseObject(dev.ninfenz.mobile.data.ProjectPaths.packSpec(entry.dir).readText(Charsets.UTF_8), "nf-md-spec/1")
                }.orNullLogged("ImportScreen")
            }
            val response = safeCall("zero-slice", buildJsonObject {
                put("text", text)
                spec?.let { put("spec", it) }
            })
            val obj = response.resultObject()
            if (response.ok && obj != null) {
                val parsedReport = dev.ninfenz.mobile.data.ZeroSliceModel.parse(obj)
                val currentDoc = doc
                val sections = currentDoc?.text?.let { MarkdownSlicer.slice(MarkdownBlocks.parse(it), sliceMinChars) } ?: emptyList()
                val computed = parsedReport.mappings.mapNotNull { mapping ->
                    sections.getOrNull(mapping.fromIndex)
                        ?.blocks?.joinToString("\n\n") { it.text }
                        ?.takeIf { it.isNotBlank() }
                        ?.let { mapping.toId to it }
                }.toMap()
                val report = parsedReport.copy(slotValues = parsedReport.projectSlots + computed)
                zeroSlice = report
                if (currentDoc != null) {
                    val digest = currentDoc.source.sha256 ?: currentDoc.textDigest.orEmpty()
                    if (digest.isNotBlank()) zeroSliceStore.save(digest, report)
                    val matched = currentDoc.mappings.indices.filter { i ->
                        report.mappings.any { it.toId == currentDoc.mappings[i].toId && it.confidence >= 60 }
                    }.toSet()
                    acceptedMappings = acceptedMappings + matched
                }
                zeroSliceNote = context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.import_zero_slice_note, report.exceptions.size, report.coverage, report.exceptions.size)
            } else {
                zeroSliceNote = context.getString(dev.ninfenz.mobile.R.string.import_zero_slice_failed, response.error?.message ?: "unknown")
            }
        }
    
}

internal fun ImportUiState.importText(text: String, sourceKind: String, name: String) {

        scope.launch {
            if (text.toByteArray(Charsets.UTF_8).size > dev.ninfenz.mobile.data.FileAccess.MAX_IMPORT_BYTES) {
                error = CoreResponse.failure(
                    "NF-IMP-003",
                    context.getString(dev.ninfenz.mobile.R.string.import_file_too_large),
                    context.getString(dev.ninfenz.mobile.R.string.import_file_too_large_fix),
                    3
                ).error
                return@launch
            }
            val dir = File(context.cacheDir, "imports").apply { mkdirs() }
            val file = File(dir, name)
            file.writeText(text, Charsets.UTF_8)
            importFromFile(file, sourceKind, name, "text/plain", text.toByteArray(Charsets.UTF_8).size.toLong())
        }
    
}

internal fun ImportUiState.importClipboard() {

        val manager = context.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as? android.content.ClipboardManager
        val text = manager?.primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(context)?.toString()
        if (text.isNullOrBlank()) {
            error = CoreResponse.failure(
                "NF-E-003",
                context.getString(dev.ninfenz.mobile.R.string.import_clipboard_empty),
                context.getString(dev.ninfenz.mobile.R.string.import_clipboard_empty_fix),
                2
            ).error
            return
        }
        importText(text, ImportSource.CLIPBOARD, "clipboard.md")
    
}

