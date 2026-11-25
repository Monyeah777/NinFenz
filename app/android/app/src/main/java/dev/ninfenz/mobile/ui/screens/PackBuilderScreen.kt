package dev.ninfenz.mobile.ui.screens

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
fun PackBuilderScreen(draftId: String, onBack: () -> Unit, onInstalled: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val store = remember { PackDraftStore(context.filesDir) }
    val draft = remember(draftId) { store.load(draftId) }
    var id by remember(draftId) { mutableStateOf(draft?.id.orEmpty()) }
    var version by remember(draftId) { mutableStateOf(draft?.version.orEmpty()) }
    var title by remember(draftId) { mutableStateOf(draft?.title.orEmpty()) }
    var report by remember { mutableStateOf<String?>(null) }
    var releaseText by remember { mutableStateOf<String?>(null) }
    var preview by remember { mutableStateOf<String?>(null) }
    var goldenStatus by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var busy by remember { mutableStateOf(false) }
    fun read(file: String): String = File(draft?.dir, file).takeIf { it.isFile }?.readText(Charsets.UTF_8).orEmpty()
    var protocolText by remember(draftId) { mutableStateOf(read("protocol/nf-protocol-pack.json")) }
    var graphText by remember(draftId) { mutableStateOf(read("pipeline/main.nfg.json")) }
    var specText by remember(draftId) { mutableStateOf(read("spec/main.nfspec.json")) }

    NfScaffold(title = "Pack Studio", onBack = onBack) {
        if (draft == null) {
            EmptyState("Pack draft not found")
            return@NfScaffold
        }
        CardBox(title = "Metadata") {
            FormTextField("id", id, { id = it })
            FormTextField("version", version, { version = it })
            FormTextField("title", title, { title = it })
            Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                OutlinedButton(onClick = {
                    store.updateMeta(draft, id.trim(), version.trim(), title.trim())
                    report = "metadata saved"
                }) { Text("Save metadata") }
                OutlinedButton(onClick = { report = null; error = null }) { Text("Clear") }
            }
        }
        CardBox(title = "Files") {
            draft.dir.walkTopDown().filter { it.isFile }.sortedBy { it.path }.take(40).forEach { file ->
                Text(file.relativeTo(draft.dir).invariantSeparatorsPath + " · " + file.length(), style = NfType.meta)
            }
        }
        StructuredProtocolCard("Protocol form", protocolText, { protocolText = it }, draft.dir)
        JsonEditorCard("Protocol JSON", "protocol/nf-protocol-pack.json", protocolText, { protocolText = it }, draft.dir)
        StructuredGraphCard("Pipeline form", graphText, { graphText = it }, draft.dir)
        JsonEditorCard("Pipeline JSON", "pipeline/main.nfg.json", graphText, { graphText = it }, draft.dir)
        StructuredSpecCard("Spec form", specText, { specText = it }, draft.dir)
        JsonEditorCard("Spec JSON", "spec/main.nfspec.json", specText, { specText = it }, draft.dir)
        CardBox(title = "Validate & package") {
            Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                OutlinedButton(enabled = !busy, onClick = {
                    busy = true
                    error = null
                    scope.launch {
                        try {
                            val graph = Json.parseToJsonElement(graphText).jsonObject
                            val spec = Json.parseToJsonElement(specText).jsonObject
                            val compiled = safeCall("graph-compile", buildJsonObject { put("graph", graph) })
                            if (!compiled.ok) {
                                error = compiled.error
                            } else {
                                val plan = compiled.resultObject()
                                if (plan == null) {
                                    error = CoreResponse.failure("NF-ASM-001", "graph-compile did not return plan", "fix pipeline", 1).error
                                } else {
                                    val inputs = buildJsonObject {
                                        (spec["slots"] as? kotlinx.serialization.json.JsonArray)?.forEach { el ->
                                            val slot = el.jsonObject
                                            val id = slot["id"]?.jsonPrimitive?.content ?: return@forEach
                                            val example = (slot["examples"] as? kotlinx.serialization.json.JsonArray)
                                                ?.firstOrNull()?.jsonPrimitive?.content
                                            put(id, example ?: "test")
                                        }
                                    }
                                    val assembled = safeCall("assemble", buildJsonObject {
                                        put("plan", plan)
                                        put("spec", spec)
                                        put("inputs", inputs)
                                        put("out_dir", File(context.cacheDir, "pack-test").apply { mkdirs() }.absolutePath)
                                    })
                                    if (assembled.ok) {
                                        val md = assembled.resultObject()?.get("markdown")?.jsonPrimitive?.content ?: "assembled"
                                        preview = md
                                        val golden = store.loadGolden(draft)
                                        goldenStatus = when {
                                            golden == null -> "no golden yet"
                                            golden == md -> "golden match"
                                            else -> "golden differs @ " + (dev.ninfenz.mobile.data.ReproChecker.firstDifference(golden.toByteArray(Charsets.UTF_8), md.toByteArray(Charsets.UTF_8)) ?: -1)
                                        }
                                    } else {
                                        error = assembled.error
                                    }
                                }
                            }
                        } catch (t: Throwable) {
                            error = CoreResponse.failure("NF-ASM-003", t.message ?: t.javaClass.simpleName, "check graph/spec", 1).error
                        } finally {
                            busy = false
                        }
                    }
                }) { Text("Test assemble") }
                Button(enabled = !busy, onClick = {
                    busy = true
                    error = null
                    scope.launch {
                        try {
                            val lines = mutableListOf<String>()
                            val protocol = File(draft.dir, "protocol/nf-protocol-pack.json").takeIf { it.isFile }?.let {
                                Json.parseToJsonElement(it.readText(Charsets.UTF_8)).jsonObject
                            }
                            if (protocol != null) {
                                val r = safeCall("protocol-validate", buildJsonObject { put("pack", protocol) })
                                lines.add("protocol: " + (if (r.ok) "ok" else (r.error?.message ?: "fail")))
                            }
                            val spec = File(draft.dir, "spec/main.nfspec.json").takeIf { it.isFile }?.let {
                                Json.parseToJsonElement(it.readText(Charsets.UTF_8)).jsonObject
                            }
                            if (spec != null) {
                                val r = safeCall("spec-validate", buildJsonObject { put("spec", spec) })
                                lines.add("spec: " + (if (r.ok) "ok" else (r.error?.message ?: "fail")))
                            }
                            val graph = File(draft.dir, "pipeline/main.nfg.json").takeIf { it.isFile }?.let {
                                Json.parseToJsonElement(it.readText(Charsets.UTF_8)).jsonObject
                            }
                            if (graph != null) {
                                val r = safeCall("graph-compile", buildJsonObject { put("graph", graph) })
                                lines.add("graph: " + (if (r.ok) "ok" else (r.error?.message ?: "fail")))
                            }
                            val hash = safeCall("pack-hash", buildJsonObject { put("root", draft.dir.absolutePath) })
                            lines.add("pack-hash: " + (if (hash.ok) "ok" else (hash.error?.message ?: "fail")))
                            report = lines.joinToString("\n")
                        } catch (t: Throwable) {
                            error = CoreResponse.failure("NF-PCK-001", t.message ?: t.javaClass.simpleName, "fix draft", 1).error
                        } finally {
                            busy = false
                        }
                    }
                }) { Text(if (busy) "Working…" else "Validate") }
                Button(enabled = !busy, onClick = {
                    busy = true
                    error = null
                    scope.launch {
                        try {
                            val hash = safeCall("pack-hash", buildJsonObject { put("root", draft.dir.absolutePath) })
                            if (!hash.ok) {
                                error = hash.error
                            } else {
                                val result = hash.resultObject()
                                val items = result?.get("items")
                                val hashes = result?.get("hashes")
                                if (items != null && hashes != null) {
                                    store.writeHashes(draft, items, hashes)
                                }
                                val zip = store.packageToZip(draft, File(File(context.filesDir, "exports"), "packs"))
                                val installed = PackZipInstaller.install(zip, context.filesDir)
                                if (installed.ok) {
                                    report = "installed: " + installed.id + " " + installed.version
                                    onInstalled()
                                } else {
                                    error = CoreResponse.failure("NF-PCK-001", installed.message ?: "install failed", "check manifest", 1).error
                                }
                            }
                        } catch (t: Throwable) {
                            error = CoreResponse.failure("NF-PCK-001", t.message ?: t.javaClass.simpleName, "fix draft", 1).error
                        } finally {
                            busy = false
                        }
                    }
                }) { Text(if (busy) "Working…" else "Package & install") }
            }
            OutlinedButton(enabled = !busy, onClick = {
                busy = true
                error = null
                scope.launch {
                    try {
                        val release = safeCall("pack-release-create", buildJsonObject {
                            put("pack_root", draft.dir.absolutePath)
                            put("release_version", 1)
                            put("created_at", java.time.Instant.now().toString())
                            put("private_key", PackSigningKey.seed(context.filesDir))
                            put("channel", "local")
                        })
                        if (release.ok) {
                            val obj = release.resultObject()
                            if (obj != null) {
                                AtomicFiles.writeText(File(draft.dir, "release.json"), obj.toString())
                                releaseText = obj.toString()
                                val verify = safeCall("pack-release-verify", buildJsonObject {
                                    put("release", obj)
                                    put("pack_root", draft.dir.absolutePath)
                                })
                                report = (if (verify.ok) "release signed & verified" else "release signed; verify: " + (verify.error?.message ?: "fail")) + "\n" + obj.toString().take(400)
                            }
                        } else {
                            error = release.error
                        }
                    } catch (t: Throwable) {
                        error = CoreResponse.failure("NF-PCK-007", t.message ?: t.javaClass.simpleName, "check signing key", 1).error
                    } finally {
                        busy = false
                    }
                }
            }) { Text("Sign release") }
            OutlinedButton(enabled = !busy && releaseText != null, onClick = {
                busy = true
                error = null
                scope.launch {
                    try {
                        val release = Json.parseToJsonElement(releaseText!!).jsonObject
                        val trust = File(context.filesDir, "pack-release-trust.json")
                        val frozen = safeCall("pack-release-freeze", buildJsonObject {
                            put("release", release)
                            put("pack_root", draft.dir.absolutePath)
                            put("trust_path", trust.absolutePath)
                            put("created_at", java.time.Instant.now().toString())
                        })
                        if (!frozen.ok) {
                            error = frozen.error
                        } else {
                            val verify = safeCall("pack-release-verify", buildJsonObject {
                                put("release", release)
                                put("pack_root", draft.dir.absolutePath)
                                put("trust_path", trust.absolutePath)
                            })
                            report = (if (verify.ok) "release frozen & trusted" else "frozen; verify: " + (verify.error?.message ?: "fail")) + "\n" + trust.absolutePath
                        }
                    } catch (t: Throwable) {
                        error = CoreResponse.failure("NF-PCK-009", t.message ?: t.javaClass.simpleName, "check release", 1).error
                    } finally {
                        busy = false
                    }
                }
            }) { Text("Freeze trust") }
            releaseText?.let { Text(it.take(400), style = NfType.meta) }
            report?.let { Text(it, style = NfType.meta, modifier = Modifier.padding(top = NfSpacing.s)) }
            preview?.let {
                Text(it.take(1200), style = NfType.secondary, modifier = Modifier.padding(top = NfSpacing.s))
                Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    OutlinedButton(onClick = { store.saveGolden(draft, it); goldenStatus = "golden saved" }) {
                        Text("Save golden")
                    }
                    goldenStatus?.let { status -> Text(status, style = NfType.meta) }
                }
            }
            error?.let { Text(it.message, color = MaterialTheme.colorScheme.error, style = NfType.meta) }
        }
    }
}

private fun updateObjectArray(rootText: String, key: String, id: String, field: String, value: kotlinx.serialization.json.JsonElement): String {
    val root = Json.parseToJsonElement(rootText).jsonObject
    val arr = root[key]?.jsonArray ?: return rootText
    val next = JsonArray(arr.map { el ->
        val obj = el.jsonObject
        if (obj["id"]?.jsonPrimitive?.content == id) {
            JsonObject(obj.toMutableMap().apply { put(field, value) })
        } else el
    })
    return JsonObject(root.toMutableMap().apply { put(key, next) }).toString()
}

@Composable
private fun GraphMap(nodes: List<kotlinx.serialization.json.JsonElement>, edges: List<kotlinx.serialization.json.JsonElement>) {
    Canvas(
        modifier = Modifier.fillMaxWidth().height(180.dp).semantics {
            contentDescription = "Pipeline graph: " + nodes.size + " nodes, " + edges.size + " edges"
        }
    ) {
        val ids = nodes.map { it.jsonObject["id"]?.jsonPrimitive?.content.orEmpty() }
        val cols = 3
        val rows = ((ids.size + cols - 1) / cols).coerceAtLeast(1)
        fun pos(id: String): androidx.compose.ui.geometry.Offset {
            val index = ids.indexOf(id).coerceAtLeast(0)
            val col = index % cols
            val row = index / cols
            return androidx.compose.ui.geometry.Offset(
                x = size.width * (col + 1) / (cols + 1),
                y = size.height * (row + 1) / (rows + 1)
            )
        }
        edges.forEach { el ->
            val edge = el.jsonObject
            val from = edge["from"]?.jsonPrimitive?.content.orEmpty()
            val to = edge["to"]?.jsonPrimitive?.content.orEmpty()
            if (from.isNotBlank() && to.isNotBlank()) {
                drawLine(
                    color = androidx.compose.ui.graphics.Color(0xFF8AA6A0),
                    start = pos(from),
                    end = pos(to),
                    strokeWidth = 4f
                )
            }
        }
        ids.forEach { id ->
            drawCircle(
                color = androidx.compose.ui.graphics.Color(0xFF00695C),
                radius = 22f,
                center = pos(id)
            )
        }
    }
}

@Composable
private fun StructuredGraphCard(label: String, value: String, onChange: (String) -> Unit, dir: File) {
    val root = remember(value) { runCatching { Json.parseToJsonElement(value).jsonObject }.getOrNull() }
    var saved by remember { mutableStateOf<String?>(null) }
    CardBox(title = label) {
        if (root == null) {
            Text("Pipeline JSON invalid; use raw JSON editor below", style = NfType.meta, color = MaterialTheme.colorScheme.error)
        } else {
            val nodes = root["nodes"]?.jsonArray.orEmpty()
            val edges = root["edges"]?.jsonArray.orEmpty()
            GraphMap(nodes, edges)
            Text("nodes " + nodes.size + " · edges " + edges.size, style = NfType.meta)
            nodes.forEach { el ->
                val node = el.jsonObject
                val id = node["id"]?.jsonPrimitive?.content.orEmpty()
                Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    Text(id + " · " + (node["kind"]?.jsonPrimitive?.content ?: ""), style = NfType.label, modifier = Modifier.weight(1f))
                    TextButton(onClick = {
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
            edges.forEach { el ->
                val edge = el.jsonObject
                val eid = edge["id"]?.jsonPrimitive?.content.orEmpty()
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
                        val nextEdges = JsonArray(edges.filter { it.jsonObject["id"]?.jsonPrimitive?.content != eid })
                        val next = JsonObject(root.toMutableMap().apply { put("edges", nextEdges) })
                        onChange(next.toString())
                    }) { Text("Delete") }
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                OutlinedButton(onClick = {
                    var i = nodes.size + 1
                    var nid = "N" + i.toString().padStart(2, '0')
                    while (nodes.any { it.jsonObject["id"]?.jsonPrimitive?.content == nid }) { i++; nid = "N" + i.toString().padStart(2, '0') }
                    val node = buildJsonObject {
                        put("id", nid); put("kind", "stage"); put("title", "Node " + i)
                        put("ports", buildJsonObject { put("in", JsonArray(emptyList())); put("out", JsonArray(emptyList())) })
                    }
                    val next = JsonObject(root.toMutableMap().apply { put("nodes", JsonArray(nodes + node)) })
                    onChange(next.toString())
                }) { Text("Add node") }
                OutlinedButton(onClick = {
                    val a = nodes.getOrNull(0)?.jsonObject?.get("id")?.jsonPrimitive?.content ?: return@OutlinedButton
                    val b = nodes.getOrNull(1)?.jsonObject?.get("id")?.jsonPrimitive?.content ?: a
                    var i = edges.size + 1
                    var eid = "E" + i.toString().padStart(2, '0')
                    while (edges.any { it.jsonObject["id"]?.jsonPrimitive?.content == eid }) { i++; eid = "E" + i.toString().padStart(2, '0') }
                    val edge = buildJsonObject {
                        put("id", eid); put("from", a); put("to", b); put("from_port", "text"); put("to_port", "text"); put("type", "data")
                    }
                    val next = JsonObject(root.toMutableMap().apply { put("edges", JsonArray(edges + edge)) })
                    onChange(next.toString())
                }) { Text("Add edge") }
            }
            Button(onClick = {
                runCatching {
                    Json.parseToJsonElement(value).jsonObject
                    AtomicFiles.writeText(File(dir, "pipeline/main.nfg.json"), value)
                    saved = "saved pipeline"
                }.onFailure { saved = it.message ?: "invalid pipeline" }
            }) { Text("Save pipeline") }
            saved?.let { Text(it, style = NfType.meta) }
        }
    }
}

@Composable
private fun StructuredProtocolCard(label: String, value: String, onChange: (String) -> Unit, dir: File) {
    val root = remember(value) { runCatching { Json.parseToJsonElement(value).jsonObject }.getOrNull() }
    var saved by remember { mutableStateOf<String?>(null) }
    CardBox(title = label) {
        if (root == null) {
            Text("Protocol JSON invalid; use raw JSON editor below", style = NfType.meta, color = MaterialTheme.colorScheme.error)
        } else {
            val clauses = root["clauses"]?.jsonArray.orEmpty()
            val fields = root["fields"]?.jsonArray.orEmpty()
            clauses.forEach { el ->
                val clause = el.jsonObject
                val id = clause["id"]?.jsonPrimitive?.content.orEmpty()
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
            Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                Button(onClick = {
                    runCatching {
                        Json.parseToJsonElement(value).jsonObject
                        AtomicFiles.writeText(File(dir, "protocol/nf-protocol-pack.json"), value)
                        saved = "saved protocol"
                    }.onFailure { saved = it.message ?: "invalid protocol" }
                }) { Text("Save protocol") }
                saved?.let { Text(it, style = NfType.meta) }
            }
        }
    }
}

@Composable
private fun StructuredSpecCard(label: String, value: String, onChange: (String) -> Unit, dir: File) {
    val spec = remember(value) { runCatching { SpecModel.parse(value) }.getOrNull() }
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
private fun JsonEditorCard(
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
