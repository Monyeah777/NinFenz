package dev.ninfenz.mobile.ui.screens

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
import dev.ninfenz.mobile.ui.components.Tone
import dev.ninfenz.mobile.ui.design.NfType
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.io.File

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun PackUpdateScreen(store: LibraryStore, onBack: () -> Unit, onOpenProject: (String) -> Unit = {}) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var update by remember { mutableStateOf<PackUpdate?>(null) }
    var rawUpdate by remember { mutableStateOf<JsonObject?>(null) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var decisions by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    var resultText by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var packs by remember { mutableStateOf<List<PackEntry>>(emptyList()) }
    var matrixProjects by remember { mutableStateOf<List<dev.ninfenz.mobile.data.ProjectEntry>>(emptyList()) }
    var selected by remember { mutableStateOf<PackEntry?>(null) }
    var newRoot by remember { mutableStateOf<File?>(null) }
    var diffBusy by remember { mutableStateOf(false) }
    var preUpdateBackup by remember { mutableStateOf<File?>(null) }
    var installedUpdateTarget by remember { mutableStateOf<File?>(null) }
    var showRollbackBackup by remember { mutableStateOf(false) }
    var backupRollbackMessage by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        packs = withContext(Dispatchers.IO) { PackStore(context.filesDir).scan().packs }
        matrixProjects = withContext(Dispatchers.IO) { store.loadProjects().projects }
        selected = packs.firstOrNull()
    }

    fun runDiff(oldPack: PackEntry?, root: File?) {
        if (oldPack == null || root == null || diffBusy) return
        scope.launch {
            diffBusy = true
            error = null
            try {
                val payload = buildJsonObject {
                    put("old_root", oldPack.dir.absolutePath)
                    put("new_root", root.absolutePath)
                }
                val response = safeCall("pack-diff", payload)
                val obj = response.resultObject()
                if (response.ok && obj != null) {
                    val parsed = PackUpdateModel.parse(obj)
                    update = parsed
                    rawUpdate = obj
                    decisions = parsed.conflicts.associate { it.id to it.defaultOption }
                    resultText = null
                } else {
                    error = response.error
                }
            } catch (e: Exception) {
                error = CoreResponse.failure(
                    "NF-PCK-001",
                    context.getString(dev.ninfenz.mobile.R.string.pack_update_diff_failed, e.message ?: e.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.pack_update_diff_failed_fix),
                    1
                ).error
            } finally {
                diffBusy = false
            }
        }
    }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val text = FileAccess.readText(context, uri)
                val obj = J.parseObject(text, "nf-pack-update/1")
                val parsed = PackUpdateModel.parse(obj)
                update = parsed
                rawUpdate = obj
                decisions = parsed.conflicts.associate { it.id to it.defaultOption }
                error = null
                resultText = null
            } catch (e: Exception) {
                error = CoreResponse.failure(
                    "NF-PCK-001",
                    context.getString(dev.ninfenz.mobile.R.string.pack_update_plan_failed, e.message ?: e.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.pack_update_plan_failed_fix),
                    1
                ).error
            }
        }
    }

    val zipPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            error = null
            try {
                val meta = FileAccess.meta(context, uri)
                val zip = FileAccess.copyToCache(context, uri, meta.name)
                val dest = File(context.cacheDir, "new-pack")
                val root = withContext(Dispatchers.IO) { PackZipLoader.extract(zip, dest) }
                newRoot = root
                runDiff(selected, root)
            } catch (e: Exception) {
                error = CoreResponse.failure(
                    "NF-PCK-002",
                    context.getString(dev.ninfenz.mobile.R.string.pack_update_extract_failed, e.message ?: e.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.pack_update_extract_failed_fix),
                    1
                ).error
            }
        }
    }

    fun packDir(id: String, version: String): File = File(File(File(context.filesDir, "library/packs"), id), version)

    NfScaffold(title = stringResource(dev.ninfenz.mobile.R.string.packupdate_title), onBack = onBack) {
        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.pack_matrix_title)) {
            if (packs.isEmpty()) {
                Text(stringResource(dev.ninfenz.mobile.R.string.pack_matrix_empty), style = NfType.meta)
            } else {
                packs.groupBy { it.id }.toSortedMap().forEach { (packId, versions) ->
                    versions.sortedByDescending { it.version }.forEach { pack ->
                        val refs = matrixProjects.filter {
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

        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.packupdate_step1)) {
            if (packs.isEmpty()) {
                EmptyState(stringResource(dev.ninfenz.mobile.R.string.packupdate_no_packs))
            } else {
                Text(stringResource(dev.ninfenz.mobile.R.string.packupdate_select_base), style = NfType.meta)
                for (pack in packs) {
                    FilterChip(
                        selected = selected?.id == pack.id && selected?.version == pack.version,
                        onClick = { selected = pack; update = null; rawUpdate = null; resultText = null },
                        label = { Text(pack.id + " · " + pack.version) },
                        modifier = Modifier.padding(end = 8.dp)
                    )
                }
                FlowRow(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Button(onClick = { zipPicker.launch(arrayOf("application/zip", "application/octet-stream", "*/*")) }, enabled = !diffBusy) {
                        Text(if (diffBusy) stringResource(dev.ninfenz.mobile.R.string.packupdate_compare) else stringResource(dev.ninfenz.mobile.R.string.packupdate_choose_zip))
                    }
                    OutlinedButton(onClick = { picker.launch(arrayOf("application/json", "text/plain")) }) { Text(stringResource(dev.ninfenz.mobile.R.string.pack_update_open_plan)) }
                }
                selected?.let { Text(stringResource(dev.ninfenz.mobile.R.string.packupdate_base, it.id, it.version, it.dir.absolutePath), style = NfType.meta) }
                newRoot?.let { Text(stringResource(dev.ninfenz.mobile.R.string.packupdate_new, it.absolutePath), style = NfType.meta) }
                if (selected != null && newRoot == null) {
                    Notice(stringResource(dev.ninfenz.mobile.R.string.packupdate_hint), Tone.INFO)
                }
            }
            val u = update
            if (u != null) {
                KeyValue("from", u.from.id + " " + u.from.version)
                KeyValue("to", u.to.id + " " + u.to.version)
                KeyValue("changes", "added " + u.added.size + " · removed " + u.removed.size + " · modified " + u.modified.size)
                KeyValue("breaking", if (u.breaking) stringResource(dev.ninfenz.mobile.R.string.packupdate_breaking_yes) else stringResource(dev.ninfenz.mobile.R.string.packupdate_breaking_no))
                KeyValue(stringResource(dev.ninfenz.mobile.R.string.pack_update_affected_projects), if (u.affectedProjects.isEmpty()) stringResource(dev.ninfenz.mobile.R.string.packupdate_none) else u.affectedProjects.joinToString(","))
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
                KeyValue(stringResource(dev.ninfenz.mobile.R.string.pack_update_overlay_keys), if (u.overlayKeys.isEmpty()) stringResource(dev.ninfenz.mobile.R.string.packupdate_none) else u.overlayKeys.joinToString(","))
                for (note in u.notes) Notice(note, Tone.WARN)
            }
        }

        error?.let { ErrorNotice(it) }

        val u = update
        if (u != null) {
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
                                        selected = (decisions[conflict.id] ?: conflict.defaultOption) == option,
                                        onClick = { decisions = decisions + (conflict.id to option) },
                                        label = { Text(option) }
                                    )
                                }
                            }
                        }
                    }
                    val unresolved = u.conflicts.filter { (decisions[it.id] ?: it.defaultOption) == "defer" }
                    if (unresolved.isEmpty()) {
                        Notice(stringResource(dev.ninfenz.mobile.R.string.packupdate_all_decided, u.conflicts.size), Tone.INFO)
                    } else {
                        Notice(pluralStringResource(dev.ninfenz.mobile.R.plurals.packupdate_unresolved, unresolved.size, unresolved.size), Tone.ERROR)
                    }
                }
            }

            CardBox(title = stringResource(dev.ninfenz.mobile.R.string.packupdate_apply_rollback)) {
                val base = selected?.dir ?: packDir(u.from.id, u.from.version)
                val target = newRoot ?: packDir(u.to.id, u.to.version)
                KeyValue(stringResource(dev.ninfenz.mobile.R.string.packupdate_base_dir), if (base.exists()) stringResource(dev.ninfenz.mobile.R.string.packupdate_present) else stringResource(dev.ninfenz.mobile.R.string.packupdate_missing, base.absolutePath))
                KeyValue(stringResource(dev.ninfenz.mobile.R.string.packupdate_new_dir), if (target.exists()) stringResource(dev.ninfenz.mobile.R.string.packupdate_present) else stringResource(dev.ninfenz.mobile.R.string.packupdate_missing, target.absolutePath))
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        enabled = !busy && base.exists() && target.exists() && u.conflicts.all { (decisions[it.id] ?: it.defaultOption) != "defer" },
                        onClick = {
                            val raw = rawUpdate ?: return@Button
                            scope.launch {
                                busy = true
                                error = null
                                resultText = null
                                try {
                                    preUpdateBackup = withContext(Dispatchers.IO) {
                                        BackupService.create(context.filesDir).file
                                    }
                                    val outDir = File(context.filesDir, "library/applied").apply { mkdirs() }
                                    val payload = buildJsonObject {
                                        put("update", raw)
                                        put("base_root", base.absolutePath)
                                        put("new_root", target.absolutePath)
                                        put("decisions", buildJsonObject {
                                            for ((k, v) in decisions) put(k, v)
                                        })
                                        put("out_dir", outDir.absolutePath)
                                    }
                                    val response = safeCall("pack-merge", payload)
                                    if (response.ok) {
                                        val installed = withContext(Dispatchers.IO) {
                                            runCatching {
                                                val target = packDir(u.to.id, u.to.version)
                                                if (target.exists()) target.deleteRecursively()
                                                outDir.copyRecursively(target, overwrite = true)
                                                dev.ninfenz.mobile.data.PackStore(context.filesDir).invalidate()
                                                target
                                            }.getOrNull()
                                        }
                                        resultText = response.result?.toString()
                                        if (installed == null || !installed.isDirectory) {
                                            error = CoreResponse.failure(
                                                "NF-PCK-005",
                                                context.getString(dev.ninfenz.mobile.R.string.packupdate_install_fail),
                                                context.getString(dev.ninfenz.mobile.R.string.packupdate_install_fix),
                                                3
                                            ).error
                                        } else {
                                            installedUpdateTarget = installed
                                        }
                                    } else {
                                        error = response.error
                                    }
                                } finally {
                                    busy = false
                                }
                            }
                        }
                    ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.packupdate_applying) else stringResource(dev.ninfenz.mobile.R.string.packupdate_apply)) }

                    OutlinedButton(
                        enabled = !busy && (installedUpdateTarget != null || preUpdateBackup != null),
                        onClick = {
                            val target = installedUpdateTarget
                            if (target != null) {
                                scope.launch {
                                    busy = true
                                    error = null
                                    val removed = withContext(Dispatchers.IO) {
                                        runCatching {
                                            target.deleteRecursively()
                                            dev.ninfenz.mobile.data.PackStore(context.filesDir).invalidate()
                                        }.isSuccess
                                    }
                                    if (removed) {
                                        installedUpdateTarget = null
                                        resultText = context.getString(dev.ninfenz.mobile.R.string.packupdate_rollback_done, target.name)
                                    } else {
                                        error = CoreResponse.failure(
                                            "NF-PCK-005",
                                            context.getString(dev.ninfenz.mobile.R.string.packupdate_rollback_fail),
                                            context.getString(dev.ninfenz.mobile.R.string.packupdate_install_fix),
                                            3
                                        ).error
                                    }
                                    busy = false
                                }
                            } else {
                                showRollbackBackup = true
                            }
                        }
                    ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.packupdate_rolling) else stringResource(dev.ninfenz.mobile.R.string.packupdate_rollback)) }
                    if (preUpdateBackup == null) {
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.packupdate_rollback_no_backup),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
                resultText?.let { MonoText(it) }
                preUpdateBackup?.let {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.packupdate_pre_backup, it.absolutePath),
                        style = NfType.meta
                    )
                    TextButton(enabled = !busy, onClick = { showRollbackBackup = true }) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.packupdate_restore_backup))
                    }
                }
                backupRollbackMessage?.let { Text(it, style = NfType.meta) }
                Notice(stringResource(dev.ninfenz.mobile.R.string.packupdate_notice), Tone.INFO)
            }
        }
    }

    if (showRollbackBackup) {
        val backup = preUpdateBackup
        AlertDialog(
            onDismissRequest = { showRollbackBackup = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.packupdate_restore_backup)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.packupdate_restore_backup_body)) },
            confirmButton = {
                TextButton(
                    enabled = backup != null && !busy,
                    onClick = {
                        showRollbackBackup = false
                        if (backup != null) {
                            scope.launch {
                                busy = true
                                try {
                                    val restored = withContext(Dispatchers.IO) {
                                        BackupRestoreService.restore(backup, context.filesDir)
                                    }
                                    backupRollbackMessage = context.getString(
                                        dev.ninfenz.mobile.R.string.packupdate_restore_backup_done,
                                        restored.files
                                    )
                                } catch (t: Throwable) {
                                    backupRollbackMessage = context.getString(
                                        dev.ninfenz.mobile.R.string.packupdate_restore_backup_failed,
                                        t.message ?: t.javaClass.simpleName
                                    )
                                } finally {
                                    busy = false
                                }
                            }
                        }
                    }
                ) { Text(stringResource(dev.ninfenz.mobile.R.string.packupdate_restore_backup_confirm)) }
            },
            dismissButton = {
                TextButton(onClick = { showRollbackBackup = false }) {
                    Text(stringResource(android.R.string.cancel))
                }
            }
        )
    }
}
