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
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.material3.ExperimentalMaterial3Api

internal class ImportUiState(
    val context: android.content.Context,
    val clipboard: androidx.compose.ui.platform.ClipboardManager,
    val scope: kotlinx.coroutines.CoroutineScope,
    var prefill: SharePayload?,
    var store: LibraryStore,
    var onBack: () -> Unit,
    var onPrefillConsumed: () -> Unit,
    var autoClipboard: Boolean,
    var onAutoClipboardConsumed: () -> Unit,
    var packs: List<PackEntry>,
    var onCreateProjectFromDraft: (PackEntry, String, File) -> Unit,
    var onQuickProjectFromDraft: (PackEntry, String, File) -> Unit,
    var onCreateProjectFromTemplate: (PackEntry, String, String, String) -> Unit,
    var onProjectImported: (String, String, String) -> Unit,
    var onBundleImported: (Int) -> Unit,
    historyQueryState: androidx.compose.runtime.MutableState<String>,
    historyShowAllState: androidx.compose.runtime.MutableState<Boolean>,
) {
    var doc by mutableStateOf<ImportDoc?>(null)

    var rawResult by mutableStateOf<JsonObject?>(null)

    var error by mutableStateOf<CoreError?>(null)

    var notice by mutableStateOf<String?>(null)

    var busy by mutableStateOf(false)

    var batch by mutableStateOf<ImportBatchState?>(null)

    var savedName by mutableStateOf<String?>(null)

    var prefillNote by mutableStateOf<String?>(null)

    val shareQueueStore = ShareQueueStore(context.filesDir)

    val savedQueue = shareQueueStore.load()

    var shareQueue by mutableStateOf(savedQueue?.items ?: emptyList<SharedItem>())

    var shareCursor by mutableIntStateOf(savedQueue?.cursor ?: 0)

    var acceptedMappings by mutableStateOf<Set<Int>>(emptySet())

    var lowConfidenceOnly by mutableStateOf(false)

    var mappingThreshold by mutableStateOf(80)

    var sliceMinChars by mutableStateOf(0)

    var suggestNote by mutableStateOf<String?>(null)

    var zeroSliceNote by mutableStateOf<String?>(null)

    val zeroSliceStore = ZeroSliceStore(context.filesDir)

    var zeroSlice by mutableStateOf<ZeroSliceReport?>(null)

    var preserveNote by mutableStateOf<String?>(null)

    var preservedMarkdown by mutableStateOf<String?>(null)

    var preserveGrant by mutableStateOf<dev.ninfenz.mobile.data.CapabilityGrant?>(null)

    var preservedName by mutableStateOf("restored.md")

    val importHistory = ImportHistoryStore(context.filesDir)

    val importDraftStore = ImportDraftStore(context.filesDir)

    val templateStore = TemplateCandidateStore(context.filesDir)

    var savedTemplates by mutableStateOf(templateStore.list())

    val sampleStore = PromptSampleStore(context.filesDir)

    var savedSamples by mutableStateOf(sampleStore.list())

    var pendingDeleteSample by mutableStateOf<File?>(null)

    var pendingTemplateUse by mutableStateOf<File?>(null)

    var previewTemplate by mutableStateOf<File?>(null)

    var showAllTemplates by mutableStateOf(false)

    var showAllSamples by mutableStateOf(false)

    var showClearSamples by mutableStateOf(false)

    var showClearTemplates by mutableStateOf(false)

    var pendingDeleteTemplate by mutableStateOf<File?>(null)

    var importPreviewText by mutableStateOf<String?>(null)

    var promptProfile by mutableStateOf(PromptProfile.GENERIC)

    val extensionStore = ExtensionStore(context.filesDir)

    val importRecipes = extensionStore.contributions(setOf("import_recipe"))

    var drafts by mutableStateOf(DraftLibrary.list(context.filesDir))

    var recentImports by mutableStateOf(importHistory.recent())

    var historyQuery by historyQueryState

    var historyShowAll by historyShowAllState

    var pendingDeleteDraft by mutableStateOf<File?>(null)

    var convertDraft by mutableStateOf<File?>(null)

    var renameDraft by mutableStateOf<File?>(null)

    var renameDraftText by mutableStateOf("")

    var duplicatePrompt by mutableStateOf<DuplicatePrompt?>(null)

    var showClearConfirm by mutableStateOf(false)

    var cleared by mutableStateOf<ImportClearSnapshot?>(null)

    var clearSeconds by mutableIntStateOf(5)

    var launchTemplatePicker: (Array<String>) -> Unit = {}
    val latestPreserve = File(File(context.filesDir, "exports"), "delivery")
                    .listFiles { f -> f.isFile && f.name.endsWith(".preserve.zip") }
                    ?.maxByOrNull { it.lastModified() }

    var launchPreservePicker: (Array<String>) -> Unit = {}
    var launchCsvPicker: (Array<String>) -> Unit = {}
    var launchFilePicker: (Array<String>) -> Unit = {}
    var launchMultiPicker: (Array<String>) -> Unit = {}
    var importStep: Int = 0

}
