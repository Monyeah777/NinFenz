package dev.ninfenz.mobile.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.R
import dev.ninfenz.mobile.data.Capability
import dev.ninfenz.mobile.data.CapabilityRegistry
import dev.ninfenz.mobile.data.Density
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.data.LanguageMode
import dev.ninfenz.mobile.data.NfPrefs
import dev.ninfenz.mobile.data.PrefsStore
import dev.ninfenz.mobile.data.PrefsTheme
import dev.ninfenz.mobile.data.ThemeMode
import dev.ninfenz.mobile.data.UiPrefs
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.design.NfType
import dev.ninfenz.mobile.ui.theme.NfSpacing
import kotlinx.coroutines.launch

/** W0 自由层：预设、12 模块、界面/语言、设置导入导出与重置。 */
@Composable
fun SettingsFreeLayer(
    onThemeMode: (ThemeMode) -> Unit = {},
    onLanguageMode: (LanguageMode) -> Unit = {},
    onModulesChanged: () -> Unit = {}
) {
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val scope = rememberCoroutineScope()
    val store = remember { PrefsStore(context) }
    var prefs by remember { mutableStateOf(store.load()) }
    var note by remember { mutableStateOf<String?>(null) }
    var showReset by remember { mutableStateOf(false) }
    var showSave by remember { mutableStateOf(false) }
    var saveName by remember { mutableStateOf("") }

    fun install(next: NfPrefs) {
        prefs = store.save(next)
        CapabilityRegistry.install(prefs)
        onModulesChanged()
    }

    fun applyTheme(theme: PrefsTheme) {
        onThemeMode(
            when (theme) {
                PrefsTheme.LIGHT -> ThemeMode.LIGHT
                PrefsTheme.DARK, PrefsTheme.HIGH_CONTRAST -> ThemeMode.DARK
                PrefsTheme.SYSTEM -> ThemeMode.SYSTEM
            }
        )
    }

    fun applyLanguage(language: LanguageMode) = onLanguageMode(language)

    val importPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            runCatching { FileAccess.readText(context, uri) }
                .onSuccess { text ->
                    runCatching { store.importJson(text) }
                        .onSuccess { imported ->
                            prefs = imported
                            CapabilityRegistry.install(imported)
                            onModulesChanged()
                            applyTheme(imported.ui.theme)
                            applyLanguage(imported.language)
                            note = context.getString(R.string.settings_prefs_imported)
                        }
                        .onFailure { note = context.getString(R.string.settings_prefs_invalid, it.message ?: it.javaClass.simpleName) }
                }
                .onFailure { note = context.getString(R.string.settings_prefs_invalid, it.message ?: it.javaClass.simpleName) }
        }
    }

    CardBox(title = stringResource(R.string.settings_free_layer)) {
        Text(
            stringResource(R.string.settings_modules_hint),
            style = NfType.meta,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        Text(stringResource(R.string.settings_workflow_presets), style = NfType.sectionTitle)
        Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
            prefs.workflows.filter { it.source == "builtin" }.forEach { preset ->
                val label = presetLabel(preset.id)
                TextButton(onClick = {
                    val next = store.applyWorkflow(preset.id)
                    prefs = next
                    CapabilityRegistry.install(next)
                    onModulesChanged()
                    applyTheme(next.ui.theme)
                    note = context.getString(R.string.settings_workflow_applied, label)
                }) { Text(label) }
            }
        }
        TextButton(onClick = {
            saveName = context.getString(R.string.settings_workflow_save_user)
            showSave = true
        }) { Text(stringResource(R.string.settings_workflow_save_user)) }

        Text(stringResource(R.string.settings_modules), style = NfType.sectionTitle)
        Capability.entries.forEach { cap ->
            Row(
                modifier = Modifier.fillMaxWidth().padding(vertical = NfSpacing.xs),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(capabilityLabel(cap), style = NfType.body)
                    Text(
                        capabilityDescription(cap),
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Switch(
                    checked = prefs.modules.enabled(cap),
                    onCheckedChange = { enabled ->
                        install(prefs.copy(modules = prefs.modules.with(cap, enabled)))
                        note = context.getString(R.string.settings_prefs_saved)
                    }
                )
            }
        }

        Text(stringResource(R.string.settings_ui_appearance), style = NfType.sectionTitle)
        Text(stringResource(R.string.settings_density), style = NfType.meta)
        Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
            Density.entries.forEach { density ->
                FilterChip(
                    selected = prefs.ui.density == density,
                    onClick = {
                        install(prefs.copy(ui = prefs.ui.copy(density = density)))
                    },
                    label = { Text(densityLabel(density)) }
                )
            }
        }
        Text(stringResource(R.string.settings_font_scale), style = NfType.meta)
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
            TextButton(
                enabled = prefs.ui.fontScalePercent > 80,
                onClick = {
                    install(prefs.copy(ui = prefs.ui.copy(fontScalePercent = (prefs.ui.fontScalePercent - 10).coerceAtLeast(80))))
                }
            ) { Text(stringResource(R.string.settings_font_decrease)) }
            Text(stringResource(R.string.settings_font_scale_value, prefs.ui.fontScalePercent))
            TextButton(
                enabled = prefs.ui.fontScalePercent < 200,
                onClick = {
                    install(prefs.copy(ui = prefs.ui.copy(fontScalePercent = (prefs.ui.fontScalePercent + 10).coerceAtMost(200))))
                }
            ) { Text(stringResource(R.string.settings_font_increase)) }
        }
        Text(stringResource(R.string.settings_theme), style = NfType.meta)
        Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
            listOf(PrefsTheme.SYSTEM, PrefsTheme.LIGHT, PrefsTheme.DARK).forEach { theme ->
                FilterChip(
                    selected = prefs.ui.theme == theme,
                    onClick = {
                        install(prefs.copy(ui = prefs.ui.copy(theme = theme)))
                        applyTheme(theme)
                    },
                    label = { Text(themeLabel(theme)) }
                )
            }
        }
        Text(stringResource(R.string.settings_language), style = NfType.meta)
        Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
            listOf(LanguageMode.SYSTEM, LanguageMode.ZH, LanguageMode.EN).forEach { language ->
                FilterChip(
                    selected = prefs.language == language,
                    onClick = {
                        install(prefs.copy(language = language))
                        applyLanguage(language)
                    },
                    label = { Text(languageLabel(language)) }
                )
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.settings_motion), style = NfType.body, modifier = Modifier.weight(1f))
            Switch(
                checked = prefs.ui.motion,
                onCheckedChange = { motion -> install(prefs.copy(ui = prefs.ui.copy(motion = motion))) }
            )
        }

        Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
            TextButton(onClick = {
                clipboard.setText(AnnotatedString(store.exportJson()))
                note = context.getString(R.string.settings_prefs_exported)
            }) { Text(stringResource(R.string.settings_prefs_export)) }
            TextButton(onClick = { importPicker.launch(arrayOf("application/json", "text/plain")) }) {
                Text(stringResource(R.string.settings_prefs_import))
            }
            TextButton(onClick = { showReset = true }) { Text(stringResource(R.string.settings_prefs_reset)) }
        }
        note?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary) }
        store.lastError?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.error) }
    }

    if (showReset) {
        AlertDialog(
            onDismissRequest = { showReset = false },
            title = { Text(stringResource(R.string.settings_prefs_reset_title)) },
            text = { Text(stringResource(R.string.settings_prefs_reset_body)) },
            confirmButton = {
                TextButton(onClick = {
                    val reset = store.resetAll()
                    prefs = reset
                    CapabilityRegistry.install(reset)
                    onModulesChanged()
                    applyTheme(reset.ui.theme)
                    applyLanguage(reset.language)
                    showReset = false
                    note = context.getString(R.string.settings_prefs_saved)
                }) { Text(stringResource(R.string.settings_prefs_reset_confirm)) }
            },
            dismissButton = {
                TextButton(onClick = { showReset = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

    if (showSave) {
        AlertDialog(
            onDismissRequest = { showSave = false },
            title = { Text(stringResource(R.string.settings_workflow_save_user)) },
            text = {
                OutlinedTextField(
                    value = saveName,
                    onValueChange = { saveName = it },
                    singleLine = true,
                    label = { Text(stringResource(R.string.settings_workflow_presets)) }
                )
            },
            confirmButton = {
                TextButton(
                    enabled = saveName.isNotBlank(),
                    onClick = {
                        prefs = store.saveWorkflow(saveName)
                        CapabilityRegistry.install(prefs)
                        showSave = false
                        note = context.getString(R.string.settings_workflow_saved)
                    }
                ) { Text(stringResource(android.R.string.ok)) }
            },
            dismissButton = {
                TextButton(onClick = { showSave = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}

@Composable
private fun presetLabel(id: String): String = when (id) {
    "minimal" -> stringResource(R.string.settings_workflow_minimal)
    "standard" -> stringResource(R.string.settings_workflow_standard)
    "expert" -> stringResource(R.string.settings_workflow_expert)
    else -> id
}

@Composable
private fun capabilityLabel(capability: Capability): String = when (capability) {
    Capability.CONTRACT -> stringResource(R.string.settings_module_contract)
    Capability.BUILD_DIAG -> stringResource(R.string.settings_module_builddiag)
    Capability.FRAGMENTS -> stringResource(R.string.settings_module_fragments)
    Capability.MATRIX -> stringResource(R.string.settings_module_matrix)
    Capability.STYLE -> stringResource(R.string.settings_module_style)
    Capability.AI -> stringResource(R.string.settings_module_ai)
    Capability.MERGE -> stringResource(R.string.settings_module_merge)
    Capability.NETWORK -> stringResource(R.string.settings_module_network)
    Capability.SOURCES -> stringResource(R.string.settings_module_sources)
    Capability.MACROS -> stringResource(R.string.settings_module_macros)
    Capability.BATCH -> stringResource(R.string.settings_module_batch)
    Capability.SEARCH -> stringResource(R.string.settings_module_search)
}

@Composable
private fun capabilityDescription(capability: Capability): String = when (capability) {
    Capability.CONTRACT -> stringResource(R.string.settings_module_contract_desc)
    Capability.BUILD_DIAG -> stringResource(R.string.settings_module_builddiag_desc)
    Capability.FRAGMENTS -> stringResource(R.string.settings_module_fragments_desc)
    Capability.MATRIX -> stringResource(R.string.settings_module_matrix_desc)
    Capability.STYLE -> stringResource(R.string.settings_module_style_desc)
    Capability.AI -> stringResource(R.string.settings_module_ai_desc)
    Capability.MERGE -> stringResource(R.string.settings_module_merge_desc)
    Capability.NETWORK -> stringResource(R.string.settings_module_network_desc)
    Capability.SOURCES -> stringResource(R.string.settings_module_sources_desc)
    Capability.MACROS -> stringResource(R.string.settings_module_macros_desc)
    Capability.BATCH -> stringResource(R.string.settings_module_batch_desc)
    Capability.SEARCH -> stringResource(R.string.settings_module_search_desc)
}

@Composable
private fun densityLabel(density: Density): String = when (density) {
    Density.COMFORTABLE -> stringResource(R.string.settings_density_comfortable)
    Density.COMPACT -> stringResource(R.string.settings_density_compact)
}

@Composable
private fun themeLabel(theme: PrefsTheme): String = when (theme) {
    PrefsTheme.SYSTEM -> stringResource(R.string.theme_system)
    PrefsTheme.LIGHT -> stringResource(R.string.theme_light)
    PrefsTheme.DARK -> stringResource(R.string.theme_dark)
    PrefsTheme.HIGH_CONTRAST -> stringResource(R.string.settings_theme_high_contrast)
}

@Composable
private fun languageLabel(language: LanguageMode): String = when (language) {
    LanguageMode.SYSTEM -> stringResource(R.string.settings_language_system)
    LanguageMode.ZH -> stringResource(R.string.settings_language_zh)
    LanguageMode.EN -> stringResource(R.string.settings_language_en)
    LanguageMode.PSEUDO -> stringResource(R.string.settings_language_pseudo)
}
