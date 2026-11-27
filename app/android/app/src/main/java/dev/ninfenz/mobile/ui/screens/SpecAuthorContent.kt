package dev.ninfenz.mobile.ui.screens
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.SnackbarResult
import androidx.compose.material3.TextButton
import android.content.Context
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.AiRunStore
import dev.ninfenz.mobile.data.AuthorArtifactStore
import dev.ninfenz.mobile.data.Capability
import dev.ninfenz.mobile.data.CapabilityRegistry
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.data.ExtensionStore
import dev.ninfenz.mobile.data.ContractIrStore
import dev.ninfenz.mobile.data.GraphSnapshotStore
import dev.ninfenz.mobile.data.SourceStore
import dev.ninfenz.mobile.data.SpecSnapshotStore
import dev.ninfenz.mobile.data.AuthorArtifacts
import dev.ninfenz.mobile.data.SaveArtifactResult
import dev.ninfenz.mobile.data.AuthorArtifactsLoader
import dev.ninfenz.mobile.data.AuthorOverlayStore
import dev.ninfenz.mobile.data.ProtocolDraftStore
import dev.ninfenz.mobile.data.ProtocolSnapshotStore
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.SaveOverlayResult
import dev.ninfenz.mobile.model.CcosModel
import dev.ninfenz.mobile.model.MdSpec
import dev.ninfenz.mobile.model.ContextBudget
import dev.ninfenz.mobile.model.GraphEdge
import dev.ninfenz.mobile.model.GraphModel
import dev.ninfenz.mobile.model.GraphNode
import dev.ninfenz.mobile.model.PipelineGraph
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.SpecModel
import dev.ninfenz.mobile.model.SpecSection
import dev.ninfenz.mobile.model.SpecSlot
import dev.ninfenz.mobile.model.ProtocolModel
import dev.ninfenz.mobile.model.ProtocolPack
import dev.ninfenz.mobile.ui.components.NfCard
import dev.ninfenz.mobile.ui.components.NfEmptyState
import dev.ninfenz.mobile.ui.components.FormTextField
import dev.ninfenz.mobile.ui.components.NfErrorCard
import dev.ninfenz.mobile.ui.components.NfLoadingState
import dev.ninfenz.mobile.ui.components.NfSectionHeader
import dev.ninfenz.mobile.ui.components.NfCollapsibleSection
import dev.ninfenz.mobile.ui.components.MarkdownPreview
import dev.ninfenz.mobile.ui.components.NfStatusChip
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.rememberCapabilityRevision
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

@Composable
internal fun SpecAuthorContent(artifacts: AuthorArtifacts, project: Project, onSaved: () -> Unit) {
    val ui = rememberSpecAuthorState(artifacts, project)
    val capabilityRevision = rememberCapabilityRevision()
    fun apply(next: dev.ninfenz.mobile.model.MdSpec) {
        ui.undo.add(ui.spec)
        ui.redo.clear()
        ui.spec = next
    }
    val aiResultPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) {
            ui.scope.launch {
                importAiResult(ui.context, uri, ui.aiRunStore, ui.aiRuns, { ui.aiRuns = it }, { ui.aiNote = it })
            }
        }
    }
    LaunchedEffect(ui.spec, ui.retrySave) {
        specAutoSave(ui.spec, ui.retrySave, ui.store, project, ui.context, onSaved,
            isPrimed = { ui.autoSavePrimed }, onPrimed = { ui.autoSavePrimed = true },
            onAutoSaving = { ui.autoSaving = it }, onSavedMsg = { ui.savedMsg = it }, onError = { ui.error = it })
    }

    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
        SpecAuthorHeader(SpecAuthorHeaderArgs(ui.spec, ui.contractJson, ui.snippets.isNotEmpty(), capabilityRevision, ui.busy, artifacts, ui.contractStore,
            ui.snapshotNote, ui.sourceNote, ui.aiNote, ui.contractNote, ui.snippetNote,
            onShowSnippets = { ui.showSnippets = true }, onReloadSnapshots = { ui.snapshots = ui.snapshotStore.list(); ui.showSnapshots = true }, onReloadSources = { ui.sources = ui.sourceStore.list(); ui.showSources = true }, onReloadAiRuns = { ui.aiRuns = ui.aiRunStore.list(); ui.showAiRuns = true },
            onBusyChange = { ui.busy = it }, onContractJsonChange = { ui.contractJson = it }, onContractValuesChange = { ui.contractValues = it }, onContractAssignmentsChange = { ui.contractAssignments = it }, onContractExplainChange = { ui.contractExplain = it }, onShowContractExplainChange = { ui.showContractExplain = it }, onContractNoteChange = { ui.contractNote = it }))
        SpecSectionsEditor(ui.spec, onApply = { apply(it) })
        SpecSlotsEditor(ui.spec, ui.contractValues, capabilityRevision, ui.contractStore, onApply = { apply(it) }, onContractValuesChange = { ui.contractValues = it }, onContractNoteChange = { ui.contractNote = it })
        SpecUndoRedo(ui.undo.isNotEmpty(), ui.redo.isNotEmpty(), onUndo = { val previous = ui.undo.removeAt(ui.undo.lastIndex); ui.redo.add(ui.spec); ui.spec = previous }, onRedo = { val next = ui.redo.removeAt(ui.redo.lastIndex); ui.undo.add(ui.spec); ui.spec = next })
        SpecActions(SpecActionsArgs(ui.spec, project, ui.store, ui.busy, ui.report, ui.autoSaving, ui.savedMsg, ui.error, onBusyChange = { ui.busy = it }, onErrorChange = { ui.error = it }, onReportChange = { ui.report = it }, onSavedMsgChange = { ui.savedMsg = it }, onSaved = onSaved, onRetry = { ui.retrySave++ }))
    }
    if (ui.showSnippets) SpecSnippetsDialog(ui.snippets, ui.spec, onApply = { section, newSlots -> apply(ui.spec.copy(sections = ui.spec.sections + section, slots = ui.spec.slots + newSlots)) }, onNote = { ui.snippetNote = it }) { ui.showSnippets = false }
    if (ui.showSnapshots) SpecSnapshotsDialog(ui.snapshots, ui.spec, ui.snapshotStore, onSnapshotsChange = { ui.snapshots = it }, onApply = { apply(it) }, onNote = { ui.snapshotNote = it }) { ui.showSnapshots = false }
    if (ui.showContractExplain) SpecContractExplainDialog(ui.contractAssignments, ui.contractExplain) { ui.showContractExplain = false }
    if (ui.showSources) SpecSourcesDialog(ui.sources, ui.sourceStore, onSourcesChange = { ui.sources = it }, onNote = { ui.sourceNote = it }) { ui.showSources = false }
    if (ui.showAiRuns) SpecAiRunsDialog(SpecAiRunsDialogArgs(ui.aiRuns, ui.aiRunStore, ui.spec, ui.sources, project, ui.busy, onBusyChange = { ui.busy = it }, onAiRunsChange = { ui.aiRuns = it }, onNote = { ui.aiNote = it }, onImportResult = { aiResultPicker.launch(arrayOf("application/json", "text/plain")) }, onDismiss = { ui.showAiRuns = false }))
}

internal class SpecAuthorUiState(
    val context: android.content.Context,
    val project: Project,
    val scope: kotlinx.coroutines.CoroutineScope,
    val store: AuthorArtifactStore,
    val snippets: List<ExtensionStore.Contribution>,
    val snapshotStore: SpecSnapshotStore,
    val contractStore: ContractIrStore,
    val sourceStore: SourceStore,
    val aiRunStore: AiRunStore,
    initialSpec: dev.ninfenz.mobile.model.MdSpec
) {
    var spec by mutableStateOf(initialSpec)
    val undo = mutableStateListOf<dev.ninfenz.mobile.model.MdSpec>()
    val redo = mutableStateListOf<dev.ninfenz.mobile.model.MdSpec>()
    var report by mutableStateOf<String?>(null)
    var error by mutableStateOf<CoreError?>(null)
    var busy by mutableStateOf(false)
    var savedMsg by mutableStateOf<String?>(null)
    var contractValues by mutableStateOf(contractStore.loadValues())
    var aiRuns by mutableStateOf(aiRunStore.list())
    var showAiRuns by mutableStateOf(false)
    var aiNote by mutableStateOf<String?>(null)
    var contractNote by mutableStateOf<String?>(null)
    var contractJson by mutableStateOf(contractStore.load())
    var contractExplain by mutableStateOf<List<String>>(emptyList())
    var contractAssignments by mutableStateOf<Map<String, String>>(emptyMap())
    var showContractExplain by mutableStateOf(false)
    var sources by mutableStateOf(sourceStore.list())
    var showSources by mutableStateOf(false)
    var sourceNote by mutableStateOf<String?>(null)
    var snapshots by mutableStateOf(snapshotStore.list())
    var showSnapshots by mutableStateOf(false)
    var snapshotNote by mutableStateOf<String?>(null)
    var showSnippets by mutableStateOf(false)
    var snippetNote by mutableStateOf<String?>(null)
    var autoSavePrimed by mutableStateOf(false)
    var autoSaving by mutableStateOf(false)
    var retrySave by mutableIntStateOf(0)
}

internal suspend fun validateSpec(
    context: android.content.Context,
    spec: MdSpec,
    onBusyChange: (Boolean) -> Unit,
    onErrorChange: (CoreError?) -> Unit,
    onReportChange: (String?) -> Unit
) {
    val response = safeCall("spec-validate", buildJsonObject { put("spec", SpecModel.toJson(spec)) })
    if (response.ok) onReportChange(summarizeReport(context, response)) else onErrorChange(response.error)
    onBusyChange(false)
}

internal suspend fun saveSpecArtifact(
    context: android.content.Context,
    store: AuthorArtifactStore,
    project: Project,
    spec: MdSpec,
    onBusyChange: (Boolean) -> Unit,
    onErrorChange: (CoreError?) -> Unit,
    onSavedMsgChange: (String?) -> Unit,
    onSaved: () -> Unit
) {
    when (val result = store.saveSpec(project, spec)) {
        is SaveArtifactResult.Saved -> {
            onSavedMsgChange(context.getString(dev.ninfenz.mobile.R.string.author_saved_artifact, result.path, result.sha256.take(12)))
            onSaved()
        }
        is SaveArtifactResult.Failure -> onErrorChange(CoreError(result.code, result.message, result.fix, null, 1))
    }
    onBusyChange(false)
}

// ---- restored helpers (reconstructed after accidental truncation) ----

internal data class Snapshot(val values: Map<String, String>, val enabled: Map<String, Boolean>)

internal fun computeImportPrefill(context: Context, project: Project): Map<String, String> = runCatching {
    val dir = dev.ninfenz.mobile.data.ProjectPaths.authoringDir(context.filesDir, project.id)
    val file = dir.listFiles()?.firstOrNull { it.isFile && it.name.startsWith("import-") } ?: return@runCatching emptyMap()
    dev.ninfenz.mobile.data.ImportPrefill.fromJson(file.readText(Charsets.UTF_8))
}.getOrDefault(emptyMap())

internal fun computeZeroSlicePrefill(context: Context, project: Project): Map<String, String> = runCatching {
    val dir = dev.ninfenz.mobile.data.ProjectPaths.authoringDir(context.filesDir, project.id)
    val file = dir.resolve("zero-slice.json")
    dev.ninfenz.mobile.data.ZeroSliceStore(context.filesDir).read(file)?.slotValues ?: emptyMap()
}.getOrDefault(emptyMap())

internal fun computeTemplatePrefill(context: Context, project: Project, protocol: ProtocolPack): Map<String, String> = runCatching {
    val file = dev.ninfenz.mobile.data.ProjectPaths.templateMd(context.filesDir, project.id)
    if (!file.isFile) return@runCatching emptyMap<String, String>()
    val byName = dev.ninfenz.mobile.data.TemplateProtocolPrefill.parse(file.readText(Charsets.UTF_8))
    protocol.fields.mapNotNull { field ->
        val value = byName[field.label]?.takeIf { it.isNotBlank() } ?: return@mapNotNull null
        val allowed = when {
            field.type == "enum" -> value in field.options
            field.maxLen != null && value.length > field.maxLen -> false
            field.pattern != null && !runCatching { Regex(field.pattern).matches(value) }.getOrDefault(false) -> false
            else -> true
        }
        if (allowed) field.id to value else null
    }.toMap()
}.getOrDefault(emptyMap())

internal fun summarizeReport(context: Context, response: CoreResponse): String {
    val result = response.resultObject()
    val verdict = result?.get("verdict")?.jsonPrimitive?.content ?: "pass"
    val summary = result?.get("summary")?.toString() ?: ""
    val issues = result?.get("issues")?.let { if (it is JsonArray) it.size else 0 } ?: 0
    val line = context.getString(dev.ninfenz.mobile.R.string.author_validate_result, verdict, issues)
    return line + (if (summary.isNotBlank()) " · " + summary else "")
}

@Composable
internal fun ProtocolAuthorHeader(
    protocol: ProtocolPack,
    snippetsNotEmpty: Boolean,
    prefillCount: Int,
    onShowClauseLibrary: () -> Unit,
    onShowSnapshots: () -> Unit
) {
    if (prefillCount > 0) {
        Text(
            pluralStringResource(dev.ninfenz.mobile.R.plurals.author_import_prefill, prefillCount, prefillCount),
            style = NfType.meta,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.padding(horizontal = NfSpacing.page)
        )
    }
    Row(verticalAlignment = Alignment.CenterVertically) {
        NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.author_clauses, protocol.clauses.size))
        if (snippetsNotEmpty) {
            TextButton(onClick = onShowClauseLibrary) {
                Text(stringResource(dev.ninfenz.mobile.R.string.author_clause_library))
            }
        }
        TextButton(onClick = onShowSnapshots) {
            Text(stringResource(dev.ninfenz.mobile.R.string.author_protocol_snapshot))
        }
    }
}

@Composable
internal fun ProtocolClauseList(
    protocol: ProtocolPack,
    values: Map<String, String>,
    enabled: Map<String, Boolean>,
    onValuesChange: (Map<String, String>) -> Unit,
    onEnabledChange: (Map<String, Boolean>) -> Unit,
    onPushUndo: () -> Unit
) {
    for (clause in protocol.clauses) {
        NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(clause.id + " · " + clause.title, style = NfType.itemTitle, modifier = Modifier.weight(1f))
                    NfStatusChip(clause.level)
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.author_enable), style = NfType.meta, modifier = Modifier.weight(1f))
                    Switch(
                        checked = enabled[clause.id] ?: clause.enabled,
                        onCheckedChange = { checked ->
                            onPushUndo()
                            onEnabledChange(enabled + (clause.id to checked))
                        }
                    )
                }
                Text(clause.text, style = NfType.secondary)
                val check = ProtocolModel.checkClause(protocol, clause, values)
                if (!check.ok) {
                    if (check.missing.isNotEmpty()) Text(stringResource(dev.ninfenz.mobile.R.string.author_missing, check.missing.joinToString(", ")), style = NfType.meta, color = MaterialTheme.colorScheme.error)
                    if (check.unknown.isNotEmpty()) Text(stringResource(dev.ninfenz.mobile.R.string.author_unknown, check.unknown.joinToString(", ")), style = NfType.meta, color = MaterialTheme.colorScheme.error)
                }
                for (field in protocol.fields.filter { it.clause == clause.id }) {
                    Column {
                        Text(field.id + " · " + field.label + (if (field.required) stringResource(dev.ninfenz.mobile.R.string.author_required) else ""), style = NfType.label)
                        OutlinedTextField(
                            value = values[field.id] ?: "",
                            onValueChange = { text ->
                                onPushUndo()
                                onValuesChange(values + (field.id to text))
                            },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                }
            }
        }
    }
}

@Composable
internal fun ProtocolSaveBar(
    undoSize: Int,
    saving: Boolean,
    saveMessage: String?,
    saveError: String?,
    onUndo: () -> Unit,
    onSave: () -> Unit
) {
    Row(
        modifier = Modifier.padding(horizontal = NfSpacing.page),
        horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
    ) {
        OutlinedButton(enabled = undoSize > 0 && !saving, onClick = onUndo) { Text(stringResource(dev.ninfenz.mobile.R.string.author_undo)) }
        Button(enabled = !saving, onClick = onSave) { Text(if (saving) stringResource(dev.ninfenz.mobile.R.string.author_saving) else stringResource(dev.ninfenz.mobile.R.string.author_save)) }
    }
    saveMessage?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
    saveError?.let { message ->
        NfErrorCard("NF-PCK-003", message, stringResource(dev.ninfenz.mobile.R.string.author_diag_fix), modifier = Modifier.padding(horizontal = NfSpacing.page))
    }
}
