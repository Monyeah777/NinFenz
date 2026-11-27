package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.util.orNullLogged
import android.content.ClipData
import android.content.ClipboardManager
import android.net.Uri
import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Checkbox
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Button
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.TextButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import dev.ninfenz.mobile.BuildConfig
import dev.ninfenz.mobile.core.Core
import dev.ninfenz.mobile.core.CoreBridgeNative
import dev.ninfenz.mobile.core.ErrorCatalog
import dev.ninfenz.mobile.data.UriIo
import dev.ninfenz.mobile.data.AppPrefs
import dev.ninfenz.mobile.data.Capability
import dev.ninfenz.mobile.data.CapabilityRegistry
import dev.ninfenz.mobile.data.ExtensionStore
import dev.ninfenz.mobile.data.PrefsStore
import dev.ninfenz.mobile.data.LanguageMode
import dev.ninfenz.mobile.data.ThemeMode
import dev.ninfenz.mobile.data.BackupRestoreService
import dev.ninfenz.mobile.data.FeatureGate
import dev.ninfenz.mobile.data.FeaturePolicy
import dev.ninfenz.mobile.data.CrashLogStore
import dev.ninfenz.mobile.data.DiagnosticsBundle
import dev.ninfenz.mobile.data.BackupService
import dev.ninfenz.mobile.data.StorageStats
import dev.ninfenz.mobile.share.ShareExporter
import java.io.File
import java.util.Locale
import dev.ninfenz.mobile.ui.rememberCapabilityRevision
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.components.NfCollapsibleSection
import dev.ninfenz.mobile.ui.components.KeyValue
import dev.ninfenz.mobile.ui.components.MonoText
import dev.ninfenz.mobile.ui.components.NfScaffold
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType
import dev.ninfenz.mobile.ui.components.Notice
import dev.ninfenz.mobile.ui.components.Tone
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
internal fun SettingsStorageCard(s: SettingsUiState, nav: SettingsNav, pickers: SettingsPickers) {
    CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_storage_title)) {
        SettingsStorageSummary(s)
        SettingsStorageBatchDialog(s)
        SettingsStorageBackupRows(s, nav, pickers)
    }
}

@Composable
internal fun SettingsStorageSummary(s: SettingsUiState) {
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_storage_projects), humanBytes(s.stats.projects))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_storage_drafts), humanBytes(s.stats.drafts))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_storage_exports), humanBytes(s.stats.exports))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_storage_cache), humanBytes(s.stats.cache))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_storage_packs), humanBytes(s.stats.packs))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_storage_archives), humanBytes(s.stats.archives))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_storage_total), humanBytes(s.stats.total))
            Button(onClick = {
                val removed = StorageStats.clearImportCache(s.context.cacheDir)
                s.stats = StorageStats.scan(s.context.filesDir, s.context.cacheDir)
                s.cleaned = s.context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.settings_storage_cleaned, removed, removed)
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_storage_clear)) }
            s.cleaned?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary) }
            OutlinedButton(onClick = {
                s.scope.launch {
                    val created = withContext(Dispatchers.IO) {
                        File(s.context.filesDir, "app-prefs.json").writeText(AppPrefs(s.context).snapshot())
                        File(s.context.filesDir, "nf-prefs.json").writeText(PrefsStore(s.context).exportJson())
                        BackupService.create(s.context.filesDir)
                    }
                    val checked = withContext(Dispatchers.IO) { BackupRestoreService.inspect(created.file) }
                    val intent = ShareExporter.shareFileIntent(s.context, created.file, "application/zip", created.file.name)
                    ShareExporter.launchChooser(s.context, intent, created.file.name)
                    s.backups = BackupService.list(s.context.filesDir)
                    s.backupMessage = s.context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.settings_backup_done, created.entries, created.entries, humanBytes(created.bytes)) +
                        if (checked.ok) s.context.getString(dev.ninfenz.mobile.R.string.settings_backup_verified)
                        else s.context.getString(dev.ninfenz.mobile.R.string.settings_backup_verify_failed, checked.error ?: s.context.getString(dev.ninfenz.mobile.R.string.unknown_reason))
                }
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_export)) }
            OutlinedButton(onClick = {
                s.scope.launch {
                    val created = withContext(Dispatchers.IO) {
                        runCatching { dev.ninfenz.mobile.data.ProjectBundleExporter.create(s.context.filesDir, s.context.cacheDir) }.orNullLogged("SettingsScreen")
                    }
                    if (created == null) {
                        s.backupMessage = s.context.getString(dev.ninfenz.mobile.R.string.settings_bundle_empty)
                    } else {
                        val intent = ShareExporter.shareFileIntent(s.context, created.file, "application/zip", created.file.name)
                        ShareExporter.launchChooser(s.context, intent, created.file.name)
                        s.backupMessage = s.context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.settings_bundle_done, created.count, created.count)
                    }
                }
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_bundle_export)) }
            OutlinedButton(onClick = {
                val list = runCatching { dev.ninfenz.mobile.data.LibraryStore(s.context.filesDir).loadProjects().projects }.getOrDefault(emptyList())
                if (list.isEmpty()) {
                    s.backupMessage = s.context.getString(dev.ninfenz.mobile.R.string.settings_batch_failed)
                } else {
                    s.batchSelected = list.map { it.project.id }.toSet()
                    s.batchCandidates = list
                }
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_batch_run)) }
}

@Composable
internal fun SettingsStorageBatchDialog(s: SettingsUiState) {
            s.batchCandidates?.let { candidates ->
                AlertDialog(
                    onDismissRequest = { s.batchCandidates = null },
                    title = { Text(pluralStringResource(dev.ninfenz.mobile.R.plurals.settings_batch_title, s.batchSelected.size, s.batchSelected.size)) },
                    text = {
                        Column(Modifier.heightIn(max = 360.dp).verticalScroll(rememberScrollState())) {
                            Row {
                                TextButton(onClick = { s.batchSelected = candidates.map { it.project.id }.toSet() }) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.settings_batch_select_all))
                                }
                                TextButton(onClick = { s.batchSelected = emptySet() }) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.settings_batch_clear))
                                }
                            }
                            candidates.forEach { entry ->
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Checkbox(
                                        checked = entry.project.id in s.batchSelected,
                                        onCheckedChange = { checked ->
                                            s.batchSelected = if (checked) s.batchSelected + entry.project.id else s.batchSelected - entry.project.id
                                        }
                                    )
                                    Text(entry.project.title)
                                }
                            }
                        }
                    },
                    confirmButton = {
                        TextButton(
                            enabled = s.batchSelected.isNotEmpty(),
                            onClick = {
                                val ids = s.batchSelected
                                s.batchCandidates = null
                                s.scope.launch {
                                    val created = withContext(Dispatchers.IO) {
                                        runCatching { dev.ninfenz.mobile.ui.BatchAssembler.assembleAll(s.context, s.context.filesDir, s.context.cacheDir, ids) }.orNullLogged("SettingsScreen")
                                    }
                                    if (created == null) {
                                        s.backupMessage = s.context.getString(dev.ninfenz.mobile.R.string.settings_batch_failed)
                                    } else {
                                        val ok = created.items.count { it.ok }
                                        val intent = ShareExporter.shareFileIntent(s.context, created.file, "application/zip", created.file.name)
                                        ShareExporter.launchChooser(s.context, intent, created.file.name)
                                        val firstFailure = created.items.firstOrNull { !it.ok }
                                        s.backupMessage = s.context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.settings_batch_done, ok, ok, created.items.size) +
                                            if (firstFailure != null) "\n" + s.context.getString(dev.ninfenz.mobile.R.string.settings_batch_failed_detail, firstFailure.title) else ""
                                    }
                                }
                            }
                        ) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_batch_start)) }
                    },
                    dismissButton = { TextButton(onClick = { s.batchCandidates = null }) { Text(stringResource(dev.ninfenz.mobile.R.string.new_project_cancel)) } }
                )
            }
}

@Composable
internal fun SettingsStorageBackupRows(s: SettingsUiState, nav: SettingsNav, pickers: SettingsPickers) {
            s.backupMessage?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary) }
            OutlinedButton(onClick = {
                pickers.restore()
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_restore)) }
            OutlinedButton(onClick = nav.onNfDocMerge) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_nfdoc_merge)) }
            OutlinedButton(onClick = nav.onPatch) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_patch)) }
            OutlinedButton(onClick = {
                val removed = BackupService.prune(s.context.filesDir, 5)
                s.backups = BackupService.list(s.context.filesDir)
                s.stats = StorageStats.scan(s.context.filesDir, s.context.cacheDir)
                s.cleaned = s.context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.settings_backup_pruned, removed, removed)
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_prune)) }
            if (s.backups.isEmpty()) {
                Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_empty), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (s.backups.size > 3) {
                OutlinedButton(onClick = { s.showAllBackups = true }) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_all, s.backups.size))
                }
            }
            s.backups.take(3).forEach { backup ->
                Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    Text(
                        backup.name + " · " + humanBytes(backup.length()),
                        style = NfType.meta,
                        modifier = Modifier.weight(1f)
                    )
                    TextButton(onClick = {
                        s.scope.launch {
                            val checked = withContext(Dispatchers.IO) { BackupRestoreService.inspect(backup) }
                            if (!checked.ok) {
                                s.backupMessage = s.context.getString(dev.ninfenz.mobile.R.string.backup_verify_failed, checked.error ?: s.context.getString(dev.ninfenz.mobile.R.string.unknown_reason))
                            } else {
                                s.pendingRestore = backup
                                s.restoreEntries = checked.entries.size
                            }
                        }
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_restore_one)) }
                }
            }
            s.lastSnapshot?.let { snapshot ->
                OutlinedButton(onClick = {
                    s.scope.launch {
                        val checked = withContext(Dispatchers.IO) { BackupRestoreService.inspect(snapshot) }
                        if (!checked.ok) {
                            s.backupMessage = s.context.getString(dev.ninfenz.mobile.R.string.backup_snapshot_failed, checked.error ?: s.context.getString(dev.ninfenz.mobile.R.string.unknown_reason))
                        } else {
                            s.pendingRestore = snapshot
                            s.restoreEntries = checked.entries.size
                        }
                    }
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_rollback)) }
            }
}

@Composable
internal fun SettingsPrivacySection() {
        NfCollapsibleSection(title = stringResource(dev.ninfenz.mobile.R.string.settings_privacy), initiallyExpanded = false) {
            Column(
                modifier = Modifier.padding(horizontal = NfSpacing.page),
                verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(NfSpacing.xs)
            ) {
                Text(stringResource(dev.ninfenz.mobile.R.string.settings_privacy_1), style = NfType.meta)
                Text(stringResource(dev.ninfenz.mobile.R.string.settings_privacy_2), style = NfType.meta)
                Text(stringResource(dev.ninfenz.mobile.R.string.settings_privacy_3), style = NfType.meta)
                Text(stringResource(dev.ninfenz.mobile.R.string.settings_privacy_4), style = NfType.meta)
                Text(stringResource(dev.ninfenz.mobile.R.string.settings_privacy_5), style = NfType.meta)
            }
        }
}

@Composable
internal fun SettingsDiagInfoSection(s: SettingsUiState, diagnosticsText: String) {
        NfCollapsibleSection(title = stringResource(dev.ninfenz.mobile.R.string.settings_diag_info), initiallyExpanded = false) {
            Column(
                modifier = Modifier.padding(horizontal = NfSpacing.page),
                verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(NfSpacing.s)
            ) {
            MonoText(s.diagnosticsText)
            Button(onClick = {
                val manager = s.context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
                manager?.setPrimaryClip(ClipData.newPlainText("NF Mobile diagnostics", s.diagnosticsText))
                s.copied = true
            }) {
                Text(if (s.copied) stringResource(dev.ninfenz.mobile.R.string.settings_copied) else stringResource(dev.ninfenz.mobile.R.string.settings_copy))
            }
            OutlinedButton(onClick = {
                s.scope.launch {
                    val created = withContext(Dispatchers.IO) { DiagnosticsBundle.create(s.context.filesDir, s.diagnosticsText, s.crash) }
                    val intent = ShareExporter.shareFileIntent(s.context, created.file, "application/zip", created.file.name)
                    ShareExporter.launchChooser(s.context, intent, created.file.name)
                    s.backupMessage = s.context.getString(dev.ninfenz.mobile.R.string.settings_diagnostics_done, humanBytes(created.bytes))
                }
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_diagnostics_export)) }
            }
        }
}

@Composable
internal fun SettingsCrashCard(s: SettingsUiState) {
        if (s.crash != null) {
            CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_crash_title)) {
                MonoText(s.crash!!.take(2000))
                Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = {
                        val text = s.crash ?: return@OutlinedButton
                        val file = ShareExporter.writeSharedFile(s.context, "nf-crash", "txt", text)
                        val intent = ShareExporter.shareFileIntent(s.context, file, "text/plain", "NF Mobile crash log")
                        ShareExporter.launchChooser(s.context, intent, s.context.getString(dev.ninfenz.mobile.R.string.settings_crash_share))
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_crash_share)) }
                    Button(onClick = {
                        CrashLogStore(s.context.filesDir).clear()
                        s.crash = null
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_crash_clear)) }
                }
            }
        }
}
