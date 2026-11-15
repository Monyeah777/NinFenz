package dev.ninfenz.mobile.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.data.LibraryStore
import dev.ninfenz.mobile.model.ConflictBoard
import dev.ninfenz.mobile.model.PackUpdate
import dev.ninfenz.mobile.model.PackUpdateModel
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.components.EmptyState
import dev.ninfenz.mobile.ui.components.ErrorNotice
import dev.ninfenz.mobile.ui.components.KeyValue
import dev.ninfenz.mobile.ui.components.MonoText
import dev.ninfenz.mobile.ui.components.NfScaffold
import dev.ninfenz.mobile.ui.components.Notice
import dev.ninfenz.mobile.ui.components.Tone
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.io.File

@Composable
fun PackUpdateScreen(store: LibraryStore, onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var update by remember { mutableStateOf<PackUpdate?>(null) }
    var rawUpdate by remember { mutableStateOf<JsonObject?>(null) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var decisions by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    var resultText by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val text = FileAccess.readText(context, uri)
                val obj = J.parseObject(text, "nf-pack-update/1")
                val parsed = PackUpdateModel.parse(obj)
                update = parsed
                rawUpdate = obj
                decisions = parsed.conflicts.associate { it.id to it.defaultOption }
                error = null
                resultText = null
            } catch (e: Exception) {
                error = CoreResponse.failure("NF-PCK-001", "更新计划解析失败：" + (e.message ?: e.javaClass.simpleName), "按 app/schema/nf-pack-update.schema.json 修正", 1).error
            }
        }
    }

    fun packDir(id: String, version: String): File = File(File(File(context.filesDir, "library/packs"), id), version)

    NfScaffold(title = "PackUpdate · diff/冲突/应用/回滚", onBack = onBack) {
        CardBox(title = "更新计划") {
            Button(onClick = { picker.launch(arrayOf("application/json", "text/plain")) }) { Text("打开 .nfupdate.json") }
            val u = update
            if (u == null) {
                EmptyState("尚未加载更新计划。应用/回滚需要 library/packs/<id>/<version> 两端目录都在场。")
            } else {
                KeyValue("from", u.from.id + " " + u.from.version)
                KeyValue("to", u.to.id + " " + u.to.version)
                KeyValue("changes", "added " + u.added.size + " · removed " + u.removed.size + " · modified " + u.modified.size)
                KeyValue("breaking", if (u.breaking) "是（删除/结构变更）" else "否")
                KeyValue("影响项目", if (u.affectedProjects.isEmpty()) "（无）" else u.affectedProjects.joinToString(","))
                KeyValue("overlay 键", if (u.overlayKeys.isEmpty()) "（无）" else u.overlayKeys.joinToString(","))
                for (note in u.notes) Notice(note, Tone.WARN)
            }
        }

        error?.let { ErrorNotice(it) }

        val u = update
        if (u != null) {
            CardBox(title = "变更") {
                for (c in u.added) Text("+ " + c.path, style = MaterialTheme.typography.bodySmall)
                for (c in u.removed) Text("- " + c.path, style = MaterialTheme.typography.bodySmall)
                for (c in u.modified) Text("~ " + c.path, style = MaterialTheme.typography.bodySmall)
                if (u.totalChanges == 0) EmptyState("无变更")
            }

            CardBox(title = "冲突决策（默认 defer）") {
                if (u.conflicts.isEmpty()) {
                    Notice("无冲突：可直接应用。", Tone.INFO)
                } else {
                    for (conflict in u.conflicts) {
                        Column(modifier = Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(conflict.id + " · " + conflict.kind + " · " + conflict.path, style = MaterialTheme.typography.bodyMedium)
                            Text("options=" + conflict.options.joinToString("/") + " · default=" + conflict.defaultOption,
                                style = MaterialTheme.typography.bodySmall)
                            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                for (option in conflict.options) {
                                    FilterChip(
                                        selected = (decisions[conflict.id] ?: conflict.defaultOption) == option,
                                        onClick = { decisions = decisions + (conflict.id to option) },
                                        label = { Text(option) }
                                    )
                                }
                            }
                        }
                    }
                    val unresolved = u.conflicts.filter { (decisions[it.id] ?: it.defaultOption) == "defer" }
                    if (unresolved.isEmpty()) {
                        Notice("全部冲突已裁决（" + u.conflicts.size + " 个）", Tone.INFO)
                    } else {
                        Notice("未裁决 " + unresolved.size + " 个：defer 不得应用（NF-PCK-006）", Tone.ERROR)
                    }
                }
            }

            CardBox(title = "应用 / 回滚") {
                val base = packDir(u.from.id, u.from.version)
                val target = packDir(u.to.id, u.to.version)
                KeyValue("base 目录", if (base.exists()) "在场" else "缺失 " + base.absolutePath)
                KeyValue("new 目录", if (target.exists()) "在场" else "缺失 " + target.absolutePath)
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        enabled = !busy && base.exists() && target.exists() && u.conflicts.all { (decisions[it.id] ?: it.defaultOption) != "defer" },
                        onClick = {
                            val raw = rawUpdate ?: return@Button
                            scope.launch {
                                busy = true
                                error = null
                                resultText = null
                                try {
                                    val outDir = File(context.filesDir, "library/applied").apply { mkdirs() }
                                    val payload = buildJsonObject {
                                        put("update", raw)
                                        put("base_root", base.absolutePath)
                                        put("new_root", target.absolutePath)
                                        put("decisions", buildJsonObject {
                                            for ((k, v) in decisions) put(k, v)
                                        })
                                        put("out_dir", outDir.absolutePath)
                                    }
                                    val response = safeCall("pack-merge", payload)
                                    if (response.ok) {
                                        resultText = response.result?.toString()
                                    } else {
                                        error = response.error
                                    }
                                } finally {
                                    busy = false
                                }
                            }
                        }
                    ) { Text(if (busy) "应用中…" else "应用更新") }

                    OutlinedButton(
                        enabled = !busy && base.exists() && target.exists(),
                        onClick = {
                            val raw = rawUpdate ?: return@OutlinedButton
                            scope.launch {
                                busy = true
                                error = null
                                resultText = null
                                try {
                                    // 回滚 = 反向 update（base=新版目录，new=旧版目录），仍走同一 pack-merge op
                                    val reversed = PackUpdateModel.reversed(PackUpdateModel.parse(raw))
                                    val rawReversed = PackUpdateModel.toJson(reversed)
                                    val outDir = File(context.filesDir, "library/applied-rollback").apply { mkdirs() }
                                    val payload = buildJsonObject {
                                        put("update", rawReversed)
                                        put("base_root", target.absolutePath)
                                        put("new_root", base.absolutePath)
                                        put("out_dir", outDir.absolutePath)
                                    }
                                    val response = safeCall("pack-merge", payload)
                                    if (response.ok) {
                                        resultText = "回滚结果：" + response.result?.toString()
                                    } else {
                                        error = response.error
                                    }
                                } finally {
                                    busy = false
                                }
                            }
                        }
                    ) { Text(if (busy) "回滚中…" else "回滚") }
                }
                resultText?.let { MonoText(it) }
                Notice("应用/回滚均为原子替换 + 复验；失败时核心返回错误码（NF-PCK-00x）而不是静默部分写入。", Tone.INFO)
            }
        }
    }
}
