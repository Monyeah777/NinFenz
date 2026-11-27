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
fun AssemblyScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val ui = remember { AssemblyUiState() }
    val reqInput = remember { BringIntoViewRequester() }
    val reqSlots = remember { BringIntoViewRequester() }
    val reqAssemble = remember { BringIntoViewRequester() }
    val reqExport = remember { BringIntoViewRequester() }

    val planPicker = rememberAssemblyPlanPicker(context, scope,
        onLoaded = { parsed, obj, values -> ui.plan = parsed; ui.rawPlan = obj; ui.inputs = values },
        onError = { ui.error = it })
    val specPicker = rememberAssemblySpecPicker(context, scope,
        onLoaded = { parsed, obj -> ui.spec = parsed; ui.rawSpec = obj },
        onError = { ui.error = it })

    NfScaffold(title = stringResource(dev.ninfenz.mobile.R.string.assembly_title), onBack = onBack) {
        AssemblyStepBar(reqInput, reqSlots, reqAssemble, reqExport)
        if (ui.showBrowse) AssemblyBrowseDialog(ui.plan, ui.spec, ui.extraSlots) { ui.showBrowse = false }
        AssemblyInputCard(ui.plan, ui.spec,
            onOpenPlan = { planPicker(arrayOf("application/json", "text/plain")) },
            onOpenSpec = { specPicker(arrayOf("application/json", "text/plain")) },
            modifier = Modifier.bringIntoViewRequester(reqInput),
            onBrowse = { ui.showBrowse = true })
        ui.error?.let { ErrorNotice(it) }

        val p = ui.plan
        val s = ui.spec
        if (p == null || s == null) {
            EmptyState(stringResource(dev.ninfenz.mobile.R.string.assembly_need_plan))
        } else {
            AssemblyWorkspace(p, ui.rawPlan, ui.rawSpec, ui.inputs, ui.markdown, ui.metaSummary, ui.report,
                ui.manifest, ui.busy, ui.assembleRepro, ui.validateRepro, ui.extraSlots, ui.newSlot,
                reqSlots, reqAssemble, reqExport,
                onInputsChange = { ui.inputs = it }, onExtraSlotsChange = { ui.extraSlots = it },
                onNewSlotChange = { ui.newSlot = it },
                onRemoveSlot = { slot -> ui.extraSlots = ui.extraSlots - slot; ui.inputs = ui.inputs - slot },
                onBusyChange = { ui.busy = it }, onErrorChange = { ui.error = it },
                onMarkdownChange = { ui.markdown = it }, onMetaSummaryChange = { ui.metaSummary = it },
                onAssembleReproChange = { ui.assembleRepro = it }, onValidateReproChange = { ui.validateRepro = it },
                onReportChange = { ui.report = it }, onManifestChange = { ui.manifest = it })
        }
    }
}

internal class AssemblyUiState {
    var plan by mutableStateOf<AssemblyPlan?>(null)
    var spec by mutableStateOf<MdSpec?>(null)
    var rawPlan by mutableStateOf<JsonObject?>(null)
    var rawSpec by mutableStateOf<JsonObject?>(null)
    var inputs by mutableStateOf<Map<String, String>>(emptyMap())
    var markdown by mutableStateOf<String?>(null)
    var metaSummary by mutableStateOf<String?>(null)
    var error by mutableStateOf<CoreError?>(null)
    var report by mutableStateOf<ValidateReport?>(null)
    var manifest by mutableStateOf<String?>(null)
    var busy by mutableStateOf(false)
    var assembleRepro by mutableStateOf<String?>(null)
    var validateRepro by mutableStateOf<String?>(null)
    var extraSlots by mutableStateOf<List<String>>(emptyList())
    var newSlot by mutableStateOf("")
    var showBrowse by mutableStateOf(false)
}

@Composable
private fun rememberAssemblyPlanPicker(
    context: android.content.Context,
    scope: kotlinx.coroutines.CoroutineScope,
    onLoaded: (AssemblyPlan?, JsonObject, Map<String, String>) -> Unit,
    onError: (CoreError?) -> Unit
): (Array<String>) -> Unit {
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val text = FileAccess.readText(context, uri)
                val obj = J.parseObject(text, "nf-assembly-plan/1")
                val parsed = PlanModel.parse(obj)
                onLoaded(parsed, obj, parsed?.slots?.associate { it to "" } ?: emptyMap())
                onError(null)
            } catch (e: Exception) {
                onError(CoreResponse.failure(
                    "NF-ASM-003",
                    context.getString(dev.ninfenz.mobile.R.string.assembly_plan_failed, e.message ?: e.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.assembly_plan_failed_fix),
                    1
                ).error)
            }
        }
    }
    return { input -> picker.launch(input) }
}

@Composable
private fun rememberAssemblySpecPicker(
    context: android.content.Context,
    scope: kotlinx.coroutines.CoroutineScope,
    onLoaded: (MdSpec?, JsonObject) -> Unit,
    onError: (CoreError?) -> Unit
): (Array<String>) -> Unit {
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val text = FileAccess.readText(context, uri)
                val obj = J.parseObject(text, "nf-md-spec/1")
                onLoaded(SpecModel.parse(obj), obj)
                onError(null)
            } catch (e: Exception) {
                onError(CoreResponse.failure(
                    "NF-SPC-001",
                    context.getString(dev.ninfenz.mobile.R.string.assembly_spec_failed, e.message ?: e.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.assembly_spec_failed_fix),
                    1
                ).error)
            }
        }
    }
    return { input -> picker.launch(input) }
}
