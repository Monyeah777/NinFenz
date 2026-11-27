package dev.ninfenz.mobile.ui.screens
import dev.ninfenz.mobile.util.orNullLogged
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
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
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.data.PackDraftStore
import dev.ninfenz.mobile.data.AtomicFiles
import dev.ninfenz.mobile.data.PackSigningKey
import dev.ninfenz.mobile.data.PackZipInstaller
import dev.ninfenz.mobile.model.SpecModel
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.components.EmptyState
import dev.ninfenz.mobile.ui.components.FormTextField
import dev.ninfenz.mobile.ui.components.NfScaffold
import dev.ninfenz.mobile.ui.design.NfType
import dev.ninfenz.mobile.ui.theme.NfContentColors
import dev.ninfenz.mobile.ui.theme.NfSpacing
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import java.io.File

@Composable
internal fun StructuredSpecCard(label: String, value: String, onChange: (String) -> Unit, dir: File) {
    val spec = remember(value) { runCatching { SpecModel.parse(value) }.orNullLogged("PackBuilderScreen") }
    var saved by remember { mutableStateOf<String?>(null) }
    CardBox(title = label) {
        if (spec == null) {
            Text("Spec JSON invalid; use raw JSON editor below", style = NfType.meta, color = MaterialTheme.colorScheme.error)
        } else {
            spec.sections.forEachIndexed { sectionIndex, section ->
                Text("Section " + (sectionIndex + 1) + " · " + section.id, style = NfType.label)
                OutlinedTextField(
                    value = section.title,
                    onValueChange = { newTitle ->
                        val next = spec.copy(sections = spec.sections.mapIndexed { i, s -> if (i == sectionIndex) s.copy(title = newTitle) else s })
                        onChange(SpecModel.toJson(next).toString())
                    },
                    label = { Text("Section title") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                section.slots.forEach { slotId ->
                    val slot = spec.slots.firstOrNull { it.id == slotId } ?: return@forEach
                    SpecSlotEditor(slot, spec, value, onChange)
                }
                OutlinedButton(onClick = {
                    var index = spec.slots.size + 1
                    var newId = "SLT-" + index.toString().padStart(2, '0')
                    while (spec.slots.any { it.id == newId }) { index++; newId = "SLT-" + index.toString().padStart(2, '0') }
                    val slot = dev.ninfenz.mobile.model.SpecSlot(id = newId, name = "Slot " + index, section = section.id, kind = "text", required = false)
                    val next = spec.copy(
                        sections = spec.sections.mapIndexed { i, s -> if (i == sectionIndex) s.copy(slots = s.slots + newId) else s },
                        slots = spec.slots + slot
                    )
                    onChange(SpecModel.toJson(next).toString())
                }) { Text("Add slot") }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                Button(onClick = {
                    runCatching {
                        SpecModel.parse(value)
                        AtomicFiles.writeText(File(dir, "spec/main.nfspec.json"), value)
                        saved = "saved spec"
                    }.onFailure { saved = it.message ?: "invalid spec" }
                }) { Text("Save spec") }
                saved?.let { Text(it, style = NfType.meta) }
            }
        }
    }
}

@Composable
internal fun JsonEditorCard(
    label: String,
    path: String,
    value: String,
    onChange: (String) -> Unit,
    dir: File
) {
    var saved by remember { mutableStateOf<String?>(null) }
    CardBox(title = label) {
        OutlinedTextField(
            value = value,
            onValueChange = onChange,
            minLines = 6,
            maxLines = 14,
            modifier = Modifier.fillMaxWidth()
        )
        Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
            Button(onClick = {
                runCatching {
                    Json.parseToJsonElement(value).jsonObject
                    AtomicFiles.writeText(File(dir, path), value)
                    saved = "saved " + path
                }.onFailure { saved = it.message ?: "invalid json" }
            }) { Text("Save JSON") }
            saved?.let { Text(it, style = NfType.meta) }
        }
    }
}

@Composable
internal fun GraphNodeEditRow(node: JsonObject, id: String, value: String, onChange: (String) -> Unit) {
    Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
        Text(id + " · " + (node["kind"]?.jsonPrimitive?.content ?: ""), style = NfType.label, modifier = Modifier.weight(1f))
        TextButton(onClick = {
            val root = Json.parseToJsonElement(value).jsonObject
            val nodes = root["nodes"]?.jsonArray.orEmpty()
            val edges = root["edges"]?.jsonArray.orEmpty()
            val nextNodes = JsonArray(nodes.filter { it.jsonObject["id"]?.jsonPrimitive?.content != id })
            val nextEdges = JsonArray(edges.filter {
                val e = it.jsonObject
                e["from"]?.jsonPrimitive?.content != id && e["to"]?.jsonPrimitive?.content != id
            })
            val next = JsonObject(root.toMutableMap().apply { put("nodes", nextNodes); put("edges", nextEdges) })
            onChange(next.toString())
        }) { Text("Delete") }
    }
    OutlinedTextField(
        value = node["title"]?.jsonPrimitive?.content.orEmpty(),
        onValueChange = { onChange(updateObjectArray(value, "nodes", id, "title", JsonPrimitive(it))) },
        label = { Text("node title") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth()
    )
}

@Composable
internal fun GraphEdgeEditRow(edge: JsonObject, eid: String, value: String, onChange: (String) -> Unit) {
    Text(eid + " · " + (edge["type"]?.jsonPrimitive?.content ?: ""), style = NfType.label)
    Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        OutlinedTextField(
            value = edge["from"]?.jsonPrimitive?.content.orEmpty(),
            onValueChange = { onChange(updateObjectArray(value, "edges", eid, "from", JsonPrimitive(it))) },
            label = { Text("from") }, singleLine = true, modifier = Modifier.weight(1f)
        )
        OutlinedTextField(
            value = edge["to"]?.jsonPrimitive?.content.orEmpty(),
            onValueChange = { onChange(updateObjectArray(value, "edges", eid, "to", JsonPrimitive(it))) },
            label = { Text("to") }, singleLine = true, modifier = Modifier.weight(1f)
        )
        TextButton(onClick = {
            val root = Json.parseToJsonElement(value).jsonObject
            val edges = root["edges"]?.jsonArray.orEmpty()
            val nextEdges = JsonArray(edges.filter { it.jsonObject["id"]?.jsonPrimitive?.content != eid })
            val next = JsonObject(root.toMutableMap().apply { put("edges", nextEdges) })
            onChange(next.toString())
        }) { Text("Delete") }
    }
}

@Composable
internal fun ProtocolClauseEditor(
    clause: JsonObject,
    id: String,
    fields: List<kotlinx.serialization.json.JsonElement>,
    value: String,
    onChange: (String) -> Unit
) {
    Text(id + " · " + (clause["level"]?.jsonPrimitive?.content ?: ""), style = NfType.label)
    OutlinedTextField(
        value = clause["title"]?.jsonPrimitive?.content.orEmpty(),
        onValueChange = { onChange(updateObjectArray(value, "clauses", id, "title", JsonPrimitive(it))) },
        label = { Text("Clause title") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth()
    )
    OutlinedTextField(
        value = clause["text"]?.jsonPrimitive?.content.orEmpty(),
        onValueChange = { onChange(updateObjectArray(value, "clauses", id, "text", JsonPrimitive(it))) },
        label = { Text("Clause text") },
        minLines = 2,
        modifier = Modifier.fillMaxWidth()
    )
    Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
        Text("enabled", style = NfType.meta, modifier = Modifier.weight(1f))
        Switch(
            checked = clause["enabled"]?.jsonPrimitive?.booleanOrNull ?: true,
            onCheckedChange = { onChange(updateObjectArray(value, "clauses", id, "enabled", JsonPrimitive(it))) }
        )
    }
    fields.filter { it.jsonObject["clause"]?.jsonPrimitive?.content == id }.forEach { fEl ->
        val field = fEl.jsonObject
        val fid = field["id"]?.jsonPrimitive?.content.orEmpty()
        OutlinedTextField(
            value = field["label"]?.jsonPrimitive?.content.orEmpty(),
            onValueChange = { onChange(updateObjectArray(value, "fields", fid, "label", JsonPrimitive(it))) },
            label = { Text(fid + " label") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )
        Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
            Text("required", style = NfType.meta, modifier = Modifier.weight(1f))
            Switch(
                checked = field["required"]?.jsonPrimitive?.booleanOrNull ?: false,
                onCheckedChange = { onChange(updateObjectArray(value, "fields", fid, "required", JsonPrimitive(it))) }
            )
        }
    }
}

@Composable
private fun SpecSlotEditor(
    slot: dev.ninfenz.mobile.model.SpecSlot,
    spec: dev.ninfenz.mobile.model.MdSpec,
    value: String,
    onChange: (String) -> Unit
) {
    OutlinedTextField(
        value = slot.name,
        onValueChange = { newName ->
            val next = spec.copy(slots = spec.slots.map { if (it.id == slot.id) it.copy(name = newName) else it })
            onChange(SpecModel.toJson(next).toString())
        },
        label = { Text(slot.id + " name") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth()
    )
    Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
        Text("required", style = NfType.meta, modifier = Modifier.weight(1f))
        Switch(
            checked = slot.required,
            onCheckedChange = { checked ->
                val next = spec.copy(slots = spec.slots.map { if (it.id == slot.id) it.copy(required = checked) else it })
                onChange(SpecModel.toJson(next).toString())
            }
        )
    }
    OutlinedTextField(
        value = slot.visibleIf?.slot.orEmpty(),
        onValueChange = { dep ->
            val next = spec.copy(slots = spec.slots.map {
                if (it.id == slot.id) it.copy(visibleIf = if (dep.isBlank()) null else dev.ninfenz.mobile.model.SpecVisibleIf(dep, it.visibleIf?.equals ?: "")) else it
            })
            onChange(SpecModel.toJson(next).toString())
        },
        label = { Text("visible if slot") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth()
    )
    OutlinedTextField(
        value = slot.visibleIf?.equals.orEmpty(),
        onValueChange = { expected ->
            val dep = slot.visibleIf?.slot.orEmpty()
            val next = spec.copy(slots = spec.slots.map {
                if (it.id == slot.id) it.copy(visibleIf = if (dep.isBlank()) null else dev.ninfenz.mobile.model.SpecVisibleIf(dep, expected)) else it
            })
            onChange(SpecModel.toJson(next).toString())
        },
        label = { Text("visible if equals") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth()
    )
}
