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
import androidx.compose.material3.Switch
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
import dev.ninfenz.mobile.model.ProtocolPack
import dev.ninfenz.mobile.model.ProtocolModel
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
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

@Composable
fun ProtocolScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var pack by remember { mutableStateOf<ProtocolPack?>(null) }
    var rawPack by remember { mutableStateOf<JsonObject?>(null) }
    var values by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    var enabled by remember { mutableStateOf<Map<String, Boolean>>(emptyMap()) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var rendered by remember { mutableStateOf<List<String>?>(null) }
    var renderError by remember { mutableStateOf<CoreError?>(null) }
    var busy by remember { mutableStateOf(false) }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val text = FileAccess.readText(context, uri)
                val obj = J.parseObject(text, "nf-protocol-pack/1")
                val parsed = ProtocolModel.parse(obj)
                pack = parsed
                rawPack = obj
                values = parsed.fields.associate { it.id to (it.defaultText ?: "") }
                enabled = parsed.clauses.associate { it.id to it.enabled }
                error = null
                rendered = null
                renderError = null
            } catch (e: Exception) {
                error = CoreResponse.failure(
                    (e as? dev.ninfenz.mobile.core.ModelException)?.code ?: "NF-PRT-001",
                    "协议包解析失败：" + (e.message ?: e.javaClass.simpleName),
                    "按 app/schema/nf-protocol-pack.schema.json 修正",
                    1
                ).error
            }
        }
    }

    NfScaffold(title = stringResource(dev.ninfenz.mobile.R.string.protocol_title), onBack = onBack) {
        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.protocol_pack)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { picker.launch(arrayOf("application/json", "text/plain")) }) { Text(stringResource(dev.ninfenz.mobile.R.string.protocol_pick)) }
                OutlinedButton(onClick = { rendered = null; renderError = null }) { Text(stringResource(dev.ninfenz.mobile.R.string.protocol_clear_render)) }
            }
            val p = pack
            if (p == null) {
                EmptyState(stringResource(dev.ninfenz.mobile.R.string.protocol_empty))
            } else {
                KeyValue("id/version", p.id + " " + p.version + "（proto " + p.protoVersion + "）")
                KeyValue("条款/字段/规则", p.clauses.size.toString() + " / " + p.fields.size + " / " + p.rules.size)
                KeyValue("compat", "protocol " + p.protocolMin + ".." + p.protocolMax + " · app_min " + p.appMin)
            }
        }

        error?.let { ErrorNotice(it) }

        val p = pack
        if (p != null) {
            for (clause in p.clauses) {
                val clauseEnabled = enabled[clause.id] ?: clause.enabled
                CardBox(title = clause.id + " · " + clause.title + " [" + clause.level + "]") {
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.protocol_enable), style = MaterialTheme.typography.bodyMedium)
                        Switch(
                            checked = clauseEnabled,
                            onCheckedChange = { checked -> enabled = enabled + (clause.id to checked) }
                        )
                    }
                    MonoText(clause.text)
                    val check = ProtocolModel.checkClause(p, clause, values)
                    if (check.ok) {
                        Notice("占位符检查通过（本地预检）", Tone.INFO)
                    } else {
                        if (check.missing.isNotEmpty()) {
                            Notice("缺必填字段：" + check.missing.joinToString(", ") + "（NF-PRT-003）", Tone.ERROR)
                        }
                        if (check.unknown.isNotEmpty()) {
                            Notice("未声明占位符：" + check.unknown.joinToString(", ") + "（NF-PRT-004）", Tone.WARN)
                        }
                    }
                    for (field in p.fields.filter { it.clause == clause.id }) {
                        FormTextField(
                            label = field.id + " · " + field.label + (if (field.required) "（必填）" else "（可选）") + " [" + field.type + "]",
                            value = values[field.id] ?: "",
                            onValueChange = { v -> values = values + (field.id to v) }
                        )
                        field.maxLen?.let { Text("max_len=" + it, style = MaterialTheme.typography.labelSmall) }
                        field.pattern?.let { Text("pattern=" + it, style = MaterialTheme.typography.labelSmall) }
                    }
                    Text(stringResource(dev.ninfenz.mobile.R.string.protocol_rules, p.rules.joinToString { it.id + "(" + it.severity + ")" }), style = MaterialTheme.typography.bodySmall)
                }
            }

            CardBox(title = stringResource(dev.ninfenz.mobile.R.string.protocol_render)) {
                Button(
                    enabled = !busy,
                    onClick = {
                        val raw = rawPack ?: return@Button
                        scope.launch {
                            busy = true
                            renderError = null
                            try {
                                val payload = buildJsonObject {
                                    put("pack", raw)
                                    put("values", buildJsonObject {
                                        for ((k, v) in values) put(k, v)
                                    })
                                }
                                val response = safeCall("protocol-render", payload)
                                if (response.ok) {
                                    val result = response.resultObject()
                                    val clauses = result?.get("clauses") as? JsonArray
                                    rendered = clauses?.map { el ->
                                        val o = el as? JsonObject
                                        (o?.let { J.optString(it, "id") } ?: "?") + "：" + (o?.let { J.optString(it, "text") } ?: "")
                                    } ?: emptyList()
                                } else {
                                    renderError = response.error
                                }
                            } finally {
                                busy = false
                            }
                        }
                    }
                ) { Text(if (busy) "渲染中…" else "用核心渲染条款") }
                Text(stringResource(dev.ninfenz.mobile.R.string.protocol_note), style = MaterialTheme.typography.bodySmall)
                renderError?.let { ErrorNotice(it) }
                rendered?.let { list ->
                    if (list.isEmpty()) {
                        EmptyState(stringResource(dev.ninfenz.mobile.R.string.protocol_no_clauses))
                    } else {
                        for (line in list) MonoText(line)
                    }
                }
            }
        }
    }
}
