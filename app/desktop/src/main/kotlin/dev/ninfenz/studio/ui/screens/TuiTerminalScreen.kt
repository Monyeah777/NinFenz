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
import dev.ninfenz.studio.tui.TuiResult
import dev.ninfenz.studio.tui.TuiRunner
import dev.ninfenz.studio.ui.Field
import dev.ninfenz.studio.ui.KeyValue
import dev.ninfenz.studio.ui.Mono
import dev.ninfenz.studio.ui.Notice
import dev.ninfenz.studio.ui.Section
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

@Composable
fun TuiTerminalScreen() {
    val scope = rememberCoroutineScope()
    val repoRoot = remember { TuiRunner.findRepoRoot() }
    val python = remember { TuiRunner.pythonCommand() }
    var commandText by remember { mutableStateOf("python tui/nf.py --selftest") }
    var last by remember { mutableStateOf<TuiResult?>(null) }
    var busy by remember { mutableStateOf(false) }

    Section("TUI 集成（不重写 TUI）") {
        KeyValue("仓库根", repoRoot?.absolutePath ?: "未找到（向上找 tui/nf.py 失败）")
        KeyValue("python", if (python.isEmpty()) "不在 PATH" else python.joinToString(" "))
        if (repoRoot == null) {
            Notice("找不到仓库根：Studio 需在 NinFenz 检出目录内运行，或用 -Duser.dir 指定。")
        }
        if (python.isEmpty()) {
            Notice("找不到 python：安装 Python 3.11+ 并加入 PATH。")
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(enabled = !busy && repoRoot != null && python.isNotEmpty(), onClick = {
                val root = repoRoot ?: return@Button
                scope.launch {
                    busy = true
                    last = withContext(Dispatchers.IO) {
                        TuiRunner.run(python + listOf("tui/nf.py", "--selftest"), root)
                    }
                    busy = false
                }
            }) { Text(if (busy) "运行中…" else "--selftest") }
            Button(enabled = !busy && repoRoot != null && python.isNotEmpty(), onClick = {
                val root = repoRoot ?: return@Button
                scope.launch {
                    busy = true
                    last = withContext(Dispatchers.IO) {
                        TuiRunner.run(python + listOf("tui/nf.py", "--list-actions", "--json"), root)
                    }
                    busy = false
                }
            }) { Text("--list-actions --json") }
        }
    }

    Section("自定义命令") {
        Field("command", commandText, { commandText = it })
        OutlinedButton(enabled = !busy && repoRoot != null, onClick = {
            val root = repoRoot ?: return@OutlinedButton
            val parts = commandText.trim().split(Regex("\\s+")).filter { it.isNotBlank() }
            if (parts.isEmpty()) return@OutlinedButton
            scope.launch {
                busy = true
                last = withContext(Dispatchers.IO) { TuiRunner.run(parts, root) }
                busy = false
            }
        }) { Text(if (busy) "运行中…" else "运行") }
        last?.let { result ->
            KeyValue("exit", result.exit.toString() + if (result.timedOut) "（超时）" else "")
            KeyValue("command", result.commandLine)
            Mono(result.output)
        }
        Text("TUI 是终端/检验面；Studio 只做调用与回放，不复制其逻辑。", style = MaterialTheme.typography.bodySmall)
    }
}
