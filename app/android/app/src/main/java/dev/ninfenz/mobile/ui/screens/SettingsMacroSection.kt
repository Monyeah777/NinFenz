package dev.ninfenz.mobile.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
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
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.design.NfType
import dev.ninfenz.mobile.ui.theme.NfSpacing
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject

/** W7 语义宏：导入/列表/dry-run；不录坐标，不直接写文件。 */
@Composable
fun SettingsMacroSection() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val store = remember { MacroStore(context.filesDir) }
    var items by remember { mutableStateOf(store.list()) }
    var note by remember { mutableStateOf<String?>(null) }
    var lastPlan by remember { mutableStateOf<kotlinx.serialization.json.JsonObject?>(null) }

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
    }
}
