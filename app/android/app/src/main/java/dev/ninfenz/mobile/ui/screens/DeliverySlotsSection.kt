package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.TextButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import dev.ninfenz.mobile.model.AssemblyPlan
import dev.ninfenz.mobile.model.SlotInput
import dev.ninfenz.mobile.ui.components.NfCollapsibleSection
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType

internal class DeliverySlotsArgs(
    val plan: AssemblyPlan?,
    val specMeta: dev.ninfenz.mobile.model.MdSpec?,
    val inputs: Map<String, String>,
    val parsedTemplateSlots: Map<String, String>,
    val batchNote: String?,
    val variantNote: String?,
    val draftNote: String?,
    val batchUndo: Map<String, String>?,
    val hasVariants: Boolean,
    val hasTransforms: Boolean,
    val onShowConstraintLens: () -> Unit,
    val onBatchImport: () -> Unit,
    val onShowPresets: () -> Unit,
    val onShowVariants: () -> Unit,
    val onShowTransforms: () -> Unit,
    val onUndoBatch: (Map<String, String>) -> Unit,
    val onInputsChange: (Map<String, String>) -> Unit,
    val onPaste: (String) -> Unit,
    val onOpenPicker: (String) -> Unit,
    val onFillTemplate: () -> Unit
)

@Composable
internal fun DeliverySlotsSection(a: DeliverySlotsArgs) {
    NfCollapsibleSection(
        title = stringResource(dev.ninfenz.mobile.R.string.delivery_slots),
        subtitle = a.plan?.let { stringResource(dev.ninfenz.mobile.R.string.delivery_plan_summary, it.steps.size, it.slots.size) },
        initiallyExpanded = true
    ) {
        a.plan?.let { SlotsToolbar(a) }
        val p = a.plan
        if (p == null) {
            Text(stringResource(dev.ninfenz.mobile.R.string.delivery_compile_first), style = NfType.meta, modifier = Modifier.padding(horizontal = NfSpacing.page))
        } else if (p.slots.isEmpty()) {
            Text(stringResource(dev.ninfenz.mobile.R.string.delivery_no_slots), style = NfType.meta, modifier = Modifier.padding(horizontal = NfSpacing.page))
        } else {
            val requiredSlots = a.specMeta?.slots?.filter { it.required && slotVisible(it, a.inputs) }.orEmpty()
            if (requiredSlots.isNotEmpty()) SlotsProgressBlock(a, requiredSlots)
            var lastSection: String? = null
            for (slot in p.slots) {
                val slotMeta = a.specMeta?.slots?.firstOrNull { it.id == slot }
                if (!slotVisible(slotMeta, a.inputs)) continue
                Column(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                    val sectionTitle = slotMeta?.let { meta -> a.specMeta?.sections?.firstOrNull { it.id == meta.section }?.title }
                    val sectionId = slotMeta?.section
                    if (sectionTitle != null && sectionId != null && sectionId != lastSection) {
                        val sectionSlots = a.specMeta?.sections?.firstOrNull { it.id == sectionId }?.slots.orEmpty()
                        val sectionFilled = sectionSlots.count { !a.inputs[it].isNullOrBlank() }
                        SlotsSectionHeader(sectionTitle, sectionFilled, sectionSlots.size)
                        lastSection = sectionId
                    }
                    SlotMetaBlock(slot, slotMeta)
                    SlotActionRow(slot, slotMeta, a.inputs, a.onInputsChange, a.onPaste, a.onOpenPicker)
                    SlotEditorField(slot, slotMeta, a.inputs, a.onInputsChange, p.slots.lastOrNull() == slot)
                }
            }
        }
    }
}

@Composable
internal fun SlotsToolbar(a: DeliverySlotsArgs) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            stringResource(dev.ninfenz.mobile.R.string.delivery_slot_batch_hint),
            style = NfType.meta,
            modifier = Modifier.weight(1f)
        )
        Row {
            TextButton(onClick = a.onShowConstraintLens) {
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_constraint_panel))
            }
            TextButton(onClick = a.onBatchImport) {
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_batch_import))
            }
            TextButton(onClick = a.onShowPresets) {
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_presets))
            }
            if (a.hasVariants) {
                TextButton(onClick = a.onShowVariants) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_variants))
                }
            }
            if (a.hasTransforms) {
                TextButton(onClick = a.onShowTransforms) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_transforms))
                }
            }
        }
    }
    a.batchNote?.let {
        Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page))
    }
    a.variantNote?.let {
        Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page))
    }
    a.batchUndo?.let { snapshot ->
        TextButton(
            onClick = { a.onUndoBatch(snapshot) },
            modifier = Modifier.padding(horizontal = NfSpacing.page)
        ) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_batch_undo)) }
    }
    a.draftNote?.let {
        Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(horizontal = NfSpacing.page))
    }
}

@Composable
internal fun SlotsSectionHeader(title: String, filled: Int, total: Int) {
    Text(
        title + "  " + filled + "/" + total,
        style = NfType.itemTitle,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.semantics { heading() }
    )
}

@Composable
internal fun SlotsProgressBlock(a: DeliverySlotsArgs, requiredSlots: List<dev.ninfenz.mobile.model.SpecSlot>) {
    val plan = a.plan ?: return
    val requiredFilled = requiredSlots.count { !a.inputs[it.id].isNullOrBlank() }
    Text(
        stringResource(dev.ninfenz.mobile.R.string.delivery_required_progress, requiredFilled, requiredSlots.size),
        style = NfType.meta,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(horizontal = NfSpacing.page)
    )
    androidx.compose.material3.LinearProgressIndicator(
        progress = { requiredFilled.toFloat() / requiredSlots.size.toFloat() },
        modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page)
    )
    val fillable = a.parsedTemplateSlots.count { (id, value) ->
        id in plan.slots && a.inputs[id].isNullOrBlank() &&
            templateValueAllowed(a.specMeta?.slots?.firstOrNull { it.id == id }, value)
    }
    if (fillable > 0) {
        TextButton(onClick = a.onFillTemplate) {
            Text(pluralStringResource(dev.ninfenz.mobile.R.plurals.delivery_fill_template_count, fillable, fillable))
        }
    }
}

@Composable
internal fun SlotMetaBlock(slot: String, slotMeta: dev.ninfenz.mobile.model.SpecSlot?) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Text(slot, style = NfType.label)
            slotMeta?.let {
                Text(it.name, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(
                    stringResource(if (it.required) dev.ninfenz.mobile.R.string.delivery_slot_required else dev.ninfenz.mobile.R.string.delivery_slot_optional),
                    style = NfType.meta,
                    color = if (it.required) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
                )
                Text(it.kind, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (it.minChars != null || it.maxChars != null) {
                    Text(
                        when {
                            it.minChars != null && it.maxChars != null ->
                                stringResource(dev.ninfenz.mobile.R.string.delivery_slot_budget, it.minChars, it.maxChars)
                            it.maxChars != null ->
                                stringResource(dev.ninfenz.mobile.R.string.delivery_slot_budget_max, it.maxChars)
                            else ->
                                stringResource(dev.ninfenz.mobile.R.string.delivery_slot_budget_min, it.minChars ?: 0)
                        },
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                val rules = listOfNotNull(
                    it.pattern?.let { pattern -> "pattern: " + pattern },
                    it.startsWith?.let { prefix -> "start: " + prefix },
                    it.endsWith?.let { suffix -> "end: " + suffix },
                    if (it.nonEmpty) "non-empty" else null
                )
                if (rules.isNotEmpty()) {
                    Text(
                        rules.joinToString(" · "),
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}

@Composable
internal fun SlotActionRow(
    slot: String,
    slotMeta: dev.ninfenz.mobile.model.SpecSlot?,
    inputs: Map<String, String>,
    onInputsChange: (Map<String, String>) -> Unit,
    onPaste: (String) -> Unit,
    onOpenPicker: (String) -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(top = NfSpacing.xs),
        horizontalArrangement = Arrangement.End
    ) {
        slotMeta?.examples?.firstOrNull()?.let { example ->
            TextButton(onClick = { onInputsChange(inputs + (slot to example)) }) {
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_example))
            }
        }
        if ((inputs[slot] ?: "").isNotBlank()) {
            TextButton(onClick = { onInputsChange(inputs - slot) }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_clear)) }
        }
        TextButton(onClick = { onPaste(slot) }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_paste)) }
        TextButton(onClick = { onOpenPicker(slot) }) { Text(stringResource(dev.ninfenz.mobile.R.string.action_import)) }
    }
}

@Composable
internal fun SlotEditorField(
    slot: String,
    slotMeta: dev.ninfenz.mobile.model.SpecSlot?,
    inputs: Map<String, String>,
    onInputsChange: (Map<String, String>) -> Unit,
    lastSlot: Boolean
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val focusManager = androidx.compose.ui.platform.LocalFocusManager.current
    OutlinedTextField(
        value = inputs[slot] ?: "",
        onValueChange = { value ->
            val clean = SlotInput.sanitize(slotMeta?.kind, value)
            val limited = slotMeta?.maxChars?.let { clean.take(it) } ?: clean
            onInputsChange(inputs + (slot to limited))
        },
        singleLine = false,
        minLines = 2,
        maxLines = 6,
        keyboardOptions = KeyboardOptions(
            keyboardType = when (slotMeta?.kind) {
                "number", "int", "integer" -> KeyboardType.Number
                "decimal", "float" -> KeyboardType.Decimal
                else -> KeyboardType.Text
            },
            imeAction = if (lastSlot) ImeAction.Done else ImeAction.Next
        ),
        keyboardActions = KeyboardActions(
            onDone = { focusManager.clearFocus() },
            onNext = { focusManager.moveFocus(FocusDirection.Down) }
        ),
        placeholder = { Text(slotMeta?.examples?.firstOrNull().orEmpty(), maxLines = 2) },
        textStyle = if (slotMeta?.kind == "code" || slotMeta?.kind == "json") {
            NfType.secondary.copy(fontFamily = FontFamily.Monospace)
        } else {
            NfType.secondary
        },
        supportingText = {
            val issue = slotIssue(context, slotMeta, inputs[slot].orEmpty())
            if (issue != null) {
                Text(issue, color = MaterialTheme.colorScheme.error)
            } else {
                Text(pluralStringResource(dev.ninfenz.mobile.R.plurals.delivery_slot_chars, (inputs[slot] ?: "").length, (inputs[slot] ?: "").length))
            }
        },
        modifier = Modifier.fillMaxWidth().semantics {
            contentDescription = slot + " " + (slotMeta?.name ?: "")
        }
    )
}
