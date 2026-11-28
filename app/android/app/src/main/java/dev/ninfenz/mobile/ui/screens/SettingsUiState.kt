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
import dev.ninfenz.mobile.data.EntitlementStore
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

import kotlinx.coroutines.CoroutineScope

internal data class SettingsNav(
    val onBack: () -> Unit,
    val onErrorCodes: () -> Unit,
    val onDataRestored: () -> Unit,
    val onNfDocMerge: () -> Unit,
    val onPatch: () -> Unit,
    val onDesignSystem: () -> Unit,
    val onDecisionLog: () -> Unit,
    val onExtensions: () -> Unit,
    val onTemplates: () -> Unit,
    val onThemeMode: (ThemeMode) -> Unit,
    val onLanguageMode: (LanguageMode) -> Unit,
    val onDynamicColor: (Boolean) -> Unit,
)

internal data class SettingsPickers(
    val chainFirst: () -> Unit,
    val upgrade: () -> Unit,
    val chainSecond: () -> Unit,
    val restore: () -> Unit,
)

internal class SettingsUiState(
    val context: Context,
    val scope: CoroutineScope,
) {
    val diag = Core.diagnostics()
    var crash by mutableStateOf(CrashLogStore(context.filesDir).read())
    var moduleVersion by mutableIntStateOf(0)
    var copied by mutableStateOf(false)
    var selfCheck by mutableStateOf<dev.ninfenz.mobile.data.PropertyHarness.Report?>(null)
    var tier by mutableStateOf(FeatureGate.tier())
    var licenseInput by mutableStateOf("")
    var licenseBusy by mutableStateOf(false)
    var licenseReason by mutableStateOf<String?>(null)
    var licenseValid by mutableStateOf(EntitlementStore.isActivated(context))

    fun activateLicense() {
        if (licenseBusy) return
        licenseBusy = true
        scope.launch {
            val state = EntitlementStore.activate(context, licenseInput)
            licenseValid = state.valid
            licenseReason = if (state.valid) "ok" else (state.reasonCode ?: "NF-LIC-001")
            if (state.valid) licenseInput = ""
            tier = FeatureGate.tier()
            licenseBusy = false
        }
    }
    val audit = FeatureGate.auditEnabled()
    val extensionStore = ExtensionStore(context.filesDir)
    val workspacePresets = extensionStore.contributions(setOf("workspace_preset"))
    var chainFirst by mutableStateOf<File?>(null)
    var chainSecond by mutableStateOf<File?>(null)
    var chainNote by mutableStateOf<String?>(null)
    var upgradeNote by mutableStateOf<String?>(null)
    var stats by mutableStateOf(StorageStats.scan(context.filesDir, context.cacheDir))
    var cleaned by mutableStateOf<String?>(null)
    var backupMessage by mutableStateOf<String?>(null)
    var backups by mutableStateOf(BackupService.list(context.filesDir))
    var showAllBackups by mutableStateOf(false)
    var pendingDeleteBackup by mutableStateOf<File?>(null)
    var restoring by mutableStateOf(false)
    var pendingRestore by mutableStateOf<File?>(null)
    var restoreEntries by mutableIntStateOf(0)
    var lastSnapshot by mutableStateOf(BackupRestoreService.lastSnapshot(context.filesDir))
    var batchCandidates by mutableStateOf<List<dev.ninfenz.mobile.data.ProjectEntry>?>(null)
    var batchSelected by mutableStateOf<Set<String>>(emptySet())

    val diagnosticsText: String get() = buildString {
        appendLine("app=dev.ninfenz.mobile " + BuildConfig.VERSION_NAME + " (" + BuildConfig.VERSION_CODE + ")")
        appendLine("android=" + android.os.Build.VERSION.RELEASE + " sdk=" + android.os.Build.VERSION.SDK_INT)
        appendLine("abi=" + android.os.Build.SUPPORTED_ABIS.joinToString(","))
        appendLine("core.backend=" + diag.backend)
        appendLine("core.abi=" + (diag.abiVersion ?: "unavailable"))
        appendLine("core.nativeReady=" + diag.nativeReady)
        appendLine("errorCatalog.loaded=" + diag.errorCatalogLoaded + " count=" + diag.errorCodeCount)
        appendLine("telemetry=none network=denied account=none")
        appendLine("crash.log=" + (crash != null))
    }

    fun onChainFirstPicked(uri: Uri?) {
        if (uri != null) scope.launch {
            chainFirst = withContext(Dispatchers.IO) { dev.ninfenz.mobile.data.FileAccess.copyToCache(context, uri, "chain-first.zip") }
            chainNote = null
        }
    }
    fun onUpgradePicked(uri: Uri?) {
        if (uri != null) scope.launch {
            upgradeNote = null
            runCatching {
                val file = withContext(Dispatchers.IO) {
                    val cached = dev.ninfenz.mobile.data.FileAccess.copyToCache(context, uri, "upgrade.zip")
                    val out = File(File(context.filesDir, "exports"), "upgrade").apply { mkdirs() }
                    dev.ninfenz.mobile.data.PreservationUpgrader.upgrade(cached, out).file
                }
                upgradeNote = context.getString(dev.ninfenz.mobile.R.string.settings_upgrade_done, file.name)
            }.onFailure {
                upgradeNote = context.getString(dev.ninfenz.mobile.R.string.settings_upgrade_fail, it.message ?: it.javaClass.simpleName)
            }
        }
    }
    fun onChainSecondPicked(uri: Uri?) {
        if (uri != null) scope.launch {
            chainSecond = withContext(Dispatchers.IO) { dev.ninfenz.mobile.data.FileAccess.copyToCache(context, uri, "chain-second.zip") }
            chainNote = null
        }
    }
    fun onRestorePicked(uri: Uri?) {
        if (uri == null) return
        scope.launch {
            backupMessage = null
            val file = File(context.cacheDir, "restore.zip")
            withContext(Dispatchers.IO) {
                UriIo.copyTo(context, uri, file)
            }
            val checked = withContext(Dispatchers.IO) { BackupRestoreService.inspect(file) }
            if (!checked.ok) {
                backupMessage = context.getString(dev.ninfenz.mobile.R.string.backup_verify_failed, checked.error ?: context.getString(dev.ninfenz.mobile.R.string.unknown_reason))
            } else {
                pendingRestore = file
                restoreEntries = checked.entries.size
            }
        }
    }

    fun restoreFrom(file: File, onDataRestored: () -> Unit) {
        restoring = true
        scope.launch {
            try {
                val result = withContext(Dispatchers.IO) {
                    runCatching { BackupRestoreService.restore(file, context.filesDir) }
                }
                backupMessage = result.fold(
                    onSuccess = {
                        context.resources.getQuantityString(
                            dev.ninfenz.mobile.R.plurals.settings_backup_restored,
                            it.files,
                            it.files,
                            it.snapshot?.name ?: "-"
                        )
                    },
                    onFailure = { context.getString(dev.ninfenz.mobile.R.string.backup_restore_failed, it.message ?: it.javaClass.simpleName) }
                )
                lastSnapshot = BackupRestoreService.lastSnapshot(context.filesDir)
                onDataRestored()
                val prefsRestored = runCatching {
                    File(context.filesDir, "app-prefs.json").takeIf { it.isFile }?.readText()
                        ?.let { AppPrefs(context).restore(it) } ?: false
                }.getOrDefault(false)
                if (prefsRestored) {
                    findActivity(context)?.let { activity ->
                        Toast.makeText(context, dev.ninfenz.mobile.R.string.settings_prefs_restart, Toast.LENGTH_SHORT).show()
                        activity.recreate()
                    }
                }
                backups = BackupService.list(context.filesDir)
                pendingRestore = null
            } finally {
                restoring = false
            }
        }
    }
}
