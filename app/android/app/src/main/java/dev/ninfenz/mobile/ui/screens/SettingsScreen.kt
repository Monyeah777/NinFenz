package dev.ninfenz.mobile.ui.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.net.Uri
import android.content.Context
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.TextButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import dev.ninfenz.mobile.BuildConfig
import dev.ninfenz.mobile.core.Core
import dev.ninfenz.mobile.core.CoreBridgeNative
import dev.ninfenz.mobile.core.ErrorCatalog
import dev.ninfenz.mobile.data.BackupRestoreService
import dev.ninfenz.mobile.data.DiagnosticsBundle
import dev.ninfenz.mobile.data.BackupService
import dev.ninfenz.mobile.data.StorageStats
import dev.ninfenz.mobile.share.ShareExporter
import java.io.File
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.components.KeyValue
import dev.ninfenz.mobile.ui.components.MonoText
import dev.ninfenz.mobile.ui.components.NfScaffold
import dev.ninfenz.mobile.ui.components.Notice
import dev.ninfenz.mobile.ui.components.Tone
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun SettingsScreen(onBack: () -> Unit, onErrorCodes: () -> Unit = {}) {
    val context = LocalContext.current
    val diag = remember { Core.diagnostics() }
    var copied by remember { mutableStateOf(false) }
    var stats by remember { mutableStateOf(StorageStats.scan(context.filesDir, context.cacheDir)) }
    var cleaned by remember { mutableStateOf<String?>(null) }
    var backupMessage by remember { mutableStateOf<String?>(null) }
    var pendingRestore by remember { mutableStateOf<File?>(null) }
    var restoreEntries by remember { mutableStateOf(0) }
    var lastSnapshot by remember { mutableStateOf(BackupRestoreService.lastSnapshot(context.filesDir)) }
    val scope = rememberCoroutineScope()
    val restorePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            backupMessage = null
            val file = File(context.cacheDir, "restore.zip")
            withContext(Dispatchers.IO) {
                context.contentResolver.openInputStream(uri)?.use { input ->
                    file.outputStream().use { output -> input.copyTo(output) }
                }
            }
            val checked = withContext(Dispatchers.IO) { BackupRestoreService.inspect(file) }
            if (!checked.ok) {
                backupMessage = "备份校验失败：" + (checked.error ?: "未知原因")
            } else {
                pendingRestore = file
                restoreEntries = checked.entries.size
            }
        }
    }

    val diagnosticsText = buildString {
        appendLine("app=dev.ninfenz.mobile " + BuildConfig.VERSION_NAME + " (" + BuildConfig.VERSION_CODE + ")")
        appendLine("android=" + android.os.Build.VERSION.RELEASE + " sdk=" + android.os.Build.VERSION.SDK_INT)
        appendLine("abi=" + android.os.Build.SUPPORTED_ABIS.joinToString(","))
        appendLine("core.backend=" + diag.backend)
        appendLine("core.abi=" + (diag.abiVersion ?: "unavailable"))
        appendLine("core.nativeReady=" + diag.nativeReady)
        appendLine("errorCatalog.loaded=" + diag.errorCatalogLoaded + " count=" + diag.errorCodeCount)
        appendLine("telemetry=none network=denied account=none")
    }

    NfScaffold(title = stringResource(dev.ninfenz.mobile.R.string.settings_title), onBack = onBack) {
        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_core_diag)) {
            KeyValue("backend", diag.backend)
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_abi), diag.abiVersion ?: stringResource(dev.ninfenz.mobile.R.string.settings_abi_unavailable))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_native), if (diag.nativeReady) stringResource(dev.ninfenz.mobile.R.string.settings_loaded) else stringResource(dev.ninfenz.mobile.R.string.settings_missing))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_err_registry), if (diag.errorCatalogLoaded) stringResource(dev.ninfenz.mobile.R.string.settings_err_count, diag.errorCodeCount) else stringResource(dev.ninfenz.mobile.R.string.settings_not_packaged))
            if (!diag.nativeReady) {
                Notice("NF-E-005：共享核心原生库不可用。\n" + CoreBridgeNative.GUIDANCE, Tone.ERROR)
            }
            Text(
                text = stringResource(dev.ninfenz.mobile.R.string.settings_error_hint, ErrorCatalog.all().size),
                style = MaterialTheme.typography.bodySmall
            )
            OutlinedButton(onClick = onErrorCodes) {
                Text(stringResource(dev.ninfenz.mobile.R.string.error_codes_title))
            }
        }

        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_storage_title)) {
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_storage_projects), humanBytes(stats.projects))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_storage_drafts), humanBytes(stats.drafts))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_storage_exports), humanBytes(stats.exports))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_storage_cache), humanBytes(stats.cache))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_storage_total), humanBytes(stats.total))
            Button(onClick = {
                val removed = StorageStats.clearImportCache(context.cacheDir)
                stats = StorageStats.scan(context.filesDir, context.cacheDir)
                cleaned = context.getString(dev.ninfenz.mobile.R.string.settings_storage_cleaned, removed)
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_storage_clear)) }
            cleaned?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary) }
            OutlinedButton(onClick = {
                scope.launch {
                    val created = withContext(Dispatchers.IO) { BackupService.create(context.filesDir) }
                    val intent = ShareExporter.shareFileIntent(context, created.file, "application/zip", created.file.name)
                    ShareExporter.launchChooser(context, intent, created.file.name)
                    backupMessage = context.getString(dev.ninfenz.mobile.R.string.settings_backup_done, created.entries, humanBytes(created.bytes))
                }
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_export)) }
            backupMessage?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary) }
            OutlinedButton(onClick = {
                restorePicker.launch(arrayOf("application/zip", "*/*"))
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_restore)) }
            lastSnapshot?.let { snapshot ->
                OutlinedButton(onClick = {
                    scope.launch {
                        val checked = withContext(Dispatchers.IO) { BackupRestoreService.inspect(snapshot) }
                        if (!checked.ok) {
                            backupMessage = "快照校验失败：" + (checked.error ?: "未知原因")
                        } else {
                            pendingRestore = snapshot
                            restoreEntries = checked.entries.size
                        }
                    }
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_rollback)) }
            }
        }

        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_privacy)) {
            Text(stringResource(dev.ninfenz.mobile.R.string.settings_privacy_1), style = MaterialTheme.typography.bodySmall)
            Text(stringResource(dev.ninfenz.mobile.R.string.settings_privacy_2), style = MaterialTheme.typography.bodySmall)
            Text(stringResource(dev.ninfenz.mobile.R.string.settings_privacy_3), style = MaterialTheme.typography.bodySmall)
            Text(stringResource(dev.ninfenz.mobile.R.string.settings_privacy_4), style = MaterialTheme.typography.bodySmall)
            Text(stringResource(dev.ninfenz.mobile.R.string.settings_privacy_5), style = MaterialTheme.typography.bodySmall)
        }

        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_diag_info)) {
            MonoText(diagnosticsText)
            Button(onClick = {
                val manager = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
                manager?.setPrimaryClip(ClipData.newPlainText("NF Mobile diagnostics", diagnosticsText))
                copied = true
            }) {
                Text(if (copied) stringResource(dev.ninfenz.mobile.R.string.settings_copied) else stringResource(dev.ninfenz.mobile.R.string.settings_copy))
            }
            OutlinedButton(onClick = {
                scope.launch {
                    val created = withContext(Dispatchers.IO) { DiagnosticsBundle.create(context.filesDir, diagnosticsText) }
                    val intent = ShareExporter.shareFileIntent(context, created.file, "application/zip", created.file.name)
                    ShareExporter.launchChooser(context, intent, created.file.name)
                    backupMessage = context.getString(dev.ninfenz.mobile.R.string.settings_diagnostics_done, humanBytes(created.bytes))
                }
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_diagnostics_export)) }
        }
    }

    pendingRestore?.let { file ->
        AlertDialog(
            onDismissRequest = { pendingRestore = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_restore_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_restore_warning, restoreEntries)) },
            confirmButton = {
                TextButton(onClick = {
                    scope.launch {
                        val result = withContext(Dispatchers.IO) {
                            runCatching { BackupRestoreService.restore(file, context.filesDir) }
                        }
                        backupMessage = result.fold(
                            onSuccess = {
                                context.getString(
                                    dev.ninfenz.mobile.R.string.settings_backup_restored,
                                    it.files,
                                    it.snapshot?.name ?: "-"
                                )
                            },
                            onFailure = { "恢复失败：" + (it.message ?: it.javaClass.simpleName) }
                        )
                        lastSnapshot = BackupRestoreService.lastSnapshot(context.filesDir)
                        pendingRestore = null
                    }
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_restore_confirm)) }
            },
            dismissButton = {
                TextButton(onClick = { pendingRestore = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}

private fun humanBytes(bytes: Long): String = when {
    bytes < 1024 -> bytes.toString() + " B"
    bytes < 1024 * 1024 -> (bytes / 1024).toString() + " KB"
    else -> String.format("%.1f MB", bytes / 1024.0 / 1024.0)
}
