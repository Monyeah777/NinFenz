package dev.ninfenz.mobile.ui.screens
import dev.ninfenz.mobile.util.orNullLogged
import dev.ninfenz.mobile.data.ImportSource
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
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
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
import androidx.compose.material3.Slider
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
import androidx.compose.runtime.saveable.rememberSaveable
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
import dev.ninfenz.mobile.data.ExtensionStore
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.data.ImportDraftStore
import dev.ninfenz.mobile.data.ZeroSliceReport
import dev.ninfenz.mobile.data.ZeroSliceStore
import dev.ninfenz.mobile.data.ImportHistoryStore
import dev.ninfenz.mobile.data.PromptSampleStore
import dev.ninfenz.mobile.data.TemplateCandidateStore
import dev.ninfenz.mobile.data.TemplatePackageBuilder
import dev.ninfenz.mobile.data.TemplatePackageImporter
import dev.ninfenz.mobile.data.LibraryStore
import dev.ninfenz.mobile.model.FidelityReport
import dev.ninfenz.mobile.model.ImportBatchState
import dev.ninfenz.mobile.model.ImportBatchStatus
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
import dev.ninfenz.mobile.ui.components.NfActionBarSurface
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
import dev.ninfenz.mobile.ui.design.NfType
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

internal fun docxImportSource(context: android.content.Context, file: File, onError: (CoreError?) -> Unit): File? {
    val markdown = runCatching { DocxImporter.extract(file) }.orNullLogged("ImportScreen")?.takeIf { it.isNotBlank() }
    if (markdown == null) {
        onError(CoreResponse.failure(
            "NF-IMP-008",
            context.getString(dev.ninfenz.mobile.R.string.import_docx_failed),
            context.getString(dev.ninfenz.mobile.R.string.import_docx_failed_fix),
            2
        ).error)
        return null
    }
    return File(file.parentFile, "docx-import-" + System.nanoTime() + ".md").apply { writeText(markdown, Charsets.UTF_8) }
}

internal fun epubImportSource(context: android.content.Context, file: File, onError: (CoreError?) -> Unit): File? {
    val markdown = runCatching { EpubImporter.extract(file) }.orNullLogged("ImportScreen")?.takeIf { it.isNotBlank() }
    if (markdown == null) {
        onError(CoreResponse.failure(
            "NF-IMP-007",
            context.getString(dev.ninfenz.mobile.R.string.import_epub_failed),
            context.getString(dev.ninfenz.mobile.R.string.import_epub_failed_fix),
            2
        ).error)
        return null
    }
    return File(file.parentFile, "epub-import-" + System.nanoTime() + ".md").apply { writeText(markdown, Charsets.UTF_8) }
}

internal suspend fun importProjectBundleIfPresent(
    context: android.content.Context,
    file: File,
    isZip: Boolean,
    onBusy: (Boolean) -> Unit,
    onError: (CoreError?) -> Unit,
    onNotice: (String?) -> Unit,
    onBundleImported: (Int) -> Unit
): Boolean {
    if (!isZip || !dev.ninfenz.mobile.data.ProjectBundleImporter.hasBundle(file)) return false
    onBusy(true)
    onError(null)
    onNotice(null)
    try {
        val imported = withContext(Dispatchers.IO) { dev.ninfenz.mobile.data.ProjectBundleImporter.import(context.filesDir, file) }
        onNotice(context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.import_bundle_done, imported.count, imported.count))
        onBundleImported(imported.count)
    } catch (t: Throwable) {
        onError(CoreResponse.failure(
            "NF-PRJ-001",
            context.getString(dev.ninfenz.mobile.R.string.import_project_failed, t.message ?: t.javaClass.simpleName),
            context.getString(dev.ninfenz.mobile.R.string.import_project_failed_fix),
            2
        ).error)
    } finally {
        file.delete()
        onBusy(false)
    }
    return true
}

internal suspend fun importTemplatePackageIfPresent(
    context: android.content.Context,
    file: File,
    isZip: Boolean,
    packs: List<PackEntry>,
    onBusy: (Boolean) -> Unit,
    onError: (CoreError?) -> Unit,
    onNotice: (String?) -> Unit,
    onCreateProjectFromTemplate: (PackEntry, String, String, String) -> Unit
): Boolean {
    if (!isZip || !TemplatePackageImporter.hasTemplateJson(file)) return false
    onBusy(true)
    onError(null)
    onNotice(null)
    var importedDir: File? = null
    try {
        val imported = withContext(Dispatchers.IO) { TemplatePackageImporter.inspect(file, context.cacheDir) }
        importedDir = imported.dir
        verifyTemplateImport(context, imported, packs, VerifyTemplateImportCallbacks(onError, onCreateProjectFromTemplate))
    } catch (t: Throwable) {
        onError(CoreResponse.failure(
            "NF-E-005",
            context.getString(dev.ninfenz.mobile.R.string.import_template_import) + ": " + (t.message ?: t.javaClass.simpleName),
            context.getString(dev.ninfenz.mobile.R.string.import_parse_failed_fix),
            2
        ).error)
    } finally {
        importedDir?.deleteRecursively()
    }
    file.delete()
    onBusy(false)
    return true
}

internal suspend fun importProjectPackageIfPresent(
    context: android.content.Context,
    file: File,
    isZip: Boolean,
    onError: (CoreError?) -> Unit,
    onNotice: (String?) -> Unit,
    onProjectImported: (String, String, String) -> Unit
): Boolean {
    if (!isZip || !ProjectPackageImporter.hasProjectJson(file)) return false
    try {
        val imported = withContext(Dispatchers.IO) { ProjectPackageImporter.import(context.filesDir, file) }
        onNotice(context.resources.getQuantityString(
            dev.ninfenz.mobile.R.plurals.import_project_package_done,
            imported.dataFiles,
            imported.id,
            imported.dataFiles
        ))
        file.delete()
        onProjectImported(imported.id, imported.packId, imported.packVersion)
    } catch (t: Throwable) {
        onError(CoreResponse.failure(
            "NF-PRJ-001",
            context.getString(dev.ninfenz.mobile.R.string.import_project_failed, t.message ?: t.javaClass.simpleName),
            context.getString(dev.ninfenz.mobile.R.string.import_project_failed_fix),
            2
        ).error)
    }
    return true
}

internal suspend fun callCoreImport(
    sourceFile: File,
    sourceKind: String,
    name: String,
    mime: String?,
    size: Long
): CoreResponse {
    val payload = buildJsonObject {
        put("file", sourceFile.absolutePath)
        put("source", buildJsonObject {
            put("kind", sourceKind)
            put("name", name)
            if (mime != null) put("mime", mime)
            if (size >= 0) put("size", size)
        })
    }
    return safeCall("import", payload)
}
