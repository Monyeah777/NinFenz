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

internal suspend fun applyImportResponse(
    context: android.content.Context,
    response: CoreResponse,
    mappingThreshold: Int,
    importHistory: dev.ninfenz.mobile.data.ImportHistoryStore,
    onError: (CoreError?) -> Unit,
    onDoc: (ImportDoc?) -> Unit,
    onRawResult: (JsonObject?) -> Unit,
    onAcceptedMappings: (Set<Int>) -> Unit,
    onNotice: (String?) -> Unit,
    onDuplicatePrompt: (DuplicatePrompt?) -> Unit,
    onSuggestNote: (String?) -> Unit,
    onRecentImports: (List<dev.ninfenz.mobile.data.ImportHistoryStore.Entry>) -> Unit
) {
    if (response.ok) {
        val obj = response.resultObject()
        if (obj == null) {
            onError(CoreResponse.failure(
                "NF-E-002",
                context.getString(dev.ninfenz.mobile.R.string.import_core_missing_result),
                context.getString(dev.ninfenz.mobile.R.string.import_core_missing_result_fix),
                2
            ).error)
        } else {
            try {
                val imported = ImportModel.parse(obj)
                recordImportHistory(context, imported, importHistory, onNotice, onDuplicatePrompt, onRecentImports)
                onRawResult(obj)
                onDoc(imported)
                onAcceptedMappings(imported.mappings.indices.filter { imported.mappings[it].confidence >= mappingThreshold }.toSet())
                val suggest = safeCall("map-suggest", buildJsonObject { put("import", obj) })
                if (suggest.ok) {
                    val suggestedObj = suggest.resultObject()
                    if (suggestedObj != null) {
                        applySuggestedImport(context, suggestedObj, mappingThreshold, onDoc, onRawResult, onAcceptedMappings, onSuggestNote)
                    }
                } else {
                    onSuggestNote(context.getString(
                        dev.ninfenz.mobile.R.string.import_no_suggestion,
                        suggest.error?.message ?: context.getString(dev.ninfenz.mobile.R.string.unknown_reason)
                    ))
                }
            } catch (e: Exception) {
                onError(CoreResponse.failure(
                    (e as? dev.ninfenz.mobile.core.ModelException)?.code ?: "NF-E-002",
                    context.getString(dev.ninfenz.mobile.R.string.import_parse_failed, e.message ?: e.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.import_parse_failed_fix),
                    1
                ).error)
            }
        }
    } else {
        onError(response.error)
    }
}

internal data class VerifyTemplateImportCallbacks(
    val onError: (CoreError?) -> Unit,
    val onCreateProjectFromTemplate: (PackEntry, String, String, String) -> Unit,
)

internal suspend fun verifyTemplateImport(
    context: android.content.Context,
    imported: TemplatePackageImporter.Imported,
    packs: List<PackEntry>,
    callbacks: VerifyTemplateImportCallbacks
) {
    val hash = safeCall("pack-hash", buildJsonObject { put("root", imported.dir.absolutePath) })
    val hashes = hash.resultObject()?.get("hashes") as? kotlinx.serialization.json.JsonObject
    val tree = hashes?.get("tree")?.jsonPrimitive?.content
    val count = hashes?.get("count")?.jsonPrimitive?.content?.toIntOrNull()
    val pack = if (imported.packId != null) {
        packs.firstOrNull {
            it.id == imported.packId && (imported.packVersion == null || it.version == imported.packVersion)
        }
    } else {
        packs.firstOrNull()
    }
    if (!hash.ok || tree != imported.tree || count != imported.count) {
        callbacks.onError(hash.error ?: CoreResponse.failure("NF-PCK-003", context.getString(dev.ninfenz.mobile.R.string.import_template_tree_mismatch), context.getString(dev.ninfenz.mobile.R.string.import_template_tree_mismatch_fix), 2).error)
        return
    }
    val specObj = kotlinx.serialization.json.Json.parseToJsonElement(imported.specText).jsonObject
    val specCheck = safeCall("spec-validate", buildJsonObject { put("spec", specObj) })
    if (!specCheck.ok) {
        callbacks.onError(specCheck.error)
        return
    }
    if (pack == null) {
        callbacks.onError(CoreResponse.failure(
            "NF-PCK-002",
            if (imported.packId != null) {
                context.getString(dev.ninfenz.mobile.R.string.import_template_pack_missing, imported.packId, imported.packVersion.orEmpty())
            } else {
                context.getString(dev.ninfenz.mobile.R.string.import_template_need_pack)
            },
            context.getString(dev.ninfenz.mobile.R.string.import_template_need_pack),
            2
        ).error)
        return
    }
    callbacks.onCreateProjectFromTemplate(pack, imported.title, imported.specText, imported.templateText)
}

internal suspend fun applySuggestedImport(
    context: android.content.Context,
    suggestedObj: JsonObject,
    mappingThreshold: Int,
    onDoc: (ImportDoc?) -> Unit,
    onRawResult: (JsonObject?) -> Unit,
    onAcceptedMappings: (Set<Int>) -> Unit,
    onSuggestNote: (String?) -> Unit
) {
    val suggested = ImportModel.parse(suggestedObj)
    onDoc(suggested)
    onRawResult(suggestedObj)
    onAcceptedMappings(suggested.mappings.indices.filter { suggested.mappings[it].confidence >= mappingThreshold }.toSet())
    onSuggestNote(context.getString(dev.ninfenz.mobile.R.string.import_suggest_done))
}

internal fun recordImportHistory(
    context: android.content.Context,
    imported: ImportDoc,
    importHistory: dev.ninfenz.mobile.data.ImportHistoryStore,
    onNotice: (String?) -> Unit,
    onDuplicatePrompt: (DuplicatePrompt?) -> Unit,
    onRecentImports: (List<dev.ninfenz.mobile.data.ImportHistoryStore.Entry>) -> Unit
) {
    val digest = imported.source.sha256 ?: imported.textDigest
    if (!digest.isNullOrBlank()) {
        val previous = importHistory.find(digest)
        if (previous != null) {
            onNotice(context.getString(dev.ninfenz.mobile.R.string.import_duplicate_notice, previous.name, digest.take(12)))
            onDuplicatePrompt(DuplicatePrompt(digest, DraftLibrary.findByDigest(context.filesDir, digest)))
        }
        importHistory.record(digest, imported.source.name)
        onRecentImports(importHistory.recent())
    }
}
