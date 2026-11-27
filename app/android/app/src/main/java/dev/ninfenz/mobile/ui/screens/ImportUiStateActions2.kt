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

internal suspend fun ImportUiState.effect3() {

        val seed = dev.ninfenz.mobile.ui.ImportSeed.consume()
        if (seed != null) {
            importText(seed, ImportSource.CLIPBOARD, "daily-paste.md")
            return
        }
        if (doc == null && rawResult == null && error == null) {
            val raw = withContext(Dispatchers.IO) { importDraftStore.load() }
            if (raw != null) {
                try {
                    val obj = J.parseObject(raw, ImportModel.SCHEMA)
                    val restored = ImportModel.parse(obj)
                    rawResult = obj
                    doc = restored
                    acceptedMappings = restored.mappings.indices.filter { restored.mappings[it].confidence >= mappingThreshold }.toSet()
                    val digest = restored.source.sha256 ?: restored.textDigest.orEmpty()
                    zeroSliceStore.load(digest)?.let { report ->
                        zeroSlice = report
                        acceptedMappings = acceptedMappings + restored.mappings.indices.filter { i ->
                            report.mappings.any { it.toId == restored.mappings[i].toId && it.confidence >= 60 }
                        }.toSet()
                    }
                    notice = context.getString(dev.ninfenz.mobile.R.string.import_restored_notice)
                } catch (t: Throwable) {
                    importDraftStore.clear()
                }
            }
        }
    
}

internal suspend fun ImportUiState.effect4() {

        if (doc != null && zeroSlice == null && packs.isNotEmpty()) runZeroSlice()
    
}

internal suspend fun ImportUiState.effect5() {

        if (autoClipboard) {
            importClipboard()
            onAutoClipboardConsumed()
        }
    
}

internal fun ImportUiState.importSample() {

        scope.launch {
            try {
                val text = context.assets.open("sample-pack/docs/sample.md").bufferedReader(Charsets.UTF_8).use { it.readText() }
                val file = File(File(context.cacheDir, "imports").apply { mkdirs() }, "sample.md")
                file.writeText(text, Charsets.UTF_8)
                importFromFile(file, ImportSource.FILE, "sample.md", "text/markdown", text.toByteArray(Charsets.UTF_8).size.toLong())
            } catch (t: Throwable) {
                error = CoreResponse.failure("NF-E-004", context.getString(dev.ninfenz.mobile.R.string.import_sample_read_failed, t.message ?: t.javaClass.simpleName), context.getString(dev.ninfenz.mobile.R.string.import_sample_read_failed_fix), 2).error
            }
        }
    
}

internal fun ImportUiState.importSharedItem(item: SharedItem) {

        scope.launch {
            if (item.text != null) {
                val file = File(File(context.cacheDir, "imports").apply { mkdirs() }, "shared-text.md")
                file.writeText(item.text, Charsets.UTF_8)
                importFromFile(file, ImportSource.SHARE, "shared-text.md", item.mime ?: "text/plain", item.text.toByteArray(Charsets.UTF_8).size.toLong())
            } else if (item.uri != null) {
                try {
                    val uri = item.uri.toUri()
                    val meta = FileAccess.meta(context, uri)
                    val name = meta.name.orEmpty().lowercase()
                    if (meta.size > FileAccess.MAX_IMPORT_BYTES) {
                        error = CoreResponse.failure("NF-IMP-003", context.getString(dev.ninfenz.mobile.R.string.import_file_too_large), context.getString(dev.ninfenz.mobile.R.string.import_file_too_large_fix), 3).error
                        return@launch
                    }
                    val file = FileAccess.copyToCache(context, uri, meta.name)
                    importFromFile(file, ImportSource.SHARE, meta.name, meta.mime ?: item.mime, meta.size)
                } catch (e: Exception) {
                    error = if (e is SecurityException) {
                        CoreResponse.failure(
                            "NF-IMP-006",
                            context.getString(dev.ninfenz.mobile.R.string.import_share_permission_lost),
                            context.getString(dev.ninfenz.mobile.R.string.import_share_permission_lost_fix),
                            2
                        ).error
                    } else {
                        CoreResponse.failure(
                            "NF-E-004",
                            context.getString(dev.ninfenz.mobile.R.string.import_share_uri_failed, e.message ?: e.javaClass.simpleName),
                            context.getString(dev.ninfenz.mobile.R.string.import_share_uri_failed_fix),
                            2
                        ).error
                    }
                }
            }
        }
    
}

internal fun ImportUiState.importShare(payload: SharePayload) {

        shareQueue = payload.items
        shareCursor = 0
        val item = payload.items.firstOrNull()
        if (item == null) {
            error = CoreResponse.failure("NF-IMP-001", context.getString(dev.ninfenz.mobile.R.string.import_share_empty), context.getString(dev.ninfenz.mobile.R.string.import_share_empty_fix), 3).error
            return
        }
        importSharedItem(item)
    
}

internal fun ImportUiState.importNextSharedItem() {

        val next = shareCursor + 1
        if (next >= shareQueue.size) return
        shareCursor = next
        importSharedItem(shareQueue[next])
    
}

internal fun ImportUiState.onTemplatePickerPicked(uri: Uri?) {

        if (uri == null) return
        scope.launch {
            try {
                val file = FileAccess.copyToCache(context, uri, "candidate.json")
                val raw = file.readText(Charsets.UTF_8)
                val spec = kotlinx.serialization.json.Json.parseToJsonElement(raw).jsonObject
                val response = safeCall("spec-validate", buildJsonObject { put("spec", spec) })
                if (response.ok) {
                    val saved = templateStore.save(spec)
                    savedTemplates = templateStore.list()
                    notice = context.getString(dev.ninfenz.mobile.R.string.import_template_saved, templateStore.titleOf(saved))
                } else {
                    error = response.error
                }
                file.delete()
            } catch (t: Throwable) {
                error = CoreResponse.failure(
                    "NF-SPC-001",
                    context.getString(dev.ninfenz.mobile.R.string.import_template_import) + ": " + (t.message ?: t.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.import_parse_failed_fix),
                    2
                ).error
            }
        }
    
}

internal suspend fun ImportUiState.effect6() {

        if (prefill != null) {
            prefillNote = context.getString(dev.ninfenz.mobile.R.string.import_share_from, prefill!!.summary())
            importShare(prefill!!)
            onPrefillConsumed()
        }
    
}

internal fun ImportUiState.handlePreserve(file: File) {

        val result = dev.ninfenz.mobile.data.PreservationVerifier.verify(file)
        if (result.ok && result.grant?.allows(dev.ninfenz.mobile.data.CapabilityGrant.READ, System.currentTimeMillis()) == true) {
            preserveNote = context.getString(dev.ninfenz.mobile.R.string.import_preserve_ok, result.title ?: file.name)
            preservedMarkdown = dev.ninfenz.mobile.data.PreservationVerifier.extractMarkdown(file)
            preserveGrant = result.grant
            preservedName = (result.title ?: "restored").replace(Regex("[^A-Za-z0-9._-]"), "_") + ".md"
        } else if (result.ok) {
            preserveNote = context.getString(dev.ninfenz.mobile.R.string.import_preserve_no_read)
            preservedMarkdown = null
            preserveGrant = null
        } else {
            preserveNote = context.getString(dev.ninfenz.mobile.R.string.import_preserve_fail, result.errors.take(2).joinToString("; "))
            preservedMarkdown = null
            preserveGrant = null
        }
    
}

internal fun ImportUiState.onPreservePickerPicked(uri: Uri?) {

        if (uri == null) return
        scope.launch {
            try {
                val file = FileAccess.copyToCache(context, uri, "preserve.zip")
                handlePreserve(file)
                file.delete()
            } catch (t: Throwable) {
                preserveNote = context.getString(dev.ninfenz.mobile.R.string.import_preserve_fail, t.message ?: t.javaClass.simpleName)
            }
        }
    
}

internal fun ImportUiState.onCsvPickerPicked(uri: Uri?) {

        if (uri == null) return
        scope.launch {
            try {
                val meta = FileAccess.meta(context, uri)
                if (meta.size > FileAccess.MAX_IMPORT_BYTES) {
                    error = CoreResponse.failure("NF-IMP-003", context.getString(dev.ninfenz.mobile.R.string.import_file_too_large), context.getString(dev.ninfenz.mobile.R.string.import_file_too_large_fix), 3).error
                    return@launch
                }
                val text = FileAccess.readText(context, uri)
                val file = File(File(context.cacheDir, "imports").apply { mkdirs() }, "csv-table.md")
                file.writeText(CsvTable.toMarkdown(text), Charsets.UTF_8)
                importFromFile(file, ImportSource.SAF, meta.name, meta.mime ?: "text/csv", text.toByteArray(Charsets.UTF_8).size.toLong())
            } catch (t: Throwable) {
                error = CoreResponse.failure("NF-E-004", context.getString(dev.ninfenz.mobile.R.string.import_read_failed, t.message ?: t.javaClass.simpleName), context.getString(dev.ninfenz.mobile.R.string.import_reselect_file), 3).error
            }
        }
    
}

internal fun ImportUiState.onFilePickerPicked(uri: Uri?) {

        if (uri != null) {
            scope.launch {
                try {
                    val meta = FileAccess.meta(context, uri)
                    if (meta.size > FileAccess.MAX_IMPORT_BYTES) {
                        error = CoreResponse.failure("NF-IMP-003", context.getString(dev.ninfenz.mobile.R.string.import_file_too_large), context.getString(dev.ninfenz.mobile.R.string.import_file_too_large_fix), 3).error
                        return@launch
                    }
                    val file = FileAccess.copyToCache(context, uri, meta.name)
                    importFromFile(file, ImportSource.SAF, meta.name, meta.mime, meta.size)
                } catch (e: Exception) {
                    error = CoreResponse.failure(
                        "NF-E-004",
                        context.getString(dev.ninfenz.mobile.R.string.import_read_failed, e.message ?: e.javaClass.simpleName),
                        context.getString(dev.ninfenz.mobile.R.string.import_read_failed_fix),
                        2
                    ).error
                }
            }
        }
    
}

