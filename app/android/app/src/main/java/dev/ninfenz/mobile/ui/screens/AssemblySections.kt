package dev.ninfenz.mobile.ui.screens

import android.content.Intent
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.model.AssemblyPlan
import dev.ninfenz.mobile.model.MdSpec
import dev.ninfenz.mobile.model.PlanModel
import dev.ninfenz.mobile.model.ReportModel
import dev.ninfenz.mobile.model.SpecModel
import dev.ninfenz.mobile.model.ValidateReport
import dev.ninfenz.mobile.share.ShareExporter
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.components.EmptyState
import dev.ninfenz.mobile.ui.components.ErrorNotice
import dev.ninfenz.mobile.ui.components.FormTextField
import dev.ninfenz.mobile.ui.components.KeyValue
import dev.ninfenz.mobile.ui.components.MonoText
import dev.ninfenz.mobile.ui.components.NfScaffold
import dev.ninfenz.mobile.ui.components.Notice
import dev.ninfenz.mobile.ui.components.Tone
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.io.File

@Composable
internal fun AssemblyStepBar(
    reqInput: BringIntoViewRequester,
    reqSlots: BringIntoViewRequester,
    reqAssemble: BringIntoViewRequester,
    reqExport: BringIntoViewRequester
) {
    val scope = rememberCoroutineScope()
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(2.dp)) {
        val steps = listOf(
            stringResource(dev.ninfenz.mobile.R.string.assembly_input),
            stringResource(dev.ninfenz.mobile.R.string.assembly_slots),
            stringResource(dev.ninfenz.mobile.R.string.assembly_assemble),
            stringResource(dev.ninfenz.mobile.R.string.assembly_export)
        )
        val reqs = listOf(reqInput, reqSlots, reqAssemble, reqExport)
        steps.forEachIndexed { i, label ->
            TextButton(onClick = { scope.launch { reqs[i].bringIntoView() } }) {
                Text((i + 1).toString() + " · " + label, style = MaterialTheme.typography.labelMedium)
            }
        }
    }
}

@Composable
internal fun AssemblyBrowseDialog(
    plan: AssemblyPlan?,
    spec: MdSpec?,
    extraSlots: List<String>,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(dev.ninfenz.mobile.R.string.assembly_browse)) },
        text = {
            androidx.compose.foundation.layout.Column(
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                Text("plan: " + (plan?.pipelineId ?: "-") + " · " + (plan?.steps?.size ?: 0) + " steps", style = MaterialTheme.typography.labelMedium)
                plan?.steps?.forEach { s -> Text("• " + s.id + " · " + s.node + " · " + s.module, style = MaterialTheme.typography.bodySmall) }
                Text("spec: " + (spec?.id ?: "-") + " · " + (spec?.sections?.size ?: 0) + " sections", style = MaterialTheme.typography.labelMedium)
                spec?.sections?.forEach { s -> Text("• " + s.title + " · " + s.slots.size + " slots", style = MaterialTheme.typography.bodySmall) }
                Text("slots: " + (plan?.slots?.size ?: 0) + " + temp " + extraSlots.size, style = MaterialTheme.typography.labelMedium)
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.ok)) } }
    )
}

@Composable
internal fun AssemblyInputCard(
    plan: AssemblyPlan?,
    spec: MdSpec?,
    onOpenPlan: () -> Unit,
    onOpenSpec: () -> Unit,
    modifier: Modifier = Modifier,
    onBrowse: () -> Unit
) {
    val context = LocalContext.current
    CardBox(title = stringResource(dev.ninfenz.mobile.R.string.assembly_input), modifier = modifier) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = onOpenPlan) { Text(stringResource(dev.ninfenz.mobile.R.string.assembly_open_plan)) }
            OutlinedButton(onClick = onOpenSpec) { Text(stringResource(dev.ninfenz.mobile.R.string.assembly_open_spec)) }
        }
        KeyValue("plan", plan?.let { it.pipelineId + " · steps " + it.steps.size + " · slots " + it.slots.size } ?: context.getString(dev.ninfenz.mobile.R.string.assembly_not_loaded))
        KeyValue("spec", spec?.let { it.id + " · sections " + it.sections.size + " · slots " + it.slots.size } ?: context.getString(dev.ninfenz.mobile.R.string.assembly_not_loaded))
        TextButton(onClick = onBrowse, enabled = plan != null || spec != null) {
            Text(stringResource(dev.ninfenz.mobile.R.string.assembly_browse))
        }
        spec?.let { s ->
            val issues = SpecModel.formIssues(s)
            if (issues.isEmpty()) Notice(context.getString(dev.ninfenz.mobile.R.string.assembly_spec_local_ok), Tone.INFO)
            for (issue in issues) Notice(issue.code + "：" + issue.message, Tone.WARN)
        }
        plan?.let { p ->
            val issues = PlanModel.formIssues(p)
            if (issues.isEmpty()) Notice(context.getString(dev.ninfenz.mobile.R.string.assembly_plan_local_ok), Tone.INFO)
            for (issue in issues) Notice(issue.code + "：" + issue.message, Tone.WARN)
        }
    }
}

@Composable
internal fun AssemblyReportCard(report: ValidateReport?) {
    val context = LocalContext.current
    report?.let { r ->
        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.assembly_report)) {
            KeyValue("verdict", ReportModel.line(r))
            KeyValue("target", r.target.kind + " · " + r.target.ref)
            for (issue in r.issues) {
                Notice(issue.code + " " + (issue.path ?: "-") + "：" + issue.message + context.getString(dev.ninfenz.mobile.R.string.error_fix_suffix) + issue.fix,
                    if (issue.severity == "error") Tone.ERROR else Tone.WARN)
            }
        }
    }
}

@Composable
internal fun AssemblyPreviewCard(markdown: String?) {
    CardBox(title = stringResource(dev.ninfenz.mobile.R.string.assembly_preview)) {
        val md = markdown
        if (md == null) {
            EmptyState(stringResource(dev.ninfenz.mobile.R.string.assembly_not_assembled))
        } else {
            MonoText(md)
        }
    }
}
