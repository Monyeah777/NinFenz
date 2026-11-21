package dev.ninfenz.mobile.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.net.toUri
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.DraftLibrary
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.DocxImporter
import dev.ninfenz.mobile.data.EpubImporter
import dev.ninfenz.mobile.data.HtmlImporter
import dev.ninfenz.mobile.data.ProjectPackageImporter
import dev.ninfenz.mobile.data.TextEncoding
import dev.ninfenz.mobile.data.ShareQueueStore
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.data.ImportDraftStore
import dev.ninfenz.mobile.data.ImportHistoryStore
import dev.ninfenz.mobile.data.PromptSampleStore
import dev.ninfenz.mobile.data.TemplateCandidateStore
import dev.ninfenz.mobile.data.TemplatePackageBuilder
import dev.ninfenz.mobile.data.TemplatePackageImporter
import dev.ninfenz.mobile.data.LibraryStore
import dev.ninfenz.mobile.model.ImportDoc
import dev.ninfenz.mobile.model.MarkdownBlocks
import dev.ninfenz.mobile.model.MarkdownSlicer
import dev.ninfenz.mobile.model.PromptPack
import dev.ninfenz.mobile.model.PromptProfile
import dev.ninfenz.mobile.model.SpecModel
import dev.ninfenz.mobile.model.TemplateCandidate
import dev.ninfenz.mobile.model.CsvTable
import dev.ninfenz.mobile.model.ImportModel
import dev.ninfenz.mobile.share.SharePayload
import dev.ninfenz.mobile.share.ShareExporter
import dev.ninfenz.mobile.share.SharedItem
import dev.ninfenz.mobile.ui.components.NfCard
import dev.ninfenz.mobile.ui.components.NfEmptyState
import dev.ninfenz.mobile.ui.components.NfErrorCard
import dev.ninfenz.mobile.ui.components.MarkdownPreview
import dev.ninfenz.mobile.ui.components.NfStepStrip
import dev.ninfenz.mobile.ui.components.NfSectionHeader
import dev.ninfenz.mobile.ui.components.NfStatusChip
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.theme.NfSpacing
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/**
 * W3 导入向导：来源（文件/剪贴板/示例/分享）→ 预览（sniff/structure）→ 映射建议（core map-suggest）
 * → 保存草稿 + 映射决策 sidecar。核心失败只显示错误码/fix，不伪造预览。
 */
@Composable
fun ImportScreen(
    prefill: SharePayload?,
    store: LibraryStore,
    onBack: () -> Unit,
    onPrefillConsumed: () -> Unit = {},
    autoClipboard: Boolean = false,
    onAutoClipboardConsumed: () -> Unit = {},
    packs: List<PackEntry> = emptyList(),
    onCreateProjectFromDraft: (PackEntry, String, File) -> Unit = { _, _, _ -> },
    onQuickProjectFromDraft: (PackEntry, String, File) -> Unit = onCreateProjectFromDraft,
    onCreateProjectFromTemplate: (PackEntry, String, String, String) -> Unit = { _, _, _, _ -> },
    onProjectImported: (String, String, String) -> Unit = { _, _, _ -> },
    onBundleImported: (Int) -> Unit = {}
) {
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val scope = rememberCoroutineScope()
    var doc by remember { mutableStateOf<ImportDoc?>(null) }
    var rawResult by remember { mutableStateOf<JsonObject?>(null) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var notice by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var savedName by remember { mutableStateOf<String?>(null) }
    var prefillNote by remember { mutableStateOf<String?>(null) }
    val shareQueueStore = remember { ShareQueueStore(context.filesDir) }
    val savedQueue = remember { shareQueueStore.load() }
    var shareQueue by remember { mutableStateOf(savedQueue?.items ?: emptyList<SharedItem>()) }
    var shareCursor by remember { mutableIntStateOf(savedQueue?.cursor ?: 0) }
    LaunchedEffect(shareQueue, shareCursor) {
        if (shareQueue.isEmpty()) shareQueueStore.clear() else shareQueueStore.save(shareQueue, shareCursor)
    }
    var acceptedMappings by remember { mutableStateOf<Set<Int>>(emptySet()) }
    var suggestNote by remember { mutableStateOf<String?>(null) }
    val importHistory = remember { ImportHistoryStore(context.filesDir) }
    val importDraftStore = remember { ImportDraftStore(context.filesDir) }
    val templateStore = remember { TemplateCandidateStore(context.filesDir) }
    var savedTemplates by remember { mutableStateOf(templateStore.list()) }
    val sampleStore = remember { PromptSampleStore(context.filesDir) }
    var savedSamples by remember { mutableStateOf(sampleStore.list()) }
    var pendingDeleteSample by remember { mutableStateOf<File?>(null) }
    var pendingTemplateUse by remember { mutableStateOf<File?>(null) }
    var previewTemplate by remember { mutableStateOf<File?>(null) }
    var showAllTemplates by remember { mutableStateOf(false) }
    var showAllSamples by remember { mutableStateOf(false) }
    var showClearSamples by remember { mutableStateOf(false) }
    var showClearTemplates by remember { mutableStateOf(false) }
    var pendingDeleteTemplate by remember { mutableStateOf<File?>(null) }
    var importPreviewText by remember { mutableStateOf<String?>(null) }
    var promptProfile by remember { mutableStateOf(PromptProfile.GENERIC) }
    var drafts by remember { mutableStateOf(DraftLibrary.list(context.filesDir)) }
    var recentImports by remember { mutableStateOf(importHistory.recent()) }
    var pendingDeleteDraft by remember { mutableStateOf<File?>(null) }
    var convertDraft by remember { mutableStateOf<File?>(null) }
    var renameDraft by remember { mutableStateOf<File?>(null) }
    var renameDraftText by remember { mutableStateOf("") }
    var duplicatePrompt by remember { mutableStateOf<DuplicatePrompt?>(null) }
    var showClearConfirm by remember { mutableStateOf(false) }
    var cleared by remember { mutableStateOf<ImportClearSnapshot?>(null) }
    LaunchedEffect(cleared) {
        if (cleared != null) {
            delay(5000)
            cleared = null
        }
    }
    fun clearCurrentImport() {
        cleared = ImportClearSnapshot(
            doc = doc,
            rawResult = rawResult,
            savedName = savedName,
            acceptedMappings = acceptedMappings,
            prefillNote = prefillNote,
            notice = notice,
            suggestNote = suggestNote,
            shareQueue = shareQueue,
            shareCursor = shareCursor
        )
        doc = null
        rawResult = null
        savedName = null
        acceptedMappings = emptySet()
        prefillNote = null
        notice = null
        suggestNote = null
        error = null
        importDraftStore.clear()
        shareQueue = emptyList()
        shareCursor = 0
        showClearConfirm = false
    }

    suspend fun importFromFile(file: File, sourceKind: String, name: String, mime: String?, size: Long) {
        val isZip = file.name.endsWith(".zip", ignoreCase = true) || (mime ?: "").contains("zip", ignoreCase = true)
        if (isZip && dev.ninfenz.mobile.data.ProjectBundleImporter.hasBundle(file)) {
            busy = true
            error = null
            notice = null
            try {
                val imported = withContext(Dispatchers.IO) { dev.ninfenz.mobile.data.ProjectBundleImporter.import(context.filesDir, file) }
                notice = context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.import_bundle_done, imported.count, imported.count)
                onBundleImported(imported.count)
            } catch (t: Throwable) {
                error = CoreResponse.failure(
                    "NF-PRJ-001",
                    context.getString(dev.ninfenz.mobile.R.string.import_project_failed, t.message ?: t.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.import_project_failed_fix),
                    2
                ).error
            } finally {
                file.delete()
                busy = false
            }
            return
        }
        if (isZip && TemplatePackageImporter.hasTemplateJson(file)) {
            busy = true
            error = null
            notice = null
            var importedDir: File? = null
            try {
                val imported = withContext(Dispatchers.IO) { TemplatePackageImporter.inspect(file, context.cacheDir) }
                importedDir = imported.dir
                val hash = safeCall("pack-hash", buildJsonObject { put("root", imported.dir.absolutePath) })
                val hashes = hash.resultObject()?.get("hashes") as? kotlinx.serialization.json.JsonObject
                val tree = hashes?.get("tree")?.jsonPrimitive?.content
                val count = hashes?.get("count")?.jsonPrimitive?.content?.toIntOrNull()
                val pack = if (imported.packId != null) {
                    packs.firstOrNull {
                        it.id == imported.packId && (imported.packVersion == null || it.version == imported.packVersion)
                    }
                } else {
                    packs.firstOrNull()
                }
                if (!hash.ok || tree != imported.tree || count != imported.count) {
                    error = hash.error ?: CoreResponse.failure("NF-PCK-003", context.getString(dev.ninfenz.mobile.R.string.import_template_tree_mismatch), context.getString(dev.ninfenz.mobile.R.string.import_template_tree_mismatch_fix), 2).error
                } else {
                    val specObj = kotlinx.serialization.json.Json.parseToJsonElement(imported.specText).jsonObject
                    val specCheck = safeCall("spec-validate", buildJsonObject { put("spec", specObj) })
                    if (!specCheck.ok) {
                        error = specCheck.error
                    } else if (pack == null) {
                        error = CoreResponse.failure(
                            "NF-PCK-002",
                            if (imported.packId != null) {
                                context.getString(dev.ninfenz.mobile.R.string.import_template_pack_missing, imported.packId, imported.packVersion.orEmpty())
                            } else {
                                context.getString(dev.ninfenz.mobile.R.string.import_template_need_pack)
                            },
                            context.getString(dev.ninfenz.mobile.R.string.import_template_need_pack),
                            2
                        ).error
                    } else {
                        onCreateProjectFromTemplate(pack, imported.title, imported.specText, imported.templateText)
                    }
                }
            } catch (t: Throwable) {
                error = CoreResponse.failure(
                    "NF-E-005",
                    context.getString(dev.ninfenz.mobile.R.string.import_template_import) + ": " + (t.message ?: t.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.import_parse_failed_fix),
                    2
                ).error
            } finally {
                importedDir?.deleteRecursively()
            }
            file.delete()
            busy = false
            return
        }
        if (isZip && ProjectPackageImporter.hasProjectJson(file)) {
            try {
                val imported = withContext(Dispatchers.IO) { ProjectPackageImporter.import(context.filesDir, file) }
                notice = context.resources.getQuantityString(
                    dev.ninfenz.mobile.R.plurals.import_project_package_done,
                    imported.dataFiles,
                    imported.id,
                    imported.dataFiles
                )
                file.delete()
                onProjectImported(imported.id, imported.packId, imported.packVersion)
            } catch (t: Throwable) {
                error = CoreResponse.failure(
                    "NF-PRJ-001",
                    context.getString(dev.ninfenz.mobile.R.string.import_project_failed, t.message ?: t.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.import_project_failed_fix),
                    2
                ).error
            }
            return
        }
        busy = true
        error = null
        notice = null
        doc = null
        rawResult = null
        savedName = null
        suggestNote = null
        acceptedMappings = emptySet()
        val isPdf = name.endsWith(".pdf", true) || (mime ?: "").contains("pdf", ignoreCase = true)
        val isCsv = name.endsWith(".csv", true) || name.endsWith(".tsv", true) || (mime ?: "").contains("csv", ignoreCase = true) || (mime ?: "").contains("tab-separated", ignoreCase = true)
        val isImage = (mime ?: "").startsWith("image/") || listOf(".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp").any { name.endsWith(it, true) }
        val isDocx = name.endsWith(".docx", true) || mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        val isEpub = name.endsWith(".epub", true) || mime == "application/epub+zip" ||
            ((name.endsWith(".zip", true) || mime == "application/zip") && EpubImporter.isEpub(file))
        val isHtml = !isEpub && !isDocx && !isPdf && (name.endsWith(".html", true) || name.endsWith(".htm", true) || mime == "text/html")
        val isText = !isEpub && !isDocx && !isHtml && !isPdf && !isImage && !isCsv && (name.endsWith(".txt", true) || name.endsWith(".md", true) ||
            name.endsWith(".markdown", true) || mime?.startsWith("text/") == true)
        val sourceFile = when {
            isCsv -> {
                val markdown = CsvTable.toMarkdown(TextEncoding.decodeText(file.readBytes()))
                File(file.parentFile, "csv-import-" + System.nanoTime() + ".md").apply { writeText(markdown, Charsets.UTF_8) }
            }
            isImage -> {
                val extraction = runCatching { dev.ninfenz.mobile.data.ImageOcrImporter.extract(context, file) }
                if (extraction.isFailure) {
                    error = CoreResponse.failure(
                        "NF-IMP-004",
                        context.getString(dev.ninfenz.mobile.R.string.import_image_ocr_failed, extraction.exceptionOrNull()?.message ?: "unknown"),
                        context.getString(dev.ninfenz.mobile.R.string.import_image_ocr_required_fix),
                        3
                    ).error
                    return
                }
                var markdown = extraction.getOrNull()?.takeIf { it.isNotBlank() }
                if (markdown == null) {
                    val ocr = runCatching { dev.ninfenz.mobile.data.PdfOcrImporter.extract(context, file) }
                    if (ocr.isFailure) {
                        error = CoreResponse.failure(
                            "NF-IMP-004",
                            context.getString(dev.ninfenz.mobile.R.string.import_pdf_ocr_failed, ocr.exceptionOrNull()?.message ?: "unknown"),
                            context.getString(dev.ninfenz.mobile.R.string.import_pdf_unsupported_fix),
                            3
                        ).error
                        return
                    }
                    markdown = ocr.getOrNull()?.text?.takeIf { it.isNotBlank() }
                    if (ocr.getOrNull()?.truncated == true) {
                        notice = context.getString(dev.ninfenz.mobile.R.string.import_pdf_ocr_truncated)
                    }
                }
                if (markdown == null) {
                    error = CoreResponse.failure(
                        "NF-IMP-004",
                        context.getString(dev.ninfenz.mobile.R.string.import_image_ocr_required),
                        context.getString(dev.ninfenz.mobile.R.string.import_image_ocr_required_fix),
                        3
                    ).error
                    return
                }
                File(file.parentFile, "image-ocr-" + System.nanoTime() + ".md").apply { writeText(markdown, Charsets.UTF_8) }
            }
            isPdf -> {
                val extraction = runCatching { dev.ninfenz.mobile.data.PdfTextImporter.extract(context, file) }
                if (extraction.isFailure) {
                    error = CoreResponse.failure(
                        "NF-IMP-004",
                        context.getString(dev.ninfenz.mobile.R.string.import_pdf_failed, extraction.exceptionOrNull()?.message ?: "unknown"),
                        context.getString(dev.ninfenz.mobile.R.string.import_pdf_unsupported_fix),
                        3
                    ).error
                    return
                }
                val markdown = extraction.getOrNull()?.takeIf { it.isNotBlank() }
                if (markdown == null) {
                    error = CoreResponse.failure(
                        "NF-IMP-004",
                        context.getString(dev.ninfenz.mobile.R.string.import_pdf_no_text),
                        context.getString(dev.ninfenz.mobile.R.string.import_pdf_unsupported_fix),
                        3
                    ).error
                    return
                }
                File(file.parentFile, "pdf-import-" + System.nanoTime() + ".md").apply { writeText(markdown, Charsets.UTF_8) }
            }
            isDocx -> {
                val markdown = runCatching { DocxImporter.extract(file) }.getOrNull()?.takeIf { it.isNotBlank() }
                if (markdown == null) {
                    error = CoreResponse.failure(
                        "NF-IMP-008",
                        context.getString(dev.ninfenz.mobile.R.string.import_docx_failed),
                        context.getString(dev.ninfenz.mobile.R.string.import_docx_failed_fix),
                        2
                    ).error
                    return
                }
                File(file.parentFile, "docx-import-" + System.nanoTime() + ".md").apply { writeText(markdown, Charsets.UTF_8) }
            }
            isEpub -> {
                val markdown = runCatching { EpubImporter.extract(file) }.getOrNull()?.takeIf { it.isNotBlank() }
                if (markdown == null) {
                    error = CoreResponse.failure(
                        "NF-IMP-007",
                        context.getString(dev.ninfenz.mobile.R.string.import_epub_failed),
                        context.getString(dev.ninfenz.mobile.R.string.import_epub_failed_fix),
                        2
                    ).error
                    return
                }
                File(file.parentFile, "epub-import-" + System.nanoTime() + ".md").apply { writeText(markdown, Charsets.UTF_8) }
            }
            isHtml -> {
                val raw = HtmlImporter.decode(file.readBytes())
                val markdown = HtmlImporter.toMarkdown(raw)
                File(file.parentFile, "html-import-" + System.nanoTime() + ".md").apply { writeText(markdown, Charsets.UTF_8) }
            }
            isText -> TextEncoding.toUtf8(file) ?: file
            else -> file
        }
        val payload = buildJsonObject {
            put("file", sourceFile.absolutePath)
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
                error = CoreResponse.failure(
                    "NF-E-002",
                    context.getString(dev.ninfenz.mobile.R.string.import_core_missing_result),
                    context.getString(dev.ninfenz.mobile.R.string.import_core_missing_result_fix),
                    2
                ).error
            } else {
                try {
                    val imported = ImportModel.parse(obj)
                    val digest = imported.source.sha256 ?: imported.textDigest
                    if (!digest.isNullOrBlank()) {
                        val previous = importHistory.find(digest)
                        if (previous != null) {
                            notice = context.getString(dev.ninfenz.mobile.R.string.import_duplicate_notice, previous.name, digest.take(12))
                            duplicatePrompt = DuplicatePrompt(digest, DraftLibrary.findByDigest(context.filesDir, digest))
                        }
                        importHistory.record(digest, imported.source.name)
                        recentImports = importHistory.recent()
                    }
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
                            suggestNote = context.getString(dev.ninfenz.mobile.R.string.import_suggest_done)
                        }
                    } else {
                        suggestNote = context.getString(
                            dev.ninfenz.mobile.R.string.import_no_suggestion,
                            suggest.error?.message ?: context.getString(dev.ninfenz.mobile.R.string.unknown_reason)
                        )
                    }
                } catch (e: Exception) {
                    error = CoreResponse.failure(
                        (e as? dev.ninfenz.mobile.core.ModelException)?.code ?: "NF-E-002",
                        context.getString(dev.ninfenz.mobile.R.string.import_parse_failed, e.message ?: e.javaClass.simpleName),
                        context.getString(dev.ninfenz.mobile.R.string.import_parse_failed_fix),
                        1
                    ).error
                }
            }
        } else {
            error = response.error
        }
        rawResult?.let { importDraftStore.save(it.toString()) }
        if (sourceFile != file) sourceFile.delete()
        busy = false
    }

    fun exportTemplatePackage(file: File) {
        val pack = packs.firstOrNull()
        if (pack == null) {
            error = CoreResponse.failure(
                "NF-PCK-002",
                context.getString(dev.ninfenz.mobile.R.string.import_template_export),
                context.getString(dev.ninfenz.mobile.R.string.import_template_export),
                2
            ).error
            return
        }
        val spec = runCatching {
            kotlinx.serialization.json.Json.parseToJsonElement(file.readText(Charsets.UTF_8)).jsonObject
        }.getOrNull()
        if (spec == null) return
        scope.launch {
            busy = true
            try {
                val prepared = TemplatePackageBuilder.prepare(context.cacheDir, pack, spec, templateStore.titleOf(file))
                val response = safeCall("pack-hash", buildJsonObject { put("root", prepared.dir.absolutePath) })
                val hashes = response.resultObject()?.get("hashes") as? kotlinx.serialization.json.JsonObject
                val tree = hashes?.get("tree")?.jsonPrimitive?.content
                val count = hashes?.get("count")?.jsonPrimitive?.content?.toIntOrNull()
                if (!response.ok || tree == null || count == null) {
                    error = response.error ?: CoreResponse.failure("NF-PCK-003", context.getString(dev.ninfenz.mobile.R.string.import_pack_hash_missing), context.getString(dev.ninfenz.mobile.R.string.import_pack_hash_missing_fix), 2).error
                } else {
                    val zip = TemplatePackageBuilder.finalize(prepared, tree, count, File(context.cacheDir, "template-export"))
                    val intent = ShareExporter.shareFileIntent(context, zip, "application/zip", templateStore.titleOf(file))
                    ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.import_template_export))
                }
            } catch (t: Throwable) {
                error = CoreResponse.failure(
                    "NF-E-005",
                    context.getString(dev.ninfenz.mobile.R.string.import_template_export) + ": " + (t.message ?: t.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.import_parse_failed_fix),
                    2
                ).error
            }
            busy = false
        }
    }

    fun importCsv() {
        val manager = context.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as? android.content.ClipboardManager
        val text = manager?.primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(context)?.toString()
        if (text.isNullOrBlank()) {
            error = CoreResponse.failure(
                "NF-E-003",
                context.getString(dev.ninfenz.mobile.R.string.import_clipboard_empty),
                context.getString(dev.ninfenz.mobile.R.string.import_clipboard_empty_fix),
                2
            ).error
            return
        }
        val markdown = CsvTable.toMarkdown(text)
        scope.launch {
            if (text.toByteArray(Charsets.UTF_8).size > dev.ninfenz.mobile.data.FileAccess.MAX_IMPORT_BYTES) {
                error = CoreResponse.failure(
                    "NF-IMP-003",
                    context.getString(dev.ninfenz.mobile.R.string.import_file_too_large),
                    context.getString(dev.ninfenz.mobile.R.string.import_file_too_large_fix),
                    3
                ).error
                return@launch
            }
            val file = File(File(context.cacheDir, "imports").apply { mkdirs() }, "csv-table.md")
            file.writeText(markdown, Charsets.UTF_8)
            importFromFile(file, "clipboard", "csv-table.md", "text/markdown", markdown.toByteArray(Charsets.UTF_8).size.toLong())
        }
    }

    fun importText(text: String, sourceKind: String, name: String) {
        scope.launch {
            if (text.toByteArray(Charsets.UTF_8).size > dev.ninfenz.mobile.data.FileAccess.MAX_IMPORT_BYTES) {
                error = CoreResponse.failure(
                    "NF-IMP-003",
                    context.getString(dev.ninfenz.mobile.R.string.import_file_too_large),
                    context.getString(dev.ninfenz.mobile.R.string.import_file_too_large_fix),
                    3
                ).error
                return@launch
            }
            val dir = File(context.cacheDir, "imports").apply { mkdirs() }
            val file = File(dir, name)
            file.writeText(text, Charsets.UTF_8)
            importFromFile(file, sourceKind, name, "text/plain", text.toByteArray(Charsets.UTF_8).size.toLong())
        }
    }

    fun importClipboard() {
        val manager = context.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as? android.content.ClipboardManager
        val text = manager?.primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(context)?.toString()
        if (text.isNullOrBlank()) {
            error = CoreResponse.failure(
                "NF-E-003",
                context.getString(dev.ninfenz.mobile.R.string.import_clipboard_empty),
                context.getString(dev.ninfenz.mobile.R.string.import_clipboard_empty_fix),
                2
            ).error
            return
        }
        importText(text, "clipboard", "clipboard.md")
    }

    LaunchedEffect(Unit) {
        val seed = dev.ninfenz.mobile.ui.ImportSeed.consume()
        if (seed != null) {
            importText(seed, "daily", "daily-paste.md")
            return@LaunchedEffect
        }
        if (doc == null && rawResult == null && error == null) {
            val raw = withContext(Dispatchers.IO) { importDraftStore.load() }
            if (raw != null) {
                try {
                    val obj = J.parseObject(raw, ImportModel.SCHEMA)
                    val restored = ImportModel.parse(obj)
                    rawResult = obj
                    doc = restored
                    acceptedMappings = restored.mappings.indices.filter { restored.mappings[it].confidence >= 80 }.toSet()
                    notice = context.getString(dev.ninfenz.mobile.R.string.import_restored_notice)
                } catch (t: Throwable) {
                    importDraftStore.clear()
                }
            }
        }
    }

    LaunchedEffect(autoClipboard) {
        if (autoClipboard) {
            importClipboard()
            onAutoClipboardConsumed()
        }
    }

    fun importSample() {
        scope.launch {
            try {
                val text = context.assets.open("sample-pack/docs/sample.md").bufferedReader(Charsets.UTF_8).use { it.readText() }
                val file = File(File(context.cacheDir, "imports").apply { mkdirs() }, "sample.md")
                file.writeText(text, Charsets.UTF_8)
                importFromFile(file, "file", "sample.md", "text/markdown", text.toByteArray(Charsets.UTF_8).size.toLong())
            } catch (t: Throwable) {
                error = CoreResponse.failure("NF-E-004", context.getString(dev.ninfenz.mobile.R.string.import_sample_read_failed, t.message ?: t.javaClass.simpleName), context.getString(dev.ninfenz.mobile.R.string.import_sample_read_failed_fix), 2).error
            }
        }
    }

    fun importSharedItem(item: SharedItem) {
        scope.launch {
            if (item.text != null) {
                val file = File(File(context.cacheDir, "imports").apply { mkdirs() }, "shared-text.md")
                file.writeText(item.text, Charsets.UTF_8)
                importFromFile(file, "share", "shared-text.md", item.mime ?: "text/plain", item.text.toByteArray(Charsets.UTF_8).size.toLong())
            } else if (item.uri != null) {
                try {
                    val uri = item.uri.toUri()
                    val meta = FileAccess.meta(context, uri)
                    val name = meta.name.orEmpty().lowercase()
                    if (meta.size > FileAccess.MAX_IMPORT_BYTES) {
                        error = CoreResponse.failure("NF-IMP-003", context.getString(dev.ninfenz.mobile.R.string.import_file_too_large), context.getString(dev.ninfenz.mobile.R.string.import_file_too_large_fix), 3).error
                        return@launch
                    }
                    val file = FileAccess.copyToCache(context, uri, meta.name)
                    importFromFile(file, "share", meta.name, meta.mime ?: item.mime, meta.size)
                } catch (e: Exception) {
                    error = if (e is SecurityException) {
                        CoreResponse.failure(
                            "NF-IMP-006",
                            context.getString(dev.ninfenz.mobile.R.string.import_share_permission_lost),
                            context.getString(dev.ninfenz.mobile.R.string.import_share_permission_lost_fix),
                            2
                        ).error
                    } else {
                        CoreResponse.failure(
                            "NF-E-004",
                            context.getString(dev.ninfenz.mobile.R.string.import_share_uri_failed, e.message ?: e.javaClass.simpleName),
                            context.getString(dev.ninfenz.mobile.R.string.import_share_uri_failed_fix),
                            2
                        ).error
                    }
                }
            }
        }
    }

    fun importShare(payload: SharePayload) {
        shareQueue = payload.items
        shareCursor = 0
        val item = payload.items.firstOrNull()
        if (item == null) {
            error = CoreResponse.failure("NF-IMP-001", context.getString(dev.ninfenz.mobile.R.string.import_share_empty), context.getString(dev.ninfenz.mobile.R.string.import_share_empty_fix), 3).error
            return
        }
        importSharedItem(item)
    }

    fun importNextSharedItem() {
        val next = shareCursor + 1
        if (next >= shareQueue.size) return
        shareCursor = next
        importSharedItem(shareQueue[next])
    }

    val templatePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val file = FileAccess.copyToCache(context, uri, "candidate.json")
                val raw = file.readText(Charsets.UTF_8)
                val spec = kotlinx.serialization.json.Json.parseToJsonElement(raw).jsonObject
                val response = safeCall("spec-validate", buildJsonObject { put("spec", spec) })
                if (response.ok) {
                    val saved = templateStore.save(spec)
                    savedTemplates = templateStore.list()
                    notice = context.getString(dev.ninfenz.mobile.R.string.import_template_saved, templateStore.titleOf(saved))
                } else {
                    error = response.error
                }
                file.delete()
            } catch (t: Throwable) {
                error = CoreResponse.failure(
                    "NF-SPC-001",
                    context.getString(dev.ninfenz.mobile.R.string.import_template_import) + ": " + (t.message ?: t.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.import_parse_failed_fix),
                    2
                ).error
            }
        }
    }

    LaunchedEffect(prefill) {
        if (prefill != null) {
            prefillNote = context.getString(dev.ninfenz.mobile.R.string.import_share_from, prefill.summary())
            importShare(prefill)
            onPrefillConsumed()
        }
    }

    val filePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) {
            scope.launch {
                try {
                    val meta = FileAccess.meta(context, uri)
                    if (meta.size > FileAccess.MAX_IMPORT_BYTES) {
                        error = CoreResponse.failure("NF-IMP-003", context.getString(dev.ninfenz.mobile.R.string.import_file_too_large), context.getString(dev.ninfenz.mobile.R.string.import_file_too_large_fix), 3).error
                        return@launch
                    }
                    val file = FileAccess.copyToCache(context, uri, meta.name)
                    importFromFile(file, "saf", meta.name, meta.mime, meta.size)
                } catch (e: Exception) {
                    error = CoreResponse.failure(
                        "NF-E-004",
                        context.getString(dev.ninfenz.mobile.R.string.import_read_failed, e.message ?: e.javaClass.simpleName),
                        context.getString(dev.ninfenz.mobile.R.string.import_read_failed_fix),
                        2
                    ).error
                }
            }
        }
    }

    val importStep = when {
        savedName != null -> 3
        doc != null -> 2
        else -> 0
    }
    Box(modifier = Modifier.fillMaxSize()) {
    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(
            title = stringResource(dev.ninfenz.mobile.R.string.import_title),
            onBack = onBack,
            actions = {
                if (doc != null || rawResult != null || savedName != null || shareQueue.isNotEmpty() || prefillNote != null) {
                    TextButton(onClick = { showClearConfirm = true }, enabled = !busy) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.import_clear_action))
                    }
                }
            }
        )
        NfStepStrip(
            steps = listOf(
                stringResource(dev.ninfenz.mobile.R.string.import_step_source),
                stringResource(dev.ninfenz.mobile.R.string.import_step_preview),
                stringResource(dev.ninfenz.mobile.R.string.import_step_mapping),
                stringResource(dev.ninfenz.mobile.R.string.import_step_draft)
            ),
            current = importStep
        )
        LazyColumn(
            contentPadding = androidx.compose.foundation.layout.PaddingValues(NfSpacing.page),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
        ) {
            item {
                NfCard {
                    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.import_source), style = MaterialTheme.typography.titleLarge)
                        Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                            Button(onClick = { filePicker.launch(arrayOf("*/*")) }, enabled = !busy) { Text(stringResource(dev.ninfenz.mobile.R.string.import_pick_file)) }
                            OutlinedButton(onClick = { importClipboard() }, enabled = !busy) { Text(stringResource(dev.ninfenz.mobile.R.string.import_clipboard)) }
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                            OutlinedButton(onClick = { importCsv() }, enabled = !busy) { Text(stringResource(dev.ninfenz.mobile.R.string.import_csv)) }
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                            OutlinedButton(onClick = { importSample() }, enabled = !busy) { Text(stringResource(dev.ninfenz.mobile.R.string.import_sample)) }
                            if (prefillNote != null) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.import_share_received), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
                            }
                        }
                        if (prefillNote != null) {
                            Text(prefillNote!!, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        if (shareQueue.isNotEmpty()) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    pluralStringResource(dev.ninfenz.mobile.R.plurals.import_share_queue, shareQueue.size, shareQueue.size, shareCursor + 1),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.weight(1f)
                                )
                                if (doc == null) {
                                    TextButton(onClick = { importSharedItem(shareQueue[shareCursor]) }) {
                                        Text(stringResource(dev.ninfenz.mobile.R.string.import_share_current))
                                    }
                                } else if (shareCursor < shareQueue.size - 1) {
                                    TextButton(onClick = { importNextSharedItem() }) {
                                        Text(stringResource(dev.ninfenz.mobile.R.string.import_share_next))
                                    }
                                }
                                TextButton(onClick = {
                                    shareQueue = emptyList()
                                    shareCursor = 0
                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_share_ignore)) }
                            }
                        }
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.import_explain),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }
            if (busy) {
                item { LinearProgressIndicator(modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page)) }
                item { Text(stringResource(dev.ninfenz.mobile.R.string.import_busy), style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
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
                        title = stringResource(dev.ninfenz.mobile.R.string.import_empty_title),
                        message = stringResource(dev.ninfenz.mobile.R.string.import_empty_body),
                        actionLabel = context.getString(dev.ninfenz.mobile.R.string.import_pick_file_action),
                        onAction = { filePicker.launch(arrayOf("*/*")) },
                        secondaryLabel = context.getString(dev.ninfenz.mobile.R.string.import_sample_content),
                        onSecondary = { importSample() }
                    )
                }
            }
            if (current != null) {
                item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.import_preview)) }
                item {
                    NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                        Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                            Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s), verticalAlignment = Alignment.CenterVertically) {
                                NfStatusChip(current.format + " · " + current.confidence + "%")
                                if (current.lowConfidence) NfStatusChip(stringResource(dev.ninfenz.mobile.R.string.import_low_confidence), MaterialTheme.colorScheme.error)
                                NfStatusChip(current.source.kind)
                            }
                            Text(stringResource(dev.ninfenz.mobile.R.string.import_source_label, current.source.name), style = MaterialTheme.typography.bodySmall)
                            Text(
                                pluralStringResource(
                                    dev.ninfenz.mobile.R.plurals.import_structure,
                                    current.structure.headings.size,
                                    current.structure.headings.size,
                                    current.structure.paragraphs,
                                    current.structure.codeBlocks.size,
                                    current.structure.tables.size
                                ),
                                style = MaterialTheme.typography.bodySmall
                            )
                            current.textDigest?.let { Text(stringResource(dev.ninfenz.mobile.R.string.import_digest, it.take(16)), style = MaterialTheme.typography.bodySmall) }
                            for (note in current.reviewNotes()) {
                                Text(note, style = MaterialTheme.typography.bodySmall, color = if (current.lowConfidence) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
                val slices = current.text?.let { MarkdownSlicer.slice(MarkdownBlocks.parse(it)) } ?: emptyList()
                if (slices.isNotEmpty()) {
                    item {
                        NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.import_slices))
                    }
                    item {
                        NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                                Text(
                                    pluralStringResource(
                                        dev.ninfenz.mobile.R.plurals.import_slices_summary,
                                        slices.count { it.heading != null },
                                        slices.count { it.heading != null },
                                        slices.sumOf { it.blocks.size }
                                    ),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                                Text(
                                    stringResource(if (slices.count { it.heading != null } >= 2) dev.ninfenz.mobile.R.string.import_slice_suggestion_chapter else dev.ninfenz.mobile.R.string.import_slice_suggestion_free),
                                    style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.primary
                                )
                                TextButton(onClick = { importPreviewText = current.text }) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.import_preview_ready))
                                }
                                TextButton(onClick = {
                                    promptProfile = PromptProfile.entries[(promptProfile.ordinal + 1) % PromptProfile.entries.size]
                                }) {
                                    Text(promptProfile.label)
                                }
                                val buildPromptPack = {
                                    val sampleTexts = savedSamples.take(2).mapNotNull { sample ->
                                        runCatching { sample.readText(Charsets.UTF_8) }.getOrNull()
                                    }
                                    PromptPack.from(current.source.name, current.text.orEmpty(), slices, sampleTexts, promptProfile)
                                }
                                TextButton(onClick = {
                                    val pack = buildPromptPack()
                                    val intent = ShareExporter.shareMarkdown(context, "nf-prompt-pack", pack)
                                    ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.import_prompt_pack))
                                }) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.import_prompt_pack))
                                }
                                TextButton(onClick = { clipboard.setText(AnnotatedString(buildPromptPack())) }) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.import_prompt_copy))
                                }
                                TextButton(onClick = {
                                    val spec = TemplateCandidate.fromSlices(current.source.name, slices) ?: return@TextButton
                                    scope.launch {
                                        val response = safeCall("spec-validate", buildJsonObject { put("spec", spec) })
                                        if (response.ok) {
                                            val file = templateStore.save(spec)
                                            savedTemplates = templateStore.list()
                                            notice = context.getString(dev.ninfenz.mobile.R.string.import_template_saved, file.name)
                                        } else {
                                            error = response.error
                                        }
                                    }
                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_save_template)) }
                                TextButton(onClick = { templatePicker.launch(arrayOf("application/json", "text/json", "text/plain")) }) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.import_template_import))
                                }
                                if (savedSamples.isNotEmpty()) {
                                    Text(
                                        pluralStringResource(dev.ninfenz.mobile.R.plurals.import_samples_saved, savedSamples.size, savedSamples.size),
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                    savedSamples.take(if (showAllSamples) Int.MAX_VALUE else 3).forEach { file ->
                                        Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                                            TextButton(
                                                onClick = { importPreviewText = runCatching { file.readText(Charsets.UTF_8) }.getOrDefault("") },
                                                contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp)
                                            ) {
                                                Text(file.name, style = MaterialTheme.typography.bodySmall, maxLines = 1)
                                            }
                                            Row(
                                                modifier = Modifier.horizontalScroll(rememberScrollState()),
                                                horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
                                            ) {
                                                TextButton(onClick = {
                                                    clipboard.setText(AnnotatedString(runCatching { file.readText(Charsets.UTF_8) }.getOrDefault("")))
                                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_sample_copy)) }
                                                TextButton(onClick = {
                                                    val text = runCatching { file.readText(Charsets.UTF_8) }.getOrDefault("")
                                                    val intent = ShareExporter.shareMarkdown(context, "nf-sample", text)
                                                    ShareExporter.launchChooser(context, intent, file.name)
                                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_share)) }
                                                TextButton(onClick = { pendingDeleteSample = file }) {
                                                    Text(stringResource(dev.ninfenz.mobile.R.string.import_sample_delete))
                                                }
                                            }
                                        }
                                    }
                                    if (savedSamples.size > 3) {
                                        TextButton(onClick = { showAllSamples = !showAllSamples }) {
                                            Text(stringResource(if (showAllSamples) dev.ninfenz.mobile.R.string.import_samples_show_less else dev.ninfenz.mobile.R.string.import_samples_show_all))
                                        }
                                    }
                                    TextButton(onClick = { showClearSamples = true }) {
                                        Text(stringResource(dev.ninfenz.mobile.R.string.import_samples_clear))
                                    }
                                }
                                if (savedTemplates.isNotEmpty()) {
                                    Text(
                                        pluralStringResource(dev.ninfenz.mobile.R.plurals.import_templates_saved, savedTemplates.size, savedTemplates.size),
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                    savedTemplates.take(if (showAllTemplates) Int.MAX_VALUE else 3).forEach { file ->
                                        Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                                            TextButton(
                                                onClick = { previewTemplate = file },
                                                contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp)
                                            ) {
                                                Text(
                                                    templateStore.titleOf(file),
                                                    style = MaterialTheme.typography.bodySmall
                                                )
                                            }
                                            Row(
                                                modifier = Modifier.horizontalScroll(rememberScrollState()),
                                                horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
                                            ) {
                                                TextButton(onClick = {
                                                    val intent = ShareExporter.shareFileIntent(context, file, "application/json", file.name)
                                                    ShareExporter.launchChooser(context, intent, file.name)
                                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_share)) }
                                                TextButton(onClick = {
                                                    val json = runCatching { file.readText(Charsets.UTF_8) }.getOrDefault("")
                                                    clipboard.setText(AnnotatedString(json))
                                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_copy)) }
                                                TextButton(onClick = { pendingTemplateUse = file }) {
                                                    Text(stringResource(dev.ninfenz.mobile.R.string.import_template_use))
                                                }
                                                TextButton(onClick = { exportTemplatePackage(file) }) {
                                                    Text(stringResource(dev.ninfenz.mobile.R.string.import_template_export))
                                                }
                                                TextButton(onClick = { pendingDeleteTemplate = file }) {
                                                    Text(stringResource(dev.ninfenz.mobile.R.string.import_template_delete))
                                                }
                                            }
                                        }
                                    }
                                    if (savedTemplates.size > 3) {
                                        TextButton(onClick = { showAllTemplates = !showAllTemplates }) {
                                            Text(stringResource(if (showAllTemplates) dev.ninfenz.mobile.R.string.import_templates_show_less else dev.ninfenz.mobile.R.string.import_templates_show_all))
                                        }
                                    }
                                    TextButton(onClick = { showClearTemplates = true }) {
                                        Text(stringResource(dev.ninfenz.mobile.R.string.import_templates_clear))
                                    }
                                }
                                slices.take(6).forEach { slice ->
                                    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                        Text(
                                            slice.heading ?: stringResource(dev.ninfenz.mobile.R.string.import_slice_preamble),
                                            style = MaterialTheme.typography.titleMedium
                                        )
                                        Text(
                                            pluralStringResource(dev.ninfenz.mobile.R.plurals.import_slice_meta, slice.blocks.size, slice.blocks.size, slice.charCount),
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                        slice.blocks.firstOrNull()?.text?.lineSequence()?.firstOrNull()?.take(80)?.let {
                                            Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.import_mapping, current.mappings.size)) }
                if (current.mappings.isEmpty()) {
                    item { Text(stringResource(dev.ninfenz.mobile.R.string.import_no_mapping), style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
                } else {
                    item {
                        Row(modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.import_accepted, acceptedMappings.size, current.mappings.size), style = MaterialTheme.typography.bodySmall)
                            TextButton(onClick = {
                                acceptedMappings = if (acceptedMappings.size == current.mappings.size) emptySet() else current.mappings.indices.toSet()
                            }) { Text(if (acceptedMappings.size == current.mappings.size) stringResource(dev.ninfenz.mobile.R.string.import_accept_none) else stringResource(dev.ninfenz.mobile.R.string.import_accept_all)) }
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
                    item { Text(stringResource(dev.ninfenz.mobile.R.string.import_unmapped, current.unmapped.joinToString("；")), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
                }
                suggestNote?.let { message ->
                    item { Text(message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
                }
                item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.import_draft)) }
                if (savedName == null && rawResult != null && packs.isNotEmpty()) {
                    item {
                        val pack = packs.first()
                        Column(
                            modifier = Modifier.padding(horizontal = NfSpacing.page),
                            verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)
                        ) {
                            Button(onClick = {
                                val raw = rawResult ?: return@Button
                                val title = slices.firstOrNull { it.heading != null }?.heading ?: current.source.name
                                val base = store.uniqueDraftBase(title)
                                val file = store.saveDraft(base, raw.toString())
                                val mappingJson = buildJsonObject {
                                    put("accepted", JsonArray(acceptedMappings.sorted().map { JsonPrimitive(it) }))
                                    put("unmapped", JsonArray(current.unmapped.map { JsonPrimitive(it) }))
                                }.toString()
                                store.saveDraft(base + ".mapping", mappingJson)
                                savedName = file.name
                                drafts = DraftLibrary.list(context.filesDir)
                                onQuickProjectFromDraft(pack, title, file)
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_quick_project)) }
                            Text(
                                stringResource(dev.ninfenz.mobile.R.string.import_quick_project_note, pack.title),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }
                item {
                    if (savedName == null) {
                        Button(
                            onClick = {
                                val raw = rawResult
                                if (raw == null) {
                                    error = CoreResponse.failure(
                                        "NF-E-004",
                                        context.getString(dev.ninfenz.mobile.R.string.import_raw_missing),
                                        context.getString(dev.ninfenz.mobile.R.string.import_raw_missing_fix),
                                        2
                                    ).error
                                } else {
                                    val base = store.uniqueDraftBase(current.source.name)
                                    val file = store.saveDraft(base, raw.toString())
                                    val mappingJson = buildJsonObject {
                                        put("accepted", JsonArray(acceptedMappings.sorted().map { JsonPrimitive(it) }))
                                        put("unmapped", JsonArray(current.unmapped.map { JsonPrimitive(it) }))
                                    }.toString()
                                    store.saveDraft(base + ".mapping", mappingJson)
                                    savedName = file.name
                                    drafts = DraftLibrary.list(context.filesDir)
                                }
                            },
                            modifier = Modifier.padding(horizontal = NfSpacing.page)
                        ) { Text(stringResource(dev.ninfenz.mobile.R.string.import_save)) }
                    } else {
                        NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.import_saved, savedName ?: ""), style = MaterialTheme.typography.titleMedium)
                                Text(stringResource(dev.ninfenz.mobile.R.string.import_saved_note), style = MaterialTheme.typography.bodySmall)
                                Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                                    Button(onClick = onBack) { Text(stringResource(dev.ninfenz.mobile.R.string.import_done)) }
                                    TextButton(onClick = {
                                        doc = null
                                        rawResult = null
                                        savedName = null
                                        acceptedMappings = emptySet()
                                        error = null
                                        suggestNote = null
                                        importDraftStore.clear()
                                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_again)) }
                                }
                            }
                        }
                    }
                }
                if (drafts.isNotEmpty()) {
                    item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.import_saved_drafts)) }
                    drafts.take(5).forEach { draft ->
                        item {
                            NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(draft.name, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
                                    TextButton(onClick = {
                                        val raw = DraftLibrary.read(draft)
                                        if (raw == null) {
                                            error = CoreResponse.failure(
                                                "NF-IMP-004",
                                                context.getString(dev.ninfenz.mobile.R.string.import_draft_read_failed),
                                                context.getString(dev.ninfenz.mobile.R.string.import_draft_read_failed_fix),
                                                2
                                            ).error
                                        } else {
                                            try {
                                                val obj = J.parseObject(raw, ImportModel.SCHEMA)
                                                val parsed = ImportModel.parse(obj)
                                                rawResult = obj
                                                doc = parsed
                                                acceptedMappings = DraftLibrary.acceptedMappings(draft)
                                                    ?: parsed.mappings.indices.filter { parsed.mappings[it].confidence >= 80 }.toSet()
                                                savedName = draft.name.removeSuffix(".json")
                                                error = null
                                                importDraftStore.save(raw)
                                            } catch (t: Throwable) {
                                                error = CoreResponse.failure(
                                                    "NF-E-002",
                                                    context.getString(dev.ninfenz.mobile.R.string.import_draft_parse_failed, t.message ?: t.javaClass.simpleName),
                                                    context.getString(dev.ninfenz.mobile.R.string.import_draft_parse_failed_fix),
                                                    2
                                                ).error
                                            }
                                        }
                                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_open_draft)) }
                                    if (packs.isNotEmpty()) {
                                        TextButton(onClick = { convertDraft = draft }) {
                                            Text(stringResource(dev.ninfenz.mobile.R.string.import_draft_to_project))
                                        }
                                    }
                                    TextButton(onClick = {
                                        renameDraft = draft
                                        renameDraftText = draft.name.removeSuffix(".json")
                                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_rename_draft)) }
                                    TextButton(onClick = { pendingDeleteDraft = draft }) {
                                        Text(stringResource(dev.ninfenz.mobile.R.string.import_delete_draft))
                                    }
                                }
                            }
                        }
                    }
                }
                if (recentImports.isNotEmpty()) {
                    item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.import_recent_history)) }
                    item {
                        NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                                recentImports.take(5).forEach { entry ->
                                    val matched = DraftLibrary.findByDigest(context.filesDir, entry.digest)
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Text(
                                            entry.name + " · " + entry.digest.take(10),
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                            modifier = Modifier.weight(1f)
                                        )
                                        if (matched != null) {
                                            TextButton(onClick = {
                                                val raw = DraftLibrary.read(matched)
                                                if (raw != null) {
                                                    try {
                                                        val obj = J.parseObject(raw, ImportModel.SCHEMA)
                                                        val parsed = ImportModel.parse(obj)
                                                        rawResult = obj
                                                        doc = parsed
                                                        acceptedMappings = DraftLibrary.acceptedMappings(matched)
                                                            ?: parsed.mappings.indices.filter { parsed.mappings[it].confidence >= 80 }.toSet()
                                                        savedName = matched.name.removeSuffix(".json")
                                                        error = null
                                                        importDraftStore.save(raw)
                                                    } catch (t: Throwable) {
                                                        error = CoreResponse.failure(
                                                    "NF-E-002",
                                                    context.getString(dev.ninfenz.mobile.R.string.import_draft_parse_failed, t.message ?: t.javaClass.simpleName),
                                                    context.getString(dev.ninfenz.mobile.R.string.import_draft_parse_failed_fix),
                                                    2
                                                ).error
                                                    }
                                                }
                                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_open_draft)) }
                                        } else {
                                            Text(stringResource(dev.ninfenz.mobile.R.string.import_draft_missing), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        }
                                    }
                                }
                                TextButton(onClick = {
                                    importHistory.clear()
                                    recentImports = importHistory.recent()
                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_recent_clear)) }
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
        AnimatedVisibility(
            visible = cleared != null,
            modifier = Modifier.align(Alignment.BottomCenter),
            enter = fadeIn() + slideInVertically { it / 2 },
            exit = fadeOut() + slideOutVertically { it / 2 }
        ) {
            cleared?.let { snapshot ->
                Surface(
                    modifier = Modifier.padding(horizontal = NfSpacing.page, vertical = NfSpacing.m),
                    shape = MaterialTheme.shapes.large,
                    tonalElevation = 6.dp
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = NfSpacing.m, vertical = NfSpacing.xs),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
                    ) {
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.import_cleared),
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier.weight(1f)
                        )
                        TextButton(onClick = {
                            doc = snapshot.doc
                            rawResult = snapshot.rawResult
                            savedName = snapshot.savedName
                            acceptedMappings = snapshot.acceptedMappings
                            prefillNote = snapshot.prefillNote
                            notice = snapshot.notice
                            suggestNote = snapshot.suggestNote
                            shareQueue = snapshot.shareQueue
                            shareCursor = snapshot.shareCursor
                            snapshot.rawResult?.let { importDraftStore.save(it.toString()) }
                            cleared = null
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_clear_undo)) }
                        TextButton(onClick = { cleared = null }) {
                            Text(stringResource(android.R.string.cancel))
                        }
                    }
                }
            }
        }
    }

    renameDraft?.let { draft ->
        AlertDialog(
            onDismissRequest = { renameDraft = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.import_rename_draft)) },
            text = {
                OutlinedTextField(
                    value = renameDraftText,
                    onValueChange = { renameDraftText = it },
                    singleLine = true,
                    label = { Text(stringResource(dev.ninfenz.mobile.R.string.import_rename_draft_label)) }
                )
            },
            confirmButton = {
                TextButton(
                    enabled = renameDraftText.isNotBlank(),
                    onClick = {
                        try {
                            val renamed = DraftLibrary.rename(draft, renameDraftText)
                            drafts = DraftLibrary.list(context.filesDir)
                            if (savedName == draft.name.removeSuffix(".json")) {
                                savedName = renamed.name.removeSuffix(".json")
                            }
                            renameDraft = null
                        } catch (t: Throwable) {
                            error = CoreResponse.failure(
                                "NF-IMP-005",
                                context.getString(dev.ninfenz.mobile.R.string.import_rename_failed, t.message ?: t.javaClass.simpleName),
                                context.getString(dev.ninfenz.mobile.R.string.import_rename_failed_fix),
                                2
                            ).error
                            renameDraft = null
                        }
                    }
                ) { Text(stringResource(dev.ninfenz.mobile.R.string.import_rename_confirm)) }
            },
            dismissButton = {
                TextButton(onClick = { renameDraft = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

    convertDraft?.let { draft ->
        AlertDialog(
            onDismissRequest = { convertDraft = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.import_draft_to_project)) },
            text = {
                Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                    packs.forEach { pack ->
                        TextButton(onClick = {
                            convertDraft = null
                            onCreateProjectFromDraft(pack, draft.name.removeSuffix(".json"), draft)
                        }) { Text(pack.title + " · " + pack.id + "@" + pack.version) }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { convertDraft = null }) { Text(stringResource(dev.ninfenz.mobile.R.string.action_close)) }
            }
        )
    }

    duplicatePrompt?.let { prompt ->
        AlertDialog(
            onDismissRequest = { duplicatePrompt = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.import_duplicate_title)) },
            text = {
                Text(stringResource(dev.ninfenz.mobile.R.string.import_duplicate_body, prompt.digest.take(12)))
            },
            confirmButton = {
                TextButton(
                    enabled = prompt.draft != null,
                    onClick = {
                        val draft = prompt.draft
                        val raw = draft?.let { DraftLibrary.read(it) }
                        if (raw == null) {
                            duplicatePrompt = null
                        } else {
                            try {
                                val obj = J.parseObject(raw, ImportModel.SCHEMA)
                                val parsed = ImportModel.parse(obj)
                                rawResult = obj
                                doc = parsed
                                acceptedMappings = parsed.mappings.indices.filter { parsed.mappings[it].confidence >= 80 }.toSet()
                                importDraftStore.save(raw)
                                notice = context.getString(dev.ninfenz.mobile.R.string.import_duplicate_updated)
                            } catch (t: Throwable) {
                                error = CoreResponse.failure(
                                    "NF-E-002",
                                    context.getString(dev.ninfenz.mobile.R.string.import_parse_failed, t.message ?: t.javaClass.simpleName),
                                    context.getString(dev.ninfenz.mobile.R.string.import_parse_failed_fix),
                                    1
                                ).error
                            }
                            duplicatePrompt = null
                        }
                    }
                ) { Text(stringResource(dev.ninfenz.mobile.R.string.import_duplicate_update)) }
            },
            dismissButton = {
                Row {
                    TextButton(onClick = {
                        duplicatePrompt = null
                        doc = null
                        rawResult = null
                        acceptedMappings = emptySet()
                        importDraftStore.clear()
                        notice = context.getString(dev.ninfenz.mobile.R.string.import_duplicate_skipped)
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_duplicate_skip)) }
                    TextButton(onClick = { duplicatePrompt = null }) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.import_duplicate_new))
                    }
                }
            }
        )
    }

    pendingDeleteDraft?.let { draft ->
        AlertDialog(
            onDismissRequest = { pendingDeleteDraft = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.import_delete_draft)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.import_delete_draft_body, draft.name)) },
            confirmButton = {
                TextButton(onClick = {
                    val base = draft.name.removeSuffix(".json")
                    DraftLibrary.delete(draft)
                    drafts = DraftLibrary.list(context.filesDir)
                    if (savedName == base) savedName = null
                    pendingDeleteDraft = null
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_delete_draft)) }
            },
            dismissButton = {
                TextButton(onClick = { pendingDeleteDraft = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

    importPreviewText?.let { text ->
        Dialog(onDismissRequest = { importPreviewText = null }) {
            Surface(shape = MaterialTheme.shapes.large, tonalElevation = 6.dp) {
                Column(modifier = Modifier.fillMaxWidth().padding(NfSpacing.l), verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.import_preview_ready), style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f))
                        TextButton(onClick = { clipboard.setText(AnnotatedString(CsvTable.toMarkdown(text))) }) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.import_csv_copy))
                        }
                        TextButton(onClick = {
                            val intent = ShareExporter.shareMarkdown(context, "nf-import-preview", text)
                            ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.delivery_share_md))
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_share_md)) }
                        TextButton(onClick = { importPreviewText = null }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_close)) }
                    }
                    Column(modifier = Modifier.heightIn(max = 520.dp).verticalScroll(rememberScrollState())) {
                        MarkdownPreview(text)
                    }
                }
            }
        }
    }

    previewTemplate?.let { file ->
        val spec = remember(file) {
            runCatching { SpecModel.parse(file.readText(Charsets.UTF_8)) }.getOrNull()
        }
        Dialog(onDismissRequest = { previewTemplate = null }) {
            Surface(shape = MaterialTheme.shapes.large, tonalElevation = 6.dp) {
                Column(
                    modifier = Modifier.fillMaxWidth().padding(NfSpacing.l),
                    verticalArrangement = Arrangement.spacedBy(NfSpacing.s)
                ) {
                    Text(spec?.title ?: file.name, style = MaterialTheme.typography.titleLarge)
                    if (spec != null) {
                        Text("v" + spec.version + " · " + spec.sections.size + " sections · " + spec.slots.size + " slots", style = MaterialTheme.typography.bodySmall)
                        Column(modifier = Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState())) {
                            spec.sections.forEach { section ->
                                Text(section.title, style = MaterialTheme.typography.titleSmall)
                                section.slots.forEach { id ->
                                    val slot = spec.slots.firstOrNull { it.id == id }
                                    val meta = slot?.let {
                                        it.kind + (if (it.required) " · " + stringResource(dev.ninfenz.mobile.R.string.delivery_slot_required) else "") +
                                            (it.maxChars?.let { max -> " · max " + max } ?: "") +
                                            (it.examples.firstOrNull()?.let { example -> " · " + example } ?: "")
                                    }.orEmpty()
                                    Text("- " + id + " " + (slot?.name ?: "") + (if (meta.isNotBlank()) "  (" + meta + ")" else ""), style = MaterialTheme.typography.bodySmall)
                                }
                            }
                        }
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        TextButton(onClick = { previewTemplate = null }) { Text(stringResource(android.R.string.cancel)) }
                        TextButton(onClick = {
                            val json = runCatching { file.readText(Charsets.UTF_8) }.getOrDefault("")
                            clipboard.setText(AnnotatedString(json))
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_copy)) }
                        TextButton(onClick = {
                            previewTemplate = null
                            exportTemplatePackage(file)
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_export)) }
                        TextButton(onClick = {
                            previewTemplate = null
                            pendingTemplateUse = file
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_use)) }
                    }
                }
            }
        }
    }

    pendingTemplateUse?.let { file ->
        val pack = packs.firstOrNull()
        AlertDialog(
            onDismissRequest = { pendingTemplateUse = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_use_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_use_body)) },
            confirmButton = {
                TextButton(
                    enabled = pack != null,
                    onClick = {
                        val spec = runCatching { file.readText(Charsets.UTF_8) }.getOrNull()
                        if (pack != null && spec != null) {
                            onCreateProjectFromTemplate(pack, templateStore.titleOf(file), spec, "")
                        }
                        pendingTemplateUse = null
                    }
                ) { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_use)) }
            },
            dismissButton = {
                TextButton(onClick = { pendingTemplateUse = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

    if (showClearTemplates) {
        AlertDialog(
            onDismissRequest = { showClearTemplates = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.import_templates_clear_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.import_templates_clear_body)) },
            confirmButton = {
                TextButton(onClick = {
                    savedTemplates.forEach { templateStore.delete(it) }
                    savedTemplates = templateStore.list()
                    showClearTemplates = false
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_templates_clear)) }
            },
            dismissButton = {
                TextButton(onClick = { showClearTemplates = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

    if (showClearSamples) {
        AlertDialog(
            onDismissRequest = { showClearSamples = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.import_samples_clear_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.import_samples_clear_body)) },
            confirmButton = {
                TextButton(onClick = {
                    savedSamples.forEach { sampleStore.delete(it) }
                    savedSamples = sampleStore.list()
                    showClearSamples = false
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_samples_clear)) }
            },
            dismissButton = {
                TextButton(onClick = { showClearSamples = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

    pendingDeleteSample?.let { file ->
        AlertDialog(
            onDismissRequest = { pendingDeleteSample = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.import_sample_delete)) },
            text = { Text(file.name) },
            confirmButton = {
                TextButton(onClick = {
                    sampleStore.delete(file)
                    savedSamples = sampleStore.list()
                    pendingDeleteSample = null
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_sample_delete)) }
            },
            dismissButton = {
                TextButton(onClick = { pendingDeleteSample = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

    pendingDeleteTemplate?.let { file ->
        AlertDialog(
            onDismissRequest = { pendingDeleteTemplate = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_delete)) },
            text = { Text(templateStore.titleOf(file)) },
            confirmButton = {
                TextButton(onClick = {
                    templateStore.delete(file)
                    savedTemplates = templateStore.list()
                    pendingDeleteTemplate = null
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.import_template_delete)) }
            },
            dismissButton = {
                TextButton(onClick = { pendingDeleteTemplate = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

    if (showClearConfirm) {
        AlertDialog(
            onDismissRequest = { showClearConfirm = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.import_clear_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.import_clear_body)) },
            confirmButton = {
                TextButton(onClick = { clearCurrentImport() }) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.import_clear_action))
                }
            },
            dismissButton = {
                TextButton(onClick = { showClearConfirm = false }) {
                    Text(stringResource(android.R.string.cancel))
                }
            }
        )
    }
}

private data class ImportClearSnapshot(
    val doc: ImportDoc?,
    val rawResult: JsonObject?,
    val savedName: String?,
    val acceptedMappings: Set<Int>,
    val prefillNote: String?,
    val notice: String?,
    val suggestNote: String?,
    val shareQueue: List<SharedItem>,
    val shareCursor: Int
)

private data class DuplicatePrompt(val digest: String, val draft: File?)
