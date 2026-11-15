package dev.ninfenz.studio.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
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
import androidx.compose.ui.unit.dp
import dev.ninfenz.studio.core.CoreError
import dev.ninfenz.studio.core.CoreResponse
import dev.ninfenz.studio.core.J
import dev.ninfenz.studio.model.CcosModel
import dev.ninfenz.studio.model.CcosResult
import dev.ninfenz.studio.ui.ErrorCard
import dev.ninfenz.studio.ui.Field
import dev.ninfenz.studio.ui.FileDialogs
import dev.ninfenz.studio.ui.KeyValue
import dev.ninfenz.studio.ui.Mono
import dev.ninfenz.studio.ui.Notice
import dev.ninfenz.studio.ui.Section
import dev.ninfenz.studio.ui.safeCall
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

@Composable
fun ReviewScreen() {
    val scope = rememberCoroutineScope()
    var result by remember { mutableStateOf<CcosResult?>(null) }
    var rawTask by remember { mutableStateOf<JsonObject?>(null) }
    var reviewer by remember { mutableStateOf("") }
    var note by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var outcome by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    Section("CCOS 结果（ccos-result/1）") {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = {
                val file = FileDialogs.openFile("打开 ccos-result", "json")
                if (file != null) {
                    try {
                        result = CcosModel.parseResult(file.readText(Charsets.UTF_8))
                        error = null
                        outcome = null
                    } catch (e: Exception) {
                        error = CoreResponse.failure((e as? dev.ninfenz.studio.core.ModelException)?.code ?: "NF-CCOS-001",
                            "结果解析失败：" + (e.message ?: e.javaClass.simpleName), "按 schema 修正", 1).error
                    }
                }
            }) { Text("打开 result…") }
            OutlinedButton(onClick = {
                val file = FileDialogs.openFile("打开 ccos-task", "json")
                if (file != null) {
                    try {
                        rawTask = J.parseObject(file.readText(Charsets.UTF_8), "ccos-task/1")
                        error = null
                    } catch (e: Exception) {
                        error = CoreResponse.failure("NF-CCOS-001", "task 解析失败：" + (e.message ?: e.javaClass.simpleName), "按 schema 修正", 1).error
                    }
                }
            }) { Text("打开 task…（回钉必需）") }
        }
        error?.let { ErrorCard(it) }
        val r = result
        if (r == null) {
            Text("尚未加载结果。人审 required 恒 true，不可关闭。", style = MaterialTheme.typography.bodySmall)
        } else {
            KeyValue("task", r.taskId + " · " + r.status)
            KeyValue("task_digest", r.taskDigest.take(24) + "…")
            KeyValue("artifacts/evidence", r.artifacts.size.toString() + " / " + r.evidence.size)
            KeyValue("report", r.reportSummary)
            KeyValue("human_review", r.reviewState + "（required=" + r.reviewRequired + "）")
            for (issue in r.issues) Notice(issue.code + "：" + issue.message)
            for (artifact in r.artifacts) {
                Notice(artifact.name + " · " + artifact.mime + " · " + artifact.bytes + " bytes · sha256=" + artifact.sha256.take(20) + "…")
            }
        }
    }

    val current = result
    Section("人工评审（reviewer + note 必填）") {
        if (current == null) {
            Text("先加载结果。", style = MaterialTheme.typography.bodySmall)
        } else if (current.reviewState != "pending") {
            Notice("已裁决：" + current.reviewState + " · reviewer=" + (current.reviewer ?: "-"))
        } else {
            Field("reviewer", reviewer, { reviewer = it })
            Field("note", note, { note = it }, singleLine = false)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(enabled = !busy, onClick = {
                    val decision = CcosModel.review(current, true, reviewer, note)
                    if (!decision.ok) {
                        outcome = "未提交：" + decision.message
                        return@Button
                    }
                    val reviewed = CcosModel.withReview(current, decision.state, reviewer, note)
                    val taskJson = rawTask
                    if (taskJson == null) {
                        outcome = "缺原始 task JSON：无法回钉 task_digest（先打开 task）"
                        return@Button
                    }
                    scope.launch {
                        busy = true
                        error = null
                        try {
                            val response = safeCall("ccos-import-result", buildJsonObject {
                                put("task", taskJson)
                                put("result", CcosModel.resultJson(reviewed))
                            })
                            if (response.ok) {
                                result = reviewed
                                outcome = "核心已接收：" + (response.result?.toString() ?: "（无 result）")
                            } else {
                                error = response.error
                            }
                        } finally {
                            busy = false
                        }
                    }
                }) { Text(if (busy) "提交中…" else "通过并回传") }
                OutlinedButton(enabled = !busy, onClick = {
                    val decision = CcosModel.review(current, false, reviewer, note)
                    if (!decision.ok) {
                        outcome = "未提交：" + decision.message
                        return@OutlinedButton
                    }
                    val reviewed = CcosModel.withReview(current, decision.state, reviewer, note)
                    val taskJson = rawTask
                    if (taskJson == null) {
                        outcome = "缺原始 task JSON：无法回钉 task_digest（先打开 task）"
                        return@OutlinedButton
                    }
                    scope.launch {
                        busy = true
                        error = null
                        try {
                            val response = safeCall("ccos-import-result", buildJsonObject {
                                put("task", taskJson)
                                put("result", CcosModel.resultJson(reviewed))
                            })
                            if (response.ok) {
                                result = reviewed
                                outcome = "核心已接收：" + (response.result?.toString() ?: "（无 result）")
                            } else {
                                error = response.error
                            }
                        } finally {
                            busy = false
                        }
                    }
                }) { Text("驳回") }
            }
            outcome?.let { Mono(it) }
        }
    }
}
