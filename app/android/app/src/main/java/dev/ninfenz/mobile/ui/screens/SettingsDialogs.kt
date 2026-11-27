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
internal fun SettingsAllBackupsDialog(s: SettingsUiState) {
        AlertDialog(
            onDismissRequest = { s.showAllBackups = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_all, s.backups.size)) },
            text = {
                Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                    s.backups.forEach { backup ->
                        Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                            Text(
                                backup.name + " · " + humanBytes(backup.length()),
                                style = NfType.meta,
                                modifier = Modifier.weight(1f)
                            )
                            TextButton(onClick = {
                                s.showAllBackups = false
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
                            TextButton(onClick = {
                                s.showAllBackups = false
                                s.pendingDeleteBackup = backup
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_delete)) }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { s.showAllBackups = false }) { Text(stringResource(dev.ninfenz.mobile.R.string.action_close)) }
            }
        )
}

@Composable
internal fun SettingsDeleteBackupDialog(s: SettingsUiState, backup: File) {
        AlertDialog(
            onDismissRequest = { s.pendingDeleteBackup = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_delete_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_delete_body, backup.name)) },
            confirmButton = {
                TextButton(onClick = {
                    val ok = backup.delete()
                    s.pendingDeleteBackup = null
                    s.backups = BackupService.list(s.context.filesDir)
                    s.stats = StorageStats.scan(s.context.filesDir, s.context.cacheDir)
                    s.backupMessage = if (ok) {
                        s.context.getString(dev.ninfenz.mobile.R.string.settings_backup_deleted, backup.name)
                    } else {
                        s.context.getString(dev.ninfenz.mobile.R.string.backup_delete_failed, backup.name)
                    }
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_delete)) }
            },
            dismissButton = {
                TextButton(onClick = { s.pendingDeleteBackup = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
}

@Composable
internal fun SettingsRestoreDialog(s: SettingsUiState, file: File, onDataRestored: () -> Unit) {
        AlertDialog(
            onDismissRequest = { if (!s.restoring) s.pendingRestore = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_restore_title)) },
            text = {
                Column {
                    Text(pluralStringResource(dev.ninfenz.mobile.R.plurals.settings_backup_restore_warning, s.restoreEntries, s.restoreEntries))
                    if (s.restoring) {
                        LinearProgressIndicator(modifier = Modifier.padding(top = 12.dp))
                    }
                }
            },
            confirmButton = {
                TextButton(
                    enabled = !s.restoring,
                    onClick = { s.restoreFrom(file, onDataRestored) },
                ) { Text(stringResource(if (s.restoring) dev.ninfenz.mobile.R.string.settings_restoring else dev.ninfenz.mobile.R.string.settings_backup_restore_confirm)) }
            },
            dismissButton = {
                TextButton(enabled = !s.restoring, onClick = { s.pendingRestore = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
}

