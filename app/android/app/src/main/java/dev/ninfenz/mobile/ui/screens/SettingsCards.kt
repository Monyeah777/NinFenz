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
internal fun SettingsCoreDiagCard(s: SettingsUiState, nav: SettingsNav) {
        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_core_diag)) {
            KeyValue("backend", s.diag.backend)
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_abi), s.diag.abiVersion ?: stringResource(dev.ninfenz.mobile.R.string.settings_abi_unavailable))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_native), if (s.diag.nativeReady) stringResource(dev.ninfenz.mobile.R.string.settings_loaded) else stringResource(dev.ninfenz.mobile.R.string.settings_missing))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_err_registry), if (s.diag.errorCatalogLoaded) pluralStringResource(dev.ninfenz.mobile.R.plurals.settings_err_count, s.diag.errorCodeCount, s.diag.errorCodeCount) else stringResource(dev.ninfenz.mobile.R.string.settings_not_packaged))
            if (!s.diag.nativeReady) {
                Notice(s.context.getString(dev.ninfenz.mobile.R.string.settings_core_missing, CoreBridgeNative.GUIDANCE), Tone.ERROR)
            }
            Text(
                text = stringResource(dev.ninfenz.mobile.R.string.settings_error_hint, ErrorCatalog.all().size),
                style = NfType.meta
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = nav.onErrorCodes) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.error_codes_title))
                }
                OutlinedButton(onClick = nav.onDesignSystem) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.settings_design_system))
                }
                OutlinedButton(onClick = nav.onExtensions) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.extensions_title))
                }
                OutlinedButton(onClick = nav.onTemplates) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.template_gallery_title))
                }
                if (s.audit) OutlinedButton(onClick = nav.onDecisionLog) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.settings_decision_log))
                }
            }
        }
}

@Composable
internal fun SettingsUpgradeChainCards(s: SettingsUiState, nav: SettingsNav, pickers: SettingsPickers) {
        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_upgrade_title)) {
            Text(
                stringResource(dev.ninfenz.mobile.R.string.settings_upgrade_desc),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            OutlinedButton(onClick = { pickers.upgrade() }) {
                Text(stringResource(dev.ninfenz.mobile.R.string.settings_upgrade_pick))
            }
            s.upgradeNote?.let {
                Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary)
            }
        }

        if (s.audit) CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_chain_title)) {
            Text(
                stringResource(dev.ninfenz.mobile.R.string.settings_chain_desc),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(NfSpacing.s)) {
                OutlinedButton(onClick = { pickers.chainFirst() }) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.settings_chain_first))
                }
                OutlinedButton(onClick = { pickers.chainSecond() }) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.settings_chain_second))
                }
            }
            s.chainFirst?.let { Text(it.name, style = NfType.meta) }
            s.chainSecond?.let { Text(it.name, style = NfType.meta) }
            Button(
                enabled = s.chainFirst != null && s.chainSecond != null,
                onClick = {
                    val previous = s.chainFirst ?: return@Button
                    val next = s.chainSecond ?: return@Button
                    s.scope.launch {
                        val result = withContext(Dispatchers.IO) { dev.ninfenz.mobile.data.PreservationVerifier.chain(previous, next) }
                        s.chainNote = if (result.ok) {
                            s.context.getString(dev.ninfenz.mobile.R.string.settings_chain_ok)
                        } else {
                            s.context.getString(dev.ninfenz.mobile.R.string.settings_chain_fail, result.errors.take(2).joinToString("; "))
                        }
                    }
                }
            ) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_chain_verify)) }
            s.chainNote?.let {
                Text(it, style = NfType.meta, color = if (it == s.context.getString(dev.ninfenz.mobile.R.string.settings_chain_ok)) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error)
            }
        }
}

@Composable
internal fun SettingsTierCard(s: SettingsUiState) {
        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_tier_title)) {
            val proCount = FeaturePolicy.rules.values.count { it.minTier == FeaturePolicy.Tier.PRO }
            val ccosCount = FeaturePolicy.rules.values.count { it.minTier == FeaturePolicy.Tier.CCOS }
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_tier_current), s.tier.name)
            KeyValue("Free", stringResource(dev.ninfenz.mobile.R.string.settings_tier_free))
            KeyValue("Pro rules", proCount.toString())
            KeyValue("CCOS rules", ccosCount.toString())
            if (BuildConfig.DEBUG) {
                Text(stringResource(dev.ninfenz.mobile.R.string.settings_tier_debug), style = NfType.meta)
                Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(NfSpacing.s)) {
                    FeatureGate.Tier.values().forEach { option ->
                        FilterChip(
                            selected = s.tier == option,
                            onClick = {
                                FeatureGate.setTierForDebug(option)
                                s.tier = option
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
}

@Composable
internal fun SettingsModulesSection(s: SettingsUiState, nav: SettingsNav, capabilityRevision: Int) {
        SettingsFreeLayer(
            onThemeMode = nav.onThemeMode,
            onLanguageMode = nav.onLanguageMode,
            onModulesChanged = { s.moduleVersion++ }
        )
        if (capabilityRevision >= 0 && CapabilityRegistry.isEnabled(Capability.MACROS)) {
            SettingsMacroSection()
        }
        if (capabilityRevision >= 0 && CapabilityRegistry.isEnabled(Capability.STYLE)) {
            SettingsStyleSection()
        }
}

@Composable
internal fun SettingsSelfCheckCard(s: SettingsUiState) {
        if (s.audit) CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_selfcheck_title)) {
            Text(
                stringResource(dev.ninfenz.mobile.R.string.settings_selfcheck_desc),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Button(onClick = { s.selfCheck = dev.ninfenz.mobile.data.AppSelfCheck.run() }) {
                Text(stringResource(dev.ninfenz.mobile.R.string.settings_selfcheck_run))
            }
            s.selfCheck?.let { report ->
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
}

@Composable
internal fun SettingsWorkspaceCard(s: SettingsUiState, nav: SettingsNav) {
        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_workspace_title)) {
            if (s.workspacePresets.isEmpty()) {
                Text(stringResource(dev.ninfenz.mobile.R.string.settings_workspace_empty), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                s.workspacePresets.forEach { contribution ->
                    val theme = contribution.config["theme"]?.toString()?.trim('"')?.let { name -> ThemeMode.entries.firstOrNull { it.name == name } }
                    val language = contribution.config["language"]?.toString()?.trim('"')?.let { tag -> LanguageMode.entries.firstOrNull { it.name.equals(tag, true) || it.tag == tag } }
                    val dynamic = contribution.config["dynamic_color"]?.toString()?.toBooleanStrictOrNull()
                    Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                        Text(contribution.id, style = NfType.meta, modifier = Modifier.weight(1f))
                        TextButton(onClick = {
                            theme?.let(nav.onThemeMode)
                            language?.let(nav.onLanguageMode)
                            dynamic?.let(nav.onDynamicColor)
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.settings_workspace_apply)) }
                    }
                }
            }
        }
}
