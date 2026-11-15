package dev.ninfenz.studio.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import dev.ninfenz.studio.core.CoreError
import dev.ninfenz.studio.core.CoreResponse
import dev.ninfenz.studio.model.Project
import dev.ninfenz.studio.model.ProjectModel
import dev.ninfenz.studio.model.ProjectStatus
import dev.ninfenz.studio.ui.Field
import dev.ninfenz.studio.ui.FileDialogs
import dev.ninfenz.studio.ui.KeyValue
import dev.ninfenz.studio.ui.Notice
import dev.ninfenz.studio.ui.Section
import java.io.File

@Composable
fun ProjectManagerScreen() {
    val home = File(System.getProperty("user.home"), "NFStudio")
    var rootText by remember { mutableStateOf(File(home, "projects").absolutePath) }
    var projects by remember { mutableStateOf<List<Project>>(emptyList()) }
    var selected by remember { mutableStateOf<Project?>(null) }
    var target by remember { mutableStateOf(ProjectStatus.AUTHORING) }
    var force by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var message by remember { mutableStateOf<String?>(null) }

    fun scan(dir: File) {
        error = null
        if (!dir.isDirectory) {
            error = CoreResponse.failure("NF-E-004", "目录不存在：" + dir.absolutePath, "先创建目录或换路径", 2).error
            return
        }
        val loaded = mutableListOf<Project>()
        val failures = mutableListOf<String>()
        dir.listFiles { f -> f.isFile && f.name.endsWith(".nfproject.json") }?.sortedBy { it.name }?.forEach { f ->
            try {
                loaded.add(ProjectModel.parse(f.readText(Charsets.UTF_8)))
            } catch (e: Exception) {
                failures.add(f.name + "：" + (e.message ?: e.javaClass.simpleName))
            }
        }
        projects = loaded
        message = "扫描 " + loaded.size + " 个项目" + if (failures.isEmpty()) "" else "；失败 " + failures.size + "：" + failures.joinToString("；")
    }

    Section("项目目录（nf-project/1 引用集）") {
        Field("目录", rootText, { rootText = it })
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { scan(File(rootText)) }) { Text("扫描目录") }
            OutlinedButton(onClick = {
                val dir = FileDialogs.openDirectory("选择项目目录")
                if (dir != null) {
                    rootText = dir.absolutePath
                    scan(dir)
                }
            }) { Text("选择目录…") }
            OutlinedButton(onClick = {
                val file = FileDialogs.openFile("打开 .nfproject.json", "json")
                if (file != null) {
                    try {
                        val project = ProjectModel.parse(file.readText(Charsets.UTF_8))
                        projects = projects + project
                        selected = project
                        message = "已打开 " + file.absolutePath
                        error = null
                    } catch (e: Exception) {
                        error = CoreResponse.failure((e as? dev.ninfenz.studio.core.ModelException)?.code ?: "NF-E-002",
                            "项目解析失败：" + (e.message ?: e.javaClass.simpleName), "按 app/schema/nf-project.schema.json 修正", 1).error
                    }
                }
            }) { Text("打开项目文件…") }
        }
        message?.let { Notice(it) }
        error?.let { dev.ninfenz.studio.ui.ErrorCard(it) }
    }

    Section("已加载项目（" + projects.size + "）") {
        if (projects.isEmpty()) {
            Text("尚无项目。项目只存引用（id/version/digest）+ 状态 + 评审，不内嵌 Pack 内容。", style = MaterialTheme.typography.bodySmall)
        }
        for (project in projects) {
            Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                androidx.compose.foundation.layout.Column(modifier = Modifier.weight(1f)) {
                    Text(project.title + " · " + project.id, style = MaterialTheme.typography.bodyMedium)
                    Text(project.status.wire + " · review=" + project.review.state + " · history " + project.historyCount,
                        style = MaterialTheme.typography.bodySmall)
                }
                OutlinedButton(onClick = { selected = project }) { Text("选为当前") }
            }
        }
    }

    val current = selected
    Section("状态机（CONTRACT §5.10）") {
        if (current == null) {
            Text("先选一个项目。", style = MaterialTheme.typography.bodySmall)
        } else {
            KeyValue("当前", current.id + " · " + current.status.wire)
            KeyValue("评审", current.review.state + " · " + (current.review.reviewer ?: "-"))
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                for (status in ProjectStatus.values()) {
                    FilterChip(
                        selected = target == status,
                        onClick = { target = status },
                        label = { Text(status.wire) }
                    )
                }
            }
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("force（回退/跳跃必须显式）", style = MaterialTheme.typography.bodySmall)
                Switch(checked = force, onCheckedChange = { force = it })
            }
            Button(onClick = {
                val result = ProjectModel.transition(current.status, target, force)
                message = result.message
                if (result.ok) {
                    projects = projects.map { if (it.id == current.id) it.copy(status = result.status) else it }
                    selected = current.copy(status = result.status)
                }
            }) { Text("执行迁移") }
            if (!ProjectModel.reviewOk(current.review)) {
                Notice("评审约束不满足：approved 必须 reviewer + note + subject_digest；rejected 必须 note。")
            }
        }
    }
}
