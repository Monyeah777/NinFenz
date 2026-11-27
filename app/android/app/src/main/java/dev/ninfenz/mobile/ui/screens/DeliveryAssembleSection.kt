package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.TextButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import dev.ninfenz.mobile.model.AssemblyPlan
import dev.ninfenz.mobile.model.ReportModel
import dev.ninfenz.mobile.model.ValidateReport
import dev.ninfenz.mobile.ui.components.NfCard
import dev.ninfenz.mobile.ui.components.NfSectionHeader
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType
import java.io.File

internal class DeliveryAssembleArgs(
    val needsRevalidate: Boolean,
    val busy: Boolean,
    val canAssemble: Boolean,
    val canValidate: Boolean,
    val missingRequired: List<String>,
    val oversizedSlots: List<String>,
    val constraintViolations: List<String>,
    val markdown: String?,
    val exportMarkdown: String?,
    val report: ValidateReport?,
    val validateRepro: String?,
    val signoff: dev.ninfenz.mobile.data.ContractStore.Signoff?,
    val exportedFile: File?,
    val plan: AssemblyPlan?,
    val specMeta: dev.ninfenz.mobile.model.MdSpec?,
    val inputs: Map<String, String>,
    val assembleRequester: BringIntoViewRequester,
    val validateRequester: BringIntoViewRequester,
    val onAssemble: () -> Unit,
    val onValidate: () -> Unit,
    val onShareFix: (ValidateReport) -> Unit,
    val onSign: (List<Pair<String, Boolean>>) -> Unit,
    val onGoValidate: () -> Unit
)

@Composable
internal fun DeliveryAssembleSection(a: DeliveryAssembleArgs) {
    if (a.needsRevalidate) {
        NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_dirty_title), style = NfType.itemTitle, color = MaterialTheme.colorScheme.error)
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_dirty_body), style = NfType.meta)
            }
        }
    }
    NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.delivery_assemble_validate))
    DeliveryAssembleButtons(a)
    a.report?.let { r -> DeliveryReportBlock(r, a.markdown, a.validateRepro, a.onShareFix) }
    if (a.report?.verdict == "pass" && a.markdown != null) DeliveryContractBlock(a)
    if (a.markdown != null && a.exportMarkdown == null) DeliveryExportBlockedRow(a.onGoValidate)
}

@Composable
internal fun DeliveryAssembleButtons(a: DeliveryAssembleArgs) {
    FlowRow(
        modifier = Modifier.padding(horizontal = NfSpacing.page),
        horizontalArrangement = Arrangement.spacedBy(NfSpacing.s),
        verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)
    ) {
        Button(
            enabled = a.canAssemble,
            modifier = Modifier.bringIntoViewRequester(a.assembleRequester),
            onClick = a.onAssemble
        ) { Text(if (a.busy) stringResource(dev.ninfenz.mobile.R.string.delivery_assembling) else stringResource(dev.ninfenz.mobile.R.string.delivery_assemble)) }
        if (a.constraintViolations.isNotEmpty()) {
            Text(
                stringResource(dev.ninfenz.mobile.R.string.delivery_slot_constraint, a.constraintViolations.joinToString(", ")),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(horizontal = NfSpacing.page)
            )
        }
        if (a.oversizedSlots.isNotEmpty()) {
            Text(
                stringResource(dev.ninfenz.mobile.R.string.delivery_slot_over_budget, a.oversizedSlots.joinToString(", ")),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(horizontal = NfSpacing.page)
            )
        }
        if (a.missingRequired.isNotEmpty()) {
            Text(
                stringResource(dev.ninfenz.mobile.R.string.delivery_missing_required, a.missingRequired.joinToString(", ")),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(horizontal = NfSpacing.page)
            )
        }
        Button(
            enabled = a.canValidate,
            modifier = Modifier.bringIntoViewRequester(a.validateRequester),
            onClick = a.onValidate
        ) { Text(if (a.busy) stringResource(dev.ninfenz.mobile.R.string.delivery_validating) else stringResource(dev.ninfenz.mobile.R.string.delivery_validate)) }
    }
}

@Composable
internal fun DeliveryReportBlock(
    r: ValidateReport,
    markdown: String?,
    validateRepro: String?,
    onShareFix: (ValidateReport) -> Unit
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    Text(ReportModel.line(r), style = NfType.secondary, modifier = Modifier.padding(horizontal = NfSpacing.page))
    validateRepro?.let {
        Text(it, style = NfType.meta, modifier = Modifier.padding(horizontal = NfSpacing.page))
    }
    if (r.issues.isNotEmpty() && markdown != null) {
        TextButton(onClick = { onShareFix(r) }, modifier = Modifier.padding(horizontal = NfSpacing.page)) {
            Text(stringResource(dev.ninfenz.mobile.R.string.delivery_share_fix))
        }
    }
    for (issue in r.issues.take(20)) {
        Text(
            issue.code + " " + (issue.path ?: "-") + "：" + issue.message + context.getString(dev.ninfenz.mobile.R.string.error_fix_suffix) + issue.fix,
            style = NfType.meta,
            color = if (issue.severity == "error") MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(horizontal = NfSpacing.page)
        )
    }
}

@Composable
internal fun DeliveryContractBlock(a: DeliveryAssembleArgs) {
    val requiredSlots = a.plan?.slots?.filter { id ->
        a.specMeta?.slots?.firstOrNull { it.id == id }?.required == true
    }.orEmpty()
    val slotsFilled = requiredSlots.isEmpty() || requiredSlots.all { a.inputs[it].orEmpty().isNotBlank() }
    val checks = listOf(
        stringResource(dev.ninfenz.mobile.R.string.contract_l1) to true,
        stringResource(dev.ninfenz.mobile.R.string.contract_slots) to slotsFilled,
        stringResource(dev.ninfenz.mobile.R.string.contract_export) to (a.exportedFile != null)
    )
    Column(Modifier.padding(horizontal = NfSpacing.page, vertical = NfSpacing.s), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
        Text(stringResource(dev.ninfenz.mobile.R.string.contract_title), style = NfType.itemTitle)
        checks.forEach { (label, ok) ->
            Text((if (ok) "✓ " else "✗ ") + label, style = NfType.meta, color = if (ok) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error)
        }
        val signed = a.signoff
        val currentDigest = a.exportedFile?.let { sha256File(it) }
        val stale = signed != null && (signed.artifactSha256 == null || signed.artifactSha256 != currentDigest)
        if (signed != null && !stale) {
            Text(stringResource(dev.ninfenz.mobile.R.string.contract_signed, signed.signedAt), style = NfType.meta)
            signed.artifactSha256?.let { Text(stringResource(dev.ninfenz.mobile.R.string.contract_artifact, it), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            signed.keyFingerprint?.let { Text(stringResource(dev.ninfenz.mobile.R.string.contract_key, it.take(16)), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        } else {
            if (stale) {
                Text(stringResource(dev.ninfenz.mobile.R.string.contract_stale), style = NfType.meta, color = MaterialTheme.colorScheme.error)
            }
            Button(
                enabled = checks.all { it.second },
                onClick = { a.onSign(checks) }
            ) { Text(stringResource(dev.ninfenz.mobile.R.string.contract_sign)) }
            if (!checks.all { it.second }) {
                Text(stringResource(dev.ninfenz.mobile.R.string.contract_blocked), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
internal fun DeliveryExportBlockedRow(onGoValidate: () -> Unit) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.padding(horizontal = NfSpacing.page)
    ) {
        Text(
            stringResource(dev.ninfenz.mobile.R.string.delivery_export_blocked),
            style = NfType.meta,
            color = MaterialTheme.colorScheme.error,
            modifier = Modifier.weight(1f)
        )
        TextButton(onClick = onGoValidate) {
            Text(stringResource(dev.ninfenz.mobile.R.string.delivery_go_validate))
        }
    }
}
