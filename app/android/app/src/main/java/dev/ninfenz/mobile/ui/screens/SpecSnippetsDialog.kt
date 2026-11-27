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
internal fun SpecSectionsEditor(spec: MdSpec, onApply: (MdSpec) -> Unit) {
    for (section in spec.sections) {
        NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                Text(section.id + " · order=" + section.order, style = NfType.meta)
                FormTextField(
                    label = stringResource(dev.ninfenz.mobile.R.string.author_section_title),
                    value = section.title,
                    onValueChange = { newTitle ->
                        onApply(spec.copy(sections = spec.sections.map { if (it.id == section.id) it.copy(title = newTitle) else it }))
                    }
                )
                Text(
                    stringResource(
                        dev.ninfenz.mobile.R.string.author_order,
                        section.order,
                        if (section.required) stringResource(dev.ninfenz.mobile.R.string.author_required_label) else stringResource(dev.ninfenz.mobile.R.string.author_optional_label),
                        section.slots.joinToString(",")
                    ),
                    style = NfType.meta,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
internal fun SpecSlotsEditor(
    spec: MdSpec,
    contractValues: Map<String, String>,
    capabilityRevision: Int,
    contractStore: ContractIrStore,
    onApply: (MdSpec) -> Unit,
    onContractValuesChange: (Map<String, String>) -> Unit,
    onContractNoteChange: (String) -> Unit
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.author_slots, spec.slots.size))
    for (slot in spec.slots) {
        NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                Text(slot.id + " · " + slot.kind + (if (slot.required) " · " + stringResource(dev.ninfenz.mobile.R.string.author_required_label) else ""), style = NfType.meta)
                FormTextField(
                    label = stringResource(dev.ninfenz.mobile.R.string.author_slot_name),
                    value = slot.name,
                    onValueChange = { newName ->
                        onApply(spec.copy(slots = spec.slots.map { if (it.id == slot.id) it.copy(name = newName) else it }))
                    }
                )
                if (capabilityRevision >= 0 && CapabilityRegistry.isEnabled(Capability.CONTRACT)) {
                    FormTextField(
                        label = stringResource(dev.ninfenz.mobile.R.string.author_contract_value),
                        value = contractValues[slot.id].orEmpty(),
                        onValueChange = { value -> onContractValuesChange(contractValues + (slot.id to value)) }
                    )
                    TextButton(onClick = {
                        contractStore.saveValues(contractValues)
                        onContractValuesChange(contractStore.loadValues())
                        onContractNoteChange(context.getString(dev.ninfenz.mobile.R.string.author_contract_values_saved))
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_contract_values_save)) }
                }
            }
        }
    }
}

@Composable
internal fun SpecUndoRedo(canUndo: Boolean, canRedo: Boolean, onUndo: () -> Unit, onRedo: () -> Unit) {
    Row(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
        TextButton(enabled = canUndo, onClick = onUndo) { Text(stringResource(dev.ninfenz.mobile.R.string.author_undo)) }
        TextButton(enabled = canRedo, onClick = onRedo) { Text(stringResource(dev.ninfenz.mobile.R.string.author_redo)) }
    }
}

internal data class SpecActionsArgs(
    val spec: MdSpec,
    val project: Project,
    val store: AuthorArtifactStore,
    val busy: Boolean,
    val report: String?,
    val autoSaving: Boolean,
    val savedMsg: String?,
    val error: CoreError?,
    val onBusyChange: (Boolean) -> Unit,
    val onErrorChange: (CoreError?) -> Unit,
    val onReportChange: (String?) -> Unit,
    val onSavedMsgChange: (String?) -> Unit,
    val onSaved: () -> Unit,
    val onRetry: () -> Unit,
)

@Composable
internal fun SpecActions(args: SpecActionsArgs) = with(args) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val scope = rememberCoroutineScope()
    if (dev.ninfenz.mobile.data.FeatureGate.auditEnabled()) {
        Button(
            enabled = !busy,
            modifier = Modifier.padding(horizontal = NfSpacing.page),
            onClick = {
                onBusyChange(true)
                onErrorChange(null)
                onReportChange(null)
                scope.launch { validateSpec(context, spec, onBusyChange, onErrorChange, onReportChange) }
            }
        ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.author_validating) else stringResource(dev.ninfenz.mobile.R.string.author_validate_spec)) }
    }
    Button(
        enabled = !busy,
        modifier = Modifier.padding(horizontal = NfSpacing.page),
        onClick = {
            onBusyChange(true)
            onErrorChange(null)
            onSavedMsgChange(null)
            scope.launch { saveSpecArtifact(context, store, project, spec, onBusyChange, onErrorChange, onSavedMsgChange, onSaved) }
        }
    ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.author_saving_artifact) else stringResource(dev.ninfenz.mobile.R.string.author_save_spec)) }
    report?.let { text -> Text(text, style = NfType.secondary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
    if (autoSaving) {
        Text(stringResource(dev.ninfenz.mobile.R.string.author_autosave_saving), style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page))
    }
    savedMsg?.let { text -> Text(text, style = NfType.secondary, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
    error?.let { err ->
        NfErrorCard(err.code, err.message, err.fix, modifier = Modifier.padding(horizontal = NfSpacing.page))
        TextButton(onClick = onRetry, modifier = Modifier.padding(horizontal = NfSpacing.page)) {
            Text(stringResource(dev.ninfenz.mobile.R.string.author_retry_save))
        }
    }
}

@Composable
internal fun SpecSnippetsDialog(
    snippets: List<ExtensionStore.Contribution>,
    spec: MdSpec,
    onApply: (dev.ninfenz.mobile.model.SpecSection, List<dev.ninfenz.mobile.model.SpecSlot>) -> Unit,
    onNote: (String?) -> Unit,
    onDismiss: () -> Unit
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(dev.ninfenz.mobile.R.string.author_snippet)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                snippets.forEach { snippet ->
                    TextButton(onClick = {
                        val sec = J.optChild(snippet.config, "section")
                        val id = sec?.let { J.optString(it, "id") }.orEmpty()
                        val slotIds = sec?.let { J.optArray(it, "slots") }
                            ?.mapNotNull { (it as? kotlinx.serialization.json.JsonPrimitive)?.content }.orEmpty()
                        val newSlots = J.optArray(snippet.config, "slots").mapNotNull { el ->
                            val o = el as? JsonObject ?: return@mapNotNull null
                            val sid = J.optString(o, "id").orEmpty()
                            if (sid.isBlank()) return@mapNotNull null
                            dev.ninfenz.mobile.model.SpecSlot(
                                id = sid,
                                name = J.optString(o, "name").orEmpty().ifBlank { sid },
                                section = id,
                                kind = J.optString(o, "kind").orEmpty().ifBlank { "text" },
                                required = o["required"]?.jsonPrimitive?.content?.toBooleanStrictOrNull() ?: false
                            )
                        }
                        if (id.isBlank() || slotIds.isEmpty() || spec.sections.any { it.id == id } || newSlots.any { ns -> spec.slots.any { it.id == ns.id } }) {
                            onNote(context.getString(dev.ninfenz.mobile.R.string.author_snippet_conflict))
                        } else {
                            val nextOrder = (spec.sections.maxOfOrNull { it.order } ?: 0) + 1
                            val section = dev.ninfenz.mobile.model.SpecSection(id, sec?.let { J.optString(it, "title") } ?: id, nextOrder, true, slotIds)
                            onApply(section, newSlots)
                            onNote(context.getString(dev.ninfenz.mobile.R.string.author_snippet_applied, id))
                            onDismiss()
                        }
                    }) { Text(snippet.id) }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) } }
    )
}

@Composable
internal fun SpecSnapshotsDialog(
    snapshots: List<SpecSnapshotStore.Snapshot>,
    spec: MdSpec,
    snapshotStore: SpecSnapshotStore,
    onSnapshotsChange: (List<SpecSnapshotStore.Snapshot>) -> Unit,
    onApply: (MdSpec) -> Unit,
    onNote: (String?) -> Unit,
    onDismiss: () -> Unit
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(dev.ninfenz.mobile.R.string.author_snapshot)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                TextButton(onClick = {
                    onSnapshotsChange(snapshotStore.save(spec))
                    onNote(context.getString(dev.ninfenz.mobile.R.string.author_snapshot_save))
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_snapshot_save)) }
                if (snapshots.isEmpty()) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.author_snapshot_empty), style = NfType.meta)
                } else {
                    snapshots.take(10).forEach { snapshot ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                stringResource(
                                    dev.ninfenz.mobile.R.string.author_snapshot_meta,
                                    snapshot.sections,
                                    snapshot.slots,
                                    java.text.SimpleDateFormat("MM-dd HH:mm", java.util.Locale.getDefault()).format(java.util.Date(snapshot.at))
                                ),
                                style = NfType.meta,
                                modifier = Modifier.weight(1f)
                            )
                            TextButton(onClick = {
                                onApply(snapshotStore.restore(snapshot))
                                onNote(context.getString(dev.ninfenz.mobile.R.string.author_snapshot_restored))
                                onDismiss()
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_snapshot_restore)) }
                            TextButton(onClick = {
                                snapshotStore.remove(snapshot.id)
                                onSnapshotsChange(snapshotStore.list())
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.inbox_remove)) }
                        }
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) } }
    )
}

@Composable
internal fun SpecContractExplainDialog(
    contractAssignments: Map<String, String>,
    contractExplain: List<String>,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(dev.ninfenz.mobile.R.string.author_contract_explain_title)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                if (contractAssignments.isNotEmpty()) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.author_contract_assignments), style = NfType.label)
                    contractAssignments.toSortedMap().forEach { (key, value) ->
                        Text(key + " = " + value, style = NfType.meta)
                    }
                }
                if (contractExplain.isEmpty()) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.author_contract_explain_empty), style = NfType.meta)
                }
                contractExplain.forEach { line -> Text(line, style = NfType.meta) }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.ok)) } }
    )
}
