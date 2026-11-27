package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.TextButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import dev.ninfenz.mobile.model.AssemblyPlan
import dev.ninfenz.mobile.ui.components.NfCard
import dev.ninfenz.mobile.ui.components.NfSectionHeader
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType

@Composable
internal fun DeliveryPlanSection(
    plan: AssemblyPlan?,
    busy: Boolean,
    constraintConflicts: List<List<dev.ninfenz.mobile.model.ConstraintMUS.Rule>>,
    onBrowsePlan: () -> Unit,
    onCompile: () -> Unit
) {
    NfSectionHeader(
        stringResource(dev.ninfenz.mobile.R.string.delivery_plan),
        action = {
            TextButton(onClick = onBrowsePlan) {
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_browse_plan))
            }
        }
    )
    Button(
        enabled = !busy,
        modifier = Modifier.padding(horizontal = NfSpacing.page),
        onClick = onCompile
    ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.delivery_compiling) else stringResource(dev.ninfenz.mobile.R.string.delivery_compile)) }
    plan?.let { p ->
        Text(
            stringResource(dev.ninfenz.mobile.R.string.delivery_plan_summary, p.steps.size, p.slots.size),
            style = NfType.meta,
            modifier = Modifier.padding(horizontal = NfSpacing.page)
        )
    }
    if (constraintConflicts.isNotEmpty()) {
        NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                Text(
                    pluralStringResource(dev.ninfenz.mobile.R.plurals.delivery_constraint_conflict, constraintConflicts.size, constraintConflicts.size),
                    style = NfType.itemTitle,
                    color = MaterialTheme.colorScheme.error
                )
                constraintConflicts.take(2).forEach { conflict ->
                    Text(
                        stringResource(
                            dev.ninfenz.mobile.R.string.delivery_constraint_conflict_detail,
                            conflict.joinToString(" + ") { it.id }
                        ),
                        style = NfType.meta
                    )
                }
            }
        }
    }
}
