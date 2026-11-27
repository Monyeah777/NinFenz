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
internal fun ImportSection31(s: ImportUiState) {
    s.previewTemplate?.let { file ->
        val spec = remember(file) {
            runCatching { SpecModel.parse(file.readText(Charsets.UTF_8)) }.orNullLogged("ImportScreen")
        }
        Dialog(onDismissRequest = { s.previewTemplate = null }) {
            Surface(shape = MaterialTheme.shapes.large, tonalElevation = 6.dp) {
                Column(
                    modifier = Modifier.fillMaxWidth().padding(NfSpacing.l),
                    verticalArrangement = Arrangement.spacedBy(NfSpacing.s)
                ) {
                    Text(spec?.title ?: file.name, style = NfType.screenTitle)
                    if (spec != null) ImportTemplateBody(spec)
                    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        TextButton(onClick = { s.previewTemplate = null }) { Text(stringResource(android.R.string.cancel)) }
                        TextButton(onClick = {
                            val json = runCatching { file.readText(Charsets.UTF_8) }.getOrDefault("")
                            s.clipboard.setText(AnnotatedString(json))
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_copy)) }
                        TextButton(onClick = {
                            s.previewTemplate = null
                            s.exportTemplatePackage(file)
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_export)) }
                        TextButton(onClick = {
                            s.previewTemplate = null
                            s.pendingTemplateUse = file
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_use)) }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ImportSection32(s: ImportUiState) {
    s.pendingTemplateUse?.let { file ->
        val pack = s.packs.firstOrNull()
        AlertDialog(
            onDismissRequest = { s.pendingTemplateUse = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_use_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_use_body)) },
            confirmButton = {
                TextButton(
                    enabled = pack != null,
                    onClick = {
                        val spec = runCatching { file.readText(Charsets.UTF_8) }.orNullLogged("ImportScreen")
                        if (pack != null && spec != null) {
                            s.onCreateProjectFromTemplate(pack, s.templateStore.titleOf(file), spec, "")
                        }
                        s.pendingTemplateUse = null
                    }
                ) { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_use)) }
            },
            dismissButton = {
                TextButton(onClick = { s.pendingTemplateUse = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ImportSection33(s: ImportUiState) {
    if (s.showClearTemplates) {
        AlertDialog(
            onDismissRequest = { s.showClearTemplates = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.import_templates_clear_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.import_templates_clear_body)) },
            confirmButton = {
                TextButton(onClick = {
                    s.savedTemplates.forEach { s.templateStore.delete(it) }
                    s.savedTemplates = s.templateStore.list()
                    s.showClearTemplates = false
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_templates_clear)) }
            },
            dismissButton = {
                TextButton(onClick = { s.showClearTemplates = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ImportSection34(s: ImportUiState) {
    if (s.showClearSamples) {
        AlertDialog(
            onDismissRequest = { s.showClearSamples = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.import_samples_clear_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.import_samples_clear_body)) },
            confirmButton = {
                TextButton(onClick = {
                    s.savedSamples.forEach { s.sampleStore.delete(it) }
                    s.savedSamples = s.sampleStore.list()
                    s.showClearSamples = false
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_samples_clear)) }
            },
            dismissButton = {
                TextButton(onClick = { s.showClearSamples = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ImportSection35(s: ImportUiState) {
    s.pendingDeleteSample?.let { file ->
        AlertDialog(
            onDismissRequest = { s.pendingDeleteSample = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.import_sample_delete)) },
            text = { Text(file.name) },
            confirmButton = {
                TextButton(onClick = {
                    s.sampleStore.delete(file)
                    s.savedSamples = s.sampleStore.list()
                    s.pendingDeleteSample = null
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_sample_delete)) }
            },
            dismissButton = {
                TextButton(onClick = { s.pendingDeleteSample = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ImportSection36(s: ImportUiState) {
    s.pendingDeleteTemplate?.let { file ->
        AlertDialog(
            onDismissRequest = { s.pendingDeleteTemplate = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_delete)) },
            text = { Text(s.templateStore.titleOf(file)) },
            confirmButton = {
                TextButton(onClick = {
                    s.templateStore.delete(file)
                    s.savedTemplates = s.templateStore.list()
                    s.pendingDeleteTemplate = null
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_delete)) }
            },
            dismissButton = {
                TextButton(onClick = { s.pendingDeleteTemplate = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun ImportSection37(s: ImportUiState) {
    if (s.showClearConfirm) {
        AlertDialog(
            onDismissRequest = { s.showClearConfirm = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.import_clear_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.import_clear_body)) },
            confirmButton = {
                TextButton(onClick = { s.clearCurrentImport() }) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.import_clear_action))
                }
            },
            dismissButton = {
                TextButton(onClick = { s.showClearConfirm = false }) {
                    Text(stringResource(android.R.string.cancel))
                }
            }
        )
    }
}


@Composable
private fun ImportTemplateSlotRow(spec: dev.ninfenz.mobile.model.MdSpec, id: String) {
    val slot = spec.slots.firstOrNull { it.id == id }
    val meta = slot?.let {
        it.kind + (if (it.required) " · " + stringResource(dev.ninfenz.mobile.R.string.delivery_slot_required) else "") +
            (it.maxChars?.let { max -> " · max " + max } ?: "") +
            (it.examples.firstOrNull()?.let { example -> " · " + example } ?: "")
    }.orEmpty()
    Text("- " + id + " " + (slot?.name ?: "") + (if (meta.isNotBlank()) "  (" + meta + ")" else ""), style = NfType.meta)
}

@Composable
private fun ImportTemplateBody(spec: dev.ninfenz.mobile.model.MdSpec) {
    Text("v" + spec.version + " · " + spec.sections.size + " sections · " + spec.slots.size + " slots", style = NfType.meta)
    Column(modifier = Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState())) {
        spec.sections.forEach { section ->
            Text(section.title, style = NfType.itemTitle)
            section.slots.forEach { id ->
                ImportTemplateSlotRow(spec, id)
            }
        }
    }
}
