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
internal fun PackMetadataCard(
    id: String,
    version: String,
    title: String,
    onIdChange: (String) -> Unit,
    onVersionChange: (String) -> Unit,
    onTitleChange: (String) -> Unit,
    onSave: () -> Unit,
    onClear: () -> Unit
) {
CardBox(title = "Metadata") {
    FormTextField("id", id, onIdChange)
    FormTextField("version", version, onVersionChange)
    FormTextField("title", title, onTitleChange)
    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
        OutlinedButton(onClick = {
            onSave()
            
        }) { Text("Save metadata") }
        OutlinedButton(onClick = onClear) { Text("Clear") }
    }
}
}

@Composable
internal fun PackFilesCard(draft: PackDraftStore.Draft) {
CardBox(title = "Files") {
    draft.dir.walkTopDown().filter { it.isFile }.sortedBy { it.path }.take(40).forEach { file ->
        Text(file.relativeTo(draft.dir).invariantSeparatorsPath + " · " + file.length(), style = NfType.meta)
    }
}
}

@Composable
internal fun PackTestAssembleButton(
    draft: PackDraftStore.Draft,
    store: PackDraftStore,
    graphText: String,
    specText: String,
    busy: Boolean,
    onBusyChange: (Boolean) -> Unit,
    onErrorChange: (CoreError?) -> Unit,
    onPreviewChange: (String?) -> Unit,
    onGoldenStatusChange: (String?) -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    OutlinedButton(enabled = !busy, onClick = {
        onBusyChange(true)
        onErrorChange(null)
        scope.launch {
            try {
                testAssemble(context, draft, store, graphText, specText, onErrorChange, onPreviewChange, onGoldenStatusChange)
            } finally {
                onBusyChange(false)
            }
        }
    }) { Text("Test assemble") }
}

private suspend fun testAssemble(
    context: android.content.Context,
    draft: PackDraftStore.Draft,
    store: PackDraftStore,
    graphText: String,
    specText: String,
    onErrorChange: (CoreError?) -> Unit,
    onPreviewChange: (String?) -> Unit,
    onGoldenStatusChange: (String?) -> Unit
) {
    try {
        val graph = Json.parseToJsonElement(graphText).jsonObject
        val spec = Json.parseToJsonElement(specText).jsonObject
        val compiled = safeCall("graph-compile", buildJsonObject { put("graph", graph) })
        if (!compiled.ok) {
            onErrorChange(compiled.error)
        } else {
            val plan = compiled.resultObject()
            if (plan == null) {
                onErrorChange(CoreResponse.failure("NF-ASM-001", "graph-compile did not return plan", "fix pipeline", 1).error)
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
                    onPreviewChange(md)
                    val golden = store.loadGolden(draft)
                    onGoldenStatusChange(when {
                        golden == null -> "no golden yet"
                        golden == md -> "golden match"
                        else -> "golden differs @ " + (dev.ninfenz.mobile.data.ReproChecker.firstDifference(golden.toByteArray(Charsets.UTF_8), md.toByteArray(Charsets.UTF_8)) ?: -1)
                    })
                } else {
                    onErrorChange(assembled.error)
                }
            }
        }
    } catch (t: Throwable) {
        onErrorChange(CoreResponse.failure("NF-ASM-003", t.message ?: t.javaClass.simpleName, "check graph/spec", 1).error)
    }
}

@Composable
internal fun PackValidateButton(
    draft: PackDraftStore.Draft,
    busy: Boolean,
    onBusyChange: (Boolean) -> Unit,
    onErrorChange: (CoreError?) -> Unit,
    onReportChange: (String?) -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    Button(enabled = !busy, onClick = {
        onBusyChange(true)
        onErrorChange(null)
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
                onReportChange(lines.joinToString("\n"))
            } catch (t: Throwable) {
                onErrorChange(CoreResponse.failure("NF-PCK-001", t.message ?: t.javaClass.simpleName, "fix draft", 1).error)
            } finally {
                onBusyChange(false)
            }
        }
    }) { Text(if (busy) "Working…" else "Validate") }
}

@Composable
internal fun PackPackageInstallButton(
    draft: PackDraftStore.Draft,
    store: PackDraftStore,
    busy: Boolean,
    onBusyChange: (Boolean) -> Unit,
    onErrorChange: (CoreError?) -> Unit,
    onReportChange: (String?) -> Unit,
    onInstalled: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    Button(enabled = !busy, onClick = {
        onBusyChange(true)
        onErrorChange(null)
        scope.launch {
            try {
                val hash = safeCall("pack-hash", buildJsonObject { put("root", draft.dir.absolutePath) })
                if (!hash.ok) {
                    onErrorChange(hash.error)
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
                        onReportChange("installed: " + installed.id + " " + installed.version)
                        onInstalled()
                    } else {
                        onErrorChange(CoreResponse.failure("NF-PCK-001", installed.message ?: "install failed", "check manifest", 1).error)
                    }
                }
            } catch (t: Throwable) {
                onErrorChange(CoreResponse.failure("NF-PCK-001", t.message ?: t.javaClass.simpleName, "fix draft", 1).error)
            } finally {
                onBusyChange(false)
            }
        }
    }) { Text(if (busy) "Working…" else "Package & install") }
}

@Composable
internal fun PackSignReleaseButton(
    draft: PackDraftStore.Draft,
    busy: Boolean,
    onBusyChange: (Boolean) -> Unit,
    onErrorChange: (CoreError?) -> Unit,
    onReportChange: (String?) -> Unit,
    onReleaseTextChange: (String?) -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    OutlinedButton(enabled = !busy, onClick = {
        onBusyChange(true)
        onErrorChange(null)
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
                        onReleaseTextChange(obj.toString())
                        val verify = safeCall("pack-release-verify", buildJsonObject {
                            put("release", obj)
                            put("pack_root", draft.dir.absolutePath)
                        })
                        onReportChange((if (verify.ok) "release signed & verified" else "release signed; verify: " + (verify.error?.message ?: "fail")) + "\n" + obj.toString().take(400))
                    }
                } else {
                    onErrorChange(release.error)
                }
            } catch (t: Throwable) {
                onErrorChange(CoreResponse.failure("NF-PCK-007", t.message ?: t.javaClass.simpleName, "check signing key", 1).error)
            } finally {
                onBusyChange(false)
            }
        }
    }) { Text("Sign release") }
}

@Composable
internal fun PackFreezeTrustButton(
    draft: PackDraftStore.Draft,
    releaseText: String?,
    busy: Boolean,
    onBusyChange: (Boolean) -> Unit,
    onErrorChange: (CoreError?) -> Unit,
    onReportChange: (String?) -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    OutlinedButton(enabled = !busy && releaseText != null, onClick = {
        onBusyChange(true)
        onErrorChange(null)
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
                    onErrorChange(frozen.error)
                } else {
                    val verify = safeCall("pack-release-verify", buildJsonObject {
                        put("release", release)
                        put("pack_root", draft.dir.absolutePath)
                        put("trust_path", trust.absolutePath)
                    })
                    onReportChange((if (verify.ok) "release frozen & trusted" else "frozen; verify: " + (verify.error?.message ?: "fail")) + "\n" + trust.absolutePath)
                }
            } catch (t: Throwable) {
                onErrorChange(CoreResponse.failure("NF-PCK-009", t.message ?: t.javaClass.simpleName, "check release", 1).error)
            } finally {
                onBusyChange(false)
            }
        }
    }) { Text("Freeze trust") }
}

@Composable
internal fun PackBuildResults(
    releaseText: String?,
    report: String?,
    preview: String?,
    goldenStatus: String?,
    error: CoreError?,
    onSaveGolden: (String) -> Unit
) {
    releaseText?.let { Text(it.take(400), style = NfType.meta) }
    report?.let { Text(it, style = NfType.meta, modifier = Modifier.padding(top = NfSpacing.s)) }
    preview?.let {
        Text(it.take(1200), style = NfType.secondary, modifier = Modifier.padding(top = NfSpacing.s))
        Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
            OutlinedButton(onClick = { onSaveGolden(it) }) {
                Text("Save golden")
            }
            goldenStatus?.let { status -> Text(status, style = NfType.meta) }
        }
    }
    error?.let { Text(it.message, color = MaterialTheme.colorScheme.error, style = NfType.meta) }
}
