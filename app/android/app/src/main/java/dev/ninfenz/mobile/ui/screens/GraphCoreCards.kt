package dev.ninfenz.mobile.ui.screens
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
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
import dev.ninfenz.mobile.data.LibraryStore
import dev.ninfenz.mobile.model.GraphEdge
import dev.ninfenz.mobile.model.GraphModel
import dev.ninfenz.mobile.model.GraphNode
import dev.ninfenz.mobile.model.PipelineGraph
import dev.ninfenz.mobile.model.ValidateReport
import dev.ninfenz.mobile.model.ReportModel
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.design.NfType
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
import kotlinx.serialization.json.JsonPrimitive
import java.io.File

internal data class GraphCoreCardsArgs(
    val g: PipelineGraph,
    val store: LibraryStore,
    val busy: Boolean,
    val savedPath: String?,
    val report: ValidateReport?,
    val planSummary: String?,
    val compileRepro: String?,
    val onBusyChange: (Boolean) -> Unit,
    val onError: (CoreError?) -> Unit,
    val onReport: (ValidateReport?) -> Unit,
    val onPlanSummary: (String?) -> Unit,
    val onCompileRepro: (String?) -> Unit,
    val onSavedPath: (String?) -> Unit,
)

@Composable
internal fun GraphCoreCards(args: GraphCoreCardsArgs) = with(args) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    CardBox(title = stringResource(dev.ninfenz.mobile.R.string.graph_core)) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(enabled = !busy, onClick = {
                scope.launch { runGraphValidate(context, g, onBusyChange, onError, onReport) }
            }) { Text(if (busy) context.getString(dev.ninfenz.mobile.R.string.graph_calling) else "core graph-validate") }
            Button(enabled = !busy, onClick = {
                scope.launch { runGraphCompile(context, g, onBusyChange, onError, onPlanSummary, onCompileRepro) }
            }) { Text(if (busy) context.getString(dev.ninfenz.mobile.R.string.graph_calling) else "core graph-compile") }
        }
        report?.let { r ->
            KeyValue(context.getString(dev.ninfenz.mobile.R.string.graph_validate_label), ReportModel.line(r))
            for (issue in r.issues) Notice(issue.code + " " + (issue.path ?: "-") + "：" + issue.message + context.getString(dev.ninfenz.mobile.R.string.error_fix_suffix) + issue.fix,
                if (issue.severity == "error") Tone.ERROR else Tone.WARN)
        }
        planSummary?.let { MonoText(it) }
        compileRepro?.let { MonoText(it) }
    }

    CardBox(title = stringResource(dev.ninfenz.mobile.R.string.graph_save)) {
        Button(onClick = {
            val path = store.saveDraft("graph-" + g.id, GraphModel.toJson(g).toString())
            onSavedPath(path.absolutePath)
        }) { Text(stringResource(dev.ninfenz.mobile.R.string.graph_save_draft)) }
        savedPath?.let { Notice(context.getString(dev.ninfenz.mobile.R.string.graph_saved_prefix, it), Tone.INFO) }
    }
}

private suspend fun runGraphValidate(
    context: android.content.Context,
    g: PipelineGraph,
    onBusyChange: (Boolean) -> Unit,
    onError: (CoreError?) -> Unit,
    onReport: (ValidateReport?) -> Unit
) {
    onBusyChange(true)
    onError(null)
    onReport(null)
    try {
        val payload = buildJsonObject { put("graph", GraphModel.toJson(g)) }
        val response = safeCall("graph-validate", payload)
        if (response.ok) {
            response.resultObject()?.let { onReport(ReportModel.parse(it)) }
        } else if (response.exit == 1 && response.result != null) {
            (response.result as? JsonObject)?.let { onReport(ReportModel.parse(it)) }
            onError(response.error)
        } else {
            onError(response.error)
        }
    } finally {
        onBusyChange(false)
    }
}

private suspend fun runGraphCompile(
    context: android.content.Context,
    g: PipelineGraph,
    onBusyChange: (Boolean) -> Unit,
    onError: (CoreError?) -> Unit,
    onPlanSummary: (String?) -> Unit,
    onCompileRepro: (String?) -> Unit
) {
    onBusyChange(true)
    onError(null)
    onPlanSummary(null)
    onCompileRepro(null)
    try {
        val payload = buildJsonObject { put("graph", GraphModel.toJson(g)) }
        val response = safeCall("graph-compile", payload)
        if (response.ok) {
            val result = response.resultObject()
            if (result != null) {
                val second = safeCall("graph-compile", payload)
                val secondResult = second.resultObject()
                if (second.ok && secondResult != null) {
                    val offset = dev.ninfenz.mobile.data.ReproChecker.firstDifference(
                        result.toString().toByteArray(Charsets.UTF_8),
                        secondResult.toString().toByteArray(Charsets.UTF_8)
                    )
                    onCompileRepro(if (offset == null) {
                        context.getString(dev.ninfenz.mobile.R.string.repro_stable)
                    } else {
                        context.getString(dev.ninfenz.mobile.R.string.repro_diff, offset)
                    })
                }
            }
            onPlanSummary(if (result == null) context.getString(dev.ninfenz.mobile.R.string.graph_core_no_plan) else
                context.getString(
                    dev.ninfenz.mobile.R.string.graph_plan_summary,
                    J.optString(result, "digest") ?: context.getString(dev.ninfenz.mobile.R.string.graph_none),
                    J.optArray(result, "steps").size,
                    J.optStringList(result, "slots").joinToString(",")
                ))
        } else {
            onError(response.error)
        }
    } finally {
        onBusyChange(false)
    }
}
