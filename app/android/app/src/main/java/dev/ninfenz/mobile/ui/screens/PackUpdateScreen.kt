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
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.data.LibraryStore
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.PackStore
import dev.ninfenz.mobile.data.PackZipLoader
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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
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
    var packs by remember { mutableStateOf<List<PackEntry>>(emptyList()) }
    var selected by remember { mutableStateOf<PackEntry?>(null) }
    var newRoot by remember { mutableStateOf<File?>(null) }
    var diffBusy by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        packs = withContext(Dispatchers.IO) { PackStore(context.filesDir).scan().packs }
        selected = packs.firstOrNull()
    }

    fun runDiff(oldPack: PackEntry?, root: File?) {
        if (oldPack == null || root == null || diffBusy) return
        scope.launch {
            diffBusy = true
            error = null
            try {
                val payload = buildJsonObject {
                    put("old_root", oldPack.dir.absolutePath)
                    put("new_root", root.absolutePath)
                }
                val response = safeCall("pack-diff", payload)
                val obj = response.resultObject()
                if (response.ok && obj != null) {
                    val parsed = PackUpdateModel.parse(obj)
                    update = parsed
                    rawUpdate = obj
                    decisions = parsed.conflicts.associate { it.id to it.defaultOption }
                    resultText = null
                } else {
                    error = response.error
                }
            } catch (e: Exception) {
                error = CoreResponse.failure("NF-PCK-001", "pack-diff 失败：" + (e.message ?: e.javaClass.simpleName), "检查两版 Pack 目录", 1).error
            } finally {
                diffBusy = false
            }
        }
    }

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

    val zipPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            error = null
            try {
                val meta = FileAccess.meta(context, uri)
                val zip = FileAccess.copyToCache(context, uri, meta.name)
                val dest = File(context.cacheDir, "new-pack")
                val root = withContext(Dispatchers.IO) { PackZipLoader.extract(zip, dest) }
                newRoot = root
                runDiff(selected, root)
            } catch (e: Exception) {
                error = CoreResponse.failure("NF-PCK-002", "新版 Pack 解包失败：" + (e.message ?: e.javaClass.simpleName), "确认 zip 根/单层目录含 nf-pack.json", 1).error
            }
        }
    }

    fun packDir(id: String, version: String): File = File(File(File(context.filesDir, "library/packs"), id), version)

    NfScaffold(title = stringResource(dev.ninfenz.mobile.R.string.packupdate_title), onBack = onBack) {
        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.packupdate_step1)) {
            if (packs.isEmpty()) {
                EmptyState(stringResource(dev.ninfenz.mobile.R.string.packupdate_no_packs))
            } else {
                Text(stringResource(dev.ninfenz.mobile.R.string.packupdate_select_base), style = MaterialTheme.typography.bodySmall)
                for (pack in packs) {
                    FilterChip(
                        selected = selected?.id == pack.id && selected?.version == pack.version,
                        onClick = { selected = pack; update = null; rawUpdate = null; resultText = null },
                        label = { Text(pack.id + " · " + pack.version) },
                        modifier = Modifier.padding(end = 6.dp)
                    )
                }
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { zipPicker.launch(arrayOf("application/zip", "application/octet-stream", "*/*")) }, enabled = !diffBusy) {
                        Text(if (diffBusy) stringResource(dev.ninfenz.mobile.R.string.packupdate_compare) else stringResource(dev.ninfenz.mobile.R.string.packupdate_choose_zip))
                    }
                    OutlinedButton(onClick = { picker.launch(arrayOf("application/json", "text/plain")) }) { Text("打开更新计划") }
                }
                selected?.let { Text(stringResource(dev.ninfenz.mobile.R.string.packupdate_base, it.id, it.version, it.dir.absolutePath), style = MaterialTheme.typography.bodySmall) }
                newRoot?.let { Text(stringResource(dev.ninfenz.mobile.R.string.packupdate_new, it.absolutePath), style = MaterialTheme.typography.bodySmall) }
                if (selected != null && newRoot == null) {
                    Notice(stringResource(dev.ninfenz.mobile.R.string.packupdate_hint), Tone.INFO)
                }
            }
            val u = update
            if (u != null) {
                KeyValue("from", u.from.id + " " + u.from.version)
                KeyValue("to", u.to.id + " " + u.to.version)
                KeyValue("changes", "added " + u.added.size + " · removed " + u.removed.size + " · modified " + u.modified.size)
                KeyValue("breaking", if (u.breaking) stringResource(dev.ninfenz.mobile.R.string.packupdate_breaking_yes) else stringResource(dev.ninfenz.mobile.R.string.packupdate_breaking_no))
                KeyValue("影响项目", if (u.affectedProjects.isEmpty()) stringResource(dev.ninfenz.mobile.R.string.packupdate_none) else u.affectedProjects.joinToString(","))
                KeyValue("overlay 键", if (u.overlayKeys.isEmpty()) stringResource(dev.ninfenz.mobile.R.string.packupdate_none) else u.overlayKeys.joinToString(","))
                for (note in u.notes) Notice(note, Tone.WARN)
            }
        }

        error?.let { ErrorNotice(it) }

        val u = update
        if (u != null) {
            CardBox(title = stringResource(dev.ninfenz.mobile.R.string.packupdate_changes)) {
                for (c in u.added) Text("+ " + c.path, style = MaterialTheme.typography.bodySmall)
                for (c in u.removed) Text("- " + c.path, style = MaterialTheme.typography.bodySmall)
                for (c in u.modified) Text("~ " + c.path, style = MaterialTheme.typography.bodySmall)
                if (u.totalChanges == 0) EmptyState(stringResource(dev.ninfenz.mobile.R.string.packupdate_no_changes))
            }

            CardBox(title = stringResource(dev.ninfenz.mobile.R.string.packupdate_conflicts)) {
                if (u.conflicts.isEmpty()) {
                    Notice(stringResource(dev.ninfenz.mobile.R.string.packupdate_no_conflicts), Tone.INFO)
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
                        Notice(stringResource(dev.ninfenz.mobile.R.string.packupdate_all_decided, u.conflicts.size), Tone.INFO)
                    } else {
                        Notice(pluralStringResource(dev.ninfenz.mobile.R.plurals.packupdate_unresolved, unresolved.size, unresolved.size), Tone.ERROR)
                    }
                }
            }

            CardBox(title = stringResource(dev.ninfenz.mobile.R.string.packupdate_apply_rollback)) {
                val base = selected?.dir ?: packDir(u.from.id, u.from.version)
                val target = newRoot ?: packDir(u.to.id, u.to.version)
                KeyValue(stringResource(dev.ninfenz.mobile.R.string.packupdate_base_dir), if (base.exists()) stringResource(dev.ninfenz.mobile.R.string.packupdate_present) else stringResource(dev.ninfenz.mobile.R.string.packupdate_missing, base.absolutePath))
                KeyValue(stringResource(dev.ninfenz.mobile.R.string.packupdate_new_dir), if (target.exists()) stringResource(dev.ninfenz.mobile.R.string.packupdate_present) else stringResource(dev.ninfenz.mobile.R.string.packupdate_missing, target.absolutePath))
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
                    ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.packupdate_applying) else stringResource(dev.ninfenz.mobile.R.string.packupdate_apply)) }

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
                                        resultText = context.getString(dev.ninfenz.mobile.R.string.packupdate_result, response.result?.toString() ?: "")
                                    } else {
                                        error = response.error
                                    }
                                } finally {
                                    busy = false
                                }
                            }
                        }
                    ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.packupdate_rolling) else stringResource(dev.ninfenz.mobile.R.string.packupdate_rollback)) }
                }
                resultText?.let { MonoText(it) }
                Notice(stringResource(dev.ninfenz.mobile.R.string.packupdate_notice), Tone.INFO)
            }
        }
    }
}
