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
                            val ok = incoming.renameTo(target)
                            if (!ok) {
                                installError = context.getString(dev.ninfenz.mobile.R.string.pack_install_move_failed, target.absolutePath)
                            } else {
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
        CardBox(title = "控制面") {
            Text("本地处理 · 无账号 · 无遥测 · 无网络权限", style = MaterialTheme.typography.bodySmall)
            val diag = remember { Core.diagnostics() }
            KeyValue("核心桥", diag.backend + (if (diag.nativeReady) " · " + (diag.abiVersion ?: "") else " · 不可用（NF-E-005）"))
            KeyValue("错误码登记", if (diag.errorCatalogLoaded) diag.errorCodeCount.toString() + " 条（单一真源）" else "未打包")
        }

        CardBox(title = "屏幕导航") {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { onOpen(Screen.IMPORT) }) { Text("导入") }
                OutlinedButton(onClick = { onOpen(Screen.PROTOCOL) }) { Text("协议") }
                OutlinedButton(onClick = { onOpen(Screen.GRAPH) }) { Text("管线图") }
            }
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { onOpen(Screen.ASSEMBLY) }) { Text("装配") }
                OutlinedButton(onClick = { onOpen(Screen.PACK_UPDATE) }) { Text("Pack 更新") }
                OutlinedButton(onClick = { onOpen(Screen.CCOS) }) { Text("CCOS 人审") }
            }
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { onOpen(Screen.SETTINGS) }) { Text("设置/诊断") }
            }
        }

        CardBox(title = "Pack 库（library/packs）") {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { treePicker.launch(null) }, enabled = !busy) {
                    Text(if (busy) "安装中…" else "安装 Pack（选目录）")
                }
                OutlinedButton(onClick = { refresh() }) { Text("刷新") }
            }
            val packsDir = File(context.filesDir, "library/packs")
            val ids = packsDir.listFiles()?.filter { it.isDirectory }?.sortedBy { it.name } ?: emptyList()
            if (ids.isEmpty()) {
                EmptyState("尚无已安装 Pack。安装只写 app 私有目录，不触碰外部存储根。")
            } else {
                for (idDir in ids) {
                    val versions = idDir.listFiles()?.filter { it.isDirectory }?.map { it.name }?.sorted() ?: emptyList()
                    KeyValue(idDir.name, versions.joinToString(", "))
                }
            }
            installError?.let { Notice(it, Tone.ERROR) }
            message?.let { Notice(it, Tone.INFO) }
        }

        CardBox(title = "项目（projects/*.nfproject.json）") {
            val snap = snapshot
            if (snap == null) {
                EmptyState("读取中…")
            } else if (snap.projects.isEmpty() && snap.errors.isEmpty()) {
                EmptyState("尚无项目文件。项目=引用集合（ID+digest），不内嵌 Pack 内容。")
            } else {
                for (entry in snap.projects) {
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(8.dp)) {
                            Text(entry.project.title + " · " + entry.project.status.wire, style = MaterialTheme.typography.titleSmall)
                            Text(entry.project.id + " · base " + entry.project.refs.basePackId + " " + entry.project.refs.basePackVersion, style = MaterialTheme.typography.bodySmall)
                            Text("评审 " + entry.project.review.state + " · history " + entry.project.historyCount + " 条", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
                for (err in snap.errors) Notice("项目解析失败：" + err, Tone.ERROR)
            }
            TextButton(onClick = { refresh() }) { Text("重新扫描") }
        }
    }
}

private fun incomingCleanup(context: android.content.Context) {
    val incoming = File(context.filesDir, "library/incoming")
    val files = incoming.listFiles() ?: return
    for (f in files) f.deleteRecursively()
}
