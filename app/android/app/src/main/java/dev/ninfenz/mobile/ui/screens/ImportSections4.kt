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
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.foundation.ExperimentalFoundationApi

internal fun LazyListScope.ImportSection16(s: ImportUiState) {
            val current = s.doc ?: return
                item {
                    if (s.savedName == null) {
                        Button(
                            onClick = {
                                val raw = s.rawResult
                                if (raw == null) {
                                    s.error = CoreResponse.failure(
                                        "NF-E-004",
                                        s.context.getString(dev.ninfenz.mobile.R.string.import_raw_missing),
                                        s.context.getString(dev.ninfenz.mobile.R.string.import_raw_missing_fix),
                                        2
                                    ).error
                                } else {
                                    val base = s.store.uniqueDraftBase(current.source.name)
                                    val file = s.store.saveDraft(base, raw.toString())
                                s.zeroSlice?.let { s.zeroSliceStore.saveDraft(file, it) }
                                    val mappingJson = buildJsonObject {
                                        put("accepted", JsonArray(s.acceptedMappings.sorted().map { JsonPrimitive(it) }))
                                        put("unmapped", JsonArray(current.unmapped.map { JsonPrimitive(it) }))
                                    }.toString()
                                    s.store.saveDraft(base + ".mapping", mappingJson)
                                    s.savedName = file.name
                                    s.drafts = DraftLibrary.list(s.context.filesDir)
                                }
                            },
                            modifier = Modifier.padding(horizontal = NfSpacing.page)
                        ) { Text(stringResource(dev.ninfenz.mobile.R.string.import_save)) }
                    } else {
                        NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.import_saved, s.savedName ?: ""), style = NfType.itemTitle)
                                Text(stringResource(dev.ninfenz.mobile.R.string.import_saved_note), style = NfType.meta)
                                Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                                    Button(onClick = s.onBack) { Text(stringResource(dev.ninfenz.mobile.R.string.import_done)) }
                                    TextButton(onClick = {
                                        s.doc = null
                                        s.rawResult = null
                                        s.savedName = null
                                        s.acceptedMappings = emptySet()
                                        s.error = null
                                        s.suggestNote = null
                                        s.importDraftStore.clear()
                                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_again)) }
                                }
                            }
                        }
                    }
                }
}

internal fun LazyListScope.ImportSection17(s: ImportUiState) {
            val current = s.doc ?: return
                if (s.drafts.isNotEmpty()) {
                    ImportSection8(s)
                    ImportSection9(s)
                }
                if (s.recentImports.isNotEmpty()) {
                    ImportSection11(s)
                }
                item {
                    if (current.text != null || current.textPath != null) {
                        Text(
                            (current.text ?: current.textPath ?: "").take(400),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(horizontal = NfSpacing.page)
                        )
                    }
                }
}

internal fun LazyListScope.ImportSection18(s: ImportUiState) {
            item {
                NfCard {
                    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        ImportSection1(s)
                        s.preservedMarkdown?.let { md ->
                            if (s.preserveGrant?.allows(dev.ninfenz.mobile.data.CapabilityGrant.REASSEMBLE, System.currentTimeMillis()) == true) {
                                OutlinedButton(onClick = { s.importText(md, ImportSource.SAF, s.preservedName) }, enabled = !s.busy) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.import_restore_archive))
                                }
                            } else {
                                Text(
                                    stringResource(dev.ninfenz.mobile.R.string.import_preserve_readonly),
                                    style = NfType.meta,
                                    color = MaterialTheme.colorScheme.error
                                )
                            }
                            OutlinedButton(onClick = { s.importPreviewText = md }, enabled = !s.busy) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.import_preserve_preview))
                            }
                            if (s.preserveGrant?.allows(dev.ninfenz.mobile.data.CapabilityGrant.EXPORT, System.currentTimeMillis()) == true) {
                                OutlinedButton(onClick = { s.exportPreservedMarkdown(md) }, enabled = !s.busy) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.import_preserve_export))
                                }
                            }
                        }
                        ImportSection2(s)
                    }
                }
            }
            if (s.busy) {
                item { LinearProgressIndicator(modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page)) }
                item { Text(stringResource(dev.ninfenz.mobile.R.string.import_busy), style = NfType.meta, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
            }
}

internal fun LazyListScope.ImportSection19(s: ImportUiState) {
            if (s.error != null) {
                item {
                    Column(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                        NfErrorCard(requireNotNull(s.error).code, requireNotNull(s.error).message, requireNotNull(s.error).fix)
                        if (requireNotNull(s.error).code == "NF-E-004") {
                            TextButton(onClick = { s.launchFilePicker(arrayOf("text/markdown", "text/plain", "text/csv", "application/json", "application/zip", "application/octet-stream")) }) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.import_reselect_file))
                            }
                        }
                    }
                }
            }
            s.notice?.let { message ->
                item { Text(message, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
            }
}

internal fun LazyListScope.ImportSection20(s: ImportUiState) {
            val current = s.doc
            if (current == null && s.error == null && !s.busy) {
                item {
                    NfEmptyState(
                        icon = Icons.Filled.Add,
                        title = stringResource(dev.ninfenz.mobile.R.string.import_empty_title),
                        message = stringResource(dev.ninfenz.mobile.R.string.import_empty_body),
                        actionLabel = s.context.getString(dev.ninfenz.mobile.R.string.import_pick_file_action),
                        onAction = { s.launchFilePicker(arrayOf("text/markdown", "text/plain", "text/csv", "application/json", "application/zip", "application/octet-stream")) },
                        secondaryLabel = s.context.getString(dev.ninfenz.mobile.R.string.import_sample_content),
                        onSecondary = { s.importSample() }
                    )
                }
            }
}

internal fun LazyListScope.ImportSection21(s: ImportUiState) {
            val current = s.doc ?: return
            s.zeroSlice?.let { report ->
                item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.import_zero_slice_session_title)) }
                item {
                    NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                        Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                            Text(
                                stringResource(dev.ninfenz.mobile.R.string.import_zero_slice_coverage, report.coverage),
                                style = NfType.meta,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Text(
                                pluralStringResource(dev.ninfenz.mobile.R.plurals.import_zero_slice_mappings, report.mappings.size, report.mappings.size) +
                                    " · " +
                                    pluralStringResource(dev.ninfenz.mobile.R.plurals.import_zero_slice_exceptions, report.exceptions.size, report.exceptions.size),
                                style = NfType.meta,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            report.mappings.take(6).forEach { mapping ->
                                Text(
                                    stringResource(dev.ninfenz.mobile.R.string.import_zero_slice_mapping, mapping.fromIndex, mapping.toName.ifBlank { mapping.toId }, mapping.confidence),
                                    style = NfType.meta
                                )
                            }
                            report.exceptions.firstOrNull()?.let { exception ->
                                Text(exception.reason, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            if (s.rawResult != null && s.packs.isNotEmpty() && current != null) {
                                TextButton(onClick = { s.createZeroSliceProject(report, current) }) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.import_zero_slice_create))
                                }
                            }
                            TextButton(onClick = { s.applyZeroSliceMappings(report, current) }) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.import_zero_slice_apply))
                            }
                        }
                    }
                }
            }
}

internal fun LazyListScope.ImportSection22(s: ImportUiState) {
            val current = s.doc ?: return
            if (current != null) {
                ImportSection12(s)
                val slices = current.text?.let { MarkdownSlicer.slice(MarkdownBlocks.parse(it), s.sliceMinChars) } ?: emptyList()
                ImportSection13(s)
                ImportSection14(s)
                ImportSection15(s)
                ImportSection16(s)
                ImportSection17(s)
            }
}

