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

internal fun ImportUiState.openDraft(draft: File) {
    val raw = DraftLibrary.read(draft)
    if (raw == null) {
        error = CoreResponse.failure(
            "NF-IMP-004",
            context.getString(dev.ninfenz.mobile.R.string.import_draft_read_failed),
            context.getString(dev.ninfenz.mobile.R.string.import_draft_read_failed_fix),
            2
        ).error
    } else {
        try {
            val obj = J.parseObject(raw, ImportModel.SCHEMA)
            val parsed = ImportModel.parse(obj)
            rawResult = obj
            doc = parsed
            acceptedMappings = DraftLibrary.acceptedMappings(draft)
                ?: parsed.mappings.indices.filter { parsed.mappings[it].confidence >= mappingThreshold }.toSet()
            savedName = draft.name.removeSuffix(".json")
            error = null
            importDraftStore.save(raw)
        } catch (t: Throwable) {
            error = CoreResponse.failure(
                "NF-E-002",
                context.getString(dev.ninfenz.mobile.R.string.import_draft_parse_failed, t.message ?: t.javaClass.simpleName),
                context.getString(dev.ninfenz.mobile.R.string.import_draft_parse_failed_fix),
                2
            ).error
        }
    }
}

internal fun ImportUiState.exportPreservedMarkdown(md: String) {
    runCatching {
        val outDir = File(File(context.filesDir, "exports"), "preserve").apply { mkdirs() }
        val out = File(outDir, preservedName)
        out.writeText(md, Charsets.UTF_8)
        preserveNote = context.getString(dev.ninfenz.mobile.R.string.import_preserve_exported, out.name)
    }.onFailure {
        preserveNote = context.getString(dev.ninfenz.mobile.R.string.import_preserve_fail, it.message ?: it.javaClass.simpleName)
    }
}

internal fun ImportUiState.createZeroSliceProject(report: ZeroSliceReport, current: ImportDoc?) {
    val raw = rawResult ?: return
    val pack = packs.first()
    val title = current?.source?.name ?: "zero-slice"
    val prepared = dev.ninfenz.mobile.data.ZeroSliceProjectDraft.prepare(
        context.filesDir,
        raw.toString(),
        report,
        acceptedMappings,
        current?.unmapped.orEmpty(),
        title
    )
    savedName = prepared.file.name
    onQuickProjectFromDraft(pack, title, prepared.file)
}

internal fun ImportUiState.applyZeroSliceMappings(report: ZeroSliceReport, current: ImportDoc?) {
    val currentMappings = current?.mappings.orEmpty()
    val matched = currentMappings.indices.filter { i ->
        val m = currentMappings[i]
        report.mappings.any { it.toId == m.toId && it.confidence >= 60 }
    }.toSet()
    if (matched.isEmpty()) {
        zeroSliceNote = context.getString(dev.ninfenz.mobile.R.string.import_zero_slice_no_match)
    } else {
        acceptedMappings = acceptedMappings + matched
        zeroSliceNote = context.getString(dev.ninfenz.mobile.R.string.import_zero_slice_applied)
    }
}
