package dev.ninfenz.mobile.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalClipboardManager
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.ui.rememberCapabilityRevision
import kotlinx.coroutines.launch
import dev.ninfenz.mobile.data.EpubValidator
import dev.ninfenz.mobile.data.ExportVerifier
import dev.ninfenz.mobile.model.FidelityReconciler
import dev.ninfenz.mobile.data.HtmlValidator
import dev.ninfenz.mobile.data.PdfValidator
import java.io.File

/**
 * W5 交付台：项目 → graph-compile 计划 → 槽位输入 → assemble → validate L1 → 导出 md/zip/docx → 分享。
 * 项目状态写回已接；PDF 优先 WebView HTML/CSS（WebPdfExporter），失败回退本地基础文本（PdfExporter）。
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun DeliveryScreen(project: Project, pack: PackEntry?, onBack: () -> Unit, onOpenPacks: () -> Unit = onBack, onPatch: () -> Unit = {}, onStatusChanged: () -> Unit = {}) {
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val auditNow = dev.ninfenz.mobile.data.FeatureGate.auditEnabled()
    val scope = rememberCoroutineScope()
    val s = remember {
        DeliveryUiState(
            context = context,
            clipboard = clipboard,
            scope = scope,
            project = project,
            pack = pack,
            onBack = onBack,
            onOpenPacks = onOpenPacks,
            onPatch = onPatch,
            onStatusChanged = onStatusChanged,
            audit = auditNow,
        )
    }
    s.project = project
    s.pack = pack
    s.onBack = onBack
    s.onOpenPacks = onOpenPacks
    s.onPatch = onPatch
    s.onStatusChanged = onStatusChanged
    s.audit = auditNow
    s.capabilityRevision = rememberCapabilityRevision()
    remember(project.id) { s.resetForProject(project) }
    s.latestInputs.value = s.inputs
    s.latestPlan.value = s.plan
    val referencePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> s.onReferencePicked(uri) }
    s.launchReferencePicker = { args -> referencePicker.launch(args) }
    val slotPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> s.onSlotPicked(uri) }
    s.launchSlotPicker = { args -> slotPicker.launch(args) }
    val batchPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> s.onBatchPicked(uri) }
    s.launchBatchPicker = { args -> batchPicker.launch(args) }
    LaunchedEffect(s.restoredMarkdown) {
        if (s.markdown == null && s.restoredMarkdown != null) s.markdown = s.restoredMarkdown
    }
    LaunchedEffect(project.id, s.plan, s.rawPlan, s.inputs) { s.effectSaveDraft() }
    LaunchedEffect(project.id, s.restoredPlan) { s.effectRestorePlan() }
    DisposableEffect(project.id) {
        onDispose {
            if (s.latestPlan.value != null) s.draftStore.save(project.id, s.latestInputs.value)
        }
    }
    LaunchedEffect(pack?.dir?.absolutePath, project.id) { s.effectLoadArtifacts(pack) }
    if (s.pack == null) {
        s.PackMissingBranch()
        return
    }
    s.RootShell()
    s.SaveExportProfileDialog()
    s.ExportProfilesDialog()
    s.OutputRulesDialog()
    s.PreflightDialog()
    s.SavePresetDialog()
    s.VariantsDialog()
    s.TransformsDialog()
    s.PresetsDialog()
    s.VersionsDialog()
    s.CompareVersionDialog()
    s.MacrosDialog()
    s.MacroSelectedDialog()
    s.MacroBatchConfirmDialog()
    s.FidelityDialog()
    s.LeaveConfirmDialog()
    s.PendingTrashDialog()
    s.TrashDialog()
    s.AllExportsDialog()
    s.ResetConfirmDialog()
    s.BrowsePlanDialog()
    s.ConstraintLensDialog()
    s.GrantDialog()
    s.ManualTransformDialog()
    s.AssignBlockTextDialog()
    s.DiscardPreviewDialog()
    s.BulkDialog()
    s.EditingPreviewDialog()
    s.SlotImportTargetDialog()
    s.BatchChunksDialog()
    s.FullPreviewDialog()
}

// N-001（UI 硬编码中文）按 basename 仅豁免本文件：含中文提示的导出记录函数保留在此，便于审计口径不变。
internal fun DeliveryUiState.afterExportAll(files: List<File>, failures: List<String>, md: String) {
    batchFiles = files
    specMeta?.let { spec -> fidelityResult = FidelityReconciler.fromSpec(spec, md) }
    exportBatchNote = if (failures.isEmpty()) null else "未生成: " + failures.joinToString(",")
    exportedFile = files.firstOrNull()
    recordExport("batch", files.firstOrNull(), null)
}

internal fun DeliveryUiState.recordExport(format: String, file: File?, manifest: String?, verify: Boolean = true) {
    if (file == null) return
    val sha = manifest?.let { Regex("\"sha256\":\"([^\"]+)\"").find(it)?.groupValues?.getOrNull(1) }.orEmpty()
    val doVerify = verify && shouldVerify(format)
    val verdict = when {
        !doVerify -> null
        format == "epub" -> EpubValidator.inspect(file).let { ExportVerifier.Result(it.ok, it.message) }
        format == "pdf" -> PdfValidator.inspect(file).let { ExportVerifier.Result(it.ok, it.message) }
        format == "html" -> HtmlValidator.inspect(file).let { ExportVerifier.Result(it.ok, it.message) }
        format == "preserve" -> dev.ninfenz.mobile.data.PreservationVerifier.verify(file).let {
            ExportVerifier.Result(it.ok, if (it.ok) "" else it.errors.firstOrNull() ?: "归档校验失败")
        }
        else -> ExportVerifier.verify(file, manifest)
    }
    exportVerify = verdict
    exportHistory.record(format, file, sha, verdict?.ok, verdict?.message)
    exportEntries = exportHistory.load()
    exportNotice = if (file != null) {
        context.getString(dev.ninfenz.mobile.R.string.delivery_export_notice, format, file.name, formatBytes(file.length()))
    } else null
}
