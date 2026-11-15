package dev.ninfenz.mobile.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.Button
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import dev.ninfenz.mobile.ui.components.NfCard
import dev.ninfenz.mobile.ui.components.NfEmptyState
import dev.ninfenz.mobile.ui.components.NfErrorCard
import dev.ninfenz.mobile.ui.components.NfSectionHeader
import dev.ninfenz.mobile.ui.components.NfStatusChip
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.theme.NfSpacing
import java.io.File
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/**
 * W3 导入向导：来源（文件/剪贴板/示例/分享）→ 预览（sniff/structure）→ 映射建议（core map-suggest）
 * → 保存草稿 + 映射决策 sidecar。核心失败只显示错误码/fix，不伪造预览。
 */
@Composable
fun ImportScreen(prefill: SharePayload?, store: LibraryStore, onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var doc by remember { mutableStateOf<ImportDoc?>(null) }
    var rawResult by remember { mutableStateOf<JsonObject?>(null) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var notice by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var savedName by remember { mutableStateOf<String?>(null) }
    var prefillNote by remember { mutableStateOf<String?>(null) }
    var acceptedMappings by remember { mutableStateOf<Set<Int>>(emptySet()) }
    var suggestNote by remember { mutableStateOf<String?>(null) }

    suspend fun importFromFile(file: File, sourceKind: String, name: String, mime: String?, size: Long) {
        busy = true
        error = null
        notice = null
        doc = null
        rawResult = null
        savedName = null
        suggestNote = null
        acceptedMappings = emptySet()
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
                    val imported = ImportModel.parse(obj)
                    rawResult = obj
                    doc = imported
                    acceptedMappings = imported.mappings.indices.filter { imported.mappings[it].confidence >= 80 }.toSet()
                    // 映射建议：core map-suggest（可选；失败不阻断预览，只提示）
                    val suggest = safeCall("map-suggest", buildJsonObject { put("import", obj) })
                    if (suggest.ok) {
                        val suggestedObj = suggest.resultObject()
                        if (suggestedObj != null) {
                            doc = ImportModel.parse(suggestedObj)
                            rawResult = suggestedObj
                            acceptedMappings = doc!!.mappings.indices.filter { doc!!.mappings[it].confidence >= 80 }.toSet()
                            suggestNote = "映射建议来自 core map-suggest"
                        }
                    } else {
                        suggestNote = "核心未给出映射建议：" + (suggest.error?.message ?: "未知原因") + "（可手动采纳/跳过）"
                    }
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

    fun importSample() {
        scope.launch {
            try {
                val text = context.assets.open("sample-pack/docs/sample.md").bufferedReader(Charsets.UTF_8).use { it.readText() }
                val file = File(File(context.cacheDir, "imports").apply { mkdirs() }, "sample.md")
                file.writeText(text, Charsets.UTF_8)
                importFromFile(file, "sample", "sample.md", "text/markdown", text.toByteArray(Charsets.UTF_8).size.toLong())
            } catch (t: Throwable) {
                error = CoreResponse.failure("NF-E-004", "读取示例内容失败：" + (t.message ?: t.javaClass.simpleName), "检查 APK assets/sample-pack/docs/sample.md", 2).error
            }
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

    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = "导入", onBack = onBack)
        LazyColumn(
            contentPadding = androidx.compose.foundation.layout.PaddingValues(NfSpacing.page),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
        ) {
            item {
                NfCard {
                    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        Text("选择来源", style = MaterialTheme.typography.titleLarge)
                        Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                            Button(onClick = { filePicker.launch(arrayOf("*/*")) }, enabled = !busy) { Text("选择文件") }
                            OutlinedButton(onClick = { importClipboard() }, enabled = !busy) { Text("剪贴板") }
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                            OutlinedButton(onClick = { importSample() }, enabled = !busy) { Text("示例内容") }
                            if (prefillNote != null) {
                                Text("已接收分享载荷", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
                            }
                        }
                        if (prefillNote != null) {
                            Text(prefillNote!!, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Text(
                            "导入由核心产出 nf-import/1；低置信（<60）不自动入库，映射建议逐条给出 confidence。",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }
            if (busy) {
                item { LinearProgressIndicator(modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page)) }
                item { Text("正在调用核心 import…", style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
            }
            if (error != null) {
                item { NfErrorCard(error!!.code, error!!.message, error!!.fix, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
            }
            notice?.let { message ->
                item { Text(message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
            }

            val current = doc
            if (current == null && error == null && !busy) {
                item {
                    NfEmptyState(
                        icon = Icons.Filled.Add,
                        title = "还没有导入内容",
                        message = "从文件、剪贴板或示例内容开始；分享接收也会走这里。",
                        actionLabel = "选择文件",
                        onAction = { filePicker.launch(arrayOf("*/*")) },
                        secondaryLabel = "示例内容",
                        onSecondary = { importSample() }
                    )
                }
            }
            if (current != null) {
                item { NfSectionHeader("预览") }
                item {
                    NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                        Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                            Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s), verticalAlignment = Alignment.CenterVertically) {
                                NfStatusChip(current.format + " · " + current.confidence + "%")
                                if (current.lowConfidence) NfStatusChip("低置信", MaterialTheme.colorScheme.error)
                                NfStatusChip(current.source.kind)
                            }
                            Text("来源：" + current.source.name, style = MaterialTheme.typography.bodySmall)
                            Text(
                                "结构：标题 " + current.structure.headings.size + " · 段落 " + current.structure.paragraphs +
                                    " · 代码块 " + current.structure.codeBlocks.size + " · 表格 " + current.structure.tables.size,
                                style = MaterialTheme.typography.bodySmall
                            )
                            current.textDigest?.let { Text("digest：" + it.take(16) + "…", style = MaterialTheme.typography.bodySmall) }
                            for (note in current.reviewNotes()) {
                                Text(note, style = MaterialTheme.typography.bodySmall, color = if (current.lowConfidence) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
                item { NfSectionHeader("映射建议（" + current.mappings.size + " 条）") }
                if (current.mappings.isEmpty()) {
                    item { Text("无映射候选（NF-MAP-001）：内容会归入素材/未分类。", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
                } else {
                    item {
                        Row(modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Text("已采纳 " + acceptedMappings.size + "/" + current.mappings.size, style = MaterialTheme.typography.bodySmall)
                            TextButton(onClick = {
                                acceptedMappings = if (acceptedMappings.size == current.mappings.size) emptySet() else current.mappings.indices.toSet()
                            }) { Text(if (acceptedMappings.size == current.mappings.size) "全部取消" else "全部采纳") }
                        }
                    }
                    items(current.mappings.size) { index ->
                        val mapping = current.mappings[index]
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page, vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    mapping.fromKind + "[" + mapping.fromIndex + "] → " + mapping.toKind + " " + mapping.toId,
                                    style = MaterialTheme.typography.bodyMedium
                                )
                                Text(
                                    "confidence " + mapping.confidence + " · " + mapping.rationale,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                            Switch(
                                checked = index in acceptedMappings,
                                onCheckedChange = { checked ->
                                    acceptedMappings = if (checked) acceptedMappings + index else acceptedMappings - index
                                }
                            )
                        }
                    }
                }
                if (current.unmapped.isNotEmpty()) {
                    item { Text("未映射：" + current.unmapped.joinToString("；"), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
                }
                suggestNote?.let { message ->
                    item { Text(message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
                }
                item { NfSectionHeader("草稿") }
                item {
                    if (savedName == null) {
                        Button(
                            onClick = {
                                val raw = rawResult
                                if (raw == null) {
                                    error = CoreResponse.failure("NF-E-004", "原始响应未保留，拒绝以重序列化结果冒充核心产物", "重新导入", 2).error
                                } else {
                                    val file = store.saveDraft(current.source.name, raw.toString())
                                    val mappingJson = buildJsonObject {
                                        put("accepted", JsonArray(acceptedMappings.sorted().map { JsonPrimitive(it) }))
                                        put("unmapped", JsonArray(current.unmapped.map { JsonPrimitive(it) }))
                                    }.toString()
                                    store.saveDraft(current.source.name + ".mapping", mappingJson)
                                    savedName = file.name
                                }
                            },
                            modifier = Modifier.padding(horizontal = NfSpacing.page)
                        ) { Text("保存导入草稿 + 映射决策") }
                    } else {
                        NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                                Text("已保存草稿：" + savedName, style = MaterialTheme.typography.titleMedium)
                                Text("草稿保存在应用私有目录，未写入项目；W4 再接入「草稿 → 项目」的转换。", style = MaterialTheme.typography.bodySmall)
                                Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                                    Button(onClick = onBack) { Text("完成") }
                                    TextButton(onClick = {
                                        doc = null
                                        rawResult = null
                                        savedName = null
                                        acceptedMappings = emptySet()
                                        error = null
                                        suggestNote = null
                                    }) { Text("再导入一个") }
                                }
                            }
                        }
                    }
                }
                item {
                    if (current.text != null || current.textPath != null) {
                        Text(
                            (current.text ?: current.textPath ?: "").take(400),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(horizontal = NfSpacing.page)
                        )
                    }
                }
            }
        }
    }
}
