package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.ui.design.NfType

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
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
    var explainRules by remember { mutableStateOf(false) }
    var explainLines by remember { mutableStateOf<List<String>>(emptyList()) }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            loadProtocolPack(context, uri,
                onLoaded = { parsed, obj ->
                    pack = parsed
                    rawPack = obj
                    values = parsed.fields.associate { it.id to (it.defaultText ?: "") }
                    enabled = parsed.clauses.associate { it.id to it.enabled }
                    error = null
                    rendered = null
                    explainLines = emptyList()
                    renderError = null
                },
                onError = { error = it })
        }
    }

    NfScaffold(title = stringResource(dev.ninfenz.mobile.R.string.protocol_title), onBack = onBack) {
        ProtocolPackCard(
            context = context,
            pack = pack,
            onPick = { picker.launch(arrayOf("application/json", "text/plain")) },
            onClearRender = { rendered = null; renderError = null }
        )

        error?.let { ErrorNotice(it) }

        val p = pack
        if (p != null) {
            ProtocolClauseCards(
                p = p,
                values = values,
                enabled = enabled,
                onValuesChange = { values = it },
                onEnabledChange = { enabled = it }
            )

            ProtocolRenderCard(ProtocolRenderCardArgs(rawPack, values, explainRules, busy, rendered, renderError, explainLines,
                onBusyChange = { busy = it }, onRenderError = { renderError = it }, onRendered = { rendered = it },
                onExplainLines = { explainLines = it }, onExplainRulesChange = { explainRules = it }))
        }
    }
}

private suspend fun loadProtocolPack(
    context: android.content.Context,
    uri: Uri,
    onLoaded: (ProtocolPack, JsonObject) -> Unit,
    onError: (CoreError?) -> Unit
) {
    try {
        val text = FileAccess.readText(context, uri)
        val obj = J.parseObject(text, "nf-protocol-pack/1")
        onLoaded(ProtocolModel.parse(obj), obj)
    } catch (e: Exception) {
        onError(CoreResponse.failure(
            (e as? dev.ninfenz.mobile.core.ModelException)?.code ?: "NF-PRT-001",
            context.getString(dev.ninfenz.mobile.R.string.protocol_parse_failed, e.message ?: e.javaClass.simpleName),
            context.getString(dev.ninfenz.mobile.R.string.protocol_parse_failed_fix),
            1
        ).error)
    }
}

@Composable
private fun ProtocolPackCard(
    context: android.content.Context,
    pack: ProtocolPack?,
    onPick: () -> Unit,
    onClearRender: () -> Unit
) {
    CardBox(title = stringResource(dev.ninfenz.mobile.R.string.protocol_pack)) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = onPick) { Text(stringResource(dev.ninfenz.mobile.R.string.protocol_pick)) }
            OutlinedButton(onClick = onClearRender) { Text(stringResource(dev.ninfenz.mobile.R.string.protocol_clear_render)) }
        }
        if (pack == null) {
            EmptyState(stringResource(dev.ninfenz.mobile.R.string.protocol_empty))
        } else {
            KeyValue("id/version", pack.id + " " + pack.version + "（proto " + pack.protoVersion + "）")
            KeyValue(
                context.getString(dev.ninfenz.mobile.R.string.protocol_stats),
                pack.clauses.size.toString() + " / " + pack.fields.size + " / " + pack.rules.size
            )
            KeyValue("compat", "protocol " + pack.protocolMin + ".." + pack.protocolMax + " · app_min " + pack.appMin)
        }
    }
}

@Composable
private fun ProtocolClauseCards(
    p: ProtocolPack,
    values: Map<String, String>,
    enabled: Map<String, Boolean>,
    onValuesChange: (Map<String, String>) -> Unit,
    onEnabledChange: (Map<String, Boolean>) -> Unit
) {
    val context = LocalContext.current
    for (clause in p.clauses) {
        val clauseEnabled = enabled[clause.id] ?: clause.enabled
        CardBox(title = clause.id + " · " + clause.title + " [" + clause.level + "]") {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(stringResource(dev.ninfenz.mobile.R.string.protocol_enable), style = NfType.secondary)
                Switch(
                    checked = clauseEnabled,
                    onCheckedChange = { checked -> onEnabledChange(enabled + (clause.id to checked)) }
                )
            }
            MonoText(clause.text)
            val check = ProtocolModel.checkClause(p, clause, values)
            if (check.ok) {
                Notice(stringResource(dev.ninfenz.mobile.R.string.protocol_placeholder_ok), Tone.INFO)
            } else {
                if (check.missing.isNotEmpty()) {
                    Notice(context.getString(dev.ninfenz.mobile.R.string.protocol_missing_fields, check.missing.joinToString(", ")), Tone.ERROR)
                }
                if (check.unknown.isNotEmpty()) {
                    Notice(context.getString(dev.ninfenz.mobile.R.string.protocol_unknown_placeholders, check.unknown.joinToString(", ")), Tone.WARN)
                }
            }
            for (field in p.fields.filter { it.clause == clause.id }) {
                FormTextField(
                    label = field.id + " · " + field.label + (if (field.required) context.getString(dev.ninfenz.mobile.R.string.field_required) else context.getString(dev.ninfenz.mobile.R.string.field_optional)) + " [" + field.type + "]",
                    value = values[field.id] ?: "",
                    onValueChange = { v -> onValuesChange(values + (field.id to v)) }
                )
                field.maxLen?.let { Text("max_len=" + it, style = NfType.meta) }
                field.pattern?.let { Text("pattern=" + it, style = NfType.meta) }
            }
            Text(stringResource(dev.ninfenz.mobile.R.string.protocol_rules, p.rules.joinToString { it.id + "(" + it.severity + ")" }), style = NfType.meta)
        }
    }
}
internal data class ProtocolRenderCardArgs(
    val rawPack: JsonObject?,
    val values: Map<String, String>,
    val explainRules: Boolean,
    val busy: Boolean,
    val rendered: List<String>?,
    val renderError: CoreError?,
    val explainLines: List<String>,
    val onBusyChange: (Boolean) -> Unit,
    val onRenderError: (CoreError?) -> Unit,
    val onRendered: (List<String>?) -> Unit,
    val onExplainLines: (List<String>) -> Unit,
    val onExplainRulesChange: (Boolean) -> Unit,
)

@Composable
private fun ProtocolRenderCard(args: ProtocolRenderCardArgs) = with(args) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    CardBox(title = stringResource(dev.ninfenz.mobile.R.string.protocol_render)) {
        Button(
            enabled = !busy,
            onClick = {
                scope.launch {
                    renderProtocol(rawPack, values, explainRules, onBusyChange, onRenderError, onRendered, onExplainLines)
                }
            }
        ) { Text(if (busy) context.getString(dev.ninfenz.mobile.R.string.protocol_rendering) else context.getString(dev.ninfenz.mobile.R.string.protocol_render_button)) }
        Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
            Checkbox(checked = explainRules, onCheckedChange = { onExplainRulesChange(it) })
            Text(stringResource(dev.ninfenz.mobile.R.string.protocol_explain))
        }
        if (explainLines.isNotEmpty()) {
            Text(stringResource(dev.ninfenz.mobile.R.string.protocol_explain_trace), style = NfType.itemTitle)
            for (line in explainLines) MonoText(line)
        }
        Text(stringResource(dev.ninfenz.mobile.R.string.protocol_note), style = NfType.meta)
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

private suspend fun renderProtocol(
    rawPack: JsonObject?,
    values: Map<String, String>,
    explainRules: Boolean,
    onBusyChange: (Boolean) -> Unit,
    onRenderError: (CoreError?) -> Unit,
    onRendered: (List<String>?) -> Unit,
    onExplainLines: (List<String>) -> Unit
) {
    val raw = rawPack ?: return
    onBusyChange(true)
    onRenderError(null)
    try {
        val payload = buildJsonObject {
            put("pack", raw)
            put("values", buildJsonObject {
                for ((k, v) in values) put(k, v)
            })
            put("explain", explainRules)
        }
        val response = safeCall("protocol-render", payload)
        if (response.ok) {
            val result = response.resultObject()
            val clauses = result?.get("clauses") as? JsonArray
            onRendered(clauses?.map { el ->
                val o = el as? JsonObject
                (o?.let { J.optString(it, "id") } ?: "?") + "：" + (o?.let { J.optString(it, "text") } ?: "")
            } ?: emptyList())
            val explain = result?.get("explain") as? JsonArray
            onExplainLines(explain?.flatMap { el ->
                val rule = el as? JsonObject ?: return@flatMap emptyList<String>()
                val rid = J.optString(rule, "rule")
                val trace = rule["trace"] as? JsonArray ?: return@flatMap emptyList<String>()
                trace.mapNotNull { node ->
                    val n = node as? JsonObject ?: return@mapNotNull null
                    rid + " " + J.optString(n, "path") + " " +
                        (n["op"]?.let { J.optString(n, "op") } ?: "") +
                        "=" + (n["value"]?.toString() ?: "")
                }
            } ?: emptyList())
        } else {
            onRenderError(response.error)
        }
    } finally {
        onBusyChange(false)
    }
}