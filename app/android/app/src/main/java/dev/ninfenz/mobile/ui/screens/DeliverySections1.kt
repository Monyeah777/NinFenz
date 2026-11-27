package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.data.Capability
import dev.ninfenz.mobile.data.CapabilityRegistry
import dev.ninfenz.mobile.data.MacroStore
import dev.ninfenz.mobile.data.SourceStore
import dev.ninfenz.mobile.model.FidelityReconciler
import dev.ninfenz.mobile.ui.components.NfEmptyState
import dev.ninfenz.mobile.ui.components.NfErrorCard
import dev.ninfenz.mobile.ui.components.NfLoadingState
import dev.ninfenz.mobile.ui.components.NfStepStrip
import dev.ninfenz.mobile.ui.components.NfStatusChip
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType
import kotlinx.coroutines.launch

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.RootShell() {
    BackHandler { handleBack() }
    Column(modifier = Modifier.fillMaxSize().imePadding()) {
        TopBar()
        StepStrip()
        Body()
    }
}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.TopBar() {
    NfTopAppBar(
        title = stringResource(dev.ninfenz.mobile.R.string.delivery_title, project.title),
        onBack = { if (hasWork) showLeaveConfirm = true else onBack() },
        actions = {
            IconButton(onClick = { deliveryMenu = true }, modifier = Modifier.size(48.dp)) {
                Icon(Icons.Filled.MoreVert, contentDescription = stringResource(dev.ninfenz.mobile.R.string.common_more))
            }
            TopBarMenu()
        }
    )
}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.TopBarMenu() {
    DropdownMenu(expanded = deliveryMenu, onDismissRequest = { deliveryMenu = false }) {
        TopBarMenuItems1()
        TopBarMenuItems1b()
        TopBarMenuItems2()
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.TopBarMenuItems1() {
    if (plan != null) {
        DropdownMenuItem(
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_assemble)) },
            onClick = {
                deliveryMenu = false
                scope.launch { assembleRequester.bringIntoView() }
            }
        )
    }
    if (capabilityRevision >= 0 && CapabilityRegistry.isEnabled(Capability.MACROS)) {
        DropdownMenuItem(
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_run_macro)) },
            onClick = {
                deliveryMenu = false
                macroItems = MacroStore(context.filesDir).list()
                showMacros = true
            }
        )
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.TopBarMenuItems1b() {
    if (plan != null || inputs.isNotEmpty() || markdown != null || report != null) {
        DropdownMenuItem(
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_reset)) },
            onClick = { deliveryMenu = false; showResetConfirm = true }
        )
    }
    if (capabilityRevision >= 0 && CapabilityRegistry.isEnabled(Capability.SOURCES)) {
        DropdownMenuItem(
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_sources_appendix)) },
            onClick = {
                deliveryMenu = false
                val base = markdown.orEmpty()
                val next = SourceStore(context.filesDir, project.id).renderCitations(base)
                if (next == base) {
                    variantNote = context.getString(dev.ninfenz.mobile.R.string.delivery_sources_none)
                } else {
                    markdown = next
                    needsRevalidate = true
                    variantNote = context.getString(dev.ninfenz.mobile.R.string.delivery_sources_appended)
                }
            }
        )
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.TopBarMenuItems2() {
    DropdownMenuItem(
        text = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_fidelity)) },
        onClick = {
            deliveryMenu = false
            val currentMarkdown = markdown.orEmpty()
            val spec = specMeta
            if (currentMarkdown.isBlank() || spec == null) {
                variantNote = context.getString(dev.ninfenz.mobile.R.string.delivery_fidelity_none)
            } else {
                fidelityResult = FidelityReconciler.fromSpec(spec, currentMarkdown)
            }
        }
    )
    DropdownMenuItem(
        text = { Text(stringResource(dev.ninfenz.mobile.R.string.patch_title)) },
        onClick = { deliveryMenu = false; onPatch() }
    )
}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.StepStrip() {
    val stepLabels = if (audit) listOf(
        stringResource(dev.ninfenz.mobile.R.string.delivery_plan),
        stringResource(dev.ninfenz.mobile.R.string.delivery_slots),
        stringResource(dev.ninfenz.mobile.R.string.delivery_assemble_validate),
        stringResource(dev.ninfenz.mobile.R.string.delivery_export_section)
    ) else listOf(
        stringResource(dev.ninfenz.mobile.R.string.delivery_plan),
        stringResource(dev.ninfenz.mobile.R.string.delivery_slots),
        stringResource(dev.ninfenz.mobile.R.string.delivery_export_section)
    )
    NfStepStrip(
        steps = stepLabels,
        current = if (!audit && activeStep >= 3) 2 else activeStep,
        onStepClick = { i ->
            activeStep = if (!audit && i == 2) 3 else i
        }
    )
}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.Body() {
    val deliveryScroll = rememberScrollState()
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(deliveryScroll)
            .padding(bottom = 96.dp),
        verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
    ) {
        BodyHeader()
        BodyStatusLines()
        ValidateEffect()
        CompileEffect()
        StepContent()
    }
}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.BodyHeader() {
    Column(
        modifier = Modifier.padding(horizontal = NfSpacing.page),
        verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            NfStatusChip(statusText(context, status))
            Text(
                stringResource(dev.ninfenz.mobile.R.string.delivery_pack_label, project.refs.basePackId, project.refs.basePackVersion),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.weight(1f),
                textAlign = androidx.compose.ui.text.style.TextAlign.End
            )
        }
        specMeta?.let { meta ->
            Text(
                meta.title + " · v" + meta.version,
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        Text(stringResource(if (audit) dev.ninfenz.mobile.R.string.delivery_note else dev.ninfenz.mobile.R.string.delivery_note_daily), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.BodyStatusLines() {
    statusNote?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
    if (audit && needsRevalidate) {
        Text(
            stringResource(dev.ninfenz.mobile.R.string.delivery_need_revalidate),
            style = NfType.meta,
            color = MaterialTheme.colorScheme.error,
            modifier = Modifier.padding(horizontal = NfSpacing.page)
        )
    }
    if (contractUnsatisfiable) {
        Text(
            stringResource(dev.ninfenz.mobile.R.string.delivery_contract_unsat),
            style = NfType.meta,
            color = MaterialTheme.colorScheme.error,
            modifier = Modifier.padding(horizontal = NfSpacing.page)
        )
    }
    if (loading) NfLoadingState()
    if (loadError != null) {
        NfErrorCard("NF-PCK-003", stringResource(dev.ninfenz.mobile.R.string.delivery_load_error, requireNotNull(loadError)), stringResource(dev.ninfenz.mobile.R.string.delivery_load_fix), modifier = Modifier.padding(horizontal = NfSpacing.page))
    }
    error?.let { err -> NfErrorCard(err.code, err.message, err.fix, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.ValidateEffect() {
    LaunchedEffect(specMeta, inputs) {
        val slots = specMeta?.slots.orEmpty()
        missingRequired = missingSlotIds(slots, inputs)
        oversizedSlots = oversizedSlotIds(slots, inputs)
        constraintViolations = violatingSlotIds(slots, inputs)
    }
}

internal fun missingSlotIds(slots: List<dev.ninfenz.mobile.model.SpecSlot>, inputs: Map<String, String>): List<String> =
    slots.filter { it.required && (it.visibleIf?.let { c -> inputs[c.slot] == c.equals } ?: true) && inputs[it.id].isNullOrBlank() }.map { it.id }

internal fun oversizedSlotIds(slots: List<dev.ninfenz.mobile.model.SpecSlot>, inputs: Map<String, String>): List<String> =
    slots.filter { slot ->
        val text = inputs[slot.id].orEmpty()
        (slot.minChars != null && text.isNotBlank() && text.length < slot.minChars) || (slot.maxChars != null && text.length > slot.maxChars)
    }.map { it.id }

internal fun violatingSlotIds(slots: List<dev.ninfenz.mobile.model.SpecSlot>, inputs: Map<String, String>): List<String> =
    slots.filter { slot -> slotPatternBad(slot, inputs[slot.id].orEmpty()) || slotBoundsBad(slot, inputs[slot.id].orEmpty()) }.map { it.id }

private fun slotPatternBad(slot: dev.ninfenz.mobile.model.SpecSlot, text: String): Boolean =
    slot.pattern?.let { pattern -> text.isNotBlank() && runCatching { Regex(pattern).containsMatchIn(text) }.getOrDefault(false).not() } == true

private fun slotBoundsBad(slot: dev.ninfenz.mobile.model.SpecSlot, text: String): Boolean {
    val nonEmptyBad = slot.nonEmpty && (slot.required || text.isNotBlank()) && text.isBlank()
    val prefixBad = slot.startsWith?.let { text.isNotBlank() && !text.startsWith(it) } == true
    val suffixBad = slot.endsWith?.let { text.isNotBlank() && !text.endsWith(it) } == true
    return nonEmptyBad || prefixBad || suffixBad
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.CompileEffect() {
    val current = artifacts
    LaunchedEffect(current) {
        if (current != null && plan == null && restoredPlan == null) compilePlan(current)
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.PackMissingBranch() {
    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = project.title, onBack = onBack)
        NfEmptyState(
            icon = Icons.Filled.Info,
            title = stringResource(dev.ninfenz.mobile.R.string.delivery_pack_missing_title),
            message = stringResource(dev.ninfenz.mobile.R.string.delivery_pack_missing_body, project.refs.basePackId),
            actionLabel = stringResource(dev.ninfenz.mobile.R.string.pack_open_center),
            onAction = onOpenPacks
        )
    }
}
