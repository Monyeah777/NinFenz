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
internal fun ImportSection10(s: ImportUiState) {
                                val visibleHistory = s.recentImports.filter {
                                    s.historyQuery.isBlank() || it.name.contains(s.historyQuery, true) || it.digest.contains(s.historyQuery, true)
                                }
                                val shownHistory = if (s.historyShowAll) visibleHistory else visibleHistory.take(5)
                                shownHistory.forEach { entry ->
                                    val matched = DraftLibrary.findByDigest(s.context.filesDir, entry.digest)
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Text(
                                            entry.name + " · " + entry.digest.take(10),
                                            style = NfType.meta,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                            modifier = Modifier.weight(1f)
                                        )
                                        if (matched != null) {
                                            TextButton(onClick = {
                                                val raw = DraftLibrary.read(matched)
                                                if (raw != null) {
                                                    try {
                                                        val obj = J.parseObject(raw, ImportModel.SCHEMA)
                                                        val parsed = ImportModel.parse(obj)
                                                        s.rawResult = obj
                                                        s.doc = parsed
                                                        s.acceptedMappings = DraftLibrary.acceptedMappings(matched)
                                                            ?: parsed.mappings.indices.filter { parsed.mappings[it].confidence >= s.mappingThreshold }.toSet()
                                                        s.savedName = matched.name.removeSuffix(".json")
                                                        s.error = null
                                                        s.importDraftStore.save(raw)
                                                    } catch (t: Throwable) {
                                                        s.error = CoreResponse.failure(
                                                    "NF-E-002",
                                                    s.context.getString(dev.ninfenz.mobile.R.string.import_draft_parse_failed, t.message ?: t.javaClass.simpleName),
                                                    s.context.getString(dev.ninfenz.mobile.R.string.import_draft_parse_failed_fix),
                                                    2
                                                ).error
                                                    }
                                                }
                                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_open_draft)) }
                                        } else {
                                            Text(stringResource(dev.ninfenz.mobile.R.string.import_draft_missing), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        }
                                    }
                                }
                                if (visibleHistory.size > 5) {
                                    TextButton(onClick = { s.historyShowAll = !s.historyShowAll }) {
                                        Text(stringResource(if (s.historyShowAll) dev.ninfenz.mobile.R.string.import_recent_less else dev.ninfenz.mobile.R.string.import_recent_all))
                                    }
                                }
                                TextButton(onClick = {
                                    s.importHistory.clear()
                                    s.recentImports = s.importHistory.recent()
                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_recent_clear)) }
}

internal fun LazyListScope.ImportSection11(s: ImportUiState) {
                                val visibleHistory = s.recentImports.filter {
                                    s.historyQuery.isBlank() || it.name.contains(s.historyQuery, true) || it.digest.contains(s.historyQuery, true)
                                }
                                val shownHistory = if (s.historyShowAll) visibleHistory else visibleHistory.take(5)
                    item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.import_recent_history)) }
                    item {
                        NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                                OutlinedTextField(
                                    value = s.historyQuery,
                                    onValueChange = { s.historyQuery = it },
                                    label = { Text(stringResource(dev.ninfenz.mobile.R.string.import_recent_filter)) },
                                    singleLine = true,
                                    modifier = Modifier.fillMaxWidth()
                                )
                                val visibleHistory = s.recentImports.filter {
                                    s.historyQuery.isBlank() || it.name.contains(s.historyQuery, true) || it.digest.contains(s.historyQuery, true)
                                }
                                val shownHistory = if (s.historyShowAll) visibleHistory else visibleHistory.take(5)
                                ImportSection10(s)
                            }
                        }
                    }
}

internal fun LazyListScope.ImportSection12(s: ImportUiState) {
            val current = s.doc ?: return
                item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.import_preview)) }
                item {
                    NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                        Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                            Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s), verticalAlignment = Alignment.CenterVertically) {
                                NfStatusChip(current.format + " · " + current.confidence + "%")
                                if (current.lowConfidence) NfStatusChip(stringResource(dev.ninfenz.mobile.R.string.import_low_confidence), MaterialTheme.colorScheme.error)
                                NfStatusChip(current.source.kind)
                            }
                            Text(stringResource(dev.ninfenz.mobile.R.string.import_source_label, current.source.name), style = NfType.meta)
                            Text(
                                pluralStringResource(
                                    dev.ninfenz.mobile.R.plurals.import_structure,
                                    current.structure.headings.size,
                                    current.structure.headings.size,
                                    current.structure.paragraphs,
                                    current.structure.codeBlocks.size,
                                    current.structure.tables.size
                                ),
                                style = NfType.meta
                            )
                            val fidelity = remember(current) { FidelityReport.from(current) }
                            Text(
                                stringResource(dev.ninfenz.mobile.R.string.import_fidelity, fidelity.score, fidelity.unmapped),
                                style = NfType.meta,
                                color = if (fidelity.unmapped > 0) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            if (fidelity.lost.isNotEmpty()) {
                                Text(
                                    stringResource(dev.ninfenz.mobile.R.string.import_fidelity_lost, fidelity.lost.take(3).joinToString("；")),
                                    style = NfType.meta,
                                    color = MaterialTheme.colorScheme.error
                                )
                            }
                            current.textDigest?.let { Text(stringResource(dev.ninfenz.mobile.R.string.import_digest, it.take(16)), style = NfType.meta) }
                            for (note in current.reviewNotes()) {
                                Text(note, style = NfType.meta, color = if (current.lowConfidence) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
}

internal fun LazyListScope.ImportSection13(s: ImportUiState) {
            val current = s.doc ?: return
                val slices = current.text?.let { MarkdownSlicer.slice(MarkdownBlocks.parse(it), s.sliceMinChars) } ?: emptyList()
                if (slices.isNotEmpty()) {
                    ImportSection6(s)
                }
                item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.import_mapping, current.mappings.size)) }
}

internal fun LazyListScope.ImportSection14(s: ImportUiState) {
            val current = s.doc ?: return
                if (current.mappings.isEmpty()) {
                    ImportSection7(s)
                } else {
                    item {
                        Column(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.import_mapping_threshold, s.mappingThreshold), style = NfType.meta)
                            Slider(
                                value = s.mappingThreshold.toFloat(),
                                onValueChange = { s.mappingThreshold = it.toInt().coerceIn(0, 100) },
                                valueRange = 0f..100f,
                                steps = 19
                            )
                        }
                    }
                    item {
                        Row(modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.import_accepted, s.acceptedMappings.size, current.mappings.size), style = NfType.meta)
                            Row {
                                TextButton(onClick = { s.lowConfidenceOnly = !s.lowConfidenceOnly }) {
                                    Text(stringResource(if (s.lowConfidenceOnly) dev.ninfenz.mobile.R.string.import_show_all else dev.ninfenz.mobile.R.string.import_low_only))
                                }
                                TextButton(onClick = {
                                    s.acceptedMappings = if (s.acceptedMappings.size == current.mappings.size) emptySet() else current.mappings.indices.toSet()
                                }) { Text(if (s.acceptedMappings.size == current.mappings.size) stringResource(dev.ninfenz.mobile.R.string.import_accept_none) else stringResource(dev.ninfenz.mobile.R.string.import_accept_all)) }
                            }
                        }
                    }
                    val visibleMappings = current.mappings.indices.filter { index ->
                        !s.lowConfidenceOnly || current.mappings[index].confidence < s.mappingThreshold
                    }
                    items(visibleMappings.size) { at ->
                        val index = visibleMappings[at]
                        val mapping = current.mappings[index]
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page, vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    mapping.fromKind + "[" + mapping.fromIndex + "] → " + mapping.toKind + " " + mapping.toId,
                                    style = NfType.secondary
                                )
                                Text(
                                    "confidence " + mapping.confidence + " · " + mapping.rationale,
                                    style = NfType.meta,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                            Switch(
                                checked = index in s.acceptedMappings,
                                onCheckedChange = { checked ->
                                    s.acceptedMappings = if (checked) s.acceptedMappings + index else s.acceptedMappings - index
                                }
                            )
                        }
                    }
                }
}

internal fun LazyListScope.ImportSection15(s: ImportUiState) {
            val current = s.doc ?: return
                val slices = current.text?.let { MarkdownSlicer.slice(MarkdownBlocks.parse(it), s.sliceMinChars) } ?: emptyList()
                if (current.unmapped.isNotEmpty()) {
                    item { Text(stringResource(dev.ninfenz.mobile.R.string.import_unmapped, current.unmapped.joinToString("；")), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
                }
                s.suggestNote?.let { message ->
                    item { Text(message, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
                }
                item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.import_draft)) }
                if (s.savedName == null && s.rawResult != null && s.packs.isNotEmpty()) {
                    item {
                        val pack = s.packs.first()
                        Column(
                            modifier = Modifier.padding(horizontal = NfSpacing.page),
                            verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)
                        ) {
                            Button(onClick = {
                                val raw = s.rawResult ?: return@Button
                                val title = slices.firstOrNull { it.heading != null }?.heading ?: current.source.name
                                val base = s.store.uniqueDraftBase(title)
                                val file = s.store.saveDraft(base, raw.toString())
                                s.zeroSlice?.let { s.zeroSliceStore.saveDraft(file, it) }
                                val mappingJson = buildJsonObject {
                                    put("accepted", JsonArray(s.acceptedMappings.sorted().map { JsonPrimitive(it) }))
                                    put("unmapped", JsonArray(current.unmapped.map { JsonPrimitive(it) }))
                                }.toString()
                                s.store.saveDraft(base + ".mapping", mappingJson)
                                s.savedName = file.name
                                s.drafts = DraftLibrary.list(s.context.filesDir)
                                s.onQuickProjectFromDraft(pack, title, file)
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_quick_project)) }
                            Text(
                                stringResource(dev.ninfenz.mobile.R.string.import_quick_project_note, pack.title),
                                style = NfType.meta,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }
}

