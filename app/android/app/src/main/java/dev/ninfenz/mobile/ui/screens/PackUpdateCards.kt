package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.util.orNullLogged
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.Capability
import dev.ninfenz.mobile.data.CapabilityRegistry
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.data.LibraryStore
import dev.ninfenz.mobile.data.BackupRestoreService
import dev.ninfenz.mobile.data.BackupService
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.PackStore
import dev.ninfenz.mobile.data.PackZipLoader
import dev.ninfenz.mobile.model.ConflictBoard
import dev.ninfenz.mobile.model.PackUpdate
import dev.ninfenz.mobile.model.PackUpdateModel
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.components.EmptyState
import dev.ninfenz.mobile.ui.components.ErrorNotice
import dev.ninfenz.mobile.ui.components.KeyValue
import dev.ninfenz.mobile.ui.components.MonoText
import dev.ninfenz.mobile.ui.components.NfScaffold
import dev.ninfenz.mobile.ui.components.Notice
import dev.ninfenz.mobile.ui.rememberCapabilityRevision
import dev.ninfenz.mobile.ui.components.Tone
import dev.ninfenz.mobile.ui.design.NfType
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.io.File

@Composable
internal fun PackUpdateMatrixCard(s: PackUpdateState, onOpenProject: (String) -> Unit) {
        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.pack_matrix_title)) {
            if (s.packs.isEmpty()) {
                Text(stringResource(dev.ninfenz.mobile.R.string.pack_matrix_empty), style = NfType.meta)
            } else {
                s.packs.groupBy { it.id }.toSortedMap().forEach { (packId, versions) ->
                    versions.sortedByDescending { it.version }.forEach { pack ->
                        val refs = s.matrixProjects.filter {
                            it.project.refs.basePackId == packId && it.project.refs.basePackVersion == pack.version
                        }
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.pack_matrix_line, packId, pack.version, refs.size),
                            style = NfType.secondary
                        )
                        if (refs.isNotEmpty()) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.pack_matrix_projects), style = NfType.meta)
                            for (entry in refs) {
                                TextButton(onClick = { onOpenProject(entry.project.id) }) {
                                    Text(entry.project.title)
                                }
                            }
                        }
                    }
                }
            }
        }
}

@Composable
internal fun PackUpdatePlanCard(s: PackUpdateState, onOpenProject: (String) -> Unit, onPickZip: () -> Unit, onPickPlan: () -> Unit) {
    CardBox(title = stringResource(dev.ninfenz.mobile.R.string.packupdate_step1)) {
        PackUpdatePlanPicker(s, onPickZip, onPickPlan)
        PackUpdatePlanDetails(s, onOpenProject)
    }
}

@Composable
private fun PackUpdatePlanPicker(s: PackUpdateState, onPickZip: () -> Unit, onPickPlan: () -> Unit) {
    if (s.packs.isEmpty()) {
        EmptyState(stringResource(dev.ninfenz.mobile.R.string.packupdate_no_packs))
    } else {
        Text(stringResource(dev.ninfenz.mobile.R.string.packupdate_select_base), style = NfType.meta)
        for (pack in s.packs) {
            FilterChip(
                selected = s.selected?.id == pack.id && s.selected?.version == pack.version,
                onClick = { s.selected = pack; s.update = null; s.rawUpdate = null; s.resultText = null },
                label = { Text(pack.id + " · " + pack.version) },
                modifier = Modifier.padding(end = 8.dp)
            )
        }
        FlowRow(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Button(onClick = { onPickZip() }, enabled = !s.diffBusy) {
                Text(if (s.diffBusy) stringResource(dev.ninfenz.mobile.R.string.packupdate_compare) else stringResource(dev.ninfenz.mobile.R.string.packupdate_choose_zip))
            }
            OutlinedButton(onClick = { onPickPlan() }) { Text(stringResource(dev.ninfenz.mobile.R.string.pack_update_open_plan)) }
        }
        s.selected?.let { Text(stringResource(dev.ninfenz.mobile.R.string.packupdate_base, it.id, it.version, it.dir.absolutePath), style = NfType.meta) }
        s.newRoot?.let { Text(stringResource(dev.ninfenz.mobile.R.string.packupdate_new, it.absolutePath), style = NfType.meta) }
        if (s.selected != null && s.newRoot == null) {
            Notice(stringResource(dev.ninfenz.mobile.R.string.packupdate_hint), Tone.INFO)
        }
    }
}

@Composable
private fun PackUpdatePlanDetails(s: PackUpdateState, onOpenProject: (String) -> Unit) {
    val u = s.update
    if (u != null) {
        KeyValue("from", u.from.id + " " + u.from.version)
        KeyValue("to", u.to.id + " " + u.to.version)
        KeyValue("changes", "added " + u.added.size + " · removed " + u.removed.size + " · modified " + u.modified.size)
        KeyValue("breaking", if (u.breaking) stringResource(dev.ninfenz.mobile.R.string.packupdate_breaking_yes) else stringResource(dev.ninfenz.mobile.R.string.packupdate_breaking_no))
        KeyValue(stringResource(dev.ninfenz.mobile.R.string.pack_update_affected_projects), if (u.affectedProjects.isEmpty()) stringResource(dev.ninfenz.mobile.R.string.packupdate_none) else u.affectedProjects.joinToString(","))
        PackUpdateAffectedProjects(u, onOpenProject)
        KeyValue(stringResource(dev.ninfenz.mobile.R.string.pack_update_overlay_keys), if (u.overlayKeys.isEmpty()) stringResource(dev.ninfenz.mobile.R.string.packupdate_none) else u.overlayKeys.joinToString(","))
        for (note in u.notes) Notice(note, Tone.WARN)
    }
}

@Composable
private fun PackUpdateAffectedProjects(u: PackUpdate, onOpenProject: (String) -> Unit) {
    if (u.breaking && u.affectedProjects.isNotEmpty()) {
        Notice(stringResource(dev.ninfenz.mobile.R.string.packupdate_affected_warning, u.affectedProjects.size), Tone.WARN)
    }
    if (u.affectedProjects.isNotEmpty()) {
        FlowRow(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            for (projectId in u.affectedProjects) {
                OutlinedButton(onClick = { onOpenProject(projectId) }) { Text(projectId) }
            }
        }
    }
}

@Composable
internal fun PackUpdateChangesCard(s: PackUpdateState, u: PackUpdate) {
            CardBox(title = stringResource(dev.ninfenz.mobile.R.string.packupdate_changes)) {
                val limit = 50
                for (c in u.added.take(limit)) Text("+ " + c.path, style = NfType.meta)
                for (c in u.removed.take(limit)) Text("- " + c.path, style = NfType.meta)
                for (c in u.modified.take(limit)) Text("~ " + c.path, style = NfType.meta)
                val hidden = (u.added.size - limit).coerceAtLeast(0) +
                    (u.removed.size - limit).coerceAtLeast(0) +
                    (u.modified.size - limit).coerceAtLeast(0)
                if (hidden > 0) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.packupdate_more_changes, hidden), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                if (u.totalChanges == 0) EmptyState(stringResource(dev.ninfenz.mobile.R.string.packupdate_no_changes))
            }
}

@Composable
internal fun PackUpdateConflictsCard(s: PackUpdateState, u: PackUpdate) {
            CardBox(title = stringResource(dev.ninfenz.mobile.R.string.packupdate_conflicts)) {
                if (u.conflicts.isEmpty()) {
                    Notice(stringResource(dev.ninfenz.mobile.R.string.packupdate_no_conflicts), Tone.INFO)
                } else {
                    for (conflict in u.conflicts) {
                        Column(modifier = Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(conflict.id + " · " + conflict.kind + " · " + conflict.path, style = NfType.secondary)
                            Text("options=" + conflict.options.joinToString("/") + " · default=" + conflict.defaultOption,
                                style = NfType.meta)
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                for (option in conflict.options) {
                                    FilterChip(
                                        selected = (s.decisions[conflict.id] ?: conflict.defaultOption) == option,
                                        onClick = { s.decisions = s.decisions + (conflict.id to option) },
                                        label = { Text(option) }
                                    )
                                }
                            }
                        }
                    }
                    val unresolved = u.conflicts.filter { (s.decisions[it.id] ?: it.defaultOption) == "defer" }
                    if (unresolved.isEmpty()) {
                        Notice(stringResource(dev.ninfenz.mobile.R.string.packupdate_all_decided, u.conflicts.size), Tone.INFO)
                    } else {
                        Notice(pluralStringResource(dev.ninfenz.mobile.R.plurals.packupdate_unresolved, unresolved.size, unresolved.size), Tone.ERROR)
                    }
                }
            }
}

