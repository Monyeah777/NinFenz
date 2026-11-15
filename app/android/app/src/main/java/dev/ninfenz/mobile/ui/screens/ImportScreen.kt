package dev.ninfenz.mobile.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.data.LibraryStore
import dev.ninfenz.mobile.model.ImportDoc
import dev.ninfenz.mobile.model.ImportModel
import dev.ninfenz.mobile.share.SharePayload
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
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.io.File

@Composable
fun ImportScreen(prefill: SharePayload?, store: LibraryStore, onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var doc by remember { mutableStateOf<ImportDoc?>(null) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var busy by remember { mutableStateOf(false) }
    var savedPath by remember { mutableStateOf<String?>(null) }
    var rawResult by remember { mutableStateOf<String?>(null) }
    var prefillNote by remember { mutableStateOf<String?>(null) }
    var acceptedMappings by remember { mutableStateOf<Set<Int>>(emptySet()) }

    suspend fun importFromFile(file: File, sourceKind: String, name: String, mime: String?, size: Long) {
        busy = true
        error = null
        doc = null
        savedPath = null
        rawResult = null
        val payload = buildJsonObject {
            put("file", file.absolutePath)
            put("source", buildJsonObject {
                put("kind", sourceKind)
                put("name", name)
                if (mime != null) put("mime", mime)
                if (size >= 0) put("size", size)
            })
        }
        val response: CoreResponse = safeCall("import", payload)
        if (response.ok) {
            val obj = response.resultObject()
            if (obj == null) {
                error = CoreResponse.failure("NF-E-002", "核心 import 响应缺 result", "检查核心版本", 2).error
            } else {
                try {
                    doc = ImportModel.parse(obj)
                    rawResult = response.result?.toString()
                } catch (e: Exception) {
                    error = CoreResponse.failure(
                        (e as? dev.ninfenz.mobile.core.ModelException)?.code ?: "NF-E-002",
                        "nf-import/1 解析失败：" + (e.message ?: e.javaClass.simpleName),
                        "检查核心输出是否满足 app/schema/nf-import.schema.json",
                        1
                    ).error
                }
            }
        } else {
            error = response.error
        }
        busy = false
    }

    fun importClipboard() {
        val manager = context.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as? android.content.ClipboardManager
        val text = manager?.primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(context)?.toString()
        if (text.isNullOrBlank()) {
            error = CoreResponse.failure("NF-E-003", "剪贴板为空", "先复制一段文本", 2).error
            return
        }
        scope.launch {
            val file = File(File(context.cacheDir, "imports").apply { mkdirs() }, "clipboard.md")
            file.writeText(text, Charsets.UTF_8)
            importFromFile(file, "clipboard", "clipboard.md", "text/plain", text.toByteArray(Charsets.UTF_8).size.toLong())
        }
    }

    fun importShare(payload: SharePayload) {
        scope.launch {
            val item = payload.items.firstOrNull()
            if (item == null) {
                error = CoreResponse.failure("NF-IMP-001", "分享载荷无可导入条目", "换一种分享方式", 3).error
                return@launch
            }
            if (item.text != null) {
                val file = File(File(context.cacheDir, "imports").apply { mkdirs() }, "shared-text.md")
                file.writeText(item.text, Charsets.UTF_8)
                importFromFile(file, "share", "shared-text.md", item.mime ?: "text/plain", item.text.toByteArray(Charsets.UTF_8).size.toLong())
            } else if (item.uri != null) {
                try {
                    val uri = Uri.parse(item.uri)
                    val meta = FileAccess.meta(context, uri)
                    val file = FileAccess.copyToCache(context, uri, meta.name)
                    importFromFile(file, "share", meta.name, meta.mime ?: item.mime, meta.size)
                } catch (e: Exception) {
                    error = CoreResponse.failure("NF-E-004", "读取分享 URI 失败：" + (e.message ?: e.javaClass.simpleName), "确认授权后重试", 2).error
                }
            }
        }
    }

    LaunchedEffect(prefill) {
        if (prefill != null) {
            prefillNote = "来自分享：" + prefill.summary()
            importShare(prefill)
        }
    }

    val filePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) {
            scope.launch {
                try {
                    val meta = FileAccess.meta(context, uri)
                    val file = FileAccess.copyToCache(context, uri, meta.name)
                    importFromFile(file, "saf", meta.name, meta.mime, meta.size)
                } catch (e: Exception) {
                    error = CoreResponse.failure("NF-E-004", "读取文件失败：" + (e.message ?: e.javaClass.simpleName), "确认授权后重试", 2).error
                }
            }
        }
    }

    NfScaffold(title = "Import · 导入预览", onBack = onBack) {
        CardBox(title = "来源") {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { filePicker.launch(arrayOf("*/*")) }, enabled = !busy) { Text("选择文件(SAF)") }
                OutlinedButton(onClick = { importClipboard() }, enabled = !busy) { Text("粘贴剪贴板") }
            }
            if (busy) Notice("调用核心 import …（未就绪会报 NF-E-005，不会显示假结果）", Tone.WARN)
            prefillNote?.let { Notice(it, Tone.INFO) }
            Notice(
                "导入由核心产出 nf-import/1；低置信（<60）不自动入库，映射建议逐条带 confidence+rationale。",
                Tone.INFO
            )
        }

        error?.let { ErrorNotice(it) }

        val current = doc
        if (current == null && error == null && !busy) {
            EmptyState("尚未导入。分享/SAF/剪贴板三种入口最终都走核心 import。")
        }
        if (current != null) {
            CardBox(title = "嗅探结果") {
                KeyValue("format", current.format + "（置信度 " + current.confidence + "）")
                KeyValue("source", current.source.kind + " · " + current.source.name)
                KeyValue("mime/size", (current.source.mime ?: "-") + " / " + (current.source.size ?: -1))
                KeyValue("text_digest", current.textDigest ?: "（无）")
                KeyValue("结构", "标题 " + current.structure.headings.size + " · 段落 " + current.structure.paragraphs +
                    " · 代码块 " + current.structure.codeBlocks.size + " · 表格 " + current.structure.tables.size)
                if (current.candidates.size > 1) {
                    KeyValue("候选", current.candidates.joinToString { it.format + ":" + it.confidence })
                }
                for (note in current.reviewNotes()) Notice(note, if (current.lowConfidence) Tone.WARN else Tone.INFO)
            }

            CardBox(title = "映射建议（" + current.mappings.size + " 条）") {
                if (current.mappings.isEmpty()) {
                    EmptyState("无映射候选（NF-MAP-001）：归入素材/未分类。")
                } else {
                    current.mappings.forEachIndexed { index, mapping ->
                        Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            androidx.compose.foundation.layout.Column(modifier = Modifier.weight(1f)) {
                                Text(mapping.fromKind + "[" + mapping.fromIndex + "] -> " + mapping.toKind + " " + mapping.toId,
                                    style = MaterialTheme.typography.bodyMedium)
                                Text("confidence " + mapping.confidence + " · " + mapping.rationale,
                                    style = MaterialTheme.typography.bodySmall)
                            }
                            Switch(
                                checked = index in acceptedMappings,
                                onCheckedChange = { checked ->
                                    acceptedMappings = if (checked) acceptedMappings + index else acceptedMappings - index
                                }
                            )
                        }
                    }
                    Text("已采纳 " + acceptedMappings.size + "/" + current.mappings.size + "（决策随草稿一起落盘）",
                        style = MaterialTheme.typography.bodySmall)
                }
                if (current.unmapped.isNotEmpty()) {
                    Notice("未映射：" + current.unmapped.joinToString("；"), Tone.WARN)
                }
            }

            CardBox(title = "原文（截断预览）") {
                MonoText((current.text ?: current.textPath ?: "（无原文，仅 digest）").take(800))
            }

            CardBox(title = "草稿") {
                Button(onClick = {
                    // 保存核心 result 的 JSON（草稿；不做摘要声明，避免冒充核心 canonical 产物）
                    val raw = rawResult
                    if (raw != null) {
                        val file = store.saveDraft(current.source.name, raw)
                        val mappingJson = buildJsonObject {
                            put("accepted", kotlinx.serialization.json.JsonArray(
                                acceptedMappings.sorted().map { kotlinx.serialization.json.JsonPrimitive(it) }
                            ))
                            put("unmapped", kotlinx.serialization.json.JsonArray(
                                current.unmapped.map { kotlinx.serialization.json.JsonPrimitive(it) }
                            ))
                        }.toString()
                        store.saveDraft(current.source.name + ".mapping", mappingJson)
                        savedPath = file.absolutePath
                    } else {
                        error = CoreResponse.failure("NF-E-004", "原始响应未保留，拒绝以重序列化结果冒充核心产物", "重新导入", 2).error
                    }
                }) { Text("保存导入草稿 + 映射决策") }
                savedPath?.let { Notice("已保存：" + it, Tone.INFO) }
            }
        }
    }
}
