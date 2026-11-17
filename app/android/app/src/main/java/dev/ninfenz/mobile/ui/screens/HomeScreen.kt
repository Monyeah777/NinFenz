package dev.ninfenz.mobile.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.core.Core
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.data.LibrarySnapshot
import dev.ninfenz.mobile.data.LibraryStore
import dev.ninfenz.mobile.state.Screen
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.components.EmptyState
import dev.ninfenz.mobile.ui.components.KeyValue
import dev.ninfenz.mobile.ui.components.NfScaffold
import dev.ninfenz.mobile.ui.components.Notice
import dev.ninfenz.mobile.ui.components.Tone
import kotlinx.coroutines.launch
import java.io.File

@Composable
fun HomeScreen(store: LibraryStore, onOpen: (Screen) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var snapshot by remember { mutableStateOf<LibrarySnapshot?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    var installError by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    fun refresh() {
        snapshot = store.loadProjects()
    }
    LaunchedEffect(Unit) { refresh() }

    val treePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            busy = true
            installError = null
            try {
                val incoming = File(context.filesDir, "library/incoming").apply { mkdirs() }
                val count = FileAccess.copyTree(context, uri, incoming)
                val manifest = File(incoming, "nf-pack.json")
                if (!manifest.exists()) {
                    installError = context.getString(dev.ninfenz.mobile.R.string.pack_install_missing_manifest, count)
                } else {
                    val obj = J.parseObject(manifest.readText(Charsets.UTF_8), "nf-pack/1")
                    val id = J.optString(obj, "id")
                    val version = J.optString(obj, "version")
                    if (id == null || version == null) {
                        installError = context.getString(dev.ninfenz.mobile.R.string.pack_install_missing_id)
                    } else {
                        val target = File(File(File(context.filesDir, "library/packs"), id), version)
                        target.parentFile?.mkdirs()
                        if (target.exists()) {
                            installError = context.getString(dev.ninfenz.mobile.R.string.pack_install_duplicate, id, version)
                        } else {
                            try {
                                dev.ninfenz.mobile.data.PackInstaller.install(incoming, target, "directory")
                                message = context.getString(
                                    dev.ninfenz.mobile.R.string.pack_install_done,
                                    id,
                                    version,
                                    count
                                )
                                val verify = if (Core.diagnostics().nativeReady) {
                                    context.getString(dev.ninfenz.mobile.R.string.pack_install_core_ready)
                                } else {
                                    context.getString(dev.ninfenz.mobile.R.string.pack_install_core_missing)
                                }
                                message = context.getString(
                                    dev.ninfenz.mobile.R.string.pack_install_done_with_status,
                                    message ?: "",
                                    verify
                                )
                            } catch (t: Throwable) {
                                installError = context.getString(
                                    dev.ninfenz.mobile.R.string.pack_install_move_failed,
                                    t.message ?: target.absolutePath
                                )
                            }
                        }
                    }
                }
            } catch (e: Exception) {
                installError = context.getString(dev.ninfenz.mobile.R.string.pack_install_failed, e.message ?: e.javaClass.simpleName)
            } finally {
                busy = false
                incomingCleanup(context)
            }
        }
    }

    NfScaffold(title = "NF Mobile · Home", onBack = null) {
        CardBox(title = context.getString(dev.ninfenz.mobile.R.string.home_control_plane)) {
            Text(context.getString(dev.ninfenz.mobile.R.string.home_local_only), style = MaterialTheme.typography.bodySmall)
            val diag = remember { Core.diagnostics() }
            KeyValue(
                context.getString(dev.ninfenz.mobile.R.string.home_core_bridge),
                diag.backend + (if (diag.nativeReady) " · " + (diag.abiVersion ?: "") else context.getString(dev.ninfenz.mobile.R.string.home_core_unavailable))
            )
            KeyValue(
                context.getString(dev.ninfenz.mobile.R.string.home_error_codes),
                if (diag.errorCatalogLoaded) context.getString(dev.ninfenz.mobile.R.string.home_error_code_count, diag.errorCodeCount) else context.getString(dev.ninfenz.mobile.R.string.home_not_bundled)
            )
        }

        CardBox(title = context.getString(dev.ninfenz.mobile.R.string.home_screen_nav)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { onOpen(Screen.IMPORT) }) { Text(context.getString(dev.ninfenz.mobile.R.string.screen_import)) }
                OutlinedButton(onClick = { onOpen(Screen.PROTOCOL) }) { Text(context.getString(dev.ninfenz.mobile.R.string.screen_protocol)) }
                OutlinedButton(onClick = { onOpen(Screen.GRAPH) }) { Text(context.getString(dev.ninfenz.mobile.R.string.home_pipeline)) }
            }
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { onOpen(Screen.ASSEMBLY) }) { Text(context.getString(dev.ninfenz.mobile.R.string.screen_assembly)) }
                OutlinedButton(onClick = { onOpen(Screen.PACK_UPDATE) }) { Text(context.getString(dev.ninfenz.mobile.R.string.screen_pack_update)) }
                OutlinedButton(onClick = { onOpen(Screen.CCOS) }) { Text(context.getString(dev.ninfenz.mobile.R.string.home_ccos_review)) }
            }
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { onOpen(Screen.SETTINGS) }) { Text(context.getString(dev.ninfenz.mobile.R.string.home_settings_diag)) }
            }
        }

        CardBox(title = context.getString(dev.ninfenz.mobile.R.string.home_pack_library)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { treePicker.launch(null) }, enabled = !busy) {
                    Text(if (busy) context.getString(dev.ninfenz.mobile.R.string.home_installing) else context.getString(dev.ninfenz.mobile.R.string.home_install_pack))
                }
                OutlinedButton(onClick = { refresh() }) { Text(context.getString(dev.ninfenz.mobile.R.string.home_refresh)) }
            }
            val packsDir = File(context.filesDir, "library/packs")
            val ids = packsDir.listFiles()?.filter { it.isDirectory }?.sortedBy { it.name } ?: emptyList()
            if (ids.isEmpty()) {
                EmptyState(context.getString(dev.ninfenz.mobile.R.string.home_pack_empty))
            } else {
                for (idDir in ids) {
                    val versions = idDir.listFiles()?.filter { it.isDirectory }?.map { it.name }?.sorted() ?: emptyList()
                    KeyValue(idDir.name, versions.joinToString(", "))
                }
            }
            installError?.let { Notice(it, Tone.ERROR) }
            message?.let { Notice(it, Tone.INFO) }
        }

        CardBox(title = context.getString(dev.ninfenz.mobile.R.string.home_project_library)) {
            val snap = snapshot
            if (snap == null) {
                EmptyState(context.getString(dev.ninfenz.mobile.R.string.home_loading))
            } else if (snap.projects.isEmpty() && snap.errors.isEmpty()) {
                EmptyState(context.getString(dev.ninfenz.mobile.R.string.home_project_empty))
            } else {
                for (entry in snap.projects) {
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(8.dp)) {
                            Text(entry.project.title + " · " + entry.project.status.wire, style = MaterialTheme.typography.titleSmall)
                            Text(entry.project.id + " · base " + entry.project.refs.basePackId + " " + entry.project.refs.basePackVersion, style = MaterialTheme.typography.bodySmall)
                            Text(
                                context.getString(
                                    dev.ninfenz.mobile.R.string.home_review_summary,
                                    entry.project.review.state,
                                    entry.project.historyCount
                                ),
                                style = MaterialTheme.typography.bodySmall
                            )
                        }
                    }
                }
                for (err in snap.errors) Notice(context.getString(dev.ninfenz.mobile.R.string.home_project_parse_failed, err), Tone.ERROR)
            }
            TextButton(onClick = { refresh() }) { Text(context.getString(dev.ninfenz.mobile.R.string.home_rescan)) }
        }
    }
}

private fun incomingCleanup(context: android.content.Context) {
    val incoming = File(context.filesDir, "library/incoming")
    val files = incoming.listFiles() ?: return
    for (f in files) f.deleteRecursively()
}
