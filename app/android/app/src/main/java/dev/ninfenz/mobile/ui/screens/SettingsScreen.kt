package dev.ninfenz.mobile.ui.screens

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
    val diag = remember { Core.diagnostics() }
    var crash by remember { mutableStateOf(CrashLogStore(context.filesDir).read()) }
    var moduleVersion by remember { mutableIntStateOf(0) }
    val capabilityRevision = rememberCapabilityRevision()
    var copied by remember { mutableStateOf(false) }
    var selfCheck by remember { mutableStateOf<dev.ninfenz.mobile.data.PropertyHarness.Report?>(null) }
    var tier by remember { mutableStateOf(FeatureGate.tier()) }
    val audit = FeatureGate.auditEnabled()
    val extensionStore = remember { ExtensionStore(context.filesDir) }
    val workspacePresets = remember { extensionStore.contributions(setOf("workspace_preset")) }
    var chainFirst by remember { mutableStateOf<File?>(null) }
    var chainSecond by remember { mutableStateOf<File?>(null) }
    var chainNote by remember { mutableStateOf<String?>(null) }
    var upgradeNote by remember { mutableStateOf<String?>(null) }
    var stats by remember { mutableStateOf(StorageStats.scan(context.filesDir, context.cacheDir)) }
    var cleaned by remember { mutableStateOf<String?>(null) }
    var backupMessage by remember { mutableStateOf<String?>(null) }
    var backups by remember { mutableStateOf(BackupService.list(context.filesDir)) }
    var showAllBackups by remember { mutableStateOf(false) }
    var pendingDeleteBackup by remember { mutableStateOf<File?>(null) }
    var restoring by remember { mutableStateOf(false) }
    var pendingRestore by remember { mutableStateOf<File?>(null) }
    var restoreEntries by remember { mutableIntStateOf(0) }
    var lastSnapshot by remember { mutableStateOf(BackupRestoreService.lastSnapshot(context.filesDir)) }
    var batchCandidates by remember { mutableStateOf<List<dev.ninfenz.mobile.data.ProjectEntry>?>(null) }
    var batchSelected by remember { mutableStateOf<Set<String>>(emptySet()) }
    val scope = rememberCoroutineScope()
    val chainFirstPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) scope.launch {
            chainFirst = withContext(Dispatchers.IO) { dev.ninfenz.mobile.data.FileAccess.copyToCache(context, uri, "chain-first.zip") }
            chainNote = null
        }
    }
    val upgradePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
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
    val chainSecondPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) scope.launch {
            chainSecond = withContext(Dispatchers.IO) { dev.ninfenz.mobile.data.FileAccess.copyToCache(context, uri, "chain-second.zip") }
            chainNote = null
        }
    }
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
                backupMessage = context.getString(dev.ninfenz.mobile.R.string.backup_verify_failed, checked.error ?: context.getString(dev.ninfenz.mobile.R.string.unknown_reason))
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
        appendLine("crash.log=" + (crash != null))
    }

    NfScaffold(title = stringResource(dev.ninfenz.mobile.R.string.settings_title), onBack = onBack) {
        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_core_diag)) {
            KeyValue("backend", diag.backend)
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_abi), diag.abiVersion ?: stringResource(dev.ninfenz.mobile.R.string.settings_abi_unavailable))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_native), if (diag.nativeReady) stringResource(dev.ninfenz.mobile.R.string.settings_loaded) else stringResource(dev.ninfenz.mobile.R.string.settings_missing))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_err_registry), if (diag.errorCatalogLoaded) pluralStringResource(dev.ninfenz.mobile.R.plurals.settings_err_count, diag.errorCodeCount, diag.errorCodeCount) else stringResource(dev.ninfenz.mobile.R.string.settings_not_packaged))
            if (!diag.nativeReady) {
                Notice(context.getString(dev.ninfenz.mobile.R.string.settings_core_missing, CoreBridgeNative.GUIDANCE), Tone.ERROR)
            }
            Text(
                text = stringResource(dev.ninfenz.mobile.R.string.settings_error_hint, ErrorCatalog.all().size),
                style = NfType.meta
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onErrorCodes) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.error_codes_title))
                }
                OutlinedButton(onClick = onDesignSystem) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.settings_design_system))
                }
                OutlinedButton(onClick = onExtensions) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.extensions_title))
                }
                OutlinedButton(onClick = onTemplates) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.template_gallery_title))
                }
                if (audit) OutlinedButton(onClick = onDecisionLog) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.settings_decision_log))
                }
            }
        }

        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_upgrade_title)) {
            Text(
                stringResource(dev.ninfenz.mobile.R.string.settings_upgrade_desc),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            OutlinedButton(onClick = { upgradePicker.launch(arrayOf("application/zip", "application/octet-stream")) }) {
                Text(stringResource(dev.ninfenz.mobile.R.string.settings_upgrade_pick))
            }
            upgradeNote?.let {
                Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary)
            }
        }

        if (audit) CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_chain_title)) {
            Text(
                stringResource(dev.ninfenz.mobile.R.string.settings_chain_desc),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(NfSpacing.s)) {
                OutlinedButton(onClick = { chainFirstPicker.launch(arrayOf("application/zip", "application/octet-stream")) }) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.settings_chain_first))
                }
                OutlinedButton(onClick = { chainSecondPicker.launch(arrayOf("application/zip", "application/octet-stream")) }) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.settings_chain_second))
                }
            }
            chainFirst?.let { Text(it.name, style = NfType.meta) }
            chainSecond?.let { Text(it.name, style = NfType.meta) }
            Button(
                enabled = chainFirst != null && chainSecond != null,
                onClick = {
                    val previous = chainFirst ?: return@Button
                    val next = chainSecond ?: return@Button
                    scope.launch {
                        val result = withContext(Dispatchers.IO) { dev.ninfenz.mobile.data.PreservationVerifier.chain(previous, next) }
                        chainNote = if (result.ok) {
                            context.getString(dev.ninfenz.mobile.R.string.settings_chain_ok)
                        } else {
                            context.getString(dev.ninfenz.mobile.R.string.settings_chain_fail, result.errors.take(2).joinToString("; "))
                        }
                    }
                }
            ) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_chain_verify)) }
            chainNote?.let {
                Text(it, style = NfType.meta, color = if (it == context.getString(dev.ninfenz.mobile.R.string.settings_chain_ok)) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error)
            }
        }

        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_tier_title)) {
            val proCount = FeaturePolicy.rules.values.count { it.minTier == FeaturePolicy.Tier.PRO }
            val ccosCount = FeaturePolicy.rules.values.count { it.minTier == FeaturePolicy.Tier.CCOS }
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_tier_current), tier.name)
            KeyValue("Free", stringResource(dev.ninfenz.mobile.R.string.settings_tier_free))
            KeyValue("Pro rules", proCount.toString())
            KeyValue("CCOS rules", ccosCount.toString())
            if (BuildConfig.DEBUG) {
                Text(stringResource(dev.ninfenz.mobile.R.string.settings_tier_debug), style = NfType.meta)
                Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(NfSpacing.s)) {
                    FeatureGate.Tier.values().forEach { option ->
                        FilterChip(
                            selected = tier == option,
                            onClick = {
                                FeatureGate.setTierForDebug(option)
                                tier = option
                            },
                            label = { Text(option.name) }
                        )
                    }
                }
            } else {
                Text(
                    stringResource(dev.ninfenz.mobile.R.string.settings_tier_release_note),
                    style = NfType.meta,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }

        SettingsFreeLayer(
            onThemeMode = onThemeMode,
            onLanguageMode = onLanguageMode,
            onModulesChanged = { moduleVersion++ }
        )
        if (capabilityRevision >= 0 && CapabilityRegistry.isEnabled(Capability.MACROS)) {
            SettingsMacroSection()
        }
        if (capabilityRevision >= 0 && CapabilityRegistry.isEnabled(Capability.STYLE)) {
            SettingsStyleSection()
        }

        if (audit) CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_selfcheck_title)) {
            Text(
                stringResource(dev.ninfenz.mobile.R.string.settings_selfcheck_desc),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Button(onClick = { selfCheck = dev.ninfenz.mobile.data.AppSelfCheck.run() }) {
                Text(stringResource(dev.ninfenz.mobile.R.string.settings_selfcheck_run))
            }
            selfCheck?.let { report ->
                Text(
                    if (report.ok) {
                        stringResource(dev.ninfenz.mobile.R.string.settings_selfcheck_pass, report.checked)
                    } else {
                        stringResource(dev.ninfenz.mobile.R.string.settings_selfcheck_fail, report.failures.size, report.failures.first().seed)
                    },
                    style = NfType.meta,
                    color = if (report.ok) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
                )
            }
        }

        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_workspace_title)) {
            if (workspacePresets.isEmpty()) {
                Text(stringResource(dev.ninfenz.mobile.R.string.settings_workspace_empty), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                workspacePresets.forEach { contribution ->
                    val theme = contribution.config["theme"]?.toString()?.trim('"')?.let { name -> ThemeMode.entries.firstOrNull { it.name == name } }
                    val language = contribution.config["language"]?.toString()?.trim('"')?.let { tag -> LanguageMode.entries.firstOrNull { it.name.equals(tag, true) || it.tag == tag } }
                    val dynamic = contribution.config["dynamic_color"]?.toString()?.toBooleanStrictOrNull()
                    Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                        Text(contribution.id, style = NfType.meta, modifier = Modifier.weight(1f))
                        TextButton(onClick = {
                            theme?.let(onThemeMode)
                            language?.let(onLanguageMode)
                            dynamic?.let(onDynamicColor)
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_workspace_apply)) }
                    }
                }
            }
        }

        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_storage_title)) {
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_storage_projects), humanBytes(stats.projects))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_storage_drafts), humanBytes(stats.drafts))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_storage_exports), humanBytes(stats.exports))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_storage_cache), humanBytes(stats.cache))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_storage_packs), humanBytes(stats.packs))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_storage_archives), humanBytes(stats.archives))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_storage_total), humanBytes(stats.total))
            Button(onClick = {
                val removed = StorageStats.clearImportCache(context.cacheDir)
                stats = StorageStats.scan(context.filesDir, context.cacheDir)
                cleaned = context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.settings_storage_cleaned, removed, removed)
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_storage_clear)) }
            cleaned?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary) }
            OutlinedButton(onClick = {
                scope.launch {
                    val created = withContext(Dispatchers.IO) {
                        File(context.filesDir, "app-prefs.json").writeText(AppPrefs(context).snapshot())
                        File(context.filesDir, "nf-prefs.json").writeText(PrefsStore(context).exportJson())
                        BackupService.create(context.filesDir)
                    }
                    val checked = withContext(Dispatchers.IO) { BackupRestoreService.inspect(created.file) }
                    val intent = ShareExporter.shareFileIntent(context, created.file, "application/zip", created.file.name)
                    ShareExporter.launchChooser(context, intent, created.file.name)
                    backups = BackupService.list(context.filesDir)
                    backupMessage = context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.settings_backup_done, created.entries, created.entries, humanBytes(created.bytes)) +
                        if (checked.ok) context.getString(dev.ninfenz.mobile.R.string.settings_backup_verified)
                        else context.getString(dev.ninfenz.mobile.R.string.settings_backup_verify_failed, checked.error ?: context.getString(dev.ninfenz.mobile.R.string.unknown_reason))
                }
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_export)) }
            OutlinedButton(onClick = {
                scope.launch {
                    val created = withContext(Dispatchers.IO) {
                        runCatching { dev.ninfenz.mobile.data.ProjectBundleExporter.create(context.filesDir, context.cacheDir) }.getOrNull()
                    }
                    if (created == null) {
                        backupMessage = context.getString(dev.ninfenz.mobile.R.string.settings_bundle_empty)
                    } else {
                        val intent = ShareExporter.shareFileIntent(context, created.file, "application/zip", created.file.name)
                        ShareExporter.launchChooser(context, intent, created.file.name)
                        backupMessage = context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.settings_bundle_done, created.count, created.count)
                    }
                }
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_bundle_export)) }
            OutlinedButton(onClick = {
                val list = runCatching { dev.ninfenz.mobile.data.LibraryStore(context.filesDir).loadProjects().projects }.getOrDefault(emptyList())
                if (list.isEmpty()) {
                    backupMessage = context.getString(dev.ninfenz.mobile.R.string.settings_batch_failed)
                } else {
                    batchSelected = list.map { it.project.id }.toSet()
                    batchCandidates = list
                }
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_batch_run)) }
            batchCandidates?.let { candidates ->
                AlertDialog(
                    onDismissRequest = { batchCandidates = null },
                    title = { Text(pluralStringResource(dev.ninfenz.mobile.R.plurals.settings_batch_title, batchSelected.size, batchSelected.size)) },
                    text = {
                        Column(Modifier.heightIn(max = 360.dp).verticalScroll(rememberScrollState())) {
                            Row {
                                TextButton(onClick = { batchSelected = candidates.map { it.project.id }.toSet() }) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.settings_batch_select_all))
                                }
                                TextButton(onClick = { batchSelected = emptySet() }) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.settings_batch_clear))
                                }
                            }
                            candidates.forEach { entry ->
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Checkbox(
                                        checked = entry.project.id in batchSelected,
                                        onCheckedChange = { checked ->
                                            batchSelected = if (checked) batchSelected + entry.project.id else batchSelected - entry.project.id
                                        }
                                    )
                                    Text(entry.project.title)
                                }
                            }
                        }
                    },
                    confirmButton = {
                        TextButton(
                            enabled = batchSelected.isNotEmpty(),
                            onClick = {
                                val ids = batchSelected
                                batchCandidates = null
                                scope.launch {
                                    val created = withContext(Dispatchers.IO) {
                                        runCatching { dev.ninfenz.mobile.ui.BatchAssembler.assembleAll(context, context.filesDir, context.cacheDir, ids) }.getOrNull()
                                    }
                                    if (created == null) {
                                        backupMessage = context.getString(dev.ninfenz.mobile.R.string.settings_batch_failed)
                                    } else {
                                        val ok = created.items.count { it.ok }
                                        val intent = ShareExporter.shareFileIntent(context, created.file, "application/zip", created.file.name)
                                        ShareExporter.launchChooser(context, intent, created.file.name)
                                        val firstFailure = created.items.firstOrNull { !it.ok }
                                        backupMessage = context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.settings_batch_done, ok, ok, created.items.size) +
                                            if (firstFailure != null) "\n" + context.getString(dev.ninfenz.mobile.R.string.settings_batch_failed_detail, firstFailure.title) else ""
                                    }
                                }
                            }
                        ) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_batch_start)) }
                    },
                    dismissButton = { TextButton(onClick = { batchCandidates = null }) { Text(stringResource(dev.ninfenz.mobile.R.string.new_project_cancel)) } }
                )
            }
            backupMessage?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary) }
            OutlinedButton(onClick = {
                restorePicker.launch(arrayOf("application/zip", "*/*"))
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_restore)) }
            OutlinedButton(onClick = onNfDocMerge) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_nfdoc_merge)) }
            OutlinedButton(onClick = onPatch) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_patch)) }
            OutlinedButton(onClick = {
                val removed = BackupService.prune(context.filesDir, 5)
                backups = BackupService.list(context.filesDir)
                stats = StorageStats.scan(context.filesDir, context.cacheDir)
                cleaned = context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.settings_backup_pruned, removed, removed)
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_prune)) }
            if (backups.isEmpty()) {
                Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_empty), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (backups.size > 3) {
                OutlinedButton(onClick = { showAllBackups = true }) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_all, backups.size))
                }
            }
            backups.take(3).forEach { backup ->
                Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    Text(
                        backup.name + " · " + humanBytes(backup.length()),
                        style = NfType.meta,
                        modifier = Modifier.weight(1f)
                    )
                    TextButton(onClick = {
                        scope.launch {
                            val checked = withContext(Dispatchers.IO) { BackupRestoreService.inspect(backup) }
                            if (!checked.ok) {
                                backupMessage = context.getString(dev.ninfenz.mobile.R.string.backup_verify_failed, checked.error ?: context.getString(dev.ninfenz.mobile.R.string.unknown_reason))
                            } else {
                                pendingRestore = backup
                                restoreEntries = checked.entries.size
                            }
                        }
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_restore_one)) }
                }
            }
            lastSnapshot?.let { snapshot ->
                OutlinedButton(onClick = {
                    scope.launch {
                        val checked = withContext(Dispatchers.IO) { BackupRestoreService.inspect(snapshot) }
                        if (!checked.ok) {
                            backupMessage = context.getString(dev.ninfenz.mobile.R.string.backup_snapshot_failed, checked.error ?: context.getString(dev.ninfenz.mobile.R.string.unknown_reason))
                        } else {
                            pendingRestore = snapshot
                            restoreEntries = checked.entries.size
                        }
                    }
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_rollback)) }
            }
        }

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

        NfCollapsibleSection(title = stringResource(dev.ninfenz.mobile.R.string.settings_diag_info), initiallyExpanded = false) {
            Column(
                modifier = Modifier.padding(horizontal = NfSpacing.page),
                verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(NfSpacing.s)
            ) {
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
                    val created = withContext(Dispatchers.IO) { DiagnosticsBundle.create(context.filesDir, diagnosticsText, crash) }
                    val intent = ShareExporter.shareFileIntent(context, created.file, "application/zip", created.file.name)
                    ShareExporter.launchChooser(context, intent, created.file.name)
                    backupMessage = context.getString(dev.ninfenz.mobile.R.string.settings_diagnostics_done, humanBytes(created.bytes))
                }
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_diagnostics_export)) }
            }
        }

        if (crash != null) {
            CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_crash_title)) {
                MonoText(crash!!.take(2000))
                Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = {
                        val text = crash ?: return@OutlinedButton
                        val file = ShareExporter.writeSharedFile(context, "nf-crash", "txt", text)
                        val intent = ShareExporter.shareFileIntent(context, file, "text/plain", "NF Mobile crash log")
                        ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.settings_crash_share))
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_crash_share)) }
                    Button(onClick = {
                        CrashLogStore(context.filesDir).clear()
                        crash = null
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_crash_clear)) }
                }
            }
        }
    }

    if (showAllBackups) {
        AlertDialog(
            onDismissRequest = { showAllBackups = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_all, backups.size)) },
            text = {
                Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                    backups.forEach { backup ->
                        Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                            Text(
                                backup.name + " · " + humanBytes(backup.length()),
                                style = NfType.meta,
                                modifier = Modifier.weight(1f)
                            )
                            TextButton(onClick = {
                                showAllBackups = false
                                scope.launch {
                                    val checked = withContext(Dispatchers.IO) { BackupRestoreService.inspect(backup) }
                                    if (!checked.ok) {
                                        backupMessage = context.getString(dev.ninfenz.mobile.R.string.backup_verify_failed, checked.error ?: context.getString(dev.ninfenz.mobile.R.string.unknown_reason))
                                    } else {
                                        pendingRestore = backup
                                        restoreEntries = checked.entries.size
                                    }
                                }
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_restore_one)) }
                            TextButton(onClick = {
                                showAllBackups = false
                                pendingDeleteBackup = backup
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_delete)) }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showAllBackups = false }) { Text(stringResource(dev.ninfenz.mobile.R.string.action_close)) }
            }
        )
    }

    pendingDeleteBackup?.let { backup ->
        AlertDialog(
            onDismissRequest = { pendingDeleteBackup = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_delete_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_delete_body, backup.name)) },
            confirmButton = {
                TextButton(onClick = {
                    val ok = backup.delete()
                    pendingDeleteBackup = null
                    backups = BackupService.list(context.filesDir)
                    stats = StorageStats.scan(context.filesDir, context.cacheDir)
                    backupMessage = if (ok) {
                        context.getString(dev.ninfenz.mobile.R.string.settings_backup_deleted, backup.name)
                    } else {
                        context.getString(dev.ninfenz.mobile.R.string.backup_delete_failed, backup.name)
                    }
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_delete)) }
            },
            dismissButton = {
                TextButton(onClick = { pendingDeleteBackup = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

    pendingRestore?.let { file ->
        AlertDialog(
            onDismissRequest = { if (!restoring) pendingRestore = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.settings_backup_restore_title)) },
            text = {
                Column {
                    Text(pluralStringResource(dev.ninfenz.mobile.R.plurals.settings_backup_restore_warning, restoreEntries, restoreEntries))
                    if (restoring) {
                        LinearProgressIndicator(modifier = Modifier.padding(top = 12.dp))
                    }
                }
            },
            confirmButton = {
                TextButton(
                    enabled = !restoring,
                    onClick = {
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
                }) { Text(stringResource(if (restoring) dev.ninfenz.mobile.R.string.settings_restoring else dev.ninfenz.mobile.R.string.settings_backup_restore_confirm)) }
            },
            dismissButton = {
                TextButton(enabled = !restoring, onClick = { pendingRestore = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}

private fun findActivity(context: Context): Activity? {
    var current: Context? = context
    while (current is ContextWrapper) {
        if (current is Activity) return current
        current = current.baseContext
    }
    return null
}

private fun humanBytes(bytes: Long): String = when {
    bytes < 1024 -> bytes.toString() + " B"
    bytes < 1024 * 1024 -> (bytes / 1024).toString() + " KB"
    else -> String.format(Locale.US, "%.1f MB", bytes / 1024.0 / 1024.0)
}
