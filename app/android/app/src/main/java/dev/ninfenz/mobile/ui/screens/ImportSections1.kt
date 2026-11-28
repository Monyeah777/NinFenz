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
internal fun ImportRootShell(s: ImportUiState) {
    Box(modifier = Modifier.fillMaxSize()) {
    ImportSection24(s, Modifier.align(Alignment.BottomCenter))
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ImportSection1(s: ImportUiState) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.import_source), style = NfType.sectionTitle)
                        FlowRow(
                            horizontalArrangement = Arrangement.spacedBy(NfSpacing.s),
                            verticalArrangement = Arrangement.spacedBy(NfSpacing.s)
                        ) {
                            Button(onClick = { s.launchFilePicker(importFileMimeTypes) }, enabled = !s.busy) { Text(stringResource(dev.ninfenz.mobile.R.string.import_pick_file)) }
                            OutlinedButton(onClick = { s.importClipboard() }, enabled = !s.busy) { Text(stringResource(dev.ninfenz.mobile.R.string.import_clipboard)) }
                            OutlinedButton(onClick = { s.launchCsvPicker(arrayOf("text/csv", "text/comma-separated-values", "text/plain")) }, enabled = !s.busy) { Text(stringResource(dev.ninfenz.mobile.R.string.import_csv_file)) }
                            OutlinedButton(onClick = { s.importCsv() }, enabled = !s.busy) { Text(stringResource(dev.ninfenz.mobile.R.string.import_csv_clipboard)) }
                            OutlinedButton(onClick = { s.importSample() }, enabled = !s.busy) { Text(stringResource(dev.ninfenz.mobile.R.string.import_sample)) }
                            if (s.doc != null) {
                                OutlinedButton(onClick = { s.runZeroSlice() }, enabled = !s.busy) { Text(stringResource(dev.ninfenz.mobile.R.string.import_zero_slice)) }
                            }
                            OutlinedButton(onClick = { s.launchPreservePicker(arrayOf("application/zip", "application/octet-stream")) }, enabled = !s.busy) { Text(stringResource(dev.ninfenz.mobile.R.string.import_verify_preserve)) }
                        }
                        s.batch?.let { state ->
                            ImportBatchPanel(
                                state = state,
                                onCancel = { s.batch = s.batch?.cancel() },
                                onRetry = {
                                    s.scope.launch {
                                        val indices = s.batch?.failedIndices().orEmpty()
                                        for (index in indices) {
                                            if (s.batch?.cancelled == true) break
                                            s.runBatchIndex(index)
                                        }
                                        val finalState = s.batch
                                        s.notice = s.context.getString(
                                            dev.ninfenz.mobile.R.string.import_multi_done,
                                            finalState?.success ?: 0,
                                            finalState?.failed ?: 0
                                        )
                                    }
                                }
                            )
                        }
                        if (s.prefillNote != null) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.import_share_received), style = NfType.meta, color = MaterialTheme.colorScheme.primary)
                        }
                        s.latestPreserve?.let { archive ->
                            OutlinedButton(onClick = { s.handlePreserve(archive) }, enabled = !s.busy) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.import_verify_latest))
                            }
                        }
                        if (s.prefillNote != null) {
                            Text(requireNotNull(s.prefillNote), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        s.zeroSliceNote?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary) }
                        s.preserveNote?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary) }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ImportSection2(s: ImportUiState) {
                        if (s.shareQueue.isNotEmpty()) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    pluralStringResource(dev.ninfenz.mobile.R.plurals.import_share_queue, s.shareQueue.size, s.shareQueue.size, s.shareCursor + 1),
                                    style = NfType.meta,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.weight(1f)
                                )
                                if (s.doc == null) {
                                    TextButton(onClick = { s.importSharedItem(s.shareQueue[s.shareCursor]) }) {
                                        Text(stringResource(dev.ninfenz.mobile.R.string.import_share_current))
                                    }
                                } else if (s.shareCursor < s.shareQueue.size - 1) {
                                    TextButton(onClick = { s.importNextSharedItem() }) {
                                        Text(stringResource(dev.ninfenz.mobile.R.string.import_share_next))
                                    }
                                }
                                TextButton(onClick = {
                                    s.shareQueue = emptyList()
                                    s.shareCursor = 0
                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_share_ignore)) }
                            }
                        }
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.import_explain),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ImportSection3(s: ImportUiState) {
            val current = s.doc ?: return
                val slices = current.text?.let { MarkdownSlicer.slice(MarkdownBlocks.parse(it), s.sliceMinChars) } ?: emptyList()
                                Text(
                                    pluralStringResource(
                                        dev.ninfenz.mobile.R.plurals.import_slices_summary,
                                        slices.count { it.heading != null },
                                        slices.count { it.heading != null },
                                        slices.sumOf { it.blocks.size }
                                    ),
                                    style = NfType.meta,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                                Text(
                                    stringResource(if (slices.count { it.heading != null } >= 2) dev.ninfenz.mobile.R.string.import_slice_suggestion_chapter else dev.ninfenz.mobile.R.string.import_slice_suggestion_free),
                                    style = NfType.label,
                                    color = MaterialTheme.colorScheme.primary
                                )
                                TextButton(onClick = { s.importPreviewText = current.text }) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.import_preview_ready))
                                }
                                if (s.importRecipes.isNotEmpty()) {
                                    Row(modifier = Modifier.horizontalScroll(rememberScrollState())) {
                                        Text(stringResource(dev.ninfenz.mobile.R.string.import_recipes), style = NfType.meta, modifier = Modifier.padding(end = 8.dp))
                                        s.importRecipes.forEach { recipe ->
                                            val profile = recipe.config["prompt_profile"]?.toString()?.trim('"')
                                                ?.let { name -> PromptProfile.entries.firstOrNull { it.name.equals(name, true) } }
                                            val low = recipe.config["low_confidence_only"]?.toString()?.toBooleanStrictOrNull() ?: false
                                            val threshold = recipe.config["mapping_threshold"]?.toString()?.toIntOrNull()?.coerceIn(0, 100)
                                            val sliceMin = recipe.config["slice_min_chars"]?.toString()?.toIntOrNull()?.coerceIn(0, 2000)
                                            TextButton(onClick = {
                                                profile?.let { s.promptProfile = it }
                                                s.lowConfidenceOnly = low
                                                threshold?.let { s.mappingThreshold = it }
                                                sliceMin?.let { s.sliceMinChars = it }
                                                s.notice = s.context.getString(dev.ninfenz.mobile.R.string.import_recipe_applied, recipe.id)
                                            }) { Text(recipe.id) }
                                        }
                                    }
                                }
                                TextButton(onClick = {
                                    s.promptProfile = PromptProfile.entries[(s.promptProfile.ordinal + 1) % PromptProfile.entries.size]
                                }) {
                                    Text(s.promptProfile.label)
                                }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ImportSection4(s: ImportUiState) {
            val current = s.doc ?: return
                val slices = current.text?.let { MarkdownSlicer.slice(MarkdownBlocks.parse(it), s.sliceMinChars) } ?: emptyList()
                                val buildPromptPack = {
                                    val sampleTexts = s.savedSamples.take(2).mapNotNull { sample ->
                                        runCatching { sample.readText(Charsets.UTF_8) }.orNullLogged("ImportScreen")
                                    }
                                    PromptPack.from(current.source.name, current.text.orEmpty(), slices, sampleTexts, s.promptProfile)
                                }
                                TextButton(onClick = {
                                    val pack = buildPromptPack()
                                    val intent = ShareExporter.shareMarkdown(s.context, "nf-prompt-pack", pack)
                                    ShareExporter.launchChooser(s.context, intent, s.context.getString(dev.ninfenz.mobile.R.string.import_prompt_pack))
                                }) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.import_prompt_pack))
                                }
                                TextButton(onClick = { s.clipboard.setText(AnnotatedString(buildPromptPack())) }) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.import_prompt_copy))
                                }
                                TextButton(onClick = {
                                    val spec = TemplateCandidate.fromSlices(current.source.name, slices) ?: return@TextButton
                                    s.scope.launch {
                                        val response = safeCall("spec-validate", buildJsonObject { put("spec", spec) })
                                        if (response.ok) {
                                            val file = s.templateStore.save(spec)
                                            s.savedTemplates = s.templateStore.list()
                                            s.notice = s.context.getString(dev.ninfenz.mobile.R.string.import_template_saved, file.name)
                                        } else {
                                            s.error = response.error
                                        }
                                    }
                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_save_template)) }
                                TextButton(onClick = { s.launchTemplatePicker(arrayOf("application/json", "text/json", "text/plain")) }) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.import_template_import))
                                }
}

