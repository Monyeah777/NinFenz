package dev.ninfenz.mobile.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import dev.ninfenz.mobile.R
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.data.MacroStore
import dev.ninfenz.mobile.model.MacroRunResult
import dev.ninfenz.mobile.model.MacroRunner
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.design.NfType
import dev.ninfenz.mobile.ui.theme.NfSpacing
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put

/** W7 语义宏：导入/列表/dry-run；不录坐标，不直接写文件。 */
@Composable
fun SettingsMacroSection() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val store = remember { MacroStore(context.filesDir) }
    var items by remember { mutableStateOf(store.list()) }
    var note by remember { mutableStateOf<String?>(null) }
    var lastPlan by remember { mutableStateOf<JsonObject?>(null) }
    var lastRun by remember { mutableStateOf<MacroRunResult?>(null) }
    var paramMacro by remember { mutableStateOf<MacroStore.Macro?>(null) }
    var paramValues by remember { mutableStateOf<Map<String, String>>(emptyMap()) }

    val validateHandler: suspend (String, JsonObject) -> Result<String> = { action, params ->
        when (action) {
            "validate" -> {
                val spec = params["spec"] as? JsonObject
                if (spec == null) {
                    Result.failure(IllegalStateException(context.getString(R.string.settings_macros_validate_missing)))
                } else {
                    val response = safeCall("spec-validate", buildJsonObject { put("spec", spec) })
                    if (response.ok) Result.success("validated")
                    else Result.failure(IllegalStateException(response.error?.message ?: "validate failed"))
                }
            }
            else -> Result.failure(IllegalStateException(context.getString(R.string.settings_macros_unwired, action)))
        }
    }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            runCatching {
                val text = FileAccess.readText(context, uri)
                store.save(Json.parseToJsonElement(text).jsonObject)
                items = store.list()
                note = context.getString(R.string.settings_macros_imported)
            }.onFailure {
                note = context.getString(
                    R.string.settings_macros_failed,
                    it.message ?: it.javaClass.simpleName
                )
            }
        }
    }

    CardBox(title = stringResource(R.string.settings_macros_title)) {
        Text(
            stringResource(R.string.settings_macros_hint),
            style = NfType.meta,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
            TextButton(onClick = { picker.launch(arrayOf("application/json", "text/plain")) }) {
                Text(stringResource(R.string.settings_macros_import))
            }
        }
        if (items.isEmpty()) {
            Text(
                stringResource(R.string.settings_macros_empty),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        items.forEach { macro ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(macro.title.ifBlank { macro.id }, style = NfType.body)
                    Text(
                        macro.json["steps"]?.jsonArray?.size?.let { count ->
                            context.getString(R.string.settings_macros_steps, count)
                        } ?: "",
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                TextButton(onClick = {
                    scope.launch {
                        store.plan(macro.json)
                            .onSuccess { plan ->
                                lastPlan = plan
                                val count = plan["steps"]?.jsonArray?.size ?: 0
                                note = context.getString(R.string.settings_macros_planned, count)
                            }
                            .onFailure {
                                note = context.getString(
                                    R.string.settings_macros_failed,
                                    it.message ?: it.javaClass.simpleName
                                )
                            }
                    }
                }) { Text(stringResource(R.string.settings_macros_plan)) }
                TextButton(enabled = lastPlan != null, onClick = {
                    scope.launch {
                        val plan = lastPlan ?: return@launch
                        lastRun = MacroRunner.run(plan, validateHandler)
                    }
                }) { Text(stringResource(R.string.settings_macros_run)) }
                TextButton(onClick = {
                    paramValues = MacroRunner.placeholders(macro.json).associateWith { "" }
                    paramMacro = macro
                }) { Text(stringResource(R.string.settings_macros_params)) }
                TextButton(onClick = {
                    store.delete(macro.id)
                    items = store.list()
                }) { Text(stringResource(R.string.settings_macros_delete)) }
            }
        }
        note?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary) }
        lastPlan?.let { plan ->
            val steps = plan["steps"]?.jsonArray.orEmpty()
            Text(
                context.getString(R.string.settings_macros_plan_steps, steps.size),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            steps.forEach { step ->
                val obj = step as? kotlinx.serialization.json.JsonObject ?: return@forEach
                Text(
                    (obj["id"]?.toString()?.trim('"') ?: "") + " · " + (obj["action"]?.toString()?.trim('"') ?: ""),
                    style = NfType.meta
                )
            }
            Text(
                context.getString(R.string.settings_macros_dry_run_note),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        lastRun?.let { run ->
            Text(
                context.getString(R.string.settings_macros_run_status, run.status, run.failures),
                style = NfType.meta,
                color = if (run.failures == 0) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
            )
            run.steps.forEach { step ->
                Text(
                    context.getString(R.string.settings_macros_step_status, step.id, step.action, step.status),
                    style = NfType.meta
                )
            }
        }
    }

    paramMacro?.let { macro ->
        AlertDialog(
            onDismissRequest = { paramMacro = null },
            title = { Text(stringResource(R.string.settings_macros_params_title)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    if (paramValues.isEmpty()) {
                        Text(stringResource(R.string.settings_macros_params_empty), style = NfType.meta)
                    }
                    paramValues.keys.forEach { key ->
                        OutlinedTextField(
                            value = paramValues[key].orEmpty(),
                            onValueChange = { value -> paramValues = paramValues + (key to value) },
                            label = { Text(key) },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    scope.launch {
                        val plan = store.plan(macro.json).getOrNull()
                        if (plan == null) {
                            note = context.getString(R.string.settings_macros_failed, "plan failed")
                        } else {
                            lastRun = MacroRunner.run(MacroRunner.bind(plan, paramValues), validateHandler)
                        }
                        paramMacro = null
                    }
                }) { Text(stringResource(R.string.settings_macros_run)) }
            },
            dismissButton = {
                TextButton(onClick = { paramMacro = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}
