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
internal fun ImportSection5(s: ImportUiState) {
    val current = s.doc ?: return
    val slices = current.text?.let { MarkdownSlicer.slice(MarkdownBlocks.parse(it), s.sliceMinChars) } ?: emptyList()
    val buildPromptPack = {
        val sampleTexts = s.savedSamples.take(2).mapNotNull { sample ->
            runCatching { sample.readText(Charsets.UTF_8) }.orNullLogged("ImportScreen")
        }
        PromptPack.from(current.source.name, current.text.orEmpty(), slices, sampleTexts, s.promptProfile)
    }
    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
        ImportSection3(s)
        ImportSection4(s)
        ImportPreviewSamples(s)
        ImportPreviewTemplates(s)
        ImportPreviewSlices(s)
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ImportPreviewSamples(s: ImportUiState) {
                                if (s.savedSamples.isNotEmpty()) {
                                    Text(
                                        pluralStringResource(dev.ninfenz.mobile.R.plurals.import_samples_saved, s.savedSamples.size, s.savedSamples.size),
                                        style = NfType.meta,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                    s.savedSamples.take(if (s.showAllSamples) Int.MAX_VALUE else 3).forEach { file ->
                                        Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                                            TextButton(
                                                onClick = { s.importPreviewText = runCatching { file.readText(Charsets.UTF_8) }.getOrDefault("") },
                                                contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp)
                                            ) {
                                                Text(file.name, style = NfType.meta, maxLines = 1)
                                            }
                                            Row(
                                                modifier = Modifier.horizontalScroll(rememberScrollState()),
                                                horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
                                            ) {
                                                TextButton(onClick = {
                                                    s.clipboard.setText(AnnotatedString(runCatching { file.readText(Charsets.UTF_8) }.getOrDefault("")))
                                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_sample_copy)) }
                                                TextButton(onClick = {
                                                    val text = runCatching { file.readText(Charsets.UTF_8) }.getOrDefault("")
                                                    val intent = ShareExporter.shareMarkdown(s.context, "nf-sample", text)
                                                    ShareExporter.launchChooser(s.context, intent, file.name)
                                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_share)) }
                                                TextButton(onClick = { s.pendingDeleteSample = file }) {
                                                    Text(stringResource(dev.ninfenz.mobile.R.string.import_sample_delete))
                                                }
                                            }
                                        }
                                    }
                                    if (s.savedSamples.size > 3) {
                                        TextButton(onClick = { s.showAllSamples = !s.showAllSamples }) {
                                            Text(stringResource(if (s.showAllSamples) dev.ninfenz.mobile.R.string.import_samples_show_less else dev.ninfenz.mobile.R.string.import_samples_show_all))
                                        }
                                    }
                                    TextButton(onClick = { s.showClearSamples = true }) {
                                        Text(stringResource(dev.ninfenz.mobile.R.string.import_samples_clear))
                                    }
                                }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ImportPreviewTemplates(s: ImportUiState) {
                                if (s.savedTemplates.isNotEmpty()) {
                                    Text(
                                        pluralStringResource(dev.ninfenz.mobile.R.plurals.import_templates_saved, s.savedTemplates.size, s.savedTemplates.size),
                                        style = NfType.meta,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                    s.savedTemplates.take(if (s.showAllTemplates) Int.MAX_VALUE else 3).forEach { file ->
                                        Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                                            TextButton(
                                                onClick = { s.previewTemplate = file },
                                                contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp)
                                            ) {
                                                Text(
                                                    s.templateStore.titleOf(file),
                                                    style = NfType.meta
                                                )
                                            }
                                            Row(
                                                modifier = Modifier.horizontalScroll(rememberScrollState()),
                                                horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
                                            ) {
                                                TextButton(onClick = {
                                                    val intent = ShareExporter.shareFileIntent(s.context, file, "application/json", file.name)
                                                    ShareExporter.launchChooser(s.context, intent, file.name)
                                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_share)) }
                                                TextButton(onClick = {
                                                    val json = runCatching { file.readText(Charsets.UTF_8) }.getOrDefault("")
                                                    s.clipboard.setText(AnnotatedString(json))
                                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_copy)) }
                                                TextButton(onClick = { s.pendingTemplateUse = file }) {
                                                    Text(stringResource(dev.ninfenz.mobile.R.string.import_template_use))
                                                }
                                                TextButton(onClick = { s.exportTemplatePackage(file) }) {
                                                    Text(stringResource(dev.ninfenz.mobile.R.string.import_template_export))
                                                }
                                                TextButton(onClick = { s.pendingDeleteTemplate = file }) {
                                                    Text(stringResource(dev.ninfenz.mobile.R.string.import_template_delete))
                                                }
                                            }
                                        }
                                    }
                                    if (s.savedTemplates.size > 3) {
                                        TextButton(onClick = { s.showAllTemplates = !s.showAllTemplates }) {
                                            Text(stringResource(if (s.showAllTemplates) dev.ninfenz.mobile.R.string.import_templates_show_less else dev.ninfenz.mobile.R.string.import_templates_show_all))
                                        }
                                    }
                                    TextButton(onClick = { s.showClearTemplates = true }) {
                                        Text(stringResource(dev.ninfenz.mobile.R.string.import_templates_clear))
                                    }
                                }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ImportPreviewSlices(s: ImportUiState) {
        val current = s.doc ?: return
    val slices = current.text?.let { MarkdownSlicer.slice(MarkdownBlocks.parse(it), s.sliceMinChars) } ?: emptyList()
                                slices.take(6).forEach { slice ->
                                    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                        Text(
                                            slice.heading ?: stringResource(dev.ninfenz.mobile.R.string.import_slice_preamble),
                                            style = NfType.itemTitle
                                        )
                                        Text(
                                            pluralStringResource(dev.ninfenz.mobile.R.plurals.import_slice_meta, slice.blocks.size, slice.blocks.size, slice.charCount),
                                            style = NfType.meta,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                        slice.blocks.firstOrNull()?.text?.lineSequence()?.firstOrNull()?.take(80)?.let {
                                            Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        }
                                    }
                                }
}

internal fun LazyListScope.ImportSection6(s: ImportUiState) {
                    item {
                        NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.import_slices))
                    }
                    item {
                        Column(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.import_slice_min_chars, s.sliceMinChars), style = NfType.meta)
                            Slider(
                                value = s.sliceMinChars.toFloat(),
                                onValueChange = { s.sliceMinChars = it.toInt().coerceIn(0, 2000) },
                                valueRange = 0f..2000f,
                                steps = 19
                            )
                        }
                    }
                    item {
                        NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                            ImportSection5(s)
                        }
                    }
}

internal fun LazyListScope.ImportSection7(s: ImportUiState) {
                    item { Text(stringResource(dev.ninfenz.mobile.R.string.import_no_mapping), style = NfType.secondary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
}

internal fun LazyListScope.ImportSection8(s: ImportUiState) {
                    item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.import_saved_drafts)) }
}

internal fun LazyListScope.ImportSection9(s: ImportUiState) {
                    s.drafts.take(5).forEach { draft ->
                        item {
                            NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(draft.name, style = NfType.meta, modifier = Modifier.weight(1f))
                                    TextButton(onClick = { s.openDraft(draft) }) {
                                        Text(stringResource(dev.ninfenz.mobile.R.string.import_open_draft))
                                    }
                                    if (s.packs.isNotEmpty()) {
                                        TextButton(onClick = { s.convertDraft = draft }) {
                                            Text(stringResource(dev.ninfenz.mobile.R.string.import_draft_to_project))
                                        }
                                    }
                                    TextButton(onClick = {
                                        s.renameDraft = draft
                                        s.renameDraftText = draft.name.removeSuffix(".json")
                                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_rename_draft)) }
                                    TextButton(onClick = { s.pendingDeleteDraft = draft }) {
                                        Text(stringResource(dev.ninfenz.mobile.R.string.import_delete_draft))
                                    }
                                }
                            }
                        }
                    }
}

