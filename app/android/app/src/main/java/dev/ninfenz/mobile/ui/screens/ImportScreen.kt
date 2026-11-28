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

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ImportScreen(
    prefill: SharePayload?,
    store: LibraryStore,
    onBack: () -> Unit,
    onPrefillConsumed: () -> Unit = {},
    autoClipboard: Boolean = false,
    onAutoClipboardConsumed: () -> Unit = {},
    packs: List<PackEntry> = emptyList(),
    onCreateProjectFromDraft: (PackEntry, String, File) -> Unit = { _, _, _ -> },
    onQuickProjectFromDraft: (PackEntry, String, File) -> Unit = onCreateProjectFromDraft,
    onCreateProjectFromTemplate: (PackEntry, String, String, String) -> Unit = { _, _, _, _ -> },
    onProjectImported: (String, String, String) -> Unit = { _, _, _ -> },
    onBundleImported: (Int) -> Unit = {}
) {
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val scope = rememberCoroutineScope()
    val historyQueryState = rememberSaveable { mutableStateOf("") }
    val historyShowAllState = rememberSaveable { mutableStateOf(false) }
    val s = remember {
        ImportUiState(
            context = context, clipboard = clipboard, scope = scope,
            prefill = prefill,
            store = store,
            onBack = onBack,
            onPrefillConsumed = onPrefillConsumed,
            autoClipboard = autoClipboard,
            onAutoClipboardConsumed = onAutoClipboardConsumed,
            packs = packs,
            onCreateProjectFromDraft = onCreateProjectFromDraft,
            onQuickProjectFromDraft = onQuickProjectFromDraft,
            onCreateProjectFromTemplate = onCreateProjectFromTemplate,
            onProjectImported = onProjectImported,
            onBundleImported = onBundleImported,
            historyQueryState = historyQueryState, historyShowAllState = historyShowAllState
        )
    }
    s.prefill = prefill
    s.store = store
    s.onBack = onBack
    s.onPrefillConsumed = onPrefillConsumed
    s.autoClipboard = autoClipboard
    s.onAutoClipboardConsumed = onAutoClipboardConsumed
    s.packs = packs
    s.onCreateProjectFromDraft = onCreateProjectFromDraft
    s.onQuickProjectFromDraft = onQuickProjectFromDraft
    s.onCreateProjectFromTemplate = onCreateProjectFromTemplate
    s.onProjectImported = onProjectImported
    s.onBundleImported = onBundleImported
    val templatePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        s.onTemplatePickerPicked(uri)
    }
    s.launchTemplatePicker = { args -> templatePicker.launch(args) }
    val preservePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        s.onPreservePickerPicked(uri)
    }
    s.launchPreservePicker = { args -> preservePicker.launch(args) }
    val csvPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        s.onCsvPickerPicked(uri)
    }
    s.launchCsvPicker = { args -> csvPicker.launch(args) }
    val filePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        s.onFilePickerPicked(uri)
    }
    s.launchFilePicker = { args -> filePicker.launch(args) }
    val multiPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris: List<Uri> ->
        s.onMultiPickerPicked(uris)
    }
    s.launchMultiPicker = { args -> multiPicker.launch(args) }
    LaunchedEffect(s.shareQueue, s.shareCursor) { s.effect1() }
    LaunchedEffect(s.cleared) { s.effect2() }
    LaunchedEffect(Unit) { s.effect3() }
    LaunchedEffect(s.doc?.textDigest, s.packs.size) { s.effect4() }
    LaunchedEffect(s.autoClipboard) { s.effect5() }
    LaunchedEffect(s.prefill) { s.effect6() }
    ImportRootShell(s)
    ImportSection26(s)
    ImportSection27(s)
    ImportSection28(s)
    ImportSection29(s)
    ImportSection30(s)
    ImportSection31(s)
    ImportSection32(s)
    ImportSection33(s)
    ImportSection34(s)
    ImportSection35(s)
    ImportSection36(s)
    ImportSection37(s)
}

@Composable
internal fun ImportBatchPanel(
    state: ImportBatchState,
    onCancel: () -> Unit,
    onRetry: () -> Unit
) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)
    ) {
        Text(stringResource(dev.ninfenz.mobile.R.string.import_batch_title), style = NfType.sectionTitle)
        if (state.running || state.items.any { it.status == ImportBatchStatus.PENDING }) {
            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
        }
        Text(
            stringResource(
                dev.ninfenz.mobile.R.string.import_batch_progress,
                state.processed,
                state.total,
                state.success,
                state.failed
            ),
            style = NfType.meta,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        state.items.filter { it.status == ImportBatchStatus.FAILED }.take(5).forEach { item ->
            Text(
                stringResource(dev.ninfenz.mobile.R.string.import_batch_failed_item, item.name, item.error.orEmpty()),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.error
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
            if (state.running || state.items.any { it.status == ImportBatchStatus.PENDING }) {
                TextButton(onClick = onCancel) { Text(stringResource(dev.ninfenz.mobile.R.string.import_batch_cancel)) }
            }
            if (state.failed > 0) {
                TextButton(onClick = onRetry) { Text(stringResource(dev.ninfenz.mobile.R.string.import_batch_retry)) }
            }
        }
    }
}

internal data class ImportClearSnapshot(
    val doc: ImportDoc?,
    val rawResult: JsonObject?,
    val savedName: String?,
    val acceptedMappings: Set<Int>,
    val prefillNote: String?,
    val notice: String?,
    val suggestNote: String?,
    val shareQueue: List<SharedItem>,
    val shareCursor: Int
)

internal data class DuplicatePrompt(val digest: String, val draft: File?)

internal suspend fun prepareImportSource(
    context: android.content.Context,
    file: File,
    name: String,
    mime: String?,
    kind: ImportKind,
    onError: (CoreError?) -> Unit,
    onNotice: (String?) -> Unit
): File? {
    return when {
        kind.isCsv -> {
            val markdown = CsvTable.toMarkdown(TextEncoding.decodeText(file.readBytes()))
            File(file.parentFile, "csv-import-" + System.nanoTime() + ".md").apply { writeText(markdown, Charsets.UTF_8) }
        }
        kind.isImage -> imageImportSource(context, file, onError, onNotice) ?: return null
        kind.isPdf -> pdfImportSource(context, file, onError) ?: return null
        kind.isDocx -> docxImportSource(context, file, onError) ?: return null
        kind.isEpub -> epubImportSource(context, file, onError) ?: return null
        kind.isHtml -> {
            val raw = HtmlImporter.decode(file.readBytes())
            val markdown = HtmlImporter.toMarkdown(raw)
            File(file.parentFile, "html-import-" + System.nanoTime() + ".md").apply { writeText(markdown, Charsets.UTF_8) }
        }
        kind.isText -> TextEncoding.toUtf8(file) ?: file
        else -> file
    }
}

internal suspend fun imageImportSource(
    context: android.content.Context,
    file: File,
    onError: (CoreError?) -> Unit,
    onNotice: (String?) -> Unit
): File? {
    // MLKit 的 TextRecognizer 禁止在主线程调用（真机实测：Must not be called on the main application thread）
    val extraction = withContext(Dispatchers.IO) {
        runCatching { dev.ninfenz.mobile.data.ImageOcrImporter.extract(context, file) }
    }
    if (extraction.isFailure) {
        onError(CoreResponse.failure(
            "NF-IMP-004",
            context.getString(dev.ninfenz.mobile.R.string.import_image_ocr_failed, extraction.exceptionOrNull()?.message ?: "unknown"),
            context.getString(dev.ninfenz.mobile.R.string.import_image_ocr_required_fix),
            3
        ).error)
        return null
    }
    var markdown = extraction.orNullLogged("ImportScreen")?.takeIf { it.isNotBlank() }
    if (markdown == null) {
        val ocr = withContext(Dispatchers.IO) {
            runCatching { dev.ninfenz.mobile.data.PdfOcrImporter.extract(context, file) }
        }
        if (ocr.isFailure) {
            onError(CoreResponse.failure(
                "NF-IMP-004",
                context.getString(dev.ninfenz.mobile.R.string.import_pdf_ocr_failed, ocr.exceptionOrNull()?.message ?: "unknown"),
                context.getString(dev.ninfenz.mobile.R.string.import_pdf_unsupported_fix),
                3
            ).error)
            return null
        }
        markdown = ocr.orNullLogged("ImportScreen")?.text?.takeIf { it.isNotBlank() }
        if (ocr.orNullLogged("ImportScreen")?.truncated == true) {
            onNotice(context.getString(dev.ninfenz.mobile.R.string.import_pdf_ocr_truncated))
        }
    }
    if (markdown == null) {
        onError(CoreResponse.failure(
            "NF-IMP-004",
            context.getString(dev.ninfenz.mobile.R.string.import_image_ocr_required),
            context.getString(dev.ninfenz.mobile.R.string.import_image_ocr_required_fix),
            3
        ).error)
        return null
    }
    return File(file.parentFile, "image-ocr-" + System.nanoTime() + ".md").apply { writeText(markdown, Charsets.UTF_8) }
}

internal suspend fun pdfImportSource(
    context: android.content.Context,
    file: File,
    onError: (CoreError?) -> Unit
): File? {
    val extraction = runCatching { dev.ninfenz.mobile.data.PdfTextImporter.extract(context, file) }
    if (extraction.isFailure) {
        onError(CoreResponse.failure(
            "NF-IMP-004",
            context.getString(dev.ninfenz.mobile.R.string.import_pdf_failed, extraction.exceptionOrNull()?.message ?: "unknown"),
            context.getString(dev.ninfenz.mobile.R.string.import_pdf_unsupported_fix),
            3
        ).error)
        return null
    }
    val markdown = extraction.orNullLogged("ImportScreen")?.takeIf { it.isNotBlank() }
    if (markdown == null) {
        onError(CoreResponse.failure(
            "NF-IMP-004",
            context.getString(dev.ninfenz.mobile.R.string.import_pdf_no_text),
            context.getString(dev.ninfenz.mobile.R.string.import_pdf_unsupported_fix),
            3
        ).error)
        return null
    }
    return File(file.parentFile, "pdf-import-" + System.nanoTime() + ".md").apply { writeText(markdown, Charsets.UTF_8) }
}
