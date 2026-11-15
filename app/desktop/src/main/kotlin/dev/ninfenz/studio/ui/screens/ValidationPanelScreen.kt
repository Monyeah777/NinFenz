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
import dev.ninfenz.studio.model.ReportModel
import dev.ninfenz.studio.model.ValidateReport
import dev.ninfenz.studio.ui.ErrorCard
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
import java.io.File

@Composable
fun ValidationPanelScreen() {
    val scope = rememberCoroutineScope()
    var report by remember { mutableStateOf<ValidateReport?>(null) }
    var markdownFile by remember { mutableStateOf<File?>(null) }
    var specFile by remember { mutableStateOf<File?>(null) }
    var planFile by remember { mutableStateOf<File?>(null) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var busy by remember { mutableStateOf(false) }

    Section("打开校验报告") {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = {
                val file = FileDialogs.openFile("打开 .nfreport.json", "json")
                if (file != null) {
                    try {
                        report = ReportModel.parse(file.readText(Charsets.UTF_8))
                        error = null
                    } catch (e: Exception) {
                        error = CoreResponse.failure("NF-VAL-003", "报告解析失败：" + (e.message ?: e.javaClass.simpleName), "按 schema 修正", 1).error
                    }
                }
            }) { Text("打开报告…") }
        }
    }

    Section("L1 校验（需要 markdown + spec + plan）") {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { markdownFile = FileDialogs.openFile("打开 markdown", "md", "markdown", "txt") }) {
                Text("markdown：" + (markdownFile?.name ?: "未选"))
            }
            OutlinedButton(onClick = { specFile = FileDialogs.openFile("打开 spec", "json") }) {
                Text("spec：" + (specFile?.name ?: "未选"))
            }
            OutlinedButton(onClick = { planFile = FileDialogs.openFile("打开 plan", "json") }) {
                Text("plan：" + (planFile?.name ?: "未选"))
            }
        }
        Button(enabled = !busy && markdownFile != null && specFile != null && planFile != null, onClick = {
            val md = markdownFile ?: return@Button
            val spec = specFile ?: return@Button
            val plan = planFile ?: return@Button
            scope.launch {
                busy = true
                error = null
                report = null
                try {
                    val specObj: JsonObject = J.parseObject(spec.readText(Charsets.UTF_8), "nf-md-spec/1")
                    val planObj: JsonObject = J.parseObject(plan.readText(Charsets.UTF_8), "nf-assembly-plan/1")
                    val response = safeCall("validate", buildJsonObject {
                        put("markdown", md.readText(Charsets.UTF_8))
                        put("spec", specObj)
                        put("plan", planObj)
                        put("level", "L1")
                    })
                    if (response.resultObject() != null) report = ReportModel.parse(response.resultObject()!!)
                    if (!response.ok) error = response.error
                } finally {
                    busy = false
                }
            }
        }) { Text(if (busy) "校验中…" else "core validate L1") }
        error?.let { ErrorCard(it) }
    }

    val r = report
    Section("报告") {
        if (r == null) {
            Text("尚无报告。L2 不可用时应显式报 NF-VAL-005（exit 4），不降级当通过。", style = MaterialTheme.typography.bodySmall)
        } else {
            KeyValue("verdict", r.line())
            KeyValue("target", r.target.kind + " · " + r.target.ref)
            Mono("digest=" + r.target.digest)
            for (issue in r.issues) {
                Notice("[" + issue.severity + "] " + issue.code + " " + (issue.path ?: "-") + "：" + issue.message + "（修复：" + issue.fix + "）")
            }
        }
    }
}
