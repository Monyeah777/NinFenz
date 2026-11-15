package dev.ninfenz.studio.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import dev.ninfenz.studio.print.PrintService
import dev.ninfenz.studio.render.MarkdownRenderer
import dev.ninfenz.studio.ui.FileDialogs
import dev.ninfenz.studio.ui.KeyValue
import dev.ninfenz.studio.ui.Mono
import dev.ninfenz.studio.ui.Notice
import dev.ninfenz.studio.ui.Section
import java.io.File

@Composable
fun PrintScreen() {
    var markdown by remember { mutableStateOf("# 标题\n\n把装配结果粘贴到这里，或从文件加载。\n\n- 要点一\n- 要点二\n") }
    var preview by remember { mutableStateOf<String?>(null) }
    var htmlPath by remember { mutableStateOf<String?>(null) }
    var printMessage by remember { mutableStateOf<String?>(null) }

    Section("Markdown 输入") {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = {
                val file = FileDialogs.openFile("打开 markdown", "md", "markdown", "txt")
                if (file != null) {
                    markdown = file.readText(Charsets.UTF_8)
                    preview = null
                    htmlPath = null
                }
            }) { Text("加载 .md…") }
        }
        OutlinedTextField(
            value = markdown,
            onValueChange = { markdown = it },
            modifier = Modifier.fillMaxWidth().height(240.dp),
            textStyle = MaterialTheme.typography.bodySmall
        )
    }

    Section("打印出口") {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { preview = MarkdownRenderer.toPlainText(markdown) }) { Text("纯文本预览") }
            OutlinedButton(onClick = {
                val file = PrintService.writeHtml(markdown, "nf-studio-print")
                htmlPath = file.absolutePath
            }) { Text("生成 HTML") }
            OutlinedButton(onClick = {
                val text = MarkdownRenderer.toPlainText(markdown)
                val result = PrintService.printPlainText("NF Studio 打印", text)
                printMessage = result.message
            }) { Text("javax.print 打印") }
        }
        htmlPath?.let { path ->
            KeyValue("HTML", path)
            Notice("HTML 可直接用系统浏览器打开后 Ctrl+P 打印（无打印机时也可先存档）。")
        }
        printMessage?.let { Notice(it) }
    }

    preview?.let { text ->
        Section("纯文本预览（打印内容）") {
            Mono(text)
        }
    }
    Text("打印只做渲染出口；产物真源仍是 canonical markdown（不由打印路径改写）。", style = MaterialTheme.typography.bodySmall)
}
