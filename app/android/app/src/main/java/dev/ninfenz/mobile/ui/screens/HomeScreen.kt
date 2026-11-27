package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.ui.design.NfType

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
                installPackFromUri(context, uri, onError = { installError = it }, onMessage = { message = it })
            } catch (e: Exception) {
                installError = context.getString(dev.ninfenz.mobile.R.string.pack_install_failed, e.message ?: e.javaClass.simpleName)
            } finally {
                busy = false
                incomingCleanup(context)
            }
        }
    }

    NfScaffold(title = "NF Mobile · Home", onBack = null) {
        HomeControlPlaneCard()

        HomeNavCard(onOpen = onOpen)

        HomePackLibraryCard(
            busy = busy,
            onInstall = { treePicker.launch(null) },
            onRefresh = { refresh() },
            installError = installError,
            message = message
        )

        HomeProjectLibraryCard(
            snapshot = snapshot,
            onRefresh = { refresh() }
        )
    }
}

private suspend fun installPackFromUri(
    context: android.content.Context,
    uri: Uri,
    onError: (String?) -> Unit,
    onMessage: (String?) -> Unit
) {
    val incoming = File(context.filesDir, "library/incoming").apply { mkdirs() }
    val count = FileAccess.copyTree(context, uri, incoming)
    val manifest = File(incoming, "nf-pack.json")
    if (!manifest.exists()) {
        onError(context.getString(dev.ninfenz.mobile.R.string.pack_install_missing_manifest, count))
        return
    }
    val obj = J.parseObject(manifest.readText(Charsets.UTF_8), "nf-pack/1")
    val id = J.optString(obj, "id")
    val version = J.optString(obj, "version")
    if (id == null || version == null) {
        onError(context.getString(dev.ninfenz.mobile.R.string.pack_install_missing_id))
        return
    }
    val target = File(File(File(context.filesDir, "library/packs"), id), version)
    target.parentFile?.mkdirs()
    if (target.exists()) {
        onError(context.getString(dev.ninfenz.mobile.R.string.pack_install_duplicate, id, version))
        return
    }
    try {
        dev.ninfenz.mobile.data.PackInstaller.install(incoming, target, "directory")
        var msg = context.getString(dev.ninfenz.mobile.R.string.pack_install_done, id, version, count)
        val verify = if (Core.diagnostics().nativeReady) {
            context.getString(dev.ninfenz.mobile.R.string.pack_install_core_ready)
        } else {
            context.getString(dev.ninfenz.mobile.R.string.pack_install_core_missing)
        }
        msg = context.getString(dev.ninfenz.mobile.R.string.pack_install_done_with_status, msg, verify)
        onMessage(msg)
    } catch (t: Throwable) {
        onError(context.getString(dev.ninfenz.mobile.R.string.pack_install_move_failed, t.message ?: target.absolutePath))
    }
}

private fun incomingCleanup(context: android.content.Context) {
    val incoming = File(context.filesDir, "library/incoming")
    val files = incoming.listFiles() ?: return
    for (f in files) f.deleteRecursively()
}

@Composable
private fun HomeControlPlaneCard() {
    val context = LocalContext.current
    CardBox(title = context.getString(dev.ninfenz.mobile.R.string.home_control_plane)) {
        Text(context.getString(dev.ninfenz.mobile.R.string.home_local_only), style = NfType.meta)
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
}

@Composable
private fun HomeNavCard(onOpen: (Screen) -> Unit) {
    val context = LocalContext.current
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
}

@Composable
private fun HomePackLibraryCard(
    busy: Boolean,
    onInstall: () -> Unit,
    onRefresh: () -> Unit,
    installError: String?,
    message: String?
) {
    val context = LocalContext.current
    CardBox(title = context.getString(dev.ninfenz.mobile.R.string.home_pack_library)) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = onInstall, enabled = !busy) {
                Text(if (busy) context.getString(dev.ninfenz.mobile.R.string.home_installing) else context.getString(dev.ninfenz.mobile.R.string.home_install_pack))
            }
            OutlinedButton(onClick = onRefresh) { Text(context.getString(dev.ninfenz.mobile.R.string.home_refresh)) }
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
}

@Composable
private fun HomeProjectLibraryCard(
    snapshot: LibrarySnapshot?,
    onRefresh: () -> Unit
) {
    val context = LocalContext.current
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
                        Text(entry.project.title + " · " + entry.project.status.wire, style = NfType.itemTitle)
                        Text(entry.project.id + " · base " + entry.project.refs.basePackId + " " + entry.project.refs.basePackVersion, style = NfType.meta)
                        Text(
                            context.getString(
                                dev.ninfenz.mobile.R.string.home_review_summary,
                                entry.project.review.state,
                                entry.project.historyCount
                            ),
                            style = NfType.meta
                        )
                    }
                }
            }
            for (err in snap.errors) Notice(context.getString(dev.ninfenz.mobile.R.string.home_project_parse_failed, err), Tone.ERROR)
        }
        TextButton(onClick = onRefresh) { Text(context.getString(dev.ninfenz.mobile.R.string.home_rescan)) }
    }
}