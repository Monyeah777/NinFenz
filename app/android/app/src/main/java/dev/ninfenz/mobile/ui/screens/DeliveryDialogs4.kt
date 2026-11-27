package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.TextButton
import androidx.compose.foundation.layout.heightIn
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.model.SlotInput
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.BrowsePlanDialog() {
    if (showBrowsePlan) {
        AlertDialog(
            onDismissRequest = { showBrowsePlan = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_browse_plan)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("plan: " + (plan?.pipelineId ?: "-") + " · " + (plan?.steps?.size ?: 0) + " steps", style = NfType.label)
                    plan?.steps?.forEach { s -> Text("• " + s.id + " · " + s.node + " · " + s.module, style = NfType.meta) }
                    Text("spec: " + (specMeta?.id ?: "-") + " · " + (specMeta?.sections?.size ?: 0) + " sections", style = NfType.label)
                    specMeta?.sections?.forEach { s -> Text("• " + s.title + " · " + s.slots.size + " slots", style = NfType.meta) }
                    Text("slots: " + inputs.count { it.value.isNotBlank() } + "/" + inputs.size, style = NfType.label)
                }
            },
            confirmButton = { TextButton(onClick = { showBrowsePlan = false }) { Text(stringResource(android.R.string.ok)) } }
        )
    }

}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.ConstraintLensDialog() {
    if (showConstraintLens) {
        AlertDialog(
            onDismissRequest = { showConstraintLens = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_constraint_panel_title)) },
            text = { ConstraintLensBody() },
            confirmButton = {
                TextButton(onClick = { showConstraintLens = false }) {
                    Text(stringResource(android.R.string.ok))
                }
            }
        )
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.ConstraintLensBody() {
    Column(
        modifier = Modifier.heightIn(max = 520.dp).verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(NfSpacing.s)
    ) {
        val views = dev.ninfenz.mobile.model.ConstraintLens.view(specMeta?.slots.orEmpty(), inputs)
        if (views.isEmpty()) {
            Text(stringResource(dev.ninfenz.mobile.R.string.delivery_no_slots), style = NfType.meta)
        }
        views.forEach { view ->
            Text(view.id + " · " + view.name, style = NfType.itemTitle)
            Text(
                view.kind + " · " + stringResource(
                    if (view.required) dev.ninfenz.mobile.R.string.delivery_slot_required else dev.ninfenz.mobile.R.string.delivery_slot_optional
                ),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            OutlinedTextField(
                value = inputs[view.id].orEmpty(),
                onValueChange = { value ->
                    val clean = dev.ninfenz.mobile.model.SlotInput.sanitize(view.kind, value)
                    val limited = view.maxChars?.let { clean.take(it) } ?: clean
                    inputs = inputs + (view.id to limited)
                },
                label = { Text(view.name) },
                modifier = Modifier.fillMaxWidth(),
                minLines = 1,
                maxLines = 3
            )
            if (view.issues.isEmpty()) {
                Text(
                    stringResource(dev.ninfenz.mobile.R.string.delivery_constraint_ok),
                    style = NfType.meta,
                    color = MaterialTheme.colorScheme.primary
                )
            } else {
                Text(
                    view.issues.map { issue ->
                        when (issue) {
                            dev.ninfenz.mobile.model.ConstraintLens.Issue.REQUIRED -> stringResource(dev.ninfenz.mobile.R.string.delivery_constraint_issue_required)
                            dev.ninfenz.mobile.model.ConstraintLens.Issue.MIN -> stringResource(dev.ninfenz.mobile.R.string.delivery_constraint_issue_min)
                            dev.ninfenz.mobile.model.ConstraintLens.Issue.MAX -> stringResource(dev.ninfenz.mobile.R.string.delivery_constraint_issue_max)
                            dev.ninfenz.mobile.model.ConstraintLens.Issue.PREFIX -> stringResource(dev.ninfenz.mobile.R.string.delivery_constraint_issue_prefix)
                            dev.ninfenz.mobile.model.ConstraintLens.Issue.SUFFIX -> stringResource(dev.ninfenz.mobile.R.string.delivery_constraint_issue_suffix)
                            dev.ninfenz.mobile.model.ConstraintLens.Issue.PATTERN -> stringResource(dev.ninfenz.mobile.R.string.delivery_constraint_issue_pattern)
                        }
                    }.joinToString("；"),
                    style = NfType.meta,
                    color = MaterialTheme.colorScheme.error
                )
            }
        }
    }
}


@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.GrantDialog() {
    if (!showGrant) return
    val draft = remember(grant) { GrantDraft(grant) }
    AlertDialog(
        onDismissRequest = { showGrant = false },
        title = { Text(stringResource(dev.ninfenz.mobile.R.string.grant_title)) },
        text = { GrantDialogBody(grant, draft) },
        confirmButton = {
            TextButton(onClick = {
                val expiresAt = if (draft.days == 0) null else System.currentTimeMillis() + draft.days * 86_400_000L
                val next = dev.ninfenz.mobile.data.CapabilityGrant(draft.caps, expiresAt, draft.revoked)
                grantStore.save(project.id, next)
                grant = next
                showGrant = false
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.grant_save)) }
        },
        dismissButton = {
            TextButton(onClick = { showGrant = false }) { Text(stringResource(android.R.string.cancel)) }
        }
    )
}

internal class GrantDraft(grant: dev.ninfenz.mobile.data.CapabilityGrant) {
    var caps by mutableStateOf(grant.caps)
    var revoked by mutableStateOf(grant.revoked)
    var days by mutableIntStateOf(initialGrantDays(grant.expiresAt))
}

private fun initialGrantDays(expiresAt: Long?): Int = when {
    expiresAt == null -> 0
    expiresAt - System.currentTimeMillis() <= 7L * 86_400_000L -> 7
    else -> 30
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.GrantDialogBody(grant: dev.ninfenz.mobile.data.CapabilityGrant, draft: GrantDraft) {
    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
        Text(
            stringResource(
                dev.ninfenz.mobile.R.string.grant_current,
                grant.expiresAt?.let {
                    stringResource(dev.ninfenz.mobile.R.string.grant_until, java.text.DateFormat.getDateInstance().format(java.util.Date(it)))
                } ?: stringResource(dev.ninfenz.mobile.R.string.grant_no_expiry)
            ),
            style = NfType.meta,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(stringResource(dev.ninfenz.mobile.R.string.grant_caps), style = NfType.itemTitle)
        listOf(
            dev.ninfenz.mobile.data.CapabilityGrant.READ to dev.ninfenz.mobile.R.string.grant_cap_read,
            dev.ninfenz.mobile.data.CapabilityGrant.COMMENT to dev.ninfenz.mobile.R.string.grant_cap_comment,
            dev.ninfenz.mobile.data.CapabilityGrant.REASSEMBLE to dev.ninfenz.mobile.R.string.grant_cap_reassemble,
            dev.ninfenz.mobile.data.CapabilityGrant.EXPORT to dev.ninfenz.mobile.R.string.grant_cap_export,
            dev.ninfenz.mobile.data.CapabilityGrant.SHARE to dev.ninfenz.mobile.R.string.grant_cap_share
        ).forEach { (cap, label) ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(
                    checked = cap in draft.caps,
                    onCheckedChange = { checked ->
                        draft.caps = if (checked) draft.caps + cap else draft.caps - cap
                    }
                )
                Text(stringResource(label))
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = draft.revoked, onCheckedChange = { draft.revoked = it })
            Text(stringResource(dev.ninfenz.mobile.R.string.grant_revoked))
        }
        Text(stringResource(dev.ninfenz.mobile.R.string.grant_expiry), style = NfType.itemTitle)
        Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
            listOf(0 to dev.ninfenz.mobile.R.string.grant_never, 7 to dev.ninfenz.mobile.R.string.grant_7d, 30 to dev.ninfenz.mobile.R.string.grant_30d).forEach { (option, label) ->
                FilterChip(selected = draft.days == option, onClick = { draft.days = option }, label = { Text(stringResource(label)) })
            }
        }
    }
}
