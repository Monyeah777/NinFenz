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

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ImportSection23(s: ImportUiState) {
            val current = s.doc
        NfTopAppBar(
            title = stringResource(dev.ninfenz.mobile.R.string.import_title),
            onBack = s.onBack,
            actions = {
                TextButton(
                    onClick = { s.launchMultiPicker(arrayOf("*/*")) },
                    enabled = !s.busy && dev.ninfenz.mobile.data.CapabilityRegistry.isEnabled(dev.ninfenz.mobile.data.Capability.BATCH)
                ) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.import_multi))
                }
                if (s.doc != null || s.rawResult != null || s.savedName != null || s.shareQueue.isNotEmpty() || s.prefillNote != null) {
                    TextButton(onClick = { s.showClearConfirm = true }, enabled = !s.busy) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.import_clear_action))
                    }
                }
            }
        )
        NfStepStrip(
            steps = listOf(
                stringResource(dev.ninfenz.mobile.R.string.import_step_source),
                stringResource(dev.ninfenz.mobile.R.string.import_step_preview),
                stringResource(dev.ninfenz.mobile.R.string.import_step_mapping),
                stringResource(dev.ninfenz.mobile.R.string.import_step_draft)
            ),
            current = s.importStep
        )
        LazyColumn(
            contentPadding = androidx.compose.foundation.layout.PaddingValues(NfSpacing.page),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
        ) {
            ImportSection18(s)
            ImportSection19(s)
            val current = s.doc
            ImportSection20(s)
            ImportSection21(s)
            ImportSection22(s)
        }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ImportSection24(s: ImportUiState, modifier: Modifier) {
    Column(modifier = Modifier.fillMaxSize()) {
        ImportSection23(s)
        }
        AnimatedVisibility(
            visible = s.cleared != null,
            modifier = modifier,
            enter = fadeIn() + slideInVertically { it / 2 },
            exit = fadeOut() + slideOutVertically { it / 2 }
        ) {
            s.cleared?.let { snapshot ->
                NfActionBarSurface {
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.import_cleared_countdown, s.clearSeconds),
                            style = NfType.secondary,
                            modifier = Modifier.weight(1f)
                        )
                        TextButton(onClick = {
                            s.doc = snapshot.doc
                            s.rawResult = snapshot.rawResult
                            s.savedName = snapshot.savedName
                            s.acceptedMappings = snapshot.acceptedMappings
                            s.prefillNote = snapshot.prefillNote
                            s.notice = snapshot.notice
                            s.suggestNote = snapshot.suggestNote
                            s.shareQueue = snapshot.shareQueue
                            s.shareCursor = snapshot.shareCursor
                            snapshot.rawResult?.let { s.importDraftStore.save(it.toString()) }
                            s.cleared = null
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_clear_undo)) }
                        TextButton(onClick = { s.cleared = null }) {
                            Text(stringResource(android.R.string.cancel))
                        }
                }
            }
        }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ImportSection26(s: ImportUiState) {
    s.renameDraft?.let { draft ->
        AlertDialog(
            onDismissRequest = { s.renameDraft = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.import_rename_draft)) },
            text = {
                OutlinedTextField(
                    value = s.renameDraftText,
                    onValueChange = { s.renameDraftText = it },
                    singleLine = true,
                    label = { Text(stringResource(dev.ninfenz.mobile.R.string.import_rename_draft_label)) }
                )
            },
            confirmButton = {
                TextButton(
                    enabled = s.renameDraftText.isNotBlank(),
                    onClick = {
                        try {
                            val renamed = DraftLibrary.rename(draft, s.renameDraftText)
                            s.drafts = DraftLibrary.list(s.context.filesDir)
                            if (s.savedName == draft.name.removeSuffix(".json")) {
                                s.savedName = renamed.name.removeSuffix(".json")
                            }
                            s.renameDraft = null
                        } catch (t: Throwable) {
                            s.error = CoreResponse.failure(
                                "NF-IMP-005",
                                s.context.getString(dev.ninfenz.mobile.R.string.import_rename_failed, t.message ?: t.javaClass.simpleName),
                                s.context.getString(dev.ninfenz.mobile.R.string.import_rename_failed_fix),
                                2
                            ).error
                            s.renameDraft = null
                        }
                    }
                ) { Text(stringResource(dev.ninfenz.mobile.R.string.import_rename_confirm)) }
            },
            dismissButton = {
                TextButton(onClick = { s.renameDraft = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ImportSection27(s: ImportUiState) {
    s.convertDraft?.let { draft ->
        AlertDialog(
            onDismissRequest = { s.convertDraft = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.import_draft_to_project)) },
            text = {
                Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                    s.packs.forEach { pack ->
                        TextButton(onClick = {
                            s.convertDraft = null
                            s.onCreateProjectFromDraft(pack, draft.name.removeSuffix(".json"), draft)
                        }) { Text(pack.title + " · " + pack.id + "@" + pack.version) }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { s.convertDraft = null }) { Text(stringResource(dev.ninfenz.mobile.R.string.action_close)) }
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ImportSection28(s: ImportUiState) {
    s.duplicatePrompt?.let { prompt ->
        AlertDialog(
            onDismissRequest = { s.duplicatePrompt = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.import_duplicate_title)) },
            text = {
                Text(stringResource(dev.ninfenz.mobile.R.string.import_duplicate_body, prompt.digest.take(12)))
            },
            confirmButton = {
                TextButton(
                    enabled = prompt.draft != null,
                    onClick = {
                        val draft = prompt.draft
                        val raw = draft?.let { DraftLibrary.read(it) }
                        if (raw == null) {
                            s.duplicatePrompt = null
                        } else {
                            try {
                                val obj = J.parseObject(raw, ImportModel.SCHEMA)
                                val parsed = ImportModel.parse(obj)
                                s.rawResult = obj
                                s.doc = parsed
                                s.acceptedMappings = parsed.mappings.indices.filter { parsed.mappings[it].confidence >= s.mappingThreshold }.toSet()
                                s.importDraftStore.save(raw)
                                s.notice = s.context.getString(dev.ninfenz.mobile.R.string.import_duplicate_updated)
                            } catch (t: Throwable) {
                                s.error = CoreResponse.failure(
                                    "NF-E-002",
                                    s.context.getString(dev.ninfenz.mobile.R.string.import_parse_failed, t.message ?: t.javaClass.simpleName),
                                    s.context.getString(dev.ninfenz.mobile.R.string.import_parse_failed_fix),
                                    1
                                ).error
                            }
                            s.duplicatePrompt = null
                        }
                    }
                ) { Text(stringResource(dev.ninfenz.mobile.R.string.import_duplicate_update)) }
            },
            dismissButton = {
                Row {
                    TextButton(onClick = {
                        s.duplicatePrompt = null
                        s.doc = null
                        s.rawResult = null
                        s.acceptedMappings = emptySet()
                        s.importDraftStore.clear()
                        s.notice = s.context.getString(dev.ninfenz.mobile.R.string.import_duplicate_skipped)
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_duplicate_skip)) }
                    TextButton(onClick = { s.duplicatePrompt = null }) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.import_duplicate_new))
                    }
                }
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ImportSection29(s: ImportUiState) {
    s.pendingDeleteDraft?.let { draft ->
        AlertDialog(
            onDismissRequest = { s.pendingDeleteDraft = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.import_delete_draft)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.import_delete_draft_body, draft.name)) },
            confirmButton = {
                TextButton(onClick = {
                    val base = draft.name.removeSuffix(".json")
                    DraftLibrary.delete(draft)
                    s.drafts = DraftLibrary.list(s.context.filesDir)
                    if (s.savedName == base) s.savedName = null
                    s.pendingDeleteDraft = null
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_delete_draft)) }
            },
            dismissButton = {
                TextButton(onClick = { s.pendingDeleteDraft = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ImportSection30(s: ImportUiState) {
    s.importPreviewText?.let { text ->
        Dialog(onDismissRequest = { s.importPreviewText = null }) {
            Surface(shape = MaterialTheme.shapes.large, tonalElevation = 6.dp) {
                Column(modifier = Modifier.fillMaxWidth().padding(NfSpacing.l), verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.import_preview_ready), style = NfType.screenTitle, modifier = Modifier.weight(1f))
                        TextButton(onClick = { s.clipboard.setText(AnnotatedString(CsvTable.toMarkdown(text))) }) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.import_csv_copy))
                        }
                        TextButton(onClick = {
                            val intent = ShareExporter.shareMarkdown(s.context, "nf-import-preview", text)
                            ShareExporter.launchChooser(s.context, intent, s.context.getString(dev.ninfenz.mobile.R.string.delivery_share_md))
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_share_md)) }
                        TextButton(onClick = { s.importPreviewText = null }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_close)) }
                    }
                    Column(modifier = Modifier.heightIn(max = 520.dp).verticalScroll(rememberScrollState())) {
                        MarkdownPreview(text)
                    }
                }
            }
        }
    }
}

