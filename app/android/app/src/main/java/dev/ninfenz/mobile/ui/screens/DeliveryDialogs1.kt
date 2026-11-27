package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.TextButton
import androidx.compose.foundation.layout.heightIn
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.data.ExportProfileStore
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonPrimitive

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.SaveExportProfileDialog() {
    if (showSaveExportProfile) {
        AlertDialog(
            onDismissRequest = { showSaveExportProfile = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.export_profile_save)) },
            text = {
                OutlinedTextField(
                    value = exportProfileName,
                    onValueChange = { exportProfileName = it },
                    label = { Text(stringResource(dev.ninfenz.mobile.R.string.export_profile_name)) },
                    singleLine = true
                )
            },
            confirmButton = {
                TextButton(enabled = exportProfileName.isNotBlank(), onClick = {
                    exportProfiles = exportProfileStore.save(dev.ninfenz.mobile.data.ExportProfileStore.ProfileInput(exportProfileName, docxStyles, docxSectPr, docxTheme, docxNumbering, docxHeader, docxFooter, epubAuthor, epubLanguage, pdfPageSize, pdfIncludeTitle))
                    exportProfileName = ""
                    showSaveExportProfile = false
                }) { Text(stringResource(android.R.string.ok)) }
            },
            dismissButton = { TextButton(onClick = { showSaveExportProfile = false }) { Text(stringResource(android.R.string.cancel)) } }
        )
    }

}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.ExportProfilesDialog() {
    if (showExportProfiles) {
        AlertDialog(
            onDismissRequest = { showExportProfiles = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.export_profiles)) },
            text = {
                Column(modifier = Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    val allProfiles = exportProfiles + extensionProfiles
                    if (allProfiles.isEmpty()) Text(stringResource(dev.ninfenz.mobile.R.string.export_profiles_empty), style = NfType.meta)
                    allProfiles.forEach { profile ->
                        ExportProfileRow(profile, onApply = { applyExportProfile(it) }, onRemove = { removeExportProfile(it) })
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showExportProfiles = false }) { Text(stringResource(android.R.string.ok)) } }
        )
    }

}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.OutputRulesDialog() {
    if (showOutputRules) {
        AlertDialog(
            onDismissRequest = { showOutputRules = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_output_rule)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    TextButton(onClick = {
                        selectedOutputTemplate = null
                        outputRuleNote = context.getString(dev.ninfenz.mobile.R.string.delivery_output_rule_default)
                        showOutputRules = false
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_output_rule_default)) }
                    if (outputRules.isEmpty()) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_output_rule_empty), style = NfType.meta)
                    }
                    outputRules.forEach { rule ->
                        val template = rule.config["template"]?.toString()?.trim('"')?.takeIf { it.isNotBlank() }
                        TextButton(onClick = {
                            selectedOutputTemplate = template
                            outputRuleNote = rule.id
                            showOutputRules = false
                        }) { Text(rule.id + " · " + (template ?: "")) }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showOutputRules = false }) { Text(stringResource(android.R.string.cancel)) } }
        )
    }
}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.PreflightDialog() {
    if (showPreflight) {
        AlertDialog(
            onDismissRequest = { showPreflight = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_preflight)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    TextButton(onClick = { selectedPreflight = null; showPreflight = false }) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_preflight_default))
                    }
                    if (preflightProfiles.isEmpty()) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_preflight_empty), style = NfType.meta)
                    }
                    preflightProfiles.forEach { profile ->
                        TextButton(onClick = { selectedPreflight = profile; showPreflight = false }) {
                            Text(profile.id)
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showPreflight = false }) { Text(stringResource(android.R.string.cancel)) } }
        )
    }

}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.SavePresetDialog() {
    if (showSavePreset) {
        AlertDialog(
            onDismissRequest = { showSavePreset = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_save_preset)) },
            text = {
                OutlinedTextField(
                    value = presetName,
                    onValueChange = { presetName = it },
                    label = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_preset_name)) },
                    singleLine = true
                )
            },
            confirmButton = {
                TextButton(enabled = presetName.isNotBlank(), onClick = {
                    presetStore.save(project.id, presetName, inputs)
                    presetName = ""
                    showSavePreset = false
                }) { Text(stringResource(android.R.string.ok)) }
            },
            dismissButton = { TextButton(onClick = { showSavePreset = false }) { Text(stringResource(android.R.string.cancel)) } }
        )
    }

}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.VariantsDialog() {
    if (showVariants) {
        AlertDialog(
            onDismissRequest = { showVariants = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_variants)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    TextButton(enabled = rawPlan != null && !busy, onClick = { assembleAllVariants() }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_batch_assemble)) }
                    TextButton(enabled = rawPlan != null && !busy, onClick = { exportAllVariants() }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_batch_export)) }
                    extensionVariants.forEach { variant ->
                        TextButton(onClick = { applyVariant(variant) }) { Text(variant.id) }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showVariants = false }) { Text(stringResource(android.R.string.cancel)) } }
        )
    }
}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.TransformsDialog() {
    if (showTransforms) {
        AlertDialog(
            onDismissRequest = { showTransforms = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_transforms)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    extensionTransforms.forEach { recipe ->
                        TextButton(onClick = {
                            val kind = recipe.config["kind"]?.jsonPrimitive?.content.orEmpty()
                            val a = recipe.config["a"]?.jsonPrimitive?.content.orEmpty()
                            val b = recipe.config["b"]?.jsonPrimitive?.content.orEmpty()
                            val transform = dev.ninfenz.mobile.model.FlashFillModel.Transform(kind, a, b)
                            val before = inputs
                            val next = inputs.mapValues { (_, value) -> if (value.isNotBlank()) transform.apply(value) else value }
                            if (next != before) {
                                batchUndo = before
                                inputs = next
                                variantNote = context.getString(dev.ninfenz.mobile.R.string.delivery_transform_applied, recipe.id)
                                showTransforms = false
                            }
                        }) { Text(recipe.id) }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showTransforms = false }) { Text(stringResource(android.R.string.cancel)) } }
        )
    }

}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.PresetsDialog() {
    if (showPresets) {
        val presets = remember(showPresets) { presetStore.load(project.id) }
        AlertDialog(
            onDismissRequest = { showPresets = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_presets)) },
            text = {
                Column(modifier = Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    if (assemblyRecipes.isNotEmpty()) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_assembly_recipes), style = NfType.meta)
                        assemblyRecipes.forEach { recipe ->
                            val name = recipe.config["name"]?.toString()?.trim('"')?.ifBlank { recipe.id } ?: recipe.id
                            val recipeInputs = (recipe.config["inputs"] as? JsonObject)?.mapValues { it.value.jsonPrimitive.content }.orEmpty()
                            TextButton(onClick = {
                                presetStore.save(project.id, name, recipeInputs)
                                showPresets = false
                                variantNote = context.getString(dev.ninfenz.mobile.R.string.delivery_assembly_recipe_saved, name)
                            }) { Text(recipe.id) }
                        }
                    }
                    if (presets.isEmpty()) Text(stringResource(dev.ninfenz.mobile.R.string.delivery_presets_empty), style = NfType.meta)
                    presets.forEach { preset ->
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Text(preset.name + " · " + preset.inputs.size, style = NfType.meta)
                            Row {
                                TextButton(onClick = {
                                    inputs = inputs + preset.inputs
                                    showPresets = false
                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_apply_preset)) }
                                TextButton(onClick = { presetStore.remove(project.id, preset.id); showPresets = false }) { Text(stringResource(dev.ninfenz.mobile.R.string.inbox_remove)) }
                            }
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showSavePreset = true; showPresets = false }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_save_preset)) } },
            dismissButton = { TextButton(onClick = { showPresets = false }) { Text(stringResource(android.R.string.cancel)) } }
        )
    }

}
