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
fun SettingsScreen(
    onBack: () -> Unit,
    onErrorCodes: () -> Unit = {},
    onDataRestored: () -> Unit = {},
    onNfDocMerge: () -> Unit = {},
    onPatch: () -> Unit = {},
    onDesignSystem: () -> Unit = {},
    onDecisionLog: () -> Unit = {},
    onExtensions: () -> Unit = {},
    onTemplates: () -> Unit = {},
    onThemeMode: (ThemeMode) -> Unit = {},
    onLanguageMode: (LanguageMode) -> Unit = {},
    onDynamicColor: (Boolean) -> Unit = {}
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val s = remember { SettingsUiState(context, scope) }
    val capabilityRevision = rememberCapabilityRevision()
    val nav = SettingsNav(
        onBack = onBack, onErrorCodes = onErrorCodes, onDataRestored = onDataRestored,
        onNfDocMerge = onNfDocMerge, onPatch = onPatch, onDesignSystem = onDesignSystem,
        onDecisionLog = onDecisionLog, onExtensions = onExtensions, onTemplates = onTemplates,
        onThemeMode = onThemeMode, onLanguageMode = onLanguageMode, onDynamicColor = onDynamicColor
    )
    val chainFirstPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        s.onChainFirstPicked(uri)
    }
    val upgradePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        s.onUpgradePicked(uri)
    }
    val chainSecondPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        s.onChainSecondPicked(uri)
    }
    val restorePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        s.onRestorePicked(uri)
    }
    val pickers = SettingsPickers(
        chainFirst = { chainFirstPicker.launch(arrayOf("application/zip", "application/octet-stream")) },
        upgrade = { upgradePicker.launch(arrayOf("application/zip", "application/octet-stream")) },
        chainSecond = { chainSecondPicker.launch(arrayOf("application/zip", "application/octet-stream")) },
        restore = { restorePicker.launch(arrayOf("application/zip", "*/*")) }
    )

    NfScaffold(title = stringResource(dev.ninfenz.mobile.R.string.settings_title), onBack = onBack) {
        SettingsCoreDiagCard(s, nav)
        SettingsUpgradeChainCards(s, nav, pickers)
        SettingsTierCard(s)
        SettingsLicenseCard(s)
        SettingsModulesSection(s, nav, capabilityRevision)
        if (capabilityRevision >= 0 && CapabilityRegistry.isEnabled(Capability.MACROS)) {
            SettingsMacroSection()
        }
        if (capabilityRevision >= 0 && CapabilityRegistry.isEnabled(Capability.STYLE)) {
            SettingsStyleSection()
        }
        SettingsSelfCheckCard(s)
        SettingsWorkspaceCard(s, nav)
        SettingsStorageCard(s, nav, pickers)
        SettingsPrivacySection()
        SettingsDiagInfoSection(s, s.diagnosticsText)
        SettingsCrashCard(s)
    }

    if (s.showAllBackups) {
        SettingsAllBackupsDialog(s)
    }
    s.pendingDeleteBackup?.let { backup -> SettingsDeleteBackupDialog(s, backup) }
    s.pendingRestore?.let { file -> SettingsRestoreDialog(s, file, onDataRestored) }
}

internal fun findActivity(context: Context): Activity? {
    var current: Context? = context
    while (current is ContextWrapper) {
        if (current is Activity) return current
        current = current.baseContext
    }
    return null
}

internal fun humanBytes(bytes: Long): String = when {
    bytes < 1024 -> bytes.toString() + " B"
    bytes < 1024 * 1024 -> (bytes / 1024).toString() + " KB"
    else -> String.format(Locale.US, "%.1f MB", bytes / 1024.0 / 1024.0)
}
