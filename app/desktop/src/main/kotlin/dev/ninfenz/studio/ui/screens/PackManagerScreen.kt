package dev.ninfenz.studio.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
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
import androidx.compose.ui.unit.dp
import dev.ninfenz.studio.core.CoreError
import dev.ninfenz.studio.core.CoreResponse
import dev.ninfenz.studio.core.J
import dev.ninfenz.studio.model.ReportModel
import dev.ninfenz.studio.model.ValidateReport
import dev.ninfenz.studio.ui.ErrorCard
import dev.ninfenz.studio.ui.Field
import dev.ninfenz.studio.ui.FileDialogs
import dev.ninfenz.studio.ui.KeyValue
import dev.ninfenz.studio.ui.Mono
import dev.ninfenz.studio.ui.Notice
import dev.ninfenz.studio.ui.Section
import dev.ninfenz.studio.ui.safeCall
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.io.File

@Composable
fun PackManagerScreen() {
    val scope = rememberCoroutineScope()
    var rootText by remember { mutableStateOf(File(System.getProperty("user.home"), "NFStudio/packs").absolutePath) }
    var packDirs by remember { mutableStateOf<List<File>>(emptyList()) }
    var selected by remember { mutableStateOf<File?>(null) }
    var report by remember { mutableStateOf<ValidateReport?>(null) }
    var hashSummary by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var busy by remember { mutableStateOf(false) }

    fun scan(dir: File) {
        error = null
        if (!dir.isDirectory) {
            error = CoreResponse.failure("NF-E-004", "目录不存在：" + dir.absolutePath, "换路径或创建目录", 2).error
            return
        }
        packDirs = dir.listFiles()?.filter { it.isDirectory }?.sortedBy { it.name } ?: emptyList()
    }

    Section("Pack 管理（pack-verify / pack-hash）") {
        Field("Pack 根目录", rootText, { rootText = it })
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { scan(File(rootText)) }) { Text("扫描子目录") }
            OutlinedButton(onClick = {
                val dir = FileDialogs.openDirectory("选择 Pack 根目录")
                if (dir != null) {
                    rootText = dir.absolutePath
                    scan(dir)
                }
            }) { Text("选择目录…") }
            OutlinedButton(onClick = {
                val dir = FileDialogs.openDirectory("选择单个 Pack 目录")
                if (dir != null) {
                    selected = dir
                    hashSummary = null
                    report = null
                }
            }) { Text("选择 Pack…") }
        }
        if (packDirs.isEmpty()) {
            Text("未扫描到子目录。Pack 目录需含 nf-pack.json。", style = MaterialTheme.typography.bodySmall)
        }
        for (dir in packDirs) {
            Row(modifier = Modifier.fillMaxWidth()) {
                Text(dir.name, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
                OutlinedButton(onClick = { selected = dir; hashSummary = null; report = null }) { Text("选中") }
            }
        }
    }

    val dir = selected
    Section("选中 Pack") {
        if (dir == null) {
            Text("未选 Pack。", style = MaterialTheme.typography.bodySmall)
        } else {
            KeyValue("path", dir.absolutePath)
            val manifest = File(dir, "nf-pack.json")
            KeyValue("manifest", if (manifest.isFile) "在场" else "缺失（pack-verify 会报 NF-PCK-001）")
            if (manifest.isFile) {
                // 解析在 composable 调用之外完成（try/catch 不能包 composable 调用）
                val info = runCatching {
                    val obj = J.parseObject(manifest.readText(Charsets.UTF_8), "nf-pack/1")
                    "id=" + (J.optString(obj, "id") ?: "-") + " version=" + (J.optString(obj, "version") ?: "-") +
                        " kind=" + (J.optString(obj, "kind") ?: "-") + " items=" + J.optArray(obj, "items").size
                }.getOrElse { "manifest 解析失败：" + (it.message ?: it.javaClass.simpleName) }
                Mono(info)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(enabled = !busy, onClick = {
                    scope.launch {
                        busy = true
                        error = null
                        report = null
                        try {
                            val response = safeCall("pack-verify", buildJsonObject { put("root", dir.absolutePath) })
                            if (response.resultObject() != null) report = ReportModel.parse(response.resultObject()!!)
                            if (!response.ok) error = response.error
                        } finally {
                            busy = false
                        }
                    }
                }) { Text(if (busy) "校验中…" else "core pack-verify") }
                OutlinedButton(enabled = !busy, onClick = {
                    scope.launch {
                        busy = true
                        error = null
                        hashSummary = null
                        try {
                            val response = safeCall("pack-hash", buildJsonObject { put("root", dir.absolutePath) })
                            if (response.ok) {
                                val result = response.resultObject()
                                hashSummary = if (result == null) "无 result" else
                                    "items=" + J.optArray(result, "items").size +
                                        " · tree=" + ((result["hashes"] as? kotlinx.serialization.json.JsonObject)?.get("tree") as? JsonPrimitive)?.content.orEmpty()
                            } else {
                                error = response.error
                            }
                        } finally {
                            busy = false
                        }
                    }
                }) { Text(if (busy) "计算中…" else "core pack-hash") }
            }
            error?.let { ErrorCard(it) }
            hashSummary?.let { Mono(it) }
            report?.let { r ->
                KeyValue("verdict", r.line())
                for (issue in r.issues) Notice(issue.code + " " + (issue.path ?: "-") + "：" + issue.message + "（修复：" + issue.fix + "）")
            }
        }
    }
}
