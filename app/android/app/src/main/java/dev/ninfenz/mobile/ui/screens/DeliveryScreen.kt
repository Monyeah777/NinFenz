package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.util.orNullLogged
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton

import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem

import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Checkbox
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.TextButton
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import kotlinx.coroutines.delay
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import android.content.Context
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.UriIo
import dev.ninfenz.mobile.data.AuthorArtifacts
import dev.ninfenz.mobile.data.AuthorArtifactsLoader
import dev.ninfenz.mobile.data.AssemblyPresetStore
import dev.ninfenz.mobile.data.DeliveryDraftStore
import dev.ninfenz.mobile.data.DeliveryVersionStore
import dev.ninfenz.mobile.data.ExtensionStore
import dev.ninfenz.mobile.data.ExportProfileStore
import dev.ninfenz.mobile.data.DocxReferenceStyles
import dev.ninfenz.mobile.data.EpubExporter
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.data.EpubValidator
import dev.ninfenz.mobile.data.HtmlExporter
import dev.ninfenz.mobile.data.HtmlValidator
import dev.ninfenz.mobile.data.PdfExporter
import dev.ninfenz.mobile.data.PdfUaExporter
import dev.ninfenz.mobile.data.PdfValidator
import dev.ninfenz.mobile.data.ExportHistoryStore
import dev.ninfenz.mobile.data.Capability
import dev.ninfenz.mobile.data.CapabilityRegistry
import dev.ninfenz.mobile.data.ContractGate
import dev.ninfenz.mobile.data.ContractIrStore
import dev.ninfenz.mobile.data.DocxHeadingAudit
import dev.ninfenz.mobile.data.DocxHeadingAuditResult
import dev.ninfenz.mobile.data.DocxStyleAudit
import dev.ninfenz.mobile.data.DocxStyleAuditResult
import dev.ninfenz.mobile.data.ExportVerifier
import dev.ninfenz.mobile.data.ImportDraftStore
import dev.ninfenz.mobile.data.MacroStore
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.SourceStore
import dev.ninfenz.mobile.data.StyleMatch
import dev.ninfenz.mobile.data.StyleTemplateStore
import dev.ninfenz.mobile.data.AssemblyArtifact
import dev.ninfenz.mobile.data.ProjectStatusStore
import dev.ninfenz.mobile.data.StatusAdvanceResult
import dev.ninfenz.mobile.model.AssemblyPlan
import dev.ninfenz.mobile.model.MarkdownBlock
import dev.ninfenz.mobile.model.CorrectionPrompt
import dev.ninfenz.mobile.model.DiffKind
import dev.ninfenz.mobile.model.FidelityReconcile
import dev.ninfenz.mobile.model.FidelityReconciler
import dev.ninfenz.mobile.model.MacroBatchResult
import dev.ninfenz.mobile.model.MacroRunResult
import dev.ninfenz.mobile.model.MacroRunner
import dev.ninfenz.mobile.model.MarkdownBlocks
import dev.ninfenz.mobile.model.TextDiff
import dev.ninfenz.mobile.model.SpecModel
import dev.ninfenz.mobile.model.PlanModel
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ProjectStatus
import dev.ninfenz.mobile.model.ReportModel
import dev.ninfenz.mobile.model.SlotInput
import dev.ninfenz.mobile.model.SlotBatchImporter
import dev.ninfenz.mobile.model.SlotTextAdapter
import dev.ninfenz.mobile.model.ValidateReport
import dev.ninfenz.mobile.share.ShareExporter
import dev.ninfenz.mobile.ui.components.NfCard
import dev.ninfenz.mobile.ui.components.NfEmptyState
import dev.ninfenz.mobile.ui.components.NfCollapsibleSection
import dev.ninfenz.mobile.ui.components.NfExpandableText
import dev.ninfenz.mobile.ui.components.NfErrorCard
import dev.ninfenz.mobile.ui.components.NfLoadingState
import dev.ninfenz.mobile.ui.components.NfSectionHeader
import dev.ninfenz.mobile.ui.components.NfStepStrip
import dev.ninfenz.mobile.ui.components.NfStatusChip
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.rememberCapabilityRevision
import dev.ninfenz.mobile.ui.components.MarkdownPreview
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/**
 * W5 交付台：项目 → graph-compile 计划 → 槽位输入 → assemble → validate L1 → 导出 md/zip/docx → 分享。
 * 项目状态写回已接；PDF 优先 WebView HTML/CSS（WebPdfExporter），失败回退本地基础文本（PdfExporter）。
 */
private fun sha256File(file: File): String =
    java.security.MessageDigest.getInstance("SHA-256").digest(file.readBytes()).joinToString("") { "%02x".format(it) }

private fun templateValueAllowed(meta: dev.ninfenz.mobile.model.SpecSlot?, value: String): Boolean {
    val clean = dev.ninfenz.mobile.model.SlotInput.sanitize(meta?.kind, value)
    if (meta?.nonEmpty == true && clean.isBlank()) return false
    if (meta?.startsWith != null && !clean.startsWith(meta.startsWith)) return false
    if (meta?.endsWith != null && !clean.endsWith(meta.endsWith)) return false
    if (meta?.minChars != null && clean.length < meta.minChars) return false
    if (meta?.maxChars != null && clean.length > meta.maxChars) return false
    if (meta?.pattern != null && !runCatching { Regex(meta.pattern).matches(clean) }.getOrDefault(false)) return false
    return true
}

private fun slotIssue(context: Context, meta: dev.ninfenz.mobile.model.SpecSlot?, value: String): String? {
    if (meta == null) return null
    val clean = dev.ninfenz.mobile.model.SlotInput.sanitize(meta.kind, value)
    if (clean.isBlank() && (meta.required || meta.nonEmpty)) {
        return context.getString(dev.ninfenz.mobile.R.string.delivery_slot_required)
    }
    if (meta.minChars != null && clean.isNotBlank() && clean.length < meta.minChars) {
        return context.getString(dev.ninfenz.mobile.R.string.delivery_slot_budget_min, meta.minChars)
    }
    if (meta.maxChars != null && clean.length > meta.maxChars) {
        return context.getString(dev.ninfenz.mobile.R.string.delivery_slot_budget_max, meta.maxChars)
    }
    if (meta.startsWith != null && clean.isNotBlank() && !clean.startsWith(meta.startsWith)) {
        return context.getString(dev.ninfenz.mobile.R.string.delivery_slot_rule_prefix, meta.startsWith)
    }
    if (meta.endsWith != null && clean.isNotBlank() && !clean.endsWith(meta.endsWith)) {
        return context.getString(dev.ninfenz.mobile.R.string.delivery_slot_rule_suffix, meta.endsWith)
    }
    if (meta.pattern != null && clean.isNotBlank() && !runCatching { Regex(meta.pattern).matches(clean) }.getOrDefault(false)) {
        return context.getString(dev.ninfenz.mobile.R.string.delivery_slot_rule_pattern, meta.pattern)
    }
    return null
}

private fun parseTemplateSlots(markdown: String): Map<String, String> {
    val result = mutableMapOf<String, String>()
    markdown.lineSequence().forEach { line ->
        val trimmed = line.trim()
        if (!trimmed.startsWith("- SLT-")) return@forEach
        val rest = trimmed.removePrefix("- ")
        val id = rest.substringBefore(' ').trim()
        if (!rest.contains('：') && !rest.contains(':')) return@forEach
        val body = rest.substringAfter('：', "").ifBlank { rest.substringAfter(':', "") }
        if (id.startsWith("SLT-") && body.isNotBlank()) result[id] = body.trim()
    }
    return result
}

private fun reproTextFor(report: dev.ninfenz.mobile.data.ReproChecker.Report?, context: Context): String? =
    when {
        report == null -> null
        report.stable -> context.getString(dev.ninfenz.mobile.R.string.repro_stable)
        else -> context.getString(dev.ninfenz.mobile.R.string.repro_diff, report.firstDiff ?: -1)
    }

private fun reproTextStable(report: dev.ninfenz.mobile.data.ReproChecker.Report, context: Context): String =
    if (report.stable) {
        context.getString(dev.ninfenz.mobile.R.string.repro_stable)
    } else {
        context.getString(dev.ninfenz.mobile.R.string.repro_diff, report.firstDiff ?: -1)
    }

@Composable
private fun DeliveryPreflightButton(onShow: () -> Unit) {
    TextButton(onClick = onShow) {
        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_preflight))
    }
}

private class DeliveryExportArgs(
    val project: Project,
    val markdown: String?,
    val exportMarkdown: String?,
    val report: ValidateReport?,
    val exportedFile: File?,
    val busy: Boolean,
    val contractUnsatisfiable: Boolean,
    val exportBlocked: Boolean,
    val batchFiles: List<File>,
    val exportBatchNote: String?,
    val docxStyles: String?,
    val docxSectPr: String?,
    val docxTheme: String?,
    val docxNumbering: String?,
    val docxHeader: String?,
    val docxFooter: String?,
    val epubAuthor: String,
    val epubLanguage: String,
    val pdfPageSize: String,
    val pdfIncludeTitle: Boolean,
    val selectedOutputTemplate: String?,
    val audit: Boolean,
    val grant: dev.ninfenz.mobile.data.CapabilityGrant,
    val capabilityRevision: Int,
    val styleTemplates: List<StyleTemplateStore.StyleTemplate>,
    val showStyleTemplates: Boolean,
    val docxStyleAudit: DocxStyleAuditResult?,
    val docxHeadingAudit: DocxHeadingAuditResult?,
    val outputRuleNote: String?,
    val exportNotice: String?,
    val exportEntries: List<ExportHistoryStore.Entry>,
    val manifestText: String?,
    val exportVerify: ExportVerifier.Result?,
    val reproText: String?,
    val reproOk: Boolean?,
    val recentExpanded: Boolean,
    val evidenceBusy: Boolean,
    val evidenceNote: String?,
    val scope: kotlinx.coroutines.CoroutineScope,
    val onBusy: (Boolean) -> Unit,
    val onError: (CoreError?) -> Unit,
    val onExportAll: () -> Unit,
    val onExportDone: (String, File?, String?, dev.ninfenz.mobile.data.ReproChecker.Report?) -> Unit,
    val onShowGrant: () -> Unit,
    val onOpenStyleTemplates: () -> Unit,
    val onDismissStyleTemplates: () -> Unit,
    val onPickStyleTemplate: (StyleTemplateStore.StyleTemplate) -> Unit,
    val onShowSaveExportProfile: () -> Unit,
    val onShowExportProfiles: () -> Unit,
    val onShowOutputRules: () -> Unit,
    val onShowPreflight: () -> Unit,
    val onEpubAuthor: (String) -> Unit,
    val onEpubLanguage: (String) -> Unit,
    val onPdfPageSize: (String) -> Unit,
    val onPdfIncludeTitle: (Boolean) -> Unit,
    val onPickReference: () -> Unit,
    val onBack: () -> Unit,
    val onToggleRecent: () -> Unit,
    val onShowTrash: () -> Unit,
    val onShowAllExports: () -> Unit,
    val onClearExports: () -> Unit,
    val onPendingTrash: (ExportHistoryStore.Entry) -> Unit,
    val onEvidence: (ExportHistoryStore.Entry) -> Unit
)

@Composable
private fun DeliveryExportSection(a: DeliveryExportArgs) {
    NfCollapsibleSection(title = stringResource(dev.ninfenz.mobile.R.string.delivery_export_section), initiallyExpanded = true) {
        ExportSummary(a)
        ExportAllBlock(a)
        ExportDocsRow(a)
        ExportDataRow(a)
        ExportReadingRow(a)
        ExportPreserveRow(a)
        ExportShareRow(a)
        ExportStyleRow(a)
        ExportToolsRow(a)
        ExportFieldsRow(a)
        ExportNoticeText(a)
        if (a.exportedFile != null) ExportDoneCard(a.onBack)
        a.exportEntries.firstOrNull()?.let { latest -> LatestExportCard(a, latest) }
        ExportResultLines(a)
        DocxAuditLines(a)
        ExportRecentBlock(a)
    }
}

@Composable
private fun ExportSummary(a: DeliveryExportArgs) {
    val summary = buildList {
        add(stringResource(if (a.markdown != null) dev.ninfenz.mobile.R.string.delivery_summary_assembled else dev.ninfenz.mobile.R.string.delivery_summary_unassembled))
        if (a.audit) add(stringResource(if (a.report?.verdict == "pass") dev.ninfenz.mobile.R.string.delivery_summary_validated else dev.ninfenz.mobile.R.string.delivery_summary_unvalidated))
        add(stringResource(if (a.exportedFile != null) dev.ninfenz.mobile.R.string.delivery_summary_exported else dev.ninfenz.mobile.R.string.delivery_summary_unexported))
    }.joinToString(" · ")
    Text(summary, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page))
    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_export_group_docs), style = NfType.label, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(start = NfSpacing.page, end = NfSpacing.page, top = NfSpacing.s))
}

@Composable
private fun ExportAllBlock(a: DeliveryExportArgs) {
    OutlinedButton(
        enabled = a.exportMarkdown != null && !a.busy && !a.contractUnsatisfiable,
        onClick = a.onExportAll,
        modifier = Modifier.padding(horizontal = NfSpacing.page)
    ) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_export_all)) }
    a.batchFiles.takeIf { it.isNotEmpty() }?.let { files ->
        Text(files.joinToString(" · ") { it.name }, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page))
    }
    a.exportBatchNote?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
}

@Composable
private fun ExportDocsRow(a: DeliveryExportArgs) {
    val context = androidx.compose.ui.platform.LocalContext.current
    FlowRow(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
        ExportButton(ExportButtonArgs("md", "text/markdown", a.exportMarkdown, a.project, context, a.scope, { a.onBusy(it) }, { a.onError(it) }, a.exportBlocked, onDone = { file, manifest, report -> a.onExportDone("md", file, manifest, report) }))
        ExportButton(ExportButtonArgs("zip", "application/zip", a.exportMarkdown, a.project, context, a.scope, { a.onBusy(it) }, { a.onError(it) }, a.exportBlocked, onDone = { file, manifest, report -> a.onExportDone("zip", file, manifest, report) }))
        ExportButton(ExportButtonArgs("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", a.exportMarkdown, a.project, context, a.scope, { a.onBusy(it) }, { a.onError(it) }, a.exportBlocked, docxStyles = a.docxStyles, docxSectPr = a.docxSectPr, docxTheme = a.docxTheme, docxNumbering = a.docxNumbering, docxHeader = a.docxHeader, docxFooter = a.docxFooter, onDone = { file, manifest, report -> a.onExportDone("docx", file, manifest, report) }))
    }
}

@Composable
private fun ExportDataRow(a: DeliveryExportArgs) {
    val context = androidx.compose.ui.platform.LocalContext.current
    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_export_group_data), style = NfType.label, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(start = NfSpacing.page, end = NfSpacing.page, top = NfSpacing.s))
    FlowRow(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
        ExportButton(ExportButtonArgs("json", "application/json", a.exportMarkdown, a.project, context, a.scope, { a.onBusy(it) }, { a.onError(it) }, a.exportBlocked, onDone = { file, manifest, report -> a.onExportDone("json", file, manifest, report) }))
        ExportButton(ExportButtonArgs("skill", "application/zip", a.exportMarkdown, a.project, context, a.scope, { a.onBusy(it) }, { a.onError(it) }, a.exportBlocked, onDone = { file, manifest, report -> a.onExportDone("skill", file, manifest, report) }))
    }
}

@Composable
private fun ExportReadingRow(a: DeliveryExportArgs) {
    val context = androidx.compose.ui.platform.LocalContext.current
    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_export_group_reading), style = NfType.label, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(start = NfSpacing.page, end = NfSpacing.page, top = NfSpacing.s))
    FlowRow(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
        EpubExportButton(EpubExportButtonArgs(a.exportMarkdown, a.project, a.epubAuthor, a.epubLanguage, context, a.scope, { a.onBusy(it) }, { a.onError(it) }, a.exportBlocked, outputTemplate = a.selectedOutputTemplate, onDone = { file, report -> a.onExportDone("epub", file, null, report) }))
        PdfExportButton(PdfExportButtonArgs(a.exportMarkdown, a.project, a.pdfPageSize, a.pdfIncludeTitle, context, a.scope, { a.onBusy(it) }, { a.onError(it) }, a.exportBlocked, outputTemplate = a.selectedOutputTemplate, onDone = { file, report -> a.onExportDone("pdf", file, null, report) }))
        if (a.audit) PdfUaExportButton(a.exportMarkdown, a.project, context, a.scope, { a.onBusy(it) }, { a.onError(it) }, a.exportBlocked) { file, report -> a.onExportDone("pdf-ua", file, null, report) }
        HtmlExportButton(a.exportMarkdown, a.project, context, a.scope, { a.onBusy(it) }, { a.onError(it) }, a.exportBlocked, outputTemplate = a.selectedOutputTemplate) { file, report -> a.onExportDone("html", file, null, report) }
    }
}

@Composable
private fun ExportPreserveRow(a: DeliveryExportArgs) {
    val context = androidx.compose.ui.platform.LocalContext.current
    FlowRow(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
        if (a.audit) PreservationExportButton(a.exportMarkdown, a.project, context, a.scope, { a.onBusy(it) }, { a.onError(it) }, a.exportBlocked, a.grant) { file, report -> a.onExportDone("preserve", file, null, report) }
        if (a.audit) OutlinedButton(
            onClick = a.onShowGrant,
            modifier = Modifier.padding(horizontal = NfSpacing.page)
        ) { Text(stringResource(dev.ninfenz.mobile.R.string.grant_button)) }
        NfDocExportButton(a.exportMarkdown, a.project, context, a.scope, { a.onBusy(it) }, { a.onError(it) }, a.exportBlocked) { file, report -> a.onExportDone("nf-doc", file, null, report) }
    }
}

@Composable
private fun ExportShareRow(a: DeliveryExportArgs) {
    val context = androidx.compose.ui.platform.LocalContext.current
    FlowRow(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
        OutlinedButton(
            enabled = a.markdown != null && !a.busy,
            onClick = {
                val md = a.markdown ?: return@OutlinedButton
                val intent = ShareExporter.shareMarkdown(context, "nf-" + a.project.id, md)
                ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.delivery_share_md))
            }
        ) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_share_md)) }
        OutlinedButton(
            enabled = a.exportedFile != null,
            onClick = {
                val file = a.exportedFile ?: return@OutlinedButton
                val mime = when (file.extension.lowercase()) {
                    "md" -> "text/markdown"
                    "zip" -> "application/zip"
                    "docx" -> "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    else -> "application/octet-stream"
                }
                val intent = ShareExporter.shareFileIntent(context, file, mime, a.project.title)
                ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.delivery_share_file))
            }
        ) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_share_file)) }
    }
}

@Composable
private fun ExportStyleRow(a: DeliveryExportArgs) {
    Row(
        modifier = Modifier.padding(horizontal = NfSpacing.page),
        horizontalArrangement = Arrangement.spacedBy(NfSpacing.s),
        verticalAlignment = Alignment.CenterVertically
    ) {
        if (a.capabilityRevision >= 0 && CapabilityRegistry.isEnabled(Capability.STYLE)) {
            OutlinedButton(onClick = a.onPickReference) {
                Text(stringResource(dev.ninfenz.mobile.R.string.docx_reference_pick))
            }
        }
        if (a.capabilityRevision >= 0 && CapabilityRegistry.isEnabled(Capability.STYLE)) {
            TextButton(onClick = a.onOpenStyleTemplates) {
                Text(stringResource(dev.ninfenz.mobile.R.string.docx_style_from_library))
            }
        }
        Text(
            stringResource(
                if (a.docxStyles != null) dev.ninfenz.mobile.R.string.docx_reference_loaded
                else dev.ninfenz.mobile.R.string.docx_reference_none
            ),
            style = NfType.meta
        )
    }
    if (a.showStyleTemplates) StyleTemplatesDialog(a)
}

@Composable
private fun StyleTemplatesDialog(a: DeliveryExportArgs) {
    AlertDialog(
        onDismissRequest = a.onDismissStyleTemplates,
        title = { Text(stringResource(dev.ninfenz.mobile.R.string.docx_style_from_library)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                if (a.styleTemplates.isEmpty()) {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.docx_style_library_empty),
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                a.styleTemplates.forEach { template -> StyleTemplateRow(template, a.docxStyles, a.onPickStyleTemplate) }
            }
        },
        confirmButton = {
            TextButton(onClick = a.onDismissStyleTemplates) { Text(stringResource(android.R.string.cancel)) }
        }
    )
}

@Composable
private fun StyleTemplateRow(
    template: StyleTemplateStore.StyleTemplate,
    docxStyles: String?,
    onPick: (StyleTemplateStore.StyleTemplate) -> Unit
) {
    val docxCompatible = template.sourceFormat.equals("docx", ignoreCase = true)
    Column {
        TextButton(enabled = docxCompatible, onClick = { onPick(template) }) { Text(template.name) }
        Text(
            stringResource(dev.ninfenz.mobile.R.string.docx_style_meta, template.sourceFormat, template.digest.take(12)),
            style = NfType.meta,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        if (!docxCompatible) {
            Text(
                stringResource(dev.ninfenz.mobile.R.string.docx_pdf_not_applicable),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.error
            )
        }
        if (docxCompatible) docxStyles?.let { currentStyle ->
            Text(
                stringResource(dev.ninfenz.mobile.R.string.docx_style_match, StyleMatch.score(currentStyle, template.stylesXml)),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.primary
            )
        }
    }
}

@Composable
private fun ExportToolsRow(a: DeliveryExportArgs) {
    FlowRow(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
        TextButton(enabled = a.docxStyles != null, onClick = a.onShowSaveExportProfile) {
            Text(stringResource(dev.ninfenz.mobile.R.string.export_profile_save))
        }
        TextButton(onClick = a.onShowExportProfiles) {
            Text(stringResource(dev.ninfenz.mobile.R.string.export_profiles))
        }
        TextButton(onClick = a.onShowOutputRules) {
            Text(stringResource(dev.ninfenz.mobile.R.string.delivery_output_rule))
        }
        if (a.audit) DeliveryPreflightButton(a.onShowPreflight)
    }
    a.outputRuleNote?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
}

@Composable
private fun ExportFieldsRow(a: DeliveryExportArgs) {
    FlowRow(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
        OutlinedTextField(
            value = a.epubAuthor,
            onValueChange = a.onEpubAuthor,
            label = { Text("EPUB author") },
            singleLine = true,
            modifier = Modifier.weight(1f)
        )
        OutlinedTextField(
            value = a.epubLanguage,
            onValueChange = a.onEpubLanguage,
            label = { Text("EPUB lang") },
            singleLine = true,
            modifier = Modifier.weight(1f)
        )
    }
    Row(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s), verticalAlignment = Alignment.CenterVertically) {
        OutlinedTextField(
            value = a.pdfPageSize,
            onValueChange = a.onPdfPageSize,
            label = { Text("PDF page") },
            singleLine = true,
            modifier = Modifier.weight(1f)
        )
        Text("title", style = NfType.meta)
        Switch(checked = a.pdfIncludeTitle, onCheckedChange = a.onPdfIncludeTitle)
    }
    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_pdf_note), style = NfType.meta, modifier = Modifier.padding(horizontal = NfSpacing.page))
}

@Composable
private fun ExportNoticeText(a: DeliveryExportArgs) {
    a.exportNotice?.let { notice ->
        Text(
            notice,
            style = NfType.meta,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.padding(horizontal = NfSpacing.page)
        )
    }
}

@Composable
private fun ExportDoneCard(onBack: () -> Unit) {
    NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
        Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
            Text(stringResource(dev.ninfenz.mobile.R.string.delivery_done_title), style = NfType.itemTitle)
            Text(stringResource(dev.ninfenz.mobile.R.string.delivery_done_body), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
            TextButton(onClick = onBack) {
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_done_back))
            }
        }
    }
}

@Composable
private fun LatestExportCard(a: DeliveryExportArgs, latest: ExportHistoryStore.Entry) {
    NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
        Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
            Text(
                stringResource(dev.ninfenz.mobile.R.string.delivery_last_export) + " · " + latest.format,
                style = NfType.itemTitle
            )
            val meta = buildList {
                add(latest.name)
                latest.bytes?.let { add(formatBytes(it)) }
                latest.sha256.take(12).takeIf { it.isNotBlank() }?.let { add(it) }
            }.joinToString(" · ")
            Text(
                meta,
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            LatestExportActions(latest)
            if (a.markdown != null && latest.format.lowercase() in setOf("md", "html", "epub", "docx", "json")) {
                LatestEvidenceButton(a, latest)
            }
            a.evidenceNote?.let { note ->
                Text(note, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun LatestExportActions(latest: ExportHistoryStore.Entry) {
    val context = androidx.compose.ui.platform.LocalContext.current
    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
        TextButton(onClick = {
            val file = File(latest.path)
            if (file.isFile) {
                val intent = ShareExporter.shareFileIntent(context, file, mimeFor(latest.format), latest.name)
                ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.delivery_share_file))
            }
        }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_share_file)) }
        TextButton(onClick = {
            val file = File(latest.path)
            if (file.isFile) {
                val intent = ShareExporter.viewFileIntent(context, file, mimeFor(latest.format))
                ShareExporter.launchView(context, intent, context.getString(dev.ninfenz.mobile.R.string.delivery_open_file))
            }
        }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_open_file)) }
    }
}

@Composable
private fun LatestEvidenceButton(a: DeliveryExportArgs, latest: ExportHistoryStore.Entry) {
    OutlinedButton(
        enabled = !a.evidenceBusy,
        onClick = { a.onEvidence(latest) }
    ) {
        Text(
            stringResource(
                if (a.evidenceBusy) dev.ninfenz.mobile.R.string.delivery_evidence_pack_busy
                else dev.ninfenz.mobile.R.string.delivery_evidence_pack
            )
        )
    }
}

@Composable
private fun ExportResultLines(a: DeliveryExportArgs) {
    a.manifestText?.let { Text(it, style = NfType.meta, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
    a.exportVerify?.let {
        Text(
            it.message,
            style = NfType.meta,
            color = if (it.ok) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
            modifier = Modifier.padding(horizontal = NfSpacing.page)
        )
    }
    a.reproText?.let {
        Text(
            it,
            style = NfType.meta,
            color = if (a.reproOk == true) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
            modifier = Modifier.padding(horizontal = NfSpacing.page)
        )
    }
}

@Composable
private fun DocxAuditLines(a: DeliveryExportArgs) {
    a.docxStyleAudit?.let { auditState ->
        Text(
            when {
                auditState.definedButUnused -> stringResource(
                    dev.ninfenz.mobile.R.string.docx_style_unused,
                    auditState.found,
                    auditState.checked
                )
                auditState.ok -> stringResource(dev.ninfenz.mobile.R.string.docx_style_audit_ok, auditState.found, auditState.checked)
                else -> stringResource(dev.ninfenz.mobile.R.string.docx_style_audit, auditState.found, auditState.checked, auditState.missing.joinToString("、"))
            },
            style = NfType.meta,
            color = if (auditState.ok) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
            modifier = Modifier.padding(horizontal = NfSpacing.page)
        )
    }
    a.docxHeadingAudit?.let { auditState ->
        Text(
            stringResource(
                dev.ninfenz.mobile.R.string.docx_heading_audit,
                auditState.styledHeadings,
                auditState.markdownHeadings
            ),
            style = NfType.meta,
            color = if (auditState.ok) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
            modifier = Modifier.padding(horizontal = NfSpacing.page)
        )
    }
}

@Composable
private fun ExportRecentBlock(a: DeliveryExportArgs) {
    if (a.exportEntries.isEmpty()) return
    Row(
        modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        TextButton(onClick = a.onToggleRecent) {
            Text(
                stringResource(dev.ninfenz.mobile.R.string.delivery_recent_exports) +
                    (if (a.recentExpanded) " ▾" else " ▸"),
                style = NfType.itemTitle
            )
        }
        Row {
            TextButton(onClick = a.onShowTrash) {
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_trash))
            }
            if (a.exportEntries.size > 5) {
                TextButton(onClick = a.onShowAllExports) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_all_exports))
                }
            }
            TextButton(onClick = a.onClearExports) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_clear_exports)) }
        }
    }
    if (a.recentExpanded) a.exportEntries.take(5).forEach { entry -> RecentExportRow(entry, a.onPendingTrash) }
}

@Composable
private fun RecentExportRow(entry: ExportHistoryStore.Entry, onRemove: (ExportHistoryStore.Entry) -> Unit) {
    val context = androidx.compose.ui.platform.LocalContext.current
    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(entry.format + " · " + entry.name + (entry.bytes?.let { " · " + formatBytes(it) } ?: ""), style = NfType.meta, modifier = Modifier.weight(1f))
            entry.ok?.let { ok ->
                Text(
                    stringResource(if (ok) dev.ninfenz.mobile.R.string.export_verified else dev.ninfenz.mobile.R.string.export_verify_failed),
                    style = NfType.meta,
                    color = if (ok) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
                )
            }
            TextButton(onClick = {
                val file = File(entry.path)
                if (file.isFile) {
                    val intent = ShareExporter.shareFileIntent(context, file, mimeFor(entry.format), entry.name)
                    ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.delivery_share_file))
                }
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_share_file)) }
            TextButton(onClick = {
                val file = File(entry.path)
                if (file.isFile) {
                    val intent = ShareExporter.viewFileIntent(context, file, mimeFor(entry.format))
                    ShareExporter.launchView(context, intent, context.getString(dev.ninfenz.mobile.R.string.delivery_open_file))
                }
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_open_file)) }
            TextButton(onClick = { onRemove(entry) }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_remove_export)) }
        }
        entry.message?.takeIf { entry.ok != true }?.let { message ->
            Text(
                message,
                style = NfType.meta,
                color = MaterialTheme.colorScheme.error
            )
        }
    }
}

private class DeliveryPreviewArgs(
    val markdown: String?,
    val project: Project,
    val sampleStore: dev.ninfenz.mobile.data.PromptSampleStore,
    val copyMarkdown: (String) -> Unit,
    val onShowVersions: () -> Unit,
    val onEditPreview: (String) -> Unit,
    val onFullPreview: () -> Unit
)

@Composable
private fun DeliveryPreviewSection(a: DeliveryPreviewArgs) {
    val context = androidx.compose.ui.platform.LocalContext.current
    NfCollapsibleSection(title = stringResource(dev.ninfenz.mobile.R.string.delivery_preview), initiallyExpanded = true) {
        TextButton(onClick = a.onShowVersions) {
            Text(stringResource(dev.ninfenz.mobile.R.string.delivery_versions))
        }
        val md = a.markdown
        if (md == null) {
            Text(stringResource(dev.ninfenz.mobile.R.string.delivery_not_assembled), style = NfType.meta, modifier = Modifier.padding(horizontal = NfSpacing.page))
        } else {
            Column(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                MarkdownPreview(md, limitBlocks = 8)
                Row {
                    TextButton(onClick = { a.onEditPreview(md) }) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.preview_edit))
                    }
                    TextButton(onClick = a.onFullPreview) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.preview_full))
                    }
                    TextButton(onClick = { a.copyMarkdown(md) }) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.preview_copy))
                    }
                    TextButton(onClick = {
                        val safe = dev.ninfenz.mobile.data.ShareRedactor.redact(md)
                        val intent = ShareExporter.shareMarkdown(context, "nf-redacted", safe)
                        ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.preview_share_redacted))
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_share_redacted)) }
                    TextButton(onClick = {
                        val saved = runCatching { a.sampleStore.save("delivery-" + a.project.id, md) }.orNullLogged("DeliveryScreen")
                        android.widget.Toast.makeText(
                            context,
                            if (saved != null) context.getString(dev.ninfenz.mobile.R.string.delivery_save_sample) + ": " + saved.name
                            else context.getString(dev.ninfenz.mobile.R.string.delivery_save_sample),
                            android.widget.Toast.LENGTH_SHORT
                        ).show()
                    }) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_save_sample))
                    }
                    TextButton(onClick = {
                        val intent = ShareExporter.shareMarkdown(context, "nf-" + a.project.id, md)
                        ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.delivery_share_md))
                    }) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_share_md))
                    }
                }
            }
        }
    }
}

@Composable
private fun ExportProfileRow(
    profile: dev.ninfenz.mobile.data.ExportProfileStore.Profile,
    onApply: (dev.ninfenz.mobile.data.ExportProfileStore.Profile) -> Unit,
    onRemove: (dev.ninfenz.mobile.data.ExportProfileStore.Profile) -> Unit
) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
        Text(profile.name, style = NfType.meta)
        Row {
            TextButton(onClick = { onApply(profile) }) {
                Text(stringResource(dev.ninfenz.mobile.R.string.export_profile_apply))
            }
            if (!profile.id.startsWith("ext:")) {
                TextButton(onClick = { onRemove(profile) }) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.inbox_remove))
                }
            }
        }
    }
}

@Composable
private fun PreviewSuggestionApplyButton(slotId: String, text: String, onApply: (String, String) -> Unit) {
    TextButton(onClick = { onApply(slotId, text) }) {
        Text(stringResource(dev.ninfenz.mobile.R.string.preview_suggest_apply))
    }
}

private fun slotVisible(meta: dev.ninfenz.mobile.model.SpecSlot?, inputs: Map<String, String>): Boolean {
    val cond = meta?.visibleIf ?: return true
    return inputs[cond.slot] == cond.equals
}

private class DeliveryAssembleArgs(
    val needsRevalidate: Boolean,
    val busy: Boolean,
    val canAssemble: Boolean,
    val canValidate: Boolean,
    val missingRequired: List<String>,
    val oversizedSlots: List<String>,
    val constraintViolations: List<String>,
    val markdown: String?,
    val exportMarkdown: String?,
    val report: ValidateReport?,
    val validateRepro: String?,
    val signoff: dev.ninfenz.mobile.data.ContractStore.Signoff?,
    val exportedFile: File?,
    val plan: AssemblyPlan?,
    val specMeta: dev.ninfenz.mobile.model.MdSpec?,
    val inputs: Map<String, String>,
    val assembleRequester: BringIntoViewRequester,
    val validateRequester: BringIntoViewRequester,
    val onAssemble: () -> Unit,
    val onValidate: () -> Unit,
    val onShareFix: (ValidateReport) -> Unit,
    val onSign: (List<Pair<String, Boolean>>) -> Unit,
    val onGoValidate: () -> Unit
)

@Composable
private fun DeliveryAssembleSection(a: DeliveryAssembleArgs) {
    if (a.needsRevalidate) {
        NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_dirty_title), style = NfType.itemTitle, color = MaterialTheme.colorScheme.error)
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_dirty_body), style = NfType.meta)
            }
        }
    }
    NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.delivery_assemble_validate))
    DeliveryAssembleButtons(a)
    a.report?.let { r -> DeliveryReportBlock(r, a.markdown, a.validateRepro, a.onShareFix) }
    if (a.report?.verdict == "pass" && a.markdown != null) DeliveryContractBlock(a)
    if (a.markdown != null && a.exportMarkdown == null) DeliveryExportBlockedRow(a.onGoValidate)
}

@Composable
private fun DeliveryAssembleButtons(a: DeliveryAssembleArgs) {
    FlowRow(
        modifier = Modifier.padding(horizontal = NfSpacing.page),
        horizontalArrangement = Arrangement.spacedBy(NfSpacing.s),
        verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)
    ) {
        Button(
            enabled = a.canAssemble,
            modifier = Modifier.bringIntoViewRequester(a.assembleRequester),
            onClick = a.onAssemble
        ) { Text(if (a.busy) stringResource(dev.ninfenz.mobile.R.string.delivery_assembling) else stringResource(dev.ninfenz.mobile.R.string.delivery_assemble)) }
        if (a.constraintViolations.isNotEmpty()) {
            Text(
                stringResource(dev.ninfenz.mobile.R.string.delivery_slot_constraint, a.constraintViolations.joinToString(", ")),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(horizontal = NfSpacing.page)
            )
        }
        if (a.oversizedSlots.isNotEmpty()) {
            Text(
                stringResource(dev.ninfenz.mobile.R.string.delivery_slot_over_budget, a.oversizedSlots.joinToString(", ")),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(horizontal = NfSpacing.page)
            )
        }
        if (a.missingRequired.isNotEmpty()) {
            Text(
                stringResource(dev.ninfenz.mobile.R.string.delivery_missing_required, a.missingRequired.joinToString(", ")),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(horizontal = NfSpacing.page)
            )
        }
        Button(
            enabled = a.canValidate,
            modifier = Modifier.bringIntoViewRequester(a.validateRequester),
            onClick = a.onValidate
        ) { Text(if (a.busy) stringResource(dev.ninfenz.mobile.R.string.delivery_validating) else stringResource(dev.ninfenz.mobile.R.string.delivery_validate)) }
    }
}

@Composable
private fun DeliveryReportBlock(
    r: ValidateReport,
    markdown: String?,
    validateRepro: String?,
    onShareFix: (ValidateReport) -> Unit
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    Text(ReportModel.line(r), style = NfType.secondary, modifier = Modifier.padding(horizontal = NfSpacing.page))
    validateRepro?.let {
        Text(it, style = NfType.meta, modifier = Modifier.padding(horizontal = NfSpacing.page))
    }
    if (r.issues.isNotEmpty() && markdown != null) {
        TextButton(onClick = { onShareFix(r) }, modifier = Modifier.padding(horizontal = NfSpacing.page)) {
            Text(stringResource(dev.ninfenz.mobile.R.string.delivery_share_fix))
        }
    }
    for (issue in r.issues.take(20)) {
        Text(
            issue.code + " " + (issue.path ?: "-") + "：" + issue.message + context.getString(dev.ninfenz.mobile.R.string.error_fix_suffix) + issue.fix,
            style = NfType.meta,
            color = if (issue.severity == "error") MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(horizontal = NfSpacing.page)
        )
    }
}

@Composable
private fun DeliveryContractBlock(a: DeliveryAssembleArgs) {
    val requiredSlots = a.plan?.slots?.filter { id ->
        a.specMeta?.slots?.firstOrNull { it.id == id }?.required == true
    }.orEmpty()
    val slotsFilled = requiredSlots.isEmpty() || requiredSlots.all { a.inputs[it].orEmpty().isNotBlank() }
    val checks = listOf(
        stringResource(dev.ninfenz.mobile.R.string.contract_l1) to true,
        stringResource(dev.ninfenz.mobile.R.string.contract_slots) to slotsFilled,
        stringResource(dev.ninfenz.mobile.R.string.contract_export) to (a.exportedFile != null)
    )
    Column(Modifier.padding(horizontal = NfSpacing.page, vertical = NfSpacing.s), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
        Text(stringResource(dev.ninfenz.mobile.R.string.contract_title), style = NfType.itemTitle)
        checks.forEach { (label, ok) ->
            Text((if (ok) "✓ " else "✗ ") + label, style = NfType.meta, color = if (ok) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error)
        }
        val signed = a.signoff
        val currentDigest = a.exportedFile?.let { sha256File(it) }
        val stale = signed != null && (signed.artifactSha256 == null || signed.artifactSha256 != currentDigest)
        if (signed != null && !stale) {
            Text(stringResource(dev.ninfenz.mobile.R.string.contract_signed, signed.signedAt), style = NfType.meta)
            signed.artifactSha256?.let { Text(stringResource(dev.ninfenz.mobile.R.string.contract_artifact, it), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            signed.keyFingerprint?.let { Text(stringResource(dev.ninfenz.mobile.R.string.contract_key, it.take(16)), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        } else {
            if (stale) {
                Text(stringResource(dev.ninfenz.mobile.R.string.contract_stale), style = NfType.meta, color = MaterialTheme.colorScheme.error)
            }
            Button(
                enabled = checks.all { it.second },
                onClick = { a.onSign(checks) }
            ) { Text(stringResource(dev.ninfenz.mobile.R.string.contract_sign)) }
            if (!checks.all { it.second }) {
                Text(stringResource(dev.ninfenz.mobile.R.string.contract_blocked), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun DeliveryExportBlockedRow(onGoValidate: () -> Unit) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.padding(horizontal = NfSpacing.page)
    ) {
        Text(
            stringResource(dev.ninfenz.mobile.R.string.delivery_export_blocked),
            style = NfType.meta,
            color = MaterialTheme.colorScheme.error,
            modifier = Modifier.weight(1f)
        )
        TextButton(onClick = onGoValidate) {
            Text(stringResource(dev.ninfenz.mobile.R.string.delivery_go_validate))
        }
    }
}

@Composable
private fun DeliveryPlanSection(
    plan: AssemblyPlan?,
    busy: Boolean,
    constraintConflicts: List<List<dev.ninfenz.mobile.model.ConstraintMUS.Rule>>,
    onBrowsePlan: () -> Unit,
    onCompile: () -> Unit
) {
    NfSectionHeader(
        stringResource(dev.ninfenz.mobile.R.string.delivery_plan),
        action = {
            TextButton(onClick = onBrowsePlan) {
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_browse_plan))
            }
        }
    )
    Button(
        enabled = !busy,
        modifier = Modifier.padding(horizontal = NfSpacing.page),
        onClick = onCompile
    ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.delivery_compiling) else stringResource(dev.ninfenz.mobile.R.string.delivery_compile)) }
    plan?.let { p ->
        Text(
            stringResource(dev.ninfenz.mobile.R.string.delivery_plan_summary, p.steps.size, p.slots.size),
            style = NfType.meta,
            modifier = Modifier.padding(horizontal = NfSpacing.page)
        )
    }
    if (constraintConflicts.isNotEmpty()) {
        NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                Text(
                    pluralStringResource(dev.ninfenz.mobile.R.plurals.delivery_constraint_conflict, constraintConflicts.size, constraintConflicts.size),
                    style = NfType.itemTitle,
                    color = MaterialTheme.colorScheme.error
                )
                constraintConflicts.take(2).forEach { conflict ->
                    Text(
                        stringResource(
                            dev.ninfenz.mobile.R.string.delivery_constraint_conflict_detail,
                            conflict.joinToString(" + ") { it.id }
                        ),
                        style = NfType.meta
                    )
                }
            }
        }
    }
}

private class DeliverySlotsArgs(
    val plan: AssemblyPlan?,
    val specMeta: dev.ninfenz.mobile.model.MdSpec?,
    val inputs: Map<String, String>,
    val parsedTemplateSlots: Map<String, String>,
    val batchNote: String?,
    val variantNote: String?,
    val draftNote: String?,
    val batchUndo: Map<String, String>?,
    val hasVariants: Boolean,
    val hasTransforms: Boolean,
    val onShowConstraintLens: () -> Unit,
    val onBatchImport: () -> Unit,
    val onShowPresets: () -> Unit,
    val onShowVariants: () -> Unit,
    val onShowTransforms: () -> Unit,
    val onUndoBatch: (Map<String, String>) -> Unit,
    val onInputsChange: (Map<String, String>) -> Unit,
    val onPaste: (String) -> Unit,
    val onOpenPicker: (String) -> Unit,
    val onFillTemplate: () -> Unit
)

@Composable
private fun DeliverySlotsSection(a: DeliverySlotsArgs) {
    NfCollapsibleSection(
        title = stringResource(dev.ninfenz.mobile.R.string.delivery_slots),
        subtitle = a.plan?.let { stringResource(dev.ninfenz.mobile.R.string.delivery_plan_summary, it.steps.size, it.slots.size) },
        initiallyExpanded = true
    ) {
        a.plan?.let { SlotsToolbar(a) }
        val p = a.plan
        if (p == null) {
            Text(stringResource(dev.ninfenz.mobile.R.string.delivery_compile_first), style = NfType.meta, modifier = Modifier.padding(horizontal = NfSpacing.page))
        } else if (p.slots.isEmpty()) {
            Text(stringResource(dev.ninfenz.mobile.R.string.delivery_no_slots), style = NfType.meta, modifier = Modifier.padding(horizontal = NfSpacing.page))
        } else {
            val requiredSlots = a.specMeta?.slots?.filter { it.required && slotVisible(it, a.inputs) }.orEmpty()
            if (requiredSlots.isNotEmpty()) SlotsProgressBlock(a, requiredSlots)
            var lastSection: String? = null
            for (slot in p.slots) {
                val slotMeta = a.specMeta?.slots?.firstOrNull { it.id == slot }
                if (!slotVisible(slotMeta, a.inputs)) continue
                Column(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                    val sectionTitle = slotMeta?.let { meta -> a.specMeta?.sections?.firstOrNull { it.id == meta.section }?.title }
                    val sectionId = slotMeta?.section
                    if (sectionTitle != null && sectionId != null && sectionId != lastSection) {
                        val sectionSlots = a.specMeta?.sections?.firstOrNull { it.id == sectionId }?.slots.orEmpty()
                        val sectionFilled = sectionSlots.count { !a.inputs[it].isNullOrBlank() }
                        SlotsSectionHeader(sectionTitle, sectionFilled, sectionSlots.size)
                        lastSection = sectionId
                    }
                    SlotMetaBlock(slot, slotMeta)
                    SlotActionRow(slot, slotMeta, a.inputs, a.onInputsChange, a.onPaste, a.onOpenPicker)
                    SlotEditorField(slot, slotMeta, a.inputs, a.onInputsChange, p.slots.lastOrNull() == slot)
                }
            }
        }
    }
}

@Composable
private fun SlotsToolbar(a: DeliverySlotsArgs) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            stringResource(dev.ninfenz.mobile.R.string.delivery_slot_batch_hint),
            style = NfType.meta,
            modifier = Modifier.weight(1f)
        )
        Row {
            TextButton(onClick = a.onShowConstraintLens) {
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_constraint_panel))
            }
            TextButton(onClick = a.onBatchImport) {
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_batch_import))
            }
            TextButton(onClick = a.onShowPresets) {
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_presets))
            }
            if (a.hasVariants) {
                TextButton(onClick = a.onShowVariants) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_variants))
                }
            }
            if (a.hasTransforms) {
                TextButton(onClick = a.onShowTransforms) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_transforms))
                }
            }
        }
    }
    a.batchNote?.let {
        Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page))
    }
    a.variantNote?.let {
        Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page))
    }
    a.batchUndo?.let { snapshot ->
        TextButton(
            onClick = { a.onUndoBatch(snapshot) },
            modifier = Modifier.padding(horizontal = NfSpacing.page)
        ) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_batch_undo)) }
    }
    a.draftNote?.let {
        Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(horizontal = NfSpacing.page))
    }
}

@Composable
private fun SlotsSectionHeader(title: String, filled: Int, total: Int) {
    Text(
        title + "  " + filled + "/" + total,
        style = NfType.itemTitle,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.semantics { heading() }
    )
}

@Composable
private fun SlotsProgressBlock(a: DeliverySlotsArgs, requiredSlots: List<dev.ninfenz.mobile.model.SpecSlot>) {
    val plan = a.plan ?: return
    val requiredFilled = requiredSlots.count { !a.inputs[it.id].isNullOrBlank() }
    Text(
        stringResource(dev.ninfenz.mobile.R.string.delivery_required_progress, requiredFilled, requiredSlots.size),
        style = NfType.meta,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(horizontal = NfSpacing.page)
    )
    androidx.compose.material3.LinearProgressIndicator(
        progress = { requiredFilled.toFloat() / requiredSlots.size.toFloat() },
        modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page)
    )
    val fillable = a.parsedTemplateSlots.count { (id, value) ->
        id in plan.slots && a.inputs[id].isNullOrBlank() &&
            templateValueAllowed(a.specMeta?.slots?.firstOrNull { it.id == id }, value)
    }
    if (fillable > 0) {
        TextButton(onClick = a.onFillTemplate) {
            Text(pluralStringResource(dev.ninfenz.mobile.R.plurals.delivery_fill_template_count, fillable, fillable))
        }
    }
}

@Composable
private fun SlotMetaBlock(slot: String, slotMeta: dev.ninfenz.mobile.model.SpecSlot?) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Text(slot, style = NfType.label)
            slotMeta?.let {
                Text(it.name, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(
                    stringResource(if (it.required) dev.ninfenz.mobile.R.string.delivery_slot_required else dev.ninfenz.mobile.R.string.delivery_slot_optional),
                    style = NfType.meta,
                    color = if (it.required) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
                )
                Text(it.kind, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (it.minChars != null || it.maxChars != null) {
                    Text(
                        when {
                            it.minChars != null && it.maxChars != null ->
                                stringResource(dev.ninfenz.mobile.R.string.delivery_slot_budget, it.minChars, it.maxChars)
                            it.maxChars != null ->
                                stringResource(dev.ninfenz.mobile.R.string.delivery_slot_budget_max, it.maxChars)
                            else ->
                                stringResource(dev.ninfenz.mobile.R.string.delivery_slot_budget_min, it.minChars ?: 0)
                        },
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                val rules = listOfNotNull(
                    it.pattern?.let { pattern -> "pattern: " + pattern },
                    it.startsWith?.let { prefix -> "start: " + prefix },
                    it.endsWith?.let { suffix -> "end: " + suffix },
                    if (it.nonEmpty) "non-empty" else null
                )
                if (rules.isNotEmpty()) {
                    Text(
                        rules.joinToString(" · "),
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}

@Composable
private fun SlotActionRow(
    slot: String,
    slotMeta: dev.ninfenz.mobile.model.SpecSlot?,
    inputs: Map<String, String>,
    onInputsChange: (Map<String, String>) -> Unit,
    onPaste: (String) -> Unit,
    onOpenPicker: (String) -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(top = NfSpacing.xs),
        horizontalArrangement = Arrangement.End
    ) {
        slotMeta?.examples?.firstOrNull()?.let { example ->
            TextButton(onClick = { onInputsChange(inputs + (slot to example)) }) {
                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_example))
            }
        }
        if ((inputs[slot] ?: "").isNotBlank()) {
            TextButton(onClick = { onInputsChange(inputs - slot) }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_clear)) }
        }
        TextButton(onClick = { onPaste(slot) }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_paste)) }
        TextButton(onClick = { onOpenPicker(slot) }) { Text(stringResource(dev.ninfenz.mobile.R.string.action_import)) }
    }
}

@Composable
private fun SlotEditorField(
    slot: String,
    slotMeta: dev.ninfenz.mobile.model.SpecSlot?,
    inputs: Map<String, String>,
    onInputsChange: (Map<String, String>) -> Unit,
    lastSlot: Boolean
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val focusManager = androidx.compose.ui.platform.LocalFocusManager.current
    OutlinedTextField(
        value = inputs[slot] ?: "",
        onValueChange = { value ->
            val clean = SlotInput.sanitize(slotMeta?.kind, value)
            val limited = slotMeta?.maxChars?.let { clean.take(it) } ?: clean
            onInputsChange(inputs + (slot to limited))
        },
        singleLine = false,
        minLines = 2,
        maxLines = 6,
        keyboardOptions = KeyboardOptions(
            keyboardType = when (slotMeta?.kind) {
                "number", "int", "integer" -> KeyboardType.Number
                "decimal", "float" -> KeyboardType.Decimal
                else -> KeyboardType.Text
            },
            imeAction = if (lastSlot) ImeAction.Done else ImeAction.Next
        ),
        keyboardActions = KeyboardActions(
            onDone = { focusManager.clearFocus() },
            onNext = { focusManager.moveFocus(FocusDirection.Down) }
        ),
        placeholder = { Text(slotMeta?.examples?.firstOrNull().orEmpty(), maxLines = 2) },
        textStyle = if (slotMeta?.kind == "code" || slotMeta?.kind == "json") {
            NfType.secondary.copy(fontFamily = FontFamily.Monospace)
        } else {
            NfType.secondary
        },
        supportingText = {
            val issue = slotIssue(context, slotMeta, inputs[slot].orEmpty())
            if (issue != null) {
                Text(issue, color = MaterialTheme.colorScheme.error)
            } else {
                Text(pluralStringResource(dev.ninfenz.mobile.R.plurals.delivery_slot_chars, (inputs[slot] ?: "").length, (inputs[slot] ?: "").length))
            }
        },
        modifier = Modifier.fillMaxWidth().semantics {
            contentDescription = slot + " " + (slotMeta?.name ?: "")
        }
    )
}

@Composable
@OptIn(ExperimentalLayoutApi::class)
fun DeliveryScreen(project: Project, pack: PackEntry?, onBack: () -> Unit, onOpenPacks: () -> Unit = onBack, onPatch: () -> Unit = {}, onStatusChanged: () -> Unit = {}) {
    val context = LocalContext.current
    val audit = dev.ninfenz.mobile.data.FeatureGate.auditEnabled()
    val focusManager = LocalFocusManager.current
    val clipboard = LocalClipboardManager.current
    val sampleStore = remember { dev.ninfenz.mobile.data.PromptSampleStore(context.filesDir) }
    val scope = rememberCoroutineScope()
    val statusStore = remember { ProjectStatusStore(context.filesDir) }
    val contractStore = remember { dev.ninfenz.mobile.data.ContractStore(context.filesDir) }
    val grantStore = remember { dev.ninfenz.mobile.data.CapabilityGrantStore(context.filesDir) }
    var grant by remember(project.id) { mutableStateOf(grantStore.load(project.id) ?: dev.ninfenz.mobile.data.CapabilityGrant.defaultForPackage()) }
    var showGrant by remember { mutableStateOf(false) }
    var status by remember(project.id) { mutableStateOf(project.status) }
    var signoff by remember(project.id) { mutableStateOf(contractStore.load(project.id)) }
    var statusNote by remember { mutableStateOf<String?>(null) }
    var artifacts by remember { mutableStateOf<AuthorArtifacts?>(null) }
    var loadError by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }

    var plan by remember { mutableStateOf<AssemblyPlan?>(null) }
    var rawPlan by remember { mutableStateOf<JsonObject?>(null) }
    var inputs by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    val templateReference = remember(project.id) {
        dev.ninfenz.mobile.data.ProjectPaths.templateMd(context.filesDir, project.id)
            .takeIf { it.isFile }?.readText(Charsets.UTF_8)
    }
    val parsedTemplateSlots = remember(templateReference) { parseTemplateSlots(templateReference.orEmpty()) }
    var markdown by remember { mutableStateOf<String?>(null) }
    var showFullPreview by remember { mutableStateOf(false) }
    var editingPreview by remember { mutableStateOf(false) }
    var showResetConfirm by remember { mutableStateOf(false) }
    var previewBlocks by remember { mutableStateOf<List<MarkdownBlock>>(emptyList()) }
    var previewBaseline by remember { mutableStateOf<List<MarkdownBlock>>(emptyList()) }
    var ignoredHints by remember { mutableStateOf<Set<Int>>(emptySet()) }
    var inferredTransform by remember { mutableStateOf<dev.ninfenz.mobile.model.FlashFillModel.Transform?>(null) }
    var showManualTransform by remember { mutableStateOf(false) }
    var manualKind by remember { mutableStateOf("lower") }
    var manualA by remember { mutableStateOf("") }
    var manualB by remember { mutableStateOf("") }
    var savedTransform by remember(project.id) { mutableStateOf(dev.ninfenz.mobile.data.TransformStore(context.filesDir).load(project.id)) }
    var previewHistory by remember { mutableStateOf<List<List<MarkdownBlock>>>(emptyList()) }
    var previewRedo by remember { mutableStateOf<List<List<MarkdownBlock>>>(emptyList()) }
    var previewDirty by remember { mutableStateOf(false) }
    var showBulk by remember { mutableStateOf(false) }
    var bulkFrom by remember { mutableStateOf("") }
    var bulkTo by remember { mutableStateOf("") }
    var bulkError by remember { mutableStateOf<String?>(null) }
    var bulkMode by remember { mutableStateOf("replace") }
    var needsRevalidate by remember { mutableStateOf(false) }
    val assembleRequester = remember { BringIntoViewRequester() }
    val validateRequester = remember { BringIntoViewRequester() }
    var missingRequired by remember { mutableStateOf<List<String>>(emptyList()) }
    var oversizedSlots by remember { mutableStateOf<List<String>>(emptyList()) }
    var constraintViolations by remember { mutableStateOf<List<String>>(emptyList()) }
    var showDiscardPreview by remember { mutableStateOf(false) }
    var showConstraintLens by remember { mutableStateOf(false) }
    var assignBlockText by remember { mutableStateOf<String?>(null) }
    var report by remember { mutableStateOf<ValidateReport?>(null) }
    var manifestText by remember { mutableStateOf<String?>(null) }
    var exportedFile by remember { mutableStateOf<File?>(null) }
    var batchFiles by remember { mutableStateOf<List<File>>(emptyList()) }
    var exportBatchNote by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var slotImportTarget by remember { mutableStateOf<String?>(null) }
    var slotImportSource by remember { mutableStateOf("") }
    var slotImportFormat by remember { mutableStateOf("text") }
    var slotImportOriginal by remember { mutableIntStateOf(0) }
    var slotImportAdapted by remember { mutableIntStateOf(0) }
    var slotImportText by remember { mutableStateOf("") }
    var batchChunks by remember { mutableStateOf<List<SlotBatchImporter.Chunk>>(emptyList()) }
    var batchSource by remember { mutableStateOf("") }
    var batchNote by remember { mutableStateOf<String?>(null) }
    var batchUndo by remember { mutableStateOf<Map<String, String>?>(null) }
    val draftStore = remember { DeliveryDraftStore(context.filesDir) }
    val versionStore = remember { DeliveryVersionStore(context.filesDir) }
    val presetStore = remember { AssemblyPresetStore(context.filesDir) }
    var showVersions by remember { mutableStateOf(false) }
    var compareVersionText by remember { mutableStateOf<String?>(null) }
    var compareVersionLabel by remember { mutableStateOf("") }
    var fidelityResult by remember { mutableStateOf<FidelityReconcile?>(null) }
    var showPresets by remember { mutableStateOf(false) }
    val extensionVariants = remember { ExtensionStore(context.filesDir).contributions(setOf("delivery_variant")) }
    val extensionTransforms = remember { ExtensionStore(context.filesDir).contributions(setOf("slot_transform")) }
    val assemblyRecipes = remember { ExtensionStore(context.filesDir).contributions(setOf("assembly_recipe")) }
    var showVariants by remember { mutableStateOf(false) }
    var showTransforms by remember { mutableStateOf(false) }
    var variantNote by remember { mutableStateOf<String?>(null) }
    var showSavePreset by remember { mutableStateOf(false) }
    var presetName by remember { mutableStateOf("") }
    val exportHistory = remember { ExportHistoryStore(context.filesDir) }
    var exportEntries by remember { mutableStateOf(exportHistory.load()) }
    var recentExpanded by remember { mutableStateOf(true) }
    var showAllExports by remember { mutableStateOf(false) }
    var showTrash by remember { mutableStateOf(false) }
    var pendingTrash by remember { mutableStateOf<dev.ninfenz.mobile.data.ExportHistoryStore.Entry?>(null) }
    fun trashAndRemove(entry: dev.ninfenz.mobile.data.ExportHistoryStore.Entry) {
        runCatching {
            val source = File(entry.path)
            if (source.isFile) {
                val trash = File(File(context.filesDir, "exports"), "trash").apply { mkdirs() }
                val target = File(trash, System.currentTimeMillis().toString() + "-" + source.name)
                if (source.renameTo(target)) {
                    File(target.absolutePath + ".restore").writeText(entry.path, Charsets.UTF_8)
                }
            }
        }
        exportHistory.remove(entry.path)
        exportEntries = exportHistory.load()
    }
    var exportNotice by remember { mutableStateOf<String?>(null) }
    var evidenceBusy by remember { mutableStateOf(false) }
    var evidenceNote by remember { mutableStateOf<String?>(null) }
    var exportVerify by remember { mutableStateOf<ExportVerifier.Result?>(null) }
    var reproText by remember { mutableStateOf<String?>(null) }
    var reproOk by remember { mutableStateOf<Boolean?>(null) }
    var validateRepro by remember { mutableStateOf<String?>(null) }
    val exportProfileStore = remember { ExportProfileStore(context.filesDir) }
    var exportProfiles by remember { mutableStateOf(exportProfileStore.load()) }
    val extensionProfiles = remember {
        ExtensionStore(context.filesDir).contributions(setOf("export_profile")).mapNotNull { c ->
            val cfg = c.config
            ExportProfileStore.Profile(
                id = "ext:" + c.id,
                name = cfg["name"]?.jsonPrimitive?.content?.ifBlank { c.id } ?: c.id,
                at = 0L,
                styles = cfg["docx_styles"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() },
                sectPr = cfg["docx_sect_pr"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() },
                theme = cfg["docx_theme"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() },
                numbering = cfg["docx_numbering"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() },
                header = cfg["docx_header"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() },
                footer = cfg["docx_footer"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() },
                epubAuthor = cfg["epub_author"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() },
                epubLanguage = cfg["epub_language"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() },
                pdfPageSize = cfg["pdf_page_size"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() },
                pdfIncludeTitle = cfg["pdf_include_title"]?.jsonPrimitive?.content?.toBooleanStrictOrNull()
            )
        }
    }
    var showExportProfiles by remember { mutableStateOf(false) }
    var showSaveExportProfile by remember { mutableStateOf(false) }
    var exportProfileName by remember { mutableStateOf("") }
    val outputRules = remember { ExtensionStore(context.filesDir).contributions(setOf("output_rule")) }
    var selectedOutputTemplate by remember { mutableStateOf<String?>(null) }
    var showOutputRules by remember { mutableStateOf(false) }
    var outputRuleNote by remember { mutableStateOf<String?>(null) }
    val preflightProfiles = remember {
        if (audit) ExtensionStore(context.filesDir).contributions(setOf("preflight_profile")) else emptyList()
    }
    var selectedPreflight by remember { mutableStateOf<dev.ninfenz.mobile.data.ExtensionStore.Contribution?>(null) }
    var showPreflight by remember { mutableStateOf(false) }
    var pdfPageSize by remember { mutableStateOf("A4") }
    var pdfIncludeTitle by remember { mutableStateOf(true) }
    var epubAuthor by remember { mutableStateOf("") }
    var epubLanguage by remember { mutableStateOf("zh") }
    var docxStyles by remember { mutableStateOf<String?>(null) }
    var docxStyleAudit by remember { mutableStateOf<DocxStyleAuditResult?>(null) }
    var docxHeadingAudit by remember { mutableStateOf<DocxHeadingAuditResult?>(null) }
    val contractUnsatisfiable = remember(project.id) {
        ContractGate.blocked(ContractIrStore(context.filesDir, project.id).loadSolve())
    }
    val contractValues = remember(project.id) {
        ContractIrStore(context.filesDir, project.id).loadValues()
    }
    var docxSectPr by remember { mutableStateOf<String?>(null) }
    var docxTheme by remember { mutableStateOf<String?>(null) }
    var docxNumbering by remember { mutableStateOf<String?>(null) }
    var docxHeader by remember { mutableStateOf<String?>(null) }
    var docxFooter by remember { mutableStateOf<String?>(null) }
    val styleStore = remember { StyleTemplateStore(context.filesDir) }
    var styleTemplates by remember { mutableStateOf(emptyList<StyleTemplateStore.StyleTemplate>()) }
    var showStyleTemplates by remember { mutableStateOf(false) }
    val referencePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            scope.launch {
                val file = runCatching { FileAccess.copyToCache(context, uri, "reference.docx") }.orNullLogged("DeliveryScreen")
                val styles = file?.let { DocxReferenceStyles.extract(it) }
                val sectPr = file?.let { DocxReferenceStyles.extractSectPr(it) }
                val theme = file?.let { DocxReferenceStyles.extractTheme(it) }
                val numbering = file?.let { DocxReferenceStyles.extractNumbering(it) }
                val header = file?.let { DocxReferenceStyles.extractHeader(it) }
                val footer = file?.let { DocxReferenceStyles.extractFooter(it) }
                file?.delete()
                docxStyles = styles
                docxSectPr = sectPr
                docxTheme = theme
                docxNumbering = numbering
                docxHeader = header
                docxFooter = footer
                if (styles == null) {
                    error = CoreError(
                        "NF-EXP-002",
                        context.getString(dev.ninfenz.mobile.R.string.docx_reference_failed),
                        context.getString(dev.ninfenz.mobile.R.string.docx_reference_failed_fix),
                        null,
                        2
                    )
                }
            }
        }
    }
    val restoredInputs = remember(project.id) { draftStore.load(project.id) }
    val zeroPrefill = remember(project.id) {
        val file = dev.ninfenz.mobile.data.ProjectPaths.zeroSlice(context.filesDir, project.id)
        dev.ninfenz.mobile.data.ZeroSliceStore(context.filesDir).read(file)?.slotValues ?: emptyMap()
    }
    val protocolPrefill = remember(project.id, artifacts?.protocol, artifacts?.spec) {
        val art = artifacts
        if (art == null) emptyMap() else {
            val params = dev.ninfenz.mobile.data.ProtocolSlotPrefill.loadParams(context.filesDir, project.id)
            dev.ninfenz.mobile.data.ProtocolSlotPrefill.bind(art.protocol.fields, art.spec.slots, params)
        }
    }
    val slotPrefill = zeroPrefill + protocolPrefill
    val restoredPlan = remember(project.id) { draftStore.loadPlan(project.id) }
    val restoredMarkdown = remember(project.id) { draftStore.loadMarkdown(project.id) }
    LaunchedEffect(restoredMarkdown) {
        if (markdown == null && restoredMarkdown != null) markdown = restoredMarkdown
    }
    var draftNote by remember(project.id) {
        mutableStateOf(
            when {
                restoredInputs.isNotEmpty() -> context.getString(dev.ninfenz.mobile.R.string.delivery_draft_restored)
                protocolPrefill.isNotEmpty() -> context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.delivery_protocol_prefill, protocolPrefill.size, protocolPrefill.size)
                else -> null
            }
        )
    }

    fun pasteSlot(slot: String) {
        val manager = context.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as? android.content.ClipboardManager
        val text = manager?.primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(context)?.toString()
        if (text.isNullOrBlank()) {
            error = CoreResponse.failure("NF-E-003", context.getString(dev.ninfenz.mobile.R.string.delivery_slot_import_empty), context.getString(dev.ninfenz.mobile.R.string.delivery_slot_import_empty_fix), 2).error
            return
        }
        val adapted = SlotTextAdapter.adapt(text, "clipboard.md")
        slotImportTarget = slot
        slotImportSource = "clipboard"
        slotImportFormat = adapted.format
        slotImportOriginal = adapted.original.length
        slotImportAdapted = adapted.adapted.length
        slotImportText = adapted.adapted
    }

    val slotPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri == null) { slotImportTarget = null; return@rememberLauncherForActivityResult }
        val target = slotImportTarget ?: return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val name = uri.lastPathSegment?.substringAfterLast('/') ?: "import"
                val raw = withContext(Dispatchers.IO) { UriIo.readText(context, uri) ?: "" }
                if (raw.isBlank()) {
                    error = CoreResponse.failure("NF-E-003", context.getString(dev.ninfenz.mobile.R.string.delivery_slot_import_empty), context.getString(dev.ninfenz.mobile.R.string.delivery_slot_import_empty_fix), 2).error
                    slotImportTarget = null
                } else {
                    val adapted = SlotTextAdapter.adapt(raw, name)
                    slotImportSource = name
                    slotImportFormat = adapted.format
                    slotImportOriginal = adapted.original.length
                    slotImportAdapted = adapted.adapted.length
                    slotImportText = adapted.adapted
                }
            } catch (t: Throwable) {
                error = CoreResponse.failure("NF-E-003", context.getString(dev.ninfenz.mobile.R.string.delivery_slot_import_fail, t.message ?: t.javaClass.simpleName), context.getString(dev.ninfenz.mobile.R.string.delivery_slot_import_fail_fix), 2).error
                slotImportTarget = null
            }
        }
    }

    fun openSlotPicker(slot: String) {
        slotImportTarget = slot
        slotPicker.launch(arrayOf("*/*"))
    }

    val batchPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val name = uri.lastPathSegment?.substringAfterLast('/') ?: "batch"
                val raw = withContext(Dispatchers.IO) {
                    UriIo.readTextLimited(context, uri, MAX_IMPORT_CHARS, context.getString(dev.ninfenz.mobile.R.string.delivery_slot_import_too_large))
                }
                val chunks = SlotBatchImporter.chunks(raw, name)
                if (chunks.isEmpty()) {
                    error = CoreResponse.failure("NF-E-003", context.getString(dev.ninfenz.mobile.R.string.delivery_slot_batch_empty), context.getString(dev.ninfenz.mobile.R.string.delivery_slot_batch_empty_fix), 2).error
                } else {
                    batchSource = name
                    batchNote = null
                    batchChunks = chunks
                }
            } catch (t: Throwable) {
                error = CoreResponse.failure("NF-E-003", context.getString(dev.ninfenz.mobile.R.string.delivery_slot_import_fail, t.message ?: t.javaClass.simpleName), context.getString(dev.ninfenz.mobile.R.string.delivery_slot_import_fail_fix), 2).error
            }
        }
    }

    fun shouldVerify(format: String): Boolean {
        val profile = selectedPreflight ?: return true
        val flag = profile.config[format]?.toString()?.trim('"')?.toBooleanStrictOrNull() ?: return true
        return flag
    }

    fun recordExport(format: String, file: File?, manifest: String?, verify: Boolean = true) {
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

    fun applyBatch(onlyEmpty: Boolean) {
        val slots = plan?.slots ?: return
        if (slots.isEmpty() || batchChunks.isEmpty()) return
        val before = inputs
        val result = SlotBatchImporter.apply(batchChunks, slots, inputs, onlyEmpty)
        batchUndo = before
        inputs = result.values
        batchNote = context.getString(
            dev.ninfenz.mobile.R.string.delivery_slot_batch_done,
            result.filled,
            result.skipped,
            result.appended,
            result.dropped
        )
        batchChunks = emptyList()
    }

    var busy by remember { mutableStateOf(false) }
    val exportBlocked = busy || contractUnsatisfiable

    val latestInputs by rememberUpdatedState(inputs)
    val latestPlan by rememberUpdatedState(plan)
    LaunchedEffect(project.id, plan, rawPlan, inputs) {
        if (plan != null) {
            delay(500)
            withContext(Dispatchers.IO) { draftStore.save(project.id, inputs, rawPlan, markdown) }
        }
    }
    LaunchedEffect(project.id, restoredPlan) {
        val raw = restoredPlan ?: return@LaunchedEffect
        runCatching { PlanModel.parse(raw) }.onSuccess { parsed ->
            rawPlan = raw
            plan = parsed
            inputs = parsed.slots.associate { slot ->
                val restored = restoredInputs[slot]
                slot to (if (!restored.isNullOrBlank()) restored else contractValues[slot] ?: slotPrefill[slot] ?: "")
            }
        }
    }
    DisposableEffect(project.id) {
        onDispose {
            if (latestPlan != null) draftStore.save(project.id, latestInputs)
        }
    }

    val specOverride = dev.ninfenz.mobile.data.ProjectPaths.specOverride(context.filesDir, project.id)
    LaunchedEffect(pack?.dir?.absolutePath, project.id) {
        loading = true
        loadError = null
        try {
            if (pack != null) artifacts = withContext(Dispatchers.IO) { AuthorArtifactsLoader.load(pack, specOverride) }
        } catch (t: Throwable) {
            loadError = t.message ?: t.javaClass.simpleName
        }
        loading = false
    }

    if (pack == null) {
        Column(modifier = Modifier.fillMaxSize()) {
            NfTopAppBar(title = project.title, onBack = onBack)
            NfEmptyState(
                icon = Icons.Filled.Info,
                title = stringResource(dev.ninfenz.mobile.R.string.delivery_pack_missing_title),
                message = stringResource(dev.ninfenz.mobile.R.string.delivery_pack_missing_body, project.refs.basePackId),
                actionLabel = stringResource(dev.ninfenz.mobile.R.string.pack_open_center),
                onAction = onOpenPacks
            )
        }
        return
    }

    val step = when {
        exportedFile != null -> 3
        markdown != null || report != null -> if (audit) 2 else 3
        plan != null -> 1
        else -> 0
    }
    val specMeta = remember(artifacts?.specJson) {
        artifacts?.let { runCatching { SpecModel.parse(it.specJson) }.orNullLogged("DeliveryScreen") }
    }
    val constraintConflicts = remember(specMeta) { dev.ninfenz.mobile.model.SpecConstraintAudit.conflicts(specMeta?.slots.orEmpty()) }

    fun fillTemplateSlots() {
        val parsed = parsedTemplateSlots
        val next = inputs.toMutableMap()
        var filled = 0
        parsed.forEach { (id, value) ->
            if (!next[id].isNullOrBlank() || requireNotNull(plan).slots.none { it == id }) return@forEach
            val meta = specMeta?.slots?.firstOrNull { it.id == id }
            if (!templateValueAllowed(meta, value)) return@forEach
            next[id] = dev.ninfenz.mobile.model.SlotInput.sanitize(meta?.kind, value)
            filled++
        }
        inputs = next
        android.widget.Toast.makeText(
            context,
            context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.delivery_template_filled, filled, filled),
            android.widget.Toast.LENGTH_SHORT
        ).show()
    }

    fun assemblePayloadOf(raw: JsonObject, current: AuthorArtifacts): JsonObject = buildJsonObject {
        put("plan", raw)
        put("spec", current.specJson)
        put("inputs", buildJsonObject { for ((k, v) in inputs) put(k, v) })
    }

    suspend fun advanceStatus(target: ProjectStatus, assembly: AssemblyArtifact? = null, allowAuditSkip: Boolean = false) {
        when (val advanced = statusStore.advance(project, target, assembly, allowAuditSkip)) {
            is StatusAdvanceResult.Advanced -> {
                status = advanced.to
                statusNote = context.getString(dev.ninfenz.mobile.R.string.delivery_status_note, statusText(context, advanced.to))
                onStatusChanged()
            }
            is StatusAdvanceResult.Failure -> statusNote = context.getString(dev.ninfenz.mobile.R.string.delivery_status_fail, advanced.message)
        }
    }

    suspend fun assembleRepro(md: String, payload: JsonObject) {
        val second = safeCall("assemble", payload)
        val secondMd = second.resultObject()?.let { J.optString(it, "markdown") }
        if (second.ok && !secondMd.isNullOrBlank()) {
            val offset = dev.ninfenz.mobile.data.ReproChecker.firstDifference(
                md.toByteArray(Charsets.UTF_8),
                secondMd.toByteArray(Charsets.UTF_8)
            )
            reproOk = offset == null
            reproText = if (offset == null) {
                context.getString(dev.ninfenz.mobile.R.string.repro_stable)
            } else {
                context.getString(dev.ninfenz.mobile.R.string.repro_diff, offset)
            }
        }
    }

    fun parseReport(result: JsonObject) {
        try {
            report = ReportModel.parse(result)
        } catch (t: Throwable) {
            error = CoreResponse.failure(
                "NF-VAL-001",
                context.getString(dev.ninfenz.mobile.R.string.delivery_report_failed, t.message ?: t.javaClass.simpleName),
                context.getString(dev.ninfenz.mobile.R.string.delivery_report_failed_fix),
                1
            ).error
        }
    }

    suspend fun validateForAssemble(md: String, raw: JsonObject, current: AuthorArtifacts) {
        val validatePayload = buildJsonObject {
            put("markdown", md)
            put("spec", current.specJson)
            put("plan", raw)
            put("level", "L1")
        }
        val response = safeCall("validate", validatePayload)
        val result = response.resultObject()
        if (response.ok && result != null) {
            val second = safeCall("validate", validatePayload)
            val secondResult = second.resultObject()
            if (second.ok && secondResult != null) {
                val offset = dev.ninfenz.mobile.data.ReproChecker.firstDifference(
                    result.toString().toByteArray(Charsets.UTF_8),
                    secondResult.toString().toByteArray(Charsets.UTF_8)
                )
                validateRepro = if (offset == null) {
                    context.getString(dev.ninfenz.mobile.R.string.repro_stable)
                } else {
                    context.getString(dev.ninfenz.mobile.R.string.repro_diff, offset)
                }
            }
        }
        if (result != null) parseReport(result)
        if (!response.ok) error = response.error
        if (report?.verdict == "pass") {
            needsRevalidate = false
            advanceStatus(ProjectStatus.VALIDATED)
        }
    }

    suspend fun runAssemble(raw: JsonObject, current: AuthorArtifacts) {
        val payload = assemblePayloadOf(raw, current)
        val response = safeCall("assemble", payload)
        val result = response.resultObject()
        val md = result?.let { J.optString(it, "markdown") }
        if (response.ok && !md.isNullOrBlank()) {
            assembleRepro(md, payload)
            markdown = md
            versionStore.save(project.id, md)
            report = null
            needsRevalidate = false
            advanceStatus(ProjectStatus.ASSEMBLED, AssemblyArtifact(md.toByteArray(Charsets.UTF_8)))
            validateForAssemble(md, raw, current)
        } else {
            error = response.error ?: CoreResponse.failure(
                "NF-ASM-002",
                context.getString(dev.ninfenz.mobile.R.string.delivery_no_markdown),
                context.getString(dev.ninfenz.mobile.R.string.delivery_no_markdown_fix),
                1
            ).error
        }
        busy = false
    }

    fun startAssemble(current: AuthorArtifacts) {
        val raw = rawPlan ?: return
        busy = true
        error = null
        markdown = null
        report = null
        exportedFile = null
        exportVerify = null
        manifestText = null
        scope.launch { runAssemble(raw, current) }
    }

    suspend fun runValidate(md: String, raw: JsonObject, current: AuthorArtifacts) {
        val validatePayload = buildJsonObject {
            put("markdown", md)
            put("spec", current.specJson)
            put("plan", raw)
            put("level", "L1")
        }
        val response = safeCall("validate", validatePayload)
        val result = response.resultObject()
        if (response.ok && result != null) {
            val second = safeCall("validate", validatePayload)
            val secondResult = second.resultObject()
            if (second.ok && secondResult != null) {
                val offset = dev.ninfenz.mobile.data.ReproChecker.firstDifference(
                    result.toString().toByteArray(Charsets.UTF_8),
                    secondResult.toString().toByteArray(Charsets.UTF_8)
                )
                validateRepro = if (offset == null) {
                    context.getString(dev.ninfenz.mobile.R.string.repro_stable)
                } else {
                    context.getString(dev.ninfenz.mobile.R.string.repro_diff, offset)
                }
            }
        }
        if (result != null) parseReport(result)
        if (!response.ok) error = response.error
        if (report?.verdict == "pass") advanceStatus(ProjectStatus.VALIDATED)
        busy = false
    }

    fun startValidate(current: AuthorArtifacts) {
        val md = markdown ?: return
        val raw = rawPlan ?: return
        busy = true
        error = null
        scope.launch { runValidate(md, raw, current) }
    }

    fun shareFixPrompt(r: ValidateReport) {
        val md = markdown ?: return
        val prompt = CorrectionPrompt.build(md, r)
        val intent = ShareExporter.shareMarkdown(context, "nf-fix-prompt", prompt)
        ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.delivery_share_fix))
    }

    fun signContract(checks: List<Pair<String, Boolean>>) {
        val at = java.time.Instant.now().toString()
        val digest = exportedFile?.let { sha256File(it) }
        runCatching {
            contractStore.sign(project.id, checks.filter { it.second }.map { it.first }, at, digest)
        }.onFailure { statusNote = it.message ?: it.javaClass.simpleName }
        signoff = contractStore.load(project.id)
    }

    fun exportPayload(md: String, dir: File, format: String): JsonObject = buildJsonObject {
        put("markdown", md)
        put("format", format)
        put("out_dir", dir.absolutePath)
        put("manifest", true)
        put("title", project.title)
        put("project_id", project.id)
        if (format == "docx") {
            docxStyles?.let { put("docx_styles", it) }
            docxSectPr?.let { put("docx_sect_pr", it) }
            docxTheme?.let { put("docx_theme", it) }
            docxNumbering?.let { put("docx_numbering", it) }
            docxHeader?.let { put("docx_header", it) }
            docxFooter?.let { put("docx_footer", it) }
        }
    }

    suspend fun exportViaCore(md: String, dir: File, format: String, failures: MutableList<String>, fallbackName: String): File? =
        runCatching {
            val response = safeCall("export", exportPayload(md, dir, format))
            if (!response.ok) throw IllegalStateException(response.error?.message ?: "export failed")
            val raw = response.resultObject()?.get("files")?.toString().orEmpty()
            val name = Regex("\"name\":\"([^\"]+)\"").find(raw)?.groupValues?.getOrNull(1) ?: fallbackName
            File(dir, name)
        }.onFailure { failures += format + ":" + (it.message ?: it.javaClass.simpleName) }.orNullLogged("DeliveryScreen")

    suspend fun exportPreservation(md: String, dir: File, failures: MutableList<String>): File? {
        if (!audit) return null
        return runCatching {
            val lineage = dev.ninfenz.mobile.data.PreservationLineageStore(context.filesDir)
            val created = dev.ninfenz.mobile.data.PreservationExporter.export(
                md, project.title, project.id, dir,
                dev.ninfenz.mobile.data.PreservationOptions(
                    dev.ninfenz.mobile.data.ContractStore(context.filesDir).raw(project.id),
                    grant.toJson().toString(),
                    lineage.load(project.id)
                )
            )
            val reproDir = File(context.cacheDir, "repro-preserve-batch").apply { deleteRecursively(); mkdirs() }
            val second = dev.ninfenz.mobile.data.PreservationExporter.export(
                md, project.title, project.id, reproDir,
                dev.ninfenz.mobile.data.PreservationOptions(
                    dev.ninfenz.mobile.data.ContractStore(context.filesDir).raw(project.id),
                    grant.toJson().toString(),
                    lineage.load(project.id)
                )
            )
            val reproReport = dev.ninfenz.mobile.data.ReproChecker.check(created.file, second.file)
            reproDir.deleteRecursively()
            if (!reproReport.stable) throw IllegalStateException("repro diff " + (reproReport.firstDiff ?: -1))
            val digest = java.security.MessageDigest.getInstance("SHA-256")
                .digest(created.file.readBytes())
                .joinToString("") { "%02x".format(it.toInt() and 0xff) }
            lineage.save(project.id, digest)
            created.file
        }.onFailure { failures += "preservation:" + (it.message ?: it.javaClass.simpleName) }.orNullLogged("DeliveryScreen")
    }

    fun attemptExport(failures: MutableList<String>, label: String, block: () -> File): File? =
        try {
            block()
        } catch (t: Throwable) {
            failures += label + ":" + (t.message ?: t.javaClass.simpleName)
            null
        }

    fun afterExportAll(files: List<File>, failures: List<String>, md: String) {
        batchFiles = files
        specMeta?.let { spec -> fidelityResult = FidelityReconciler.fromSpec(spec, md) }
        exportBatchNote = if (failures.isEmpty()) null else "未生成: " + failures.joinToString(",")
        exportedFile = files.firstOrNull()
        recordExport("batch", files.firstOrNull(), null)
    }

    suspend fun runExportAll(md: String) {
        try {
            val dir = File(File(context.filesDir, "exports/delivery"), "batch-" + System.currentTimeMillis()).apply { mkdirs() }
            val failures = mutableListOf<String>()
            val docxFile = exportViaCore(md, dir, "docx", failures, "result.docx")
            val zipFile = exportViaCore(md, dir, "zip", failures, "result.zip")
            val skillFile = exportViaCore(md, dir, "skill", failures, "result-skill.zip")
            val preserveFile = exportPreservation(md, dir, failures)
            val files = buildList {
                add(File(dir, "result.md").apply { writeText(md, Charsets.UTF_8) })
                docxFile?.let { add(it) }
                zipFile?.let { add(it) }
                skillFile?.let { add(it) }
                preserveFile?.let { add(it) }
                attemptExport(failures, "epub") { dev.ninfenz.mobile.data.EpubExporter.export(md, project.title, dir, epubAuthor, epubLanguage, dev.ninfenz.mobile.data.OutputNaming.resolve(selectedOutputTemplate, project.title, "epub")).file }?.let { add(it) }
                attemptExport(failures, "html") { dev.ninfenz.mobile.data.HtmlExporter.export(md, project.title, dir, dev.ninfenz.mobile.data.OutputNaming.resolve(selectedOutputTemplate, project.title, "html")).file }?.let { add(it) }
                attemptExport(failures, "pdf") { dev.ninfenz.mobile.data.PdfExporter.export(md, project.title, dir, pdfPageSize, pdfIncludeTitle, dev.ninfenz.mobile.data.OutputNaming.resolve(selectedOutputTemplate, project.title, "pdf")).file }?.let { add(it) }
                attemptExport(failures, "nfdoc") { dev.ninfenz.mobile.data.NfDocExporter.export(md, project.title, project.id, dir).file }?.let { add(it) }
            }
            afterExportAll(files, failures, md)
        } catch (t: Throwable) {
            error = CoreError("NF-EXP-002", context.getString(dev.ninfenz.mobile.R.string.export_pdf_failed, t.message ?: t.javaClass.simpleName), context.getString(dev.ninfenz.mobile.R.string.export_failed_fix), null, 1)
        } finally {
            busy = false
        }
    }

    fun startExportAll(md: String) {
        busy = true
        error = null
        batchFiles = emptyList()
        exportBatchNote = null
        scope.launch { runExportAll(md) }
    }

    fun handleExportDone(format: String, file: File?, manifest: String?, report: dev.ninfenz.mobile.data.ReproChecker.Report?, exportMarkdown: String?) {
        exportedFile = file
        val manifestDirect = format in setOf("epub", "pdf", "html", "preserve", "nf-doc", "pdf-ua")
        if (format == "pdf-ua") {
            manifestText = null
            reproOk = report?.stable
            reproText = context.getString(dev.ninfenz.mobile.R.string.delivery_pdfua_note)
        } else if (manifestDirect) {
            manifestText = null
            reproOk = report?.stable
            reproText = report?.let { reproTextStable(it, context) }
        } else {
            manifestText = manifest
            reproOk = report?.stable
            reproText = reproTextFor(report, context)
        }
        recordExport(format, file, if (manifestDirect) null else manifest)
        if (format == "docx") {
            file?.let { exported ->
                docxStyles?.let { applied -> docxStyleAudit = DocxStyleAudit.check(applied, exported) }
                docxHeadingAudit = DocxHeadingAudit.check(exportMarkdown.orEmpty(), exported)
            }
        }
        if (format == "md") {
            scope.launch { advanceStatus(ProjectStatus.EXPORTED, allowAuditSkip = !audit) }
        }
    }

    fun openStyleTemplates() {
        styleTemplates = styleStore.list()
        showStyleTemplates = true
    }

    fun pickStyleTemplate(template: StyleTemplateStore.StyleTemplate) {
        if (!template.sourceFormat.equals("docx", ignoreCase = true)) return
        docxStyles = template.stylesXml
        docxSectPr = template.sectPr.takeIf { it.isNotBlank() }
        docxTheme = template.themeXml.takeIf { it.isNotBlank() }
        docxNumbering = template.numberingXml.takeIf { it.isNotBlank() }
        showStyleTemplates = false
    }

    fun packEvidence(latest: ExportHistoryStore.Entry) {
        val md = markdown ?: return
        evidenceBusy = true
        evidenceNote = null
        scope.launch {
            val result = dev.ninfenz.mobile.data.HardTechEvidence.pack(context, md, File(latest.path))
            evidenceNote = result.message
            evidenceBusy = false
        }
    }

    fun openPreviewEditor(md: String) {
        val parsed = MarkdownBlocks.parse(md)
        previewBlocks = parsed
        previewBaseline = parsed
        previewHistory = emptyList()
        previewRedo = emptyList()
        previewDirty = false
        editingPreview = true
    }
    var deliveryMenu by remember { mutableStateOf(false) }
    var showMacros by remember { mutableStateOf(false) }

    fun applyExportProfile(profile: dev.ninfenz.mobile.data.ExportProfileStore.Profile) {
        docxStyles = profile.styles
        docxSectPr = profile.sectPr
        docxTheme = profile.theme
        docxNumbering = profile.numbering
        docxHeader = profile.header
        docxFooter = profile.footer
        profile.epubAuthor?.let { epubAuthor = it }
        profile.epubLanguage?.let { epubLanguage = it }
        profile.pdfPageSize?.let { pdfPageSize = it }
        profile.pdfIncludeTitle?.let { pdfIncludeTitle = it }
        showExportProfiles = false
    }

    fun removeExportProfile(profile: dev.ninfenz.mobile.data.ExportProfileStore.Profile) {
        exportProfileStore.remove(profile.id)
        exportProfiles = exportProfileStore.load()
    }

    fun assembleAllVariants() {
        val raw = rawPlan ?: return
        val specJson = artifacts?.specJson ?: return
        busy = true
        scope.launch {
            var ok = 0
            var failed = 0
            for (variant in extensionVariants) {
                val variantInputs = inputs.toMutableMap()
                (variant.config["inputs"] as? JsonObject)?.forEach { (key, value) ->
                    if (plan?.slots?.contains(key) == true) variantInputs[key] = value.jsonPrimitive.content
                }
                val response = runCatching {
                    safeCall("assemble", buildJsonObject {
                        put("plan", raw)
                        put("spec", specJson)
                        put("inputs", buildJsonObject { for ((k, v) in variantInputs) put(k, v) })
                    })
                }.orNullLogged("DeliveryScreen")
                val md = response?.resultObject()?.let { J.optString(it, "markdown") }
                if (response?.ok == true && !md.isNullOrBlank()) {
                    versionStore.save(project.id, md)
                    ok++
                } else {
                    failed++
                }
            }
            variantNote = context.getString(dev.ninfenz.mobile.R.string.delivery_batch_assemble_done, ok, failed)
            busy = false
        }
    }

    fun exportVariantFormats(md: String, outDir: File, safe: String, variantId: String): Int {
        var missing = 0
        runCatching {
            dev.ninfenz.mobile.data.HtmlExporter.export(md, project.title, outDir, safe + ".html")
        }.onFailure { missing++ }
        runCatching {
            dev.ninfenz.mobile.data.EpubExporter.export(
                md, project.title, outDir, epubAuthor, epubLanguage, safe + ".epub"
            )
        }.onFailure { missing++ }
        runCatching {
            dev.ninfenz.mobile.data.PdfExporter.export(
                md, project.title, outDir, pdfPageSize, pdfIncludeTitle, safe + ".pdf"
            )
        }.onFailure { missing++ }
        runCatching {
            val doc = dev.ninfenz.mobile.model.NfDocModel.fromMarkdown(
                project.title + " · " + variantId,
                project.id + "/" + variantId,
                md
            )
            File(outDir, safe + ".nfdoc.json").writeText(
                dev.ninfenz.mobile.model.NfDocModel.toJson(doc).toString() + "\n",
                Charsets.UTF_8
            )
        }.onFailure { missing++ }
        return missing
    }

    fun exportAllVariants() {
        val raw = rawPlan ?: return
        val specJson = artifacts?.specJson ?: return
        busy = true
        scope.launch {
            val outDir = File(File(context.filesDir, "exports"), "variants").apply { mkdirs() }
            var ok = 0
            var failed = 0
            var missingFormats = 0
            for (variant in extensionVariants) {
                val variantInputs = inputs.toMutableMap()
                (variant.config["inputs"] as? JsonObject)?.forEach { (key, value) ->
                    if (plan?.slots?.contains(key) == true) variantInputs[key] = value.jsonPrimitive.content
                }
                val response = runCatching {
                    safeCall("assemble", buildJsonObject {
                        put("plan", raw)
                        put("spec", specJson)
                        put("inputs", buildJsonObject { for ((k, v) in variantInputs) put(k, v) })
                    })
                }.orNullLogged("DeliveryScreen")
                val md = response?.resultObject()?.let { J.optString(it, "markdown") }
                if (response?.ok == true && !md.isNullOrBlank()) {
                    val safe = variant.id.replace(Regex("[^A-Za-z0-9._-]"), "_")
                    File(outDir, safe + ".md").writeText(md, Charsets.UTF_8)
                    missingFormats += exportVariantFormats(md, outDir, safe, variant.id)
                    ok++
                } else {
                    failed++
                }
            }
            val suffix = if (missingFormats > 0) {
                context.getString(dev.ninfenz.mobile.R.string.delivery_batch_export_partial, missingFormats)
            } else ""
            variantNote = context.getString(dev.ninfenz.mobile.R.string.delivery_batch_export_done, ok, failed) + suffix
            busy = false
        }
    }


    fun applyVariant(variant: dev.ninfenz.mobile.data.ExtensionStore.Contribution) {
        val objectInputs = variant.config["inputs"] as? JsonObject
        val before = inputs
        val next = inputs.toMutableMap()
        var applied = 0
        var skipped = 0
        objectInputs?.forEach { (key, value) ->
            val text = value.jsonPrimitive.content
            if (plan?.slots?.contains(key) == true) {
                next[key] = text
                applied++
            } else {
                skipped++
            }
        }
        if (applied > 0) {
            batchUndo = before
            inputs = next
            variantNote = context.getString(dev.ninfenz.mobile.R.string.delivery_variant_applied, variant.id) +
                if (skipped > 0) " · skipped=" + skipped else ""
            showVariants = false
        }
    }
    var macroItems by remember { mutableStateOf(emptyList<MacroStore.Macro>()) }
    var macroResult by remember { mutableStateOf<MacroRunResult?>(null) }
    var macroBatchResult by remember { mutableStateOf<MacroBatchResult?>(null) }
    var macroSelected by remember { mutableStateOf<MacroStore.Macro?>(null) }
    var macroParams by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    var showMacroParams by remember { mutableStateOf(false) }
    var showMacroBatchConfirm by remember { mutableStateOf(false) }
    val capabilityRevision = rememberCapabilityRevision()

    fun macroExecutor(): DeliveryMacroExecutor = DeliveryMacroExecutor(
        context = context,
        projectId = project.id,
        spec = artifacts?.specJson,
        plan = rawPlan,
        inputs = inputs,
        markdownProvider = { markdown },
        onMarkdown = { next ->
            markdown = next
            needsRevalidate = true
        }
    )

    suspend fun executeMacro(macro: MacroStore.Macro, values: Map<String, String>) {
        val bound = MacroRunner.bind(macro.json, values)
        val plan = MacroStore(context.filesDir).plan(bound).orNullLogged("DeliveryScreen")
        macroBatchResult = null
        macroResult = if (plan == null) {
            MacroRunResult("failed", emptyList(), 1)
        } else {
            val executor = macroExecutor()
            MacroRunner.run(plan) { action, params -> executor.run(action, params) }
        }
    }

    suspend fun executeMacroBatch() {
        val plans = macroItems.mapNotNull { macro -> MacroStore(context.filesDir).plan(macro.json).orNullLogged("DeliveryScreen") }
        macroResult = null
        macroBatchResult = if (plans.isEmpty()) {
            MacroBatchResult("failed", emptyList(), 1)
        } else {
            val executor = macroExecutor()
            MacroRunner.runBatch(plans) { action, params -> executor.run(action, params) }
        }
    }
    var showBrowsePlan by remember { mutableStateOf(false) }
    var activeStep by remember(project.id) { mutableStateOf(step) }
    var showLeaveConfirm by remember { mutableStateOf(false) }
    val hasWork = exportedFile == null && (plan != null || markdown != null || inputs.values.any { it.isNotBlank() })
    BackHandler {
        when {
            activeStep > 0 -> activeStep = if (!audit && activeStep == 3) 1 else activeStep - 1
            hasWork -> showLeaveConfirm = true
            else -> onBack()
        }
    }
    val deliveryScroll = rememberScrollState()
    Column(modifier = Modifier.fillMaxSize().imePadding()) {
        NfTopAppBar(
            title = stringResource(dev.ninfenz.mobile.R.string.delivery_title, project.title),
            onBack = { if (hasWork) showLeaveConfirm = true else onBack() },
            actions = {
                IconButton(onClick = { deliveryMenu = true }, modifier = Modifier.size(48.dp)) {
                    Icon(Icons.Filled.MoreVert, contentDescription = stringResource(dev.ninfenz.mobile.R.string.common_more))
                }
                DropdownMenu(expanded = deliveryMenu, onDismissRequest = { deliveryMenu = false }) {
                    if (plan != null) {
                        DropdownMenuItem(
                            text = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_assemble)) },
                            onClick = {
                                deliveryMenu = false
                                scope.launch { assembleRequester.bringIntoView() }
                            }
                        )
                    }
                    if (capabilityRevision >= 0 && CapabilityRegistry.isEnabled(Capability.MACROS)) {
                        DropdownMenuItem(
                            text = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_run_macro)) },
                            onClick = {
                                deliveryMenu = false
                                macroItems = MacroStore(context.filesDir).list()
                                showMacros = true
                            }
                        )
                    }
                    if (plan != null || inputs.isNotEmpty() || markdown != null || report != null) {
                        DropdownMenuItem(
                            text = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_reset)) },
                            onClick = { deliveryMenu = false; showResetConfirm = true }
                        )
                    }
                    if (capabilityRevision >= 0 && CapabilityRegistry.isEnabled(Capability.SOURCES)) {
                        DropdownMenuItem(
                            text = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_sources_appendix)) },
                            onClick = {
                                deliveryMenu = false
                                val base = markdown.orEmpty()
                                val next = SourceStore(context.filesDir, project.id).renderCitations(base)
                                if (next == base) {
                                    variantNote = context.getString(dev.ninfenz.mobile.R.string.delivery_sources_none)
                                } else {
                                    markdown = next
                                    needsRevalidate = true
                                    variantNote = context.getString(dev.ninfenz.mobile.R.string.delivery_sources_appended)
                                }
                            }
                        )
                    }
                    DropdownMenuItem(
                        text = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_fidelity)) },
                        onClick = {
                            deliveryMenu = false
                            val currentMarkdown = markdown.orEmpty()
                            val spec = specMeta
                            if (currentMarkdown.isBlank() || spec == null) {
                                variantNote = context.getString(dev.ninfenz.mobile.R.string.delivery_fidelity_none)
                            } else {
                                fidelityResult = FidelityReconciler.fromSpec(spec, currentMarkdown)
                            }
                        }
                    )
                    DropdownMenuItem(
                        text = { Text(stringResource(dev.ninfenz.mobile.R.string.patch_title)) },
                        onClick = { deliveryMenu = false; onPatch() }
                    )
                }
            }
        )
        val stepLabels = if (audit) listOf(
            stringResource(dev.ninfenz.mobile.R.string.delivery_plan),
            stringResource(dev.ninfenz.mobile.R.string.delivery_slots),
            stringResource(dev.ninfenz.mobile.R.string.delivery_assemble_validate),
            stringResource(dev.ninfenz.mobile.R.string.delivery_export_section)
        ) else listOf(
            stringResource(dev.ninfenz.mobile.R.string.delivery_plan),
            stringResource(dev.ninfenz.mobile.R.string.delivery_slots),
            stringResource(dev.ninfenz.mobile.R.string.delivery_export_section)
        )
        NfStepStrip(
            steps = stepLabels,
            current = if (!audit && activeStep >= 3) 2 else activeStep,
            onStepClick = { i ->
                activeStep = if (!audit && i == 2) 3 else i
            }
        )
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(deliveryScroll)
                .padding(bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
        ) {
            Column(
                modifier = Modifier.padding(horizontal = NfSpacing.page),
                verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    NfStatusChip(statusText(context, status))
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.delivery_pack_label, project.refs.basePackId, project.refs.basePackVersion),
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.weight(1f),
                        textAlign = androidx.compose.ui.text.style.TextAlign.End
                    )
                }
                specMeta?.let { meta ->
                    Text(
                        meta.title + " · v" + meta.version,
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Text(stringResource(if (audit) dev.ninfenz.mobile.R.string.delivery_note else dev.ninfenz.mobile.R.string.delivery_note_daily), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            statusNote?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
            if (audit && needsRevalidate) {
                Text(
                    stringResource(dev.ninfenz.mobile.R.string.delivery_need_revalidate),
                    style = NfType.meta,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(horizontal = NfSpacing.page)
                )
            }
            if (contractUnsatisfiable) {
                Text(
                    stringResource(dev.ninfenz.mobile.R.string.delivery_contract_unsat),
                    style = NfType.meta,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(horizontal = NfSpacing.page)
                )
            }
            if (loading) NfLoadingState()
            if (loadError != null) {
                NfErrorCard("NF-PCK-003", stringResource(dev.ninfenz.mobile.R.string.delivery_load_error, requireNotNull(loadError)), stringResource(dev.ninfenz.mobile.R.string.delivery_load_fix), modifier = Modifier.padding(horizontal = NfSpacing.page))
            }
            error?.let { err -> NfErrorCard(err.code, err.message, err.fix, modifier = Modifier.padding(horizontal = NfSpacing.page)) }

            LaunchedEffect(specMeta, inputs) {
                missingRequired = specMeta?.slots?.filter { it.required && (it.visibleIf?.let { c -> inputs[c.slot] == c.equals } ?: true) && inputs[it.id].isNullOrBlank() }?.map { it.id }.orEmpty()
                oversizedSlots = specMeta?.slots?.filter { slot ->
                    val text = inputs[slot.id].orEmpty()
                    (slot.minChars != null && text.isNotBlank() && text.length < slot.minChars) || (slot.maxChars != null && text.length > slot.maxChars)
                }?.map { it.id }.orEmpty()
                constraintViolations = specMeta?.slots?.filter { slot ->
                    val text = inputs[slot.id].orEmpty()
                    val patternBad = slot.pattern?.let { pattern ->
                        text.isNotBlank() && runCatching { Regex(pattern).containsMatchIn(text) }.getOrDefault(false).not()
                    } == true
                    val nonEmptyBad = slot.nonEmpty && (slot.required || text.isNotBlank()) && text.isBlank()
                    val prefixBad = slot.startsWith?.let { text.isNotBlank() && !text.startsWith(it) } == true
                    val suffixBad = slot.endsWith?.let { text.isNotBlank() && !text.endsWith(it) } == true
                    patternBad || nonEmptyBad || prefixBad || suffixBad
                }?.map { it.id }.orEmpty()
            }
            val exportMarkdown = if (audit && (needsRevalidate || report?.verdict == "fail")) null else markdown
            val current = artifacts
            suspend fun compilePlan(art: AuthorArtifacts) {
                busy = true
                error = null
                val response = safeCall("graph-compile", buildJsonObject {
                    put("graph", art.graphJson)
                    put("spec", art.specJson)
                })
                val obj = response.resultObject()
                if (response.ok && obj != null) {
                    try {
                        val parsed = PlanModel.parse(obj)
                        plan = parsed
                        rawPlan = obj
                        inputs = parsed.slots.associate { slot ->
                            val restored = restoredInputs[slot]
                            slot to (if (!restored.isNullOrBlank()) restored else contractValues[slot] ?: slotPrefill[slot] ?: "")
                        }
                        draftStore.save(project.id, inputs, obj)
                        draftNote = if (restoredInputs.isNotEmpty()) context.getString(dev.ninfenz.mobile.R.string.delivery_draft_restored) else null
                        markdown = null
                        report = null
                        needsRevalidate = false
                        exportedFile = null
                        manifestText = null
                        batchChunks = emptyList()
                        batchNote = null
                    } catch (t: Throwable) {
                        error = CoreResponse.failure(
                            "NF-ASM-003",
                            context.getString(dev.ninfenz.mobile.R.string.delivery_plan_failed, t.message ?: t.javaClass.simpleName),
                            context.getString(dev.ninfenz.mobile.R.string.delivery_plan_failed_fix),
                            1
                        ).error
                    }
                } else {
                    error = response.error
                }
                busy = false
            }
            LaunchedEffect(current) {
                if (current != null && plan == null && restoredPlan == null) compilePlan(current)
            }
            if (current != null) {
                if (activeStep == 0) {
                    DeliveryPlanSection(
                        plan = plan,
                        busy = busy,
                        constraintConflicts = constraintConflicts,
                        onBrowsePlan = { showBrowsePlan = true },
                        onCompile = { scope.launch { compilePlan(current) } }
                    )
                }
                if (activeStep == 1) {
                    DeliverySlotsSection(
                        DeliverySlotsArgs(
                            plan = plan,
                            specMeta = specMeta,
                            inputs = inputs,
                            parsedTemplateSlots = parsedTemplateSlots,
                            batchNote = batchNote,
                            variantNote = variantNote,
                            draftNote = draftNote,
                            batchUndo = batchUndo,
                            hasVariants = extensionVariants.isNotEmpty(),
                            hasTransforms = extensionTransforms.isNotEmpty(),
                            onShowConstraintLens = { showConstraintLens = true },
                            onBatchImport = { batchPicker.launch(arrayOf("*/*")) },
                            onShowPresets = { showPresets = true },
                            onShowVariants = { showVariants = true },
                            onShowTransforms = { showTransforms = true },
                            onUndoBatch = { snapshot ->
                                inputs = snapshot
                                batchUndo = null
                                batchNote = context.getString(dev.ninfenz.mobile.R.string.delivery_slot_batch_undo_done)
                            },
                            onInputsChange = { inputs = it },
                            onPaste = { pasteSlot(it) },
                            onOpenPicker = { openSlotPicker(it) },
                            onFillTemplate = { fillTemplateSlots() }
                        )
                    )
                }
                if (audit && activeStep == 2) {
                    DeliveryAssembleSection(
                        DeliveryAssembleArgs(
                            needsRevalidate = needsRevalidate,
                            busy = busy,
                            canAssemble = !busy && rawPlan != null && missingRequired.isEmpty() && oversizedSlots.isEmpty() && constraintViolations.isEmpty(),
                            canValidate = !busy && markdown != null && rawPlan != null,
                            missingRequired = missingRequired,
                            oversizedSlots = oversizedSlots,
                            constraintViolations = constraintViolations,
                            markdown = markdown,
                            exportMarkdown = exportMarkdown,
                            report = report,
                            validateRepro = validateRepro,
                            signoff = signoff,
                            exportedFile = exportedFile,
                            plan = plan,
                            specMeta = specMeta,
                            inputs = inputs,
                            assembleRequester = assembleRequester,
                            validateRequester = validateRequester,
                            onAssemble = { startAssemble(current) },
                            onValidate = { startValidate(current) },
                            onShareFix = { r -> shareFixPrompt(r) },
                            onSign = { checks -> signContract(checks) },
                            onGoValidate = { scope.launch { validateRequester.bringIntoView() } }
                        )
                    )
                }
                if (activeStep == 3) {
                    DeliveryExportSection(
                        DeliveryExportArgs(
                            project = project,
                            markdown = markdown,
                            exportMarkdown = exportMarkdown,
                            report = report,
                            exportedFile = exportedFile,
                            busy = busy,
                            contractUnsatisfiable = contractUnsatisfiable,
                            exportBlocked = exportBlocked,
                            batchFiles = batchFiles,
                            exportBatchNote = exportBatchNote,
                            docxStyles = docxStyles,
                            docxSectPr = docxSectPr,
                            docxTheme = docxTheme,
                            docxNumbering = docxNumbering,
                            docxHeader = docxHeader,
                            docxFooter = docxFooter,
                            epubAuthor = epubAuthor,
                            epubLanguage = epubLanguage,
                            pdfPageSize = pdfPageSize,
                            pdfIncludeTitle = pdfIncludeTitle,
                            selectedOutputTemplate = selectedOutputTemplate,
                            audit = audit,
                            grant = grant,
                            capabilityRevision = capabilityRevision,
                            styleTemplates = styleTemplates,
                            showStyleTemplates = showStyleTemplates,
                            docxStyleAudit = docxStyleAudit,
                            docxHeadingAudit = docxHeadingAudit,
                            outputRuleNote = outputRuleNote,
                            exportNotice = exportNotice,
                            exportEntries = exportEntries,
                            manifestText = manifestText,
                            exportVerify = exportVerify,
                            reproText = reproText,
                            reproOk = reproOk,
                            recentExpanded = recentExpanded,
                            evidenceBusy = evidenceBusy,
                            evidenceNote = evidenceNote,
                            scope = scope,
                            onBusy = { busy = it },
                            onError = { error = it },
                            onExportAll = { exportMarkdown?.let { md -> startExportAll(md) } },
                            onExportDone = { format, file, manifest, report -> handleExportDone(format, file, manifest, report, exportMarkdown) },
                            onShowGrant = { showGrant = true },
                            onOpenStyleTemplates = { openStyleTemplates() },
                            onDismissStyleTemplates = { showStyleTemplates = false },
                            onPickStyleTemplate = { template -> pickStyleTemplate(template) },
                            onShowSaveExportProfile = { showSaveExportProfile = true },
                            onShowExportProfiles = { exportProfiles = exportProfileStore.load(); showExportProfiles = true },
                            onShowOutputRules = { showOutputRules = true },
                            onShowPreflight = { showPreflight = true },
                            onEpubAuthor = { epubAuthor = it },
                            onEpubLanguage = { epubLanguage = it },
                            onPdfPageSize = { pdfPageSize = it },
                            onPdfIncludeTitle = { pdfIncludeTitle = it },
                            onPickReference = { referencePicker.launch(arrayOf("application/vnd.openxmlformats-officedocument.wordprocessingml.document")) },
                            onBack = onBack,
                            onToggleRecent = { recentExpanded = !recentExpanded },
                            onShowTrash = { showTrash = true },
                            onShowAllExports = { showAllExports = true },
                            onClearExports = { exportHistory.clear(); exportEntries = emptyList() },
                            onPendingTrash = { pendingTrash = it },
                            onEvidence = { latest -> packEvidence(latest) }
                        )
                    )
                    DeliveryPreviewSection(
                        DeliveryPreviewArgs(
                            markdown = markdown,
                            project = project,
                            sampleStore = sampleStore,
                            copyMarkdown = { clipboard.setText(AnnotatedString(it)) },
                            onShowVersions = { showVersions = true },
                            onEditPreview = { openPreviewEditor(it) },
                            onFullPreview = { showFullPreview = true }
                        )
                    )
                }
            }
        }
    }

    if (showSaveExportProfile) {
        AlertDialog(
            onDismissRequest = { showSaveExportProfile = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.export_profile_save)) },
            text = {
                OutlinedTextField(
                    value = exportProfileName,
                    onValueChange = { exportProfileName = it },
                    label = { Text(stringResource(dev.ninfenz.mobile.R.string.export_profile_name)) },
                    singleLine = true
                )
            },
            confirmButton = {
                TextButton(enabled = exportProfileName.isNotBlank(), onClick = {
                    exportProfiles = exportProfileStore.save(dev.ninfenz.mobile.data.ExportProfileStore.ProfileInput(exportProfileName, docxStyles, docxSectPr, docxTheme, docxNumbering, docxHeader, docxFooter, epubAuthor, epubLanguage, pdfPageSize, pdfIncludeTitle))
                    exportProfileName = ""
                    showSaveExportProfile = false
                }) { Text(stringResource(android.R.string.ok)) }
            },
            dismissButton = { TextButton(onClick = { showSaveExportProfile = false }) { Text(stringResource(android.R.string.cancel)) } }
        )
    }

    if (showExportProfiles) {
        AlertDialog(
            onDismissRequest = { showExportProfiles = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.export_profiles)) },
            text = {
                Column(modifier = Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    val allProfiles = exportProfiles + extensionProfiles
                    if (allProfiles.isEmpty()) Text(stringResource(dev.ninfenz.mobile.R.string.export_profiles_empty), style = NfType.meta)
                    allProfiles.forEach { profile ->
                        ExportProfileRow(profile, onApply = { applyExportProfile(it) }, onRemove = { removeExportProfile(it) })
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showExportProfiles = false }) { Text(stringResource(android.R.string.ok)) } }
        )
    }

    if (showOutputRules) {
        AlertDialog(
            onDismissRequest = { showOutputRules = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_output_rule)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    TextButton(onClick = {
                        selectedOutputTemplate = null
                        outputRuleNote = context.getString(dev.ninfenz.mobile.R.string.delivery_output_rule_default)
                        showOutputRules = false
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_output_rule_default)) }
                    if (outputRules.isEmpty()) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_output_rule_empty), style = NfType.meta)
                    }
                    outputRules.forEach { rule ->
                        val template = rule.config["template"]?.toString()?.trim('"')?.takeIf { it.isNotBlank() }
                        TextButton(onClick = {
                            selectedOutputTemplate = template
                            outputRuleNote = rule.id
                            showOutputRules = false
                        }) { Text(rule.id + " · " + (template ?: "")) }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showOutputRules = false }) { Text(stringResource(android.R.string.cancel)) } }
        )
    }
    if (showPreflight) {
        AlertDialog(
            onDismissRequest = { showPreflight = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_preflight)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    TextButton(onClick = { selectedPreflight = null; showPreflight = false }) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_preflight_default))
                    }
                    if (preflightProfiles.isEmpty()) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_preflight_empty), style = NfType.meta)
                    }
                    preflightProfiles.forEach { profile ->
                        TextButton(onClick = { selectedPreflight = profile; showPreflight = false }) {
                            Text(profile.id)
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showPreflight = false }) { Text(stringResource(android.R.string.cancel)) } }
        )
    }

    if (showSavePreset) {
        AlertDialog(
            onDismissRequest = { showSavePreset = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_save_preset)) },
            text = {
                OutlinedTextField(
                    value = presetName,
                    onValueChange = { presetName = it },
                    label = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_preset_name)) },
                    singleLine = true
                )
            },
            confirmButton = {
                TextButton(enabled = presetName.isNotBlank(), onClick = {
                    presetStore.save(project.id, presetName, inputs)
                    presetName = ""
                    showSavePreset = false
                }) { Text(stringResource(android.R.string.ok)) }
            },
            dismissButton = { TextButton(onClick = { showSavePreset = false }) { Text(stringResource(android.R.string.cancel)) } }
        )
    }

    if (showVariants) {
        AlertDialog(
            onDismissRequest = { showVariants = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_variants)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    TextButton(enabled = rawPlan != null && !busy, onClick = { assembleAllVariants() }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_batch_assemble)) }
                    TextButton(enabled = rawPlan != null && !busy, onClick = { exportAllVariants() }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_batch_export)) }
                    extensionVariants.forEach { variant ->
                        TextButton(onClick = { applyVariant(variant) }) { Text(variant.id) }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showVariants = false }) { Text(stringResource(android.R.string.cancel)) } }
        )
    }
    if (showTransforms) {
        AlertDialog(
            onDismissRequest = { showTransforms = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_transforms)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    extensionTransforms.forEach { recipe ->
                        TextButton(onClick = {
                            val kind = recipe.config["kind"]?.jsonPrimitive?.content.orEmpty()
                            val a = recipe.config["a"]?.jsonPrimitive?.content.orEmpty()
                            val b = recipe.config["b"]?.jsonPrimitive?.content.orEmpty()
                            val transform = dev.ninfenz.mobile.model.FlashFillModel.Transform(kind, a, b)
                            val before = inputs
                            val next = inputs.mapValues { (_, value) -> if (value.isNotBlank()) transform.apply(value) else value }
                            if (next != before) {
                                batchUndo = before
                                inputs = next
                                variantNote = context.getString(dev.ninfenz.mobile.R.string.delivery_transform_applied, recipe.id)
                                showTransforms = false
                            }
                        }) { Text(recipe.id) }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showTransforms = false }) { Text(stringResource(android.R.string.cancel)) } }
        )
    }

    if (showPresets) {
        val presets = remember(showPresets) { presetStore.load(project.id) }
        AlertDialog(
            onDismissRequest = { showPresets = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_presets)) },
            text = {
                Column(modifier = Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    if (assemblyRecipes.isNotEmpty()) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_assembly_recipes), style = NfType.meta)
                        assemblyRecipes.forEach { recipe ->
                            val name = recipe.config["name"]?.toString()?.trim('"')?.ifBlank { recipe.id } ?: recipe.id
                            val recipeInputs = (recipe.config["inputs"] as? JsonObject)?.mapValues { it.value.jsonPrimitive.content }.orEmpty()
                            TextButton(onClick = {
                                presetStore.save(project.id, name, recipeInputs)
                                showPresets = false
                                variantNote = context.getString(dev.ninfenz.mobile.R.string.delivery_assembly_recipe_saved, name)
                            }) { Text(recipe.id) }
                        }
                    }
                    if (presets.isEmpty()) Text(stringResource(dev.ninfenz.mobile.R.string.delivery_presets_empty), style = NfType.meta)
                    presets.forEach { preset ->
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Text(preset.name + " · " + preset.inputs.size, style = NfType.meta)
                            Row {
                                TextButton(onClick = {
                                    inputs = inputs + preset.inputs
                                    showPresets = false
                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_apply_preset)) }
                                TextButton(onClick = { presetStore.remove(project.id, preset.id); showPresets = false }) { Text(stringResource(dev.ninfenz.mobile.R.string.inbox_remove)) }
                            }
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showSavePreset = true; showPresets = false }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_save_preset)) } },
            dismissButton = { TextButton(onClick = { showPresets = false }) { Text(stringResource(android.R.string.cancel)) } }
        )
    }

    if (showVersions) {
        val versions = remember(showVersions) { versionStore.load(project.id) }
        AlertDialog(
            onDismissRequest = { showVersions = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_versions)) },
            text = {
                Column(modifier = Modifier.heightIn(max = 480.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    if (versions.isEmpty()) Text(stringResource(dev.ninfenz.mobile.R.string.delivery_versions_empty), style = NfType.meta)
                    versions.forEachIndexed { index, version ->
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                "#" + (versions.size - index) + " · " + java.text.SimpleDateFormat("MM-dd HH:mm", java.util.Locale.getDefault()).format(java.util.Date(version.at)),
                                style = NfType.meta
                            )
                            Row {
                                TextButton(onClick = {
                                    compareVersionText = version.markdown
                                    compareVersionLabel = "#" + (versions.size - index)
                                    showVersions = false
                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_compare)) }
                                TextButton(onClick = {
                                    markdown = version.markdown
                                    needsRevalidate = true
                                    activeStep = if (audit) 2 else 3
                                    showVersions = false
                                }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_restore_version)) }
                            }
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showVersions = false }) { Text(stringResource(android.R.string.ok)) } }
        )
    }

    compareVersionText?.let { oldText ->
        val report = TextDiff.diff(oldText, markdown.orEmpty())
        val visible = report.lines.take(400)
        AlertDialog(
            onDismissRequest = { compareVersionText = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_compare) + " " + compareVersionLabel) },
            text = {
                Column(modifier = Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    if (report.changed == 0) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_compare_empty), style = NfType.meta)
                    }
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.delivery_compare_summary, report.added, report.removed),
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    if (report.degraded) {
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.delivery_compare_degraded),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.error
                        )
                    }
                    visible.forEach { line ->
                        val prefix = when (line.kind) {
                            DiffKind.ADD -> "+ "
                            DiffKind.REMOVE -> "- "
                            DiffKind.EQUAL -> "  "
                        }
                        Text(
                            prefix + line.text,
                            style = NfType.meta,
                            color = when (line.kind) {
                                DiffKind.ADD -> MaterialTheme.colorScheme.primary
                                DiffKind.REMOVE -> MaterialTheme.colorScheme.error
                                DiffKind.EQUAL -> MaterialTheme.colorScheme.onSurfaceVariant
                            }
                        )
                    }
                    if (report.lines.size > visible.size) {
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.delivery_compare_truncated, visible.size),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            },
            confirmButton = { TextButton(onClick = { compareVersionText = null }) { Text(stringResource(android.R.string.ok)) } }
        )
    }

    if (showMacros) {
        AlertDialog(
            onDismissRequest = { showMacros = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_run_macro)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    if (macroItems.isEmpty()) {
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.delivery_macro_none),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    macroItems.forEach { macro ->
                        TextButton(onClick = {
                            macroSelected = macro
                            macroParams = MacroRunner.placeholders(macro.json).associateWith { "" }
                            showMacroParams = true
                        }) { Text(macro.title.ifBlank { macro.id }) }
                    }
                    if (macroItems.isNotEmpty()) {
                        TextButton(onClick = {
                            showMacros = false
                            showMacroBatchConfirm = true
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_macro_batch_run)) }
                    }
                    macroBatchResult?.let { batch ->
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.delivery_macro_batch_status, batch.status, batch.failures),
                            style = NfType.meta,
                            color = if (batch.failures == 0) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
                        )
                        batch.runs.forEachIndexed { index, run ->
                            Text("#" + (index + 1) + " · " + run.status + " · " + run.failures, style = NfType.meta)
                        }
                    }
                    macroResult?.let { run ->
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.delivery_macro_done, run.status, run.failures),
                            style = NfType.meta,
                            color = if (run.failures == 0) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
                        )
                        run.steps.forEach { step ->
                            Text(
                                step.id + " " + step.action + " · " + step.status +
                                    (if (step.message.isBlank()) "" else " · " + step.message),
                                style = NfType.meta,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showMacros = false }) { Text(stringResource(android.R.string.cancel)) } }
        )
    }

    macroSelected?.let { macro ->
        if (showMacroParams) {
            AlertDialog(
                onDismissRequest = { showMacroParams = false },
                title = { Text(macro.title.ifBlank { macro.id }) },
                text = {
                    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                        if (macroParams.isEmpty()) {
                            Text(stringResource(dev.ninfenz.mobile.R.string.delivery_macro_no_params), style = NfType.meta)
                        }
                        macroParams.keys.forEach { key ->
                            OutlinedTextField(
                                value = macroParams[key].orEmpty(),
                                onValueChange = { value -> macroParams = macroParams + (key to value) },
                                label = { Text(key) },
                                singleLine = true,
                                modifier = Modifier.fillMaxWidth()
                            )
                        }
                    }
                },
                confirmButton = {
                    TextButton(onClick = {
                        scope.launch {
                            executeMacro(macro, macroParams)
                            showMacroParams = false
                            macroSelected = null
                            showMacros = true
                        }
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_macro_run_selected)) }
                },
                dismissButton = {
                    TextButton(onClick = { showMacroParams = false }) { Text(stringResource(android.R.string.cancel)) }
                }
            )
        }
    }

    if (showMacroBatchConfirm) {
        AlertDialog(
            onDismissRequest = { showMacroBatchConfirm = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_macro_batch_run)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_macro_batch_confirm)) },
            confirmButton = {
                TextButton(onClick = {
                    scope.launch {
                        executeMacroBatch()
                        showMacroBatchConfirm = false
                        showMacros = true
                    }
                }) { Text(stringResource(android.R.string.ok)) }
            },
            dismissButton = {
                TextButton(onClick = { showMacroBatchConfirm = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

    fidelityResult?.let { result ->
        AlertDialog(
            onDismissRequest = { fidelityResult = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_fidelity)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.delivery_fidelity_score, result.score, result.matched, result.expected),
                        style = NfType.meta,
                        color = if (result.score == 100) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
                    )
                    if (result.missing.isNotEmpty()) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_fidelity_missing, result.missing.joinToString("、")), style = NfType.meta)
                    }
                    if (result.extra.isNotEmpty()) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_fidelity_extra, result.extra.joinToString("、")), style = NfType.meta)
                    }
                }
            },
            confirmButton = { TextButton(onClick = { fidelityResult = null }) { Text(stringResource(android.R.string.ok)) } }
        )
    }

    if (showLeaveConfirm) {
        AlertDialog(
            onDismissRequest = { showLeaveConfirm = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_leave_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_leave_body)) },
            confirmButton = {
                TextButton(onClick = { showLeaveConfirm = false; onBack() }) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_leave_confirm))
                }
            },
            dismissButton = {
                TextButton(onClick = { showLeaveConfirm = false }) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_leave_stay))
                }
            }
        )
    }

    if (pendingTrash != null) {
        val entry = requireNotNull(pendingTrash)
        AlertDialog(
            onDismissRequest = { pendingTrash = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_trash_title)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    Text(entry.name, style = NfType.meta)
                    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_trash_body), style = NfType.meta)
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    trashAndRemove(entry)
                    pendingTrash = null
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_trash_confirm)) }
            },
            dismissButton = { TextButton(onClick = { pendingTrash = null }) { Text(stringResource(android.R.string.cancel)) } }
        )
    }

    if (showTrash) {
        val trashDir = File(File(context.filesDir, "exports"), "trash")
        val items = remember(showTrash) {
            trashDir.listFiles()?.filter { it.isFile && !it.name.endsWith(".restore") }?.sortedByDescending { it.lastModified() }.orEmpty()
        }
        AlertDialog(
            onDismissRequest = { showTrash = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_trash)) },
            text = {
                Column(modifier = Modifier.heightIn(max = 480.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    if (items.isEmpty()) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_trash_empty), style = NfType.meta)
                    }
                    items.forEach { file ->
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Text(file.name, style = NfType.meta, modifier = Modifier.weight(1f))
                            TextButton(onClick = {
                                val sidecar = File(file.absolutePath + ".restore")
                                val original = sidecar.takeIf { it.isFile }?.readText(Charsets.UTF_8)
                                    ?: File(File(File(context.filesDir, "exports"), "delivery"), file.name.substringAfter('-')).absolutePath
                                val target = File(original)
                                target.parentFile?.mkdirs()
                                if (file.renameTo(target)) sidecar.delete()
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_restore)) }
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showTrash = false }) { Text(stringResource(android.R.string.ok)) } }
        )
    }

    if (showAllExports) {
        AlertDialog(
            onDismissRequest = { showAllExports = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_all_exports)) },
            text = {
                Column(
                    modifier = Modifier.heightIn(max = 520.dp).verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)
                ) {
                    exportEntries.forEach { entry ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(entry.format + " · " + entry.name, style = NfType.meta, modifier = Modifier.weight(1f))
                            TextButton(onClick = {
                                val file = File(entry.path)
                                if (file.isFile) {
                                    ShareExporter.launchChooser(
                                        context,
                                        ShareExporter.shareFileIntent(context, file, mimeFor(entry.format), entry.name),
                                        context.getString(dev.ninfenz.mobile.R.string.delivery_share_file)
                                    )
                                }
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_share_file)) }
                            TextButton(onClick = { trashAndRemove(entry) }) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.delivery_remove_export))
                            }
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showAllExports = false }) { Text(stringResource(android.R.string.ok)) } }
        )
    }

    if (showResetConfirm) {
        AlertDialog(
            onDismissRequest = { showResetConfirm = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_reset_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_reset_body)) },
            confirmButton = {
                TextButton(onClick = {
                    plan = null
                    rawPlan = null
                    inputs = emptyMap()
                    markdown = null
                    report = null
                    exportedFile = null
                    manifestText = null
                    exportVerify = null
                    error = null
                    batchChunks = emptyList()
                    batchNote = null
                    previewBlocks = emptyList()
                    previewHistory = emptyList()
                    previewRedo = emptyList()
                    previewDirty = false
                    needsRevalidate = false
                    draftNote = null
                    reproOk = null
                    reproText = null
                    validateRepro = null
                    statusNote = null
                    draftStore.clear(project.id)
                    showResetConfirm = false
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_reset)) }
            },
            dismissButton = {
                TextButton(onClick = { showResetConfirm = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

    if (showBrowsePlan) {
        AlertDialog(
            onDismissRequest = { showBrowsePlan = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_browse_plan)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("plan: " + (plan?.pipelineId ?: "-") + " · " + (plan?.steps?.size ?: 0) + " steps", style = NfType.label)
                    plan?.steps?.forEach { s -> Text("• " + s.id + " · " + s.node + " · " + s.module, style = NfType.meta) }
                    Text("spec: " + (specMeta?.id ?: "-") + " · " + (specMeta?.sections?.size ?: 0) + " sections", style = NfType.label)
                    specMeta?.sections?.forEach { s -> Text("• " + s.title + " · " + s.slots.size + " slots", style = NfType.meta) }
                    Text("slots: " + inputs.count { it.value.isNotBlank() } + "/" + inputs.size, style = NfType.label)
                }
            },
            confirmButton = { TextButton(onClick = { showBrowsePlan = false }) { Text(stringResource(android.R.string.ok)) } }
        )
    }

    if (showConstraintLens) {
        AlertDialog(
            onDismissRequest = { showConstraintLens = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_constraint_panel_title)) },
            text = {
                Column(
                    modifier = Modifier.heightIn(max = 520.dp).verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(NfSpacing.s)
                ) {
                    val views = dev.ninfenz.mobile.model.ConstraintLens.view(specMeta?.slots.orEmpty(), inputs)
                    if (views.isEmpty()) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_no_slots), style = NfType.meta)
                    }
                    views.forEach { view ->
                        Text(view.id + " · " + view.name, style = NfType.itemTitle)
                        Text(
                            view.kind + " · " + stringResource(
                                if (view.required) dev.ninfenz.mobile.R.string.delivery_slot_required else dev.ninfenz.mobile.R.string.delivery_slot_optional
                            ),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        OutlinedTextField(
                            value = inputs[view.id].orEmpty(),
                            onValueChange = { value ->
                                val clean = dev.ninfenz.mobile.model.SlotInput.sanitize(view.kind, value)
                                val limited = view.maxChars?.let { clean.take(it) } ?: clean
                                inputs = inputs + (view.id to limited)
                            },
                            label = { Text(view.name) },
                            modifier = Modifier.fillMaxWidth(),
                            minLines = 1,
                            maxLines = 3
                        )
                        if (view.issues.isEmpty()) {
                            Text(
                                stringResource(dev.ninfenz.mobile.R.string.delivery_constraint_ok),
                                style = NfType.meta,
                                color = MaterialTheme.colorScheme.primary
                            )
                        } else {
                            Text(
                                view.issues.map { issue ->
                                    when (issue) {
                                        dev.ninfenz.mobile.model.ConstraintLens.Issue.REQUIRED -> stringResource(dev.ninfenz.mobile.R.string.delivery_constraint_issue_required)
                                        dev.ninfenz.mobile.model.ConstraintLens.Issue.MIN -> stringResource(dev.ninfenz.mobile.R.string.delivery_constraint_issue_min)
                                        dev.ninfenz.mobile.model.ConstraintLens.Issue.MAX -> stringResource(dev.ninfenz.mobile.R.string.delivery_constraint_issue_max)
                                        dev.ninfenz.mobile.model.ConstraintLens.Issue.PREFIX -> stringResource(dev.ninfenz.mobile.R.string.delivery_constraint_issue_prefix)
                                        dev.ninfenz.mobile.model.ConstraintLens.Issue.SUFFIX -> stringResource(dev.ninfenz.mobile.R.string.delivery_constraint_issue_suffix)
                                        dev.ninfenz.mobile.model.ConstraintLens.Issue.PATTERN -> stringResource(dev.ninfenz.mobile.R.string.delivery_constraint_issue_pattern)
                                    }
                                }.joinToString("；"),
                                style = NfType.meta,
                                color = MaterialTheme.colorScheme.error
                            )
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showConstraintLens = false }) {
                    Text(stringResource(android.R.string.ok))
                }
            }
        )
    }

    if (showGrant) {
        var caps by remember(grant) { mutableStateOf(grant.caps) }
        var revoked by remember(grant) { mutableStateOf(grant.revoked) }
        var days by remember(grant) {
            val exp = grant.expiresAt
            mutableIntStateOf(
                when {
                    exp == null -> 0
                    exp - System.currentTimeMillis() <= 7L * 86_400_000L -> 7
                    else -> 30
                }
            )
        }
        AlertDialog(
            onDismissRequest = { showGrant = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.grant_title)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    Text(
                        stringResource(
                            dev.ninfenz.mobile.R.string.grant_current,
                            grant.expiresAt?.let {
                                stringResource(dev.ninfenz.mobile.R.string.grant_until, java.text.DateFormat.getDateInstance().format(java.util.Date(it)))
                            } ?: stringResource(dev.ninfenz.mobile.R.string.grant_no_expiry)
                        ),
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(stringResource(dev.ninfenz.mobile.R.string.grant_caps), style = NfType.itemTitle)
                    listOf(
                        dev.ninfenz.mobile.data.CapabilityGrant.READ to dev.ninfenz.mobile.R.string.grant_cap_read,
                        dev.ninfenz.mobile.data.CapabilityGrant.COMMENT to dev.ninfenz.mobile.R.string.grant_cap_comment,
                        dev.ninfenz.mobile.data.CapabilityGrant.REASSEMBLE to dev.ninfenz.mobile.R.string.grant_cap_reassemble,
                        dev.ninfenz.mobile.data.CapabilityGrant.EXPORT to dev.ninfenz.mobile.R.string.grant_cap_export,
                        dev.ninfenz.mobile.data.CapabilityGrant.SHARE to dev.ninfenz.mobile.R.string.grant_cap_share
                    ).forEach { (cap, label) ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(
                                checked = cap in caps,
                                onCheckedChange = { checked ->
                                    caps = if (checked) caps + cap else caps - cap
                                }
                            )
                            Text(stringResource(label))
                        }
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = revoked, onCheckedChange = { revoked = it })
                        Text(stringResource(dev.ninfenz.mobile.R.string.grant_revoked))
                    }
                    Text(stringResource(dev.ninfenz.mobile.R.string.grant_expiry), style = NfType.itemTitle)
                    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        listOf(0 to dev.ninfenz.mobile.R.string.grant_never, 7 to dev.ninfenz.mobile.R.string.grant_7d, 30 to dev.ninfenz.mobile.R.string.grant_30d).forEach { (option, label) ->
                            FilterChip(selected = days == option, onClick = { days = option }, label = { Text(stringResource(label)) })
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    val expiresAt = if (days == 0) null else System.currentTimeMillis() + days * 86_400_000L
                    val next = dev.ninfenz.mobile.data.CapabilityGrant(caps, expiresAt, revoked)
                    grantStore.save(project.id, next)
                    grant = next
                    showGrant = false
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.grant_save)) }
            },
            dismissButton = {
                TextButton(onClick = { showGrant = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

    if (showManualTransform) {
        AlertDialog(
            onDismissRequest = { showManualTransform = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.preview_manual_transform)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.preview_manual_hint), style = NfType.meta)
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(NfSpacing.xs),
                        modifier = Modifier.horizontalScroll(rememberScrollState())
                    ) {
                        listOf("lower", "upper", "trim", "collapse", "prefix", "suffix", "replace", "truncate").forEach { kind ->
                            FilterChip(
                                selected = manualKind == kind,
                                onClick = { manualKind = kind },
                                label = { Text(dev.ninfenz.mobile.model.FlashFillModel.Transform(kind).describe()) }
                            )
                        }
                    }
                    if (manualKind in listOf("truncate", "prefix", "suffix", "replace")) {
                        OutlinedTextField(
                            value = manualA,
                            onValueChange = { manualA = it },
                            label = {
                                Text(
                                    if (manualKind == "truncate") "N" else stringResource(dev.ninfenz.mobile.R.string.preview_bulk_value)
                                )
                            },
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                    if (manualKind == "replace") {
                        OutlinedTextField(
                            value = manualB,
                            onValueChange = { manualB = it },
                            label = { Text(stringResource(dev.ninfenz.mobile.R.string.preview_bulk_to)) },
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                    val valid = when (manualKind) {
                        "truncate" -> (manualA.toIntOrNull() ?: 0) > 0
                        "prefix", "suffix", "replace" -> manualA.isNotEmpty()
                        else -> true
                    }
                    if (!valid) {
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.preview_manual_invalid),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.error
                        )
                    }
                }
            },
            confirmButton = {
                val valid = when (manualKind) {
                    "truncate" -> (manualA.toIntOrNull() ?: 0) > 0
                    "prefix", "suffix", "replace" -> manualA.isNotEmpty()
                    else -> true
                }
                TextButton(enabled = valid, onClick = {
                    val transform = dev.ninfenz.mobile.model.FlashFillModel.Transform(manualKind, manualA, manualB)
                    previewHistory = previewHistory + listOf(previewBlocks)
                    previewRedo = emptyList()
                    previewBlocks = previewBlocks.map { it.copy(text = transform.apply(it.text)) }
                    previewDirty = true
                    inferredTransform = transform
                    showManualTransform = false
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_manual_apply)) }
            },
            dismissButton = {
                TextButton(onClick = { showManualTransform = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

    assignBlockText?.let { text ->
        AlertDialog(
            onDismissRequest = { assignBlockText = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.preview_assign_title)) },
            text = {
                Column(modifier = Modifier.heightIn(max = 360.dp).verticalScroll(rememberScrollState())) {
                    specMeta?.slots?.forEach { slot ->
                        val clean = dev.ninfenz.mobile.model.SlotInput.sanitize(slot.kind, text).let { v ->
                            slot.maxChars?.let { v.take(it) } ?: v
                        }
                        val issues = buildList {
                            if (slot.nonEmpty && clean.isBlank()) add(context.getString(dev.ninfenz.mobile.R.string.slot_required))
                            if (slot.minChars != null && clean.length < slot.minChars) add(context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.slot_min_chars, slot.minChars, slot.minChars))
                            slot.startsWith?.let { if (!clean.startsWith(it)) add(context.getString(dev.ninfenz.mobile.R.string.slot_prefix, it)) }
                            slot.endsWith?.let { if (!clean.endsWith(it)) add(context.getString(dev.ninfenz.mobile.R.string.slot_suffix, it)) }
                            slot.pattern?.let { p ->
                                val matches = runCatching { Regex(p).matches(clean) }.getOrDefault(false)
                                if (!matches) add(context.getString(dev.ninfenz.mobile.R.string.slot_pattern, p))
                            }
                        }
                        TextButton(
                            enabled = issues.isEmpty(),
                            onClick = {
                                inputs = inputs + (slot.id to clean)
                                assignBlockText = null
                            }
                        ) {
                            Text(
                                slot.id + " · " + slot.name + (slot.maxChars?.let { " · " + text.length + "/" + it } ?: "") + (if (issues.isEmpty()) "" else " · " + issues.joinToString("；")),
                                color = if (issues.isEmpty()) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.error
                            )
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { assignBlockText = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

    if (showDiscardPreview) {
        AlertDialog(
            onDismissRequest = { showDiscardPreview = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.preview_discard_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.preview_discard_body)) },
            confirmButton = {
                TextButton(onClick = {
                    showDiscardPreview = false
                    editingPreview = false
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_discard)) }
            },
            dismissButton = {
                TextButton(onClick = { showDiscardPreview = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

    fun bulkApply(text: String): String = when (bulkMode) {
        "replace" -> text.replace(bulkFrom, bulkTo)
        "prefix" -> bulkFrom + text
        "suffix" -> text + bulkFrom
        "truncate" -> text.take(bulkFrom.toIntOrNull() ?: text.length)
        else -> text
    }
    if (showBulk) {
        AlertDialog(
            onDismissRequest = { showBulk = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.preview_bulk)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        listOf("replace" to dev.ninfenz.mobile.R.string.preview_bulk_replace, "prefix" to dev.ninfenz.mobile.R.string.preview_bulk_prefix, "suffix" to dev.ninfenz.mobile.R.string.preview_bulk_suffix, "truncate" to dev.ninfenz.mobile.R.string.preview_bulk_truncate).forEach { (mode, label) ->
                            FilterChip(selected = bulkMode == mode, onClick = { bulkMode = mode; bulkError = null }, label = { Text(stringResource(label)) })
                        }
                    }
                    OutlinedTextField(value = bulkFrom, onValueChange = { bulkFrom = it; bulkError = null }, label = { Text(stringResource(if (bulkMode == "replace") dev.ninfenz.mobile.R.string.preview_bulk_from else if (bulkMode == "truncate") dev.ninfenz.mobile.R.string.preview_bulk_length else dev.ninfenz.mobile.R.string.preview_bulk_value)) }, modifier = Modifier.fillMaxWidth())
                    if (bulkMode == "replace") {
                        OutlinedTextField(value = bulkTo, onValueChange = { bulkTo = it }, label = { Text(stringResource(dev.ninfenz.mobile.R.string.preview_bulk_to)) }, modifier = Modifier.fillMaxWidth())
                    }
                    Text(pluralStringResource(dev.ninfenz.mobile.R.plurals.preview_bulk_count, previewBlocks.count { bulkApply(it.text) != it.text }, previewBlocks.count { bulkApply(it.text) != it.text }), style = NfType.meta)
                    bulkError?.let { Text(it, color = MaterialTheme.colorScheme.error, style = NfType.meta) }
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    val bad = bulkFrom.isBlank() || (bulkMode == "truncate" && (bulkFrom.toIntOrNull() ?: 0) <= 0)
                    if (bad) {
                        bulkError = context.getString(dev.ninfenz.mobile.R.string.preview_bulk_empty)
                    } else {
                        previewHistory = previewHistory + listOf(previewBlocks)
                        previewRedo = emptyList()
                        previewBlocks = previewBlocks.map { it.copy(text = bulkApply(it.text)) }
                        previewDirty = true
                        showBulk = false
                    }
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_bulk_apply)) }
            },
            dismissButton = {
                TextButton(onClick = { showBulk = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
    if (editingPreview) {
        AlertDialog(
            onDismissRequest = {
                if (previewDirty) showDiscardPreview = true else editingPreview = false
            },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.preview_edit_title)) },
            text = {
                Column(
                    modifier = Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(NfSpacing.s)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.preview_edit_note),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.weight(1f)
                        )
                        TextButton(
                            enabled = previewHistory.isNotEmpty(),
                            onClick = {
                                previewRedo = previewRedo + listOf(previewBlocks)
                                previewBlocks = previewHistory.last()
                                previewHistory = previewHistory.dropLast(1)
                            }
                        ) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_undo)) }
                        TextButton(
                            enabled = previewRedo.isNotEmpty(),
                            onClick = {
                                previewHistory = previewHistory + listOf(previewBlocks)
                                previewBlocks = previewRedo.last()
                                previewRedo = previewRedo.dropLast(1)
                            }
                        ) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_redo)) }
                        TextButton(onClick = { showBulk = true }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_bulk)) }
                        TextButton(onClick = { showManualTransform = true }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_manual_transform)) }
                        TextButton(onClick = {
                            val base = previewBaseline
                            val changed = if (base.size == previewBlocks.size) {
                                base.indices.filter { base[it].text != previewBlocks[it].text }
                            } else emptyList()
                            val transform = if (changed.isNotEmpty()) {
                                dev.ninfenz.mobile.model.FlashFillModel.infer(
                                    changed.map { i -> base[i].text to previewBlocks[i].text }
                                )
                            } else null
                            if (transform == null) {
                                android.widget.Toast.makeText(context, context.getString(dev.ninfenz.mobile.R.string.preview_infer_failed), android.widget.Toast.LENGTH_SHORT).show()
                            } else {
                                previewHistory = previewHistory + listOf(previewBlocks)
                                previewRedo = emptyList()
                                previewBlocks = previewBlocks.map { it.copy(text = transform.apply(it.text)) }
                                previewDirty = true
                                inferredTransform = transform
                                android.widget.Toast.makeText(context, context.getString(dev.ninfenz.mobile.R.string.preview_infer_done, transform.describe()), android.widget.Toast.LENGTH_SHORT).show()
                            }
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_infer)) }
                        inferredTransform?.let { t ->
                            TextButton(onClick = {
                                dev.ninfenz.mobile.data.TransformStore(context.filesDir).save(project.id, t)
                                savedTransform = t
                                android.widget.Toast.makeText(context, context.getString(dev.ninfenz.mobile.R.string.preview_transform_saved), android.widget.Toast.LENGTH_SHORT).show()
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_save_transform)) }
                        }
                        savedTransform?.let { t ->
                            TextButton(onClick = {
                                previewHistory = previewHistory + listOf(previewBlocks)
                                previewRedo = emptyList()
                                previewBlocks = previewBlocks.map { it.copy(text = t.apply(it.text)) }
                                previewDirty = true
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_apply_saved)) }
                        }
                    }
                    previewBlocks.forEachIndexed { index, block ->
                        Text(block.kind, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        OutlinedTextField(
                            value = block.text,
                            onValueChange = { value ->
                                previewHistory = previewHistory + listOf(previewBlocks)
                                previewRedo = emptyList()
                                previewDirty = true
                                previewBlocks = previewBlocks.toMutableList().also { it[index] = block.copy(text = value) }
                            },
                            modifier = Modifier.fillMaxWidth(),
                            minLines = 2
                        )
                        if (block.kind in setOf("paragraph", "quote") && block.text.isNotBlank() && block.text.length <= 80 && index !in ignoredHints) {
                            val heading = previewBlocks.take(index).lastOrNull { it.kind == "heading" }?.text
                            val suggestion = dev.ninfenz.mobile.model.FormalizationSuggester.suggest(
                                block.text,
                                heading,
                                specMeta?.slots.orEmpty(),
                                inputs.filterValues { it.isNotBlank() }.keys
                            )

                            val applySuggestion: (String, String) -> Unit = { slotId, text -> inputs = inputs + (slotId to text) }
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    if (suggestion != null) {
                                        stringResource(dev.ninfenz.mobile.R.string.preview_suggest_slot, suggestion.slotId, suggestion.slotName)
                                    } else {
                                        stringResource(dev.ninfenz.mobile.R.string.preview_formalize_hint)
                                    },
                                    style = NfType.meta,
                                    color = MaterialTheme.colorScheme.primary,
                                    modifier = Modifier.weight(1f)
                                )
                                if (suggestion != null) PreviewSuggestionApplyButton(suggestion.slotId, block.text, applySuggestion)
                                TextButton(onClick = { assignBlockText = block.text }) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.preview_formalize))
                                }
                                TextButton(onClick = { ignoredHints = ignoredHints + index }) {
                                    Text(stringResource(dev.ninfenz.mobile.R.string.preview_ignore))
                                }
                            }
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                            TextButton(
                                enabled = index > 0,
                                onClick = {
                                    previewHistory = previewHistory + listOf(previewBlocks)
                                    previewBlocks = previewBlocks.toMutableList().also {
                                        val item = it.removeAt(index)
                                        it.add(index - 1, item)
                                    }
                                }
                            ) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_block_up)) }
                            TextButton(
                                enabled = index < previewBlocks.lastIndex,
                                onClick = {
                                    previewHistory = previewHistory + listOf(previewBlocks)
                                    previewBlocks = previewBlocks.toMutableList().also {
                                        val item = it.removeAt(index)
                                        it.add(index + 1, item)
                                    }
                                }
                            ) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_block_down)) }
                            TextButton(onClick = {
                                previewHistory = previewHistory + listOf(previewBlocks)
                                previewBlocks = previewBlocks.filterIndexed { i, _ -> i != index }
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_block_delete)) }
                            TextButton(onClick = { assignBlockText = block.text }) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.preview_assign_slot))
                            }
                        }
                    }
                    TextButton(onClick = {
                        previewHistory = previewHistory + listOf(previewBlocks)
                        previewBlocks = previewBlocks + MarkdownBlock(
                            id = (previewBlocks.maxOfOrNull { it.id } ?: 0) + 1,
                            text = ""
                        )
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_block_add)) }
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    markdown = MarkdownBlocks.render(previewBlocks)
                    versionStore.save(project.id, markdown ?: "")
                    previewDirty = false
                    needsRevalidate = true
                    activeStep = if (audit) 2 else 3
                    draftStore.save(project.id, inputs, rawPlan, markdown)
                    report = null
                    validateRepro = null
                    exportedFile = null
                    exportVerify = null
                    editingPreview = false
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_save)) }
            },
            dismissButton = {
                TextButton(onClick = {
                    if (previewDirty) showDiscardPreview = true else editingPreview = false
                }) {
                    Text(stringResource(android.R.string.cancel))
                }
            }
        )
    }

    slotImportTarget?.let { target ->
        AlertDialog(
            onDismissRequest = { slotImportTarget = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_import_title, target)) },
            text = {
                Column(
                    modifier = Modifier
                        .heightIn(max = 420.dp)
                        .verticalScroll(rememberScrollState())
                ) {
                    Text(
                        pluralStringResource(
                            dev.ninfenz.mobile.R.plurals.delivery_slot_import_meta,
                            slotImportAdapted,
                            slotImportSource,
                            slotImportFormat,
                            slotImportOriginal,
                            slotImportAdapted
                        ),
                        style = NfType.meta
                    )
                    NfExpandableText(slotImportText, collapsedLines = 10)
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    val meta = specMeta?.slots?.firstOrNull { it.id == target }
                    val clean = SlotInput.sanitize(meta?.kind, slotImportText).let { value ->
                        meta?.maxChars?.let { value.take(it) } ?: value
                    }
                    inputs = inputs + (target to clean)
                    slotImportTarget = null
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_replace)) }
            },
            dismissButton = {
                Row {
                    TextButton(onClick = {
                        val meta = specMeta?.slots?.firstOrNull { it.id == target }
                        val old = inputs[target].orEmpty().trim()
                        val merged = if (old.isBlank()) slotImportText else old + "\n\n" + slotImportText
                        val clean = SlotInput.sanitize(meta?.kind, merged).let { value ->
                            meta?.maxChars?.let { value.take(it) } ?: value
                        }
                        inputs = inputs + (target to clean)
                        slotImportTarget = null
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_append)) }
                    TextButton(onClick = { slotImportTarget = null }) { Text(stringResource(android.R.string.cancel)) }
                }
            }
        )
    }

    if (batchChunks.isNotEmpty()) {
        val slots = plan?.slots.orEmpty()
        AlertDialog(
            onDismissRequest = { batchChunks = emptyList() },
            title = { Text(pluralStringResource(dev.ninfenz.mobile.R.plurals.delivery_slot_batch_title, batchChunks.size, batchChunks.size, slots.size)) },
            text = {
                Column(
                    modifier = Modifier
                        .heightIn(max = 420.dp)
                        .verticalScroll(rememberScrollState())
                ) {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.delivery_slot_batch_meta, batchSource),
                        style = NfType.meta
                    )
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.delivery_slot_batch_preview_note),
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    slots.forEachIndexed { index, slot ->
                        val chunk = batchChunks.getOrNull(index)
                        if (chunk != null) {
                            val existing = inputs[slot].orEmpty()
                            Text("$slot ← " + chunk.text.replace('\n', ' ').take(48), style = NfType.meta)
                            Text(
                                stringResource(
                                    if (existing.isBlank()) dev.ninfenz.mobile.R.string.delivery_slot_batch_preview_fill
                                    else dev.ninfenz.mobile.R.string.delivery_slot_batch_preview_overwrite
                                ),
                                style = NfType.meta,
                                color = if (existing.isBlank()) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
                            )
                        }
                    }
                    if (batchChunks.size > slots.size) {
                        Text(
                            pluralStringResource(dev.ninfenz.mobile.R.plurals.delivery_slot_batch_overflow, batchChunks.size - slots.size, batchChunks.size - slots.size),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.error
                        )
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { applyBatch(onlyEmpty = true) }) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_batch_fill_empty))
                }
            },
            dismissButton = {
                Row {
                    TextButton(onClick = { applyBatch(onlyEmpty = false) }) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_slot_batch_replace_all))
                    }
                    TextButton(onClick = { batchChunks = emptyList() }) { Text(stringResource(android.R.string.cancel)) }
                }
            }
        )
    }
    if (showFullPreview) {
        val md = markdown
        if (md != null) {
            Dialog(
                onDismissRequest = { showFullPreview = false },
                properties = DialogProperties(usePlatformDefaultWidth = false)
            ) {
                Surface(modifier = Modifier.fillMaxSize()) {
                    Column(modifier = Modifier.fillMaxSize().statusBarsPadding()) {
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page, vertical = NfSpacing.s),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                stringResource(dev.ninfenz.mobile.R.string.delivery_preview),
                                style = NfType.screenTitle,
                                modifier = Modifier.weight(1f)
                            )
                            TextButton(onClick = { showFullPreview = false }) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.preview_close))
                            }
                        }
                        HorizontalDivider()
                        Column(
                            modifier = Modifier
                                .fillMaxSize()
                                .verticalScroll(rememberScrollState())
                                .padding(NfSpacing.page)
                        ) {
                            MarkdownPreview(md)
                        }
                    }
                }
            }
        }
    }
}

private const val MAX_IMPORT_CHARS = 1_048_576

private fun statusText(context: Context, status: ProjectStatus): String = when (status) {
    ProjectStatus.DRAFT -> context.getString(dev.ninfenz.mobile.R.string.delivery_status_draft)
    ProjectStatus.AUTHORING -> context.getString(dev.ninfenz.mobile.R.string.delivery_status_authoring)
    ProjectStatus.ASSEMBLED -> context.getString(dev.ninfenz.mobile.R.string.delivery_status_assembled)
    ProjectStatus.VALIDATED -> context.getString(dev.ninfenz.mobile.R.string.delivery_status_validated)
    ProjectStatus.EXPORTED -> context.getString(dev.ninfenz.mobile.R.string.delivery_status_exported)
    ProjectStatus.REVIEWED -> context.getString(dev.ninfenz.mobile.R.string.delivery_status_reviewed)
}

internal data class ExportButtonArgs(
    val format: String,
    val mime: String,
    val markdown: String?,
    val project: Project,
    val context: android.content.Context,
    val scope: kotlinx.coroutines.CoroutineScope,
    val setBusy: (Boolean) -> Unit,
    val setError: (CoreError?) -> Unit,
    val busy: Boolean,
    val docxStyles: String? = null,
    val docxSectPr: String? = null,
    val docxTheme: String? = null,
    val docxNumbering: String? = null,
    val docxHeader: String? = null,
    val docxFooter: String? = null,
    val onDone: (File?, String?, dev.ninfenz.mobile.data.ReproChecker.Report?) -> Unit,
)

@Composable
private fun ExportButton(args: ExportButtonArgs) = with(args) {
    Button(
        enabled = markdown != null && !busy,
        onClick = {
            val md = markdown ?: return@Button
            setBusy(true)
            setError(null)
            scope.launch {
                try {
                    runDeliveryExport(RunDeliveryExportArgs(format, md, project, context, setError, onDone,
                        docxStyles, docxSectPr, docxTheme, docxNumbering, docxHeader, docxFooter))
                } finally {
                    setBusy(false)
                }
            }
        }
    ) { Text(context.getString(dev.ninfenz.mobile.R.string.delivery_export, format)) }
}

@Composable
private fun PreservationExportButton(
    markdown: String?,
    project: Project,
    context: android.content.Context,
    scope: kotlinx.coroutines.CoroutineScope,
    setBusy: (Boolean) -> Unit,
    setError: (CoreError?) -> Unit,
    busy: Boolean,
    grant: dev.ninfenz.mobile.data.CapabilityGrant,
    onDone: (File, dev.ninfenz.mobile.data.ReproChecker.Report) -> Unit
) {
    Button(
        enabled = markdown != null && !busy,
        onClick = {
            val md = markdown ?: return@Button
            setBusy(true)
            setError(null)
            scope.launch {
                try {
                    val outDir = File(File(context.filesDir, "exports"), "delivery").apply { mkdirs() }
                    val lineageStore = dev.ninfenz.mobile.data.PreservationLineageStore(context.filesDir)
                    val predecessor = lineageStore.load(project.id)
                    val created = dev.ninfenz.mobile.data.PreservationExporter.export(md, project.title, project.id, outDir, dev.ninfenz.mobile.data.PreservationOptions(dev.ninfenz.mobile.data.ContractStore(context.filesDir).raw(project.id), grant.toJson().toString(), predecessor))
                    val reproDir = File(context.cacheDir, "repro-preserve").apply { deleteRecursively(); mkdirs() }
                    val second = dev.ninfenz.mobile.data.PreservationExporter.export(md, project.title, project.id, reproDir, dev.ninfenz.mobile.data.PreservationOptions(dev.ninfenz.mobile.data.ContractStore(context.filesDir).raw(project.id), grant.toJson().toString(), predecessor))
                    val report = dev.ninfenz.mobile.data.ReproChecker.check(created.file, second.file)
                    reproDir.deleteRecursively()
                    val digest = java.security.MessageDigest.getInstance("SHA-256")
                        .digest(created.file.readBytes())
                        .joinToString("") { "%02x".format(it.toInt() and 0xff) }
                    lineageStore.save(project.id, digest)
                    onDone(created.file, report)
                } catch (t: Throwable) {
                    setError(CoreError("NF-EXP-001", context.getString(dev.ninfenz.mobile.R.string.export_preserve_failed, t.message ?: t.javaClass.simpleName), context.getString(dev.ninfenz.mobile.R.string.export_failed_fix), null, 1))
                } finally {
                    setBusy(false)
                }
            }
        }
    ) { Text(context.getString(dev.ninfenz.mobile.R.string.delivery_export, "preserve")) }
}

@Composable
private fun NfDocExportButton(
    markdown: String?,
    project: Project,
    context: android.content.Context,
    scope: kotlinx.coroutines.CoroutineScope,
    setBusy: (Boolean) -> Unit,
    setError: (CoreError?) -> Unit,
    busy: Boolean,
    onDone: (File, dev.ninfenz.mobile.data.ReproChecker.Report) -> Unit
) {
    Button(
        enabled = markdown != null && !busy,
        onClick = {
            val md = markdown ?: return@Button
            setBusy(true)
            setError(null)
            scope.launch {
                try {
                    val outDir = File(File(context.filesDir, "exports"), "delivery").apply { mkdirs() }
                    val created = dev.ninfenz.mobile.data.NfDocExporter.export(md, project.title, project.id, outDir)
                    val reproDir = File(context.cacheDir, "repro-nfdoc").apply { deleteRecursively(); mkdirs() }
                    val second = dev.ninfenz.mobile.data.NfDocExporter.export(md, project.title, project.id, reproDir)
                    val report = dev.ninfenz.mobile.data.ReproChecker.check(created.file, second.file)
                    reproDir.deleteRecursively()
                    onDone(created.file, report)
                } catch (t: Throwable) {
                    setError(CoreError("NF-EXP-001", context.getString(dev.ninfenz.mobile.R.string.export_nfdoc_failed, t.message ?: t.javaClass.simpleName), context.getString(dev.ninfenz.mobile.R.string.export_failed_fix), null, 1))
                } finally {
                    setBusy(false)
                }
            }
        }
    ) { Text(context.getString(dev.ninfenz.mobile.R.string.delivery_export, "nf-doc")) }
}

internal data class EpubExportButtonArgs(
    val markdown: String?,
    val project: Project,
    val author: String,
    val language: String,
    val context: android.content.Context,
    val scope: kotlinx.coroutines.CoroutineScope,
    val setBusy: (Boolean) -> Unit,
    val setError: (CoreError?) -> Unit,
    val busy: Boolean,
    val outputTemplate: String? = null,
    val onDone: (File, dev.ninfenz.mobile.data.ReproChecker.Report) -> Unit,
)

@Composable
private fun EpubExportButton(args: EpubExportButtonArgs) = with(args) {
    Button(
        enabled = markdown != null && !busy,
        onClick = {
            val md = markdown ?: return@Button
            setBusy(true)
            setError(null)
            scope.launch {
                try {
                    val outDir = File(File(context.filesDir, "exports"), "delivery").apply { mkdirs() }
                    val fileName = dev.ninfenz.mobile.data.OutputNaming.resolve(outputTemplate, project.title, "epub")
                    val created = EpubExporter.export(md, project.title, outDir, author, language, fileName)
                    val reproDir = File(context.cacheDir, "repro-epub").apply { deleteRecursively(); mkdirs() }
                    val second = EpubExporter.export(md, project.title, reproDir, author, language, fileName)
                    val report = dev.ninfenz.mobile.data.ReproChecker.check(created.file, second.file)
                    reproDir.deleteRecursively()
                    onDone(created.file, report)
                } catch (t: Throwable) {
                    setError(CoreError("NF-EXP-001", context.getString(dev.ninfenz.mobile.R.string.export_epub_failed, t.message ?: t.javaClass.simpleName), context.getString(dev.ninfenz.mobile.R.string.export_failed_fix), null, 1))
                } finally {
                    setBusy(false)
                }
            }
        }
    ) { Text(context.getString(dev.ninfenz.mobile.R.string.delivery_export, "epub")) }
}

internal data class PdfExportButtonArgs(
    val markdown: String?,
    val project: Project,
    val pageSize: String,
    val includeTitle: Boolean,
    val context: android.content.Context,
    val scope: kotlinx.coroutines.CoroutineScope,
    val setBusy: (Boolean) -> Unit,
    val setError: (CoreError?) -> Unit,
    val busy: Boolean,
    val outputTemplate: String? = null,
    val onDone: (File, dev.ninfenz.mobile.data.ReproChecker.Report) -> Unit,
)

@Composable
private fun PdfExportButton(args: PdfExportButtonArgs) = with(args) {
    Button(
        enabled = markdown != null && !busy,
        onClick = {
            val md = markdown ?: return@Button
            setBusy(true)
            setError(null)
            scope.launch {
                try {
                    val outDir = File(File(context.filesDir, "exports"), "delivery").apply { mkdirs() }
                    val fileName = dev.ninfenz.mobile.data.OutputNaming.resolve(outputTemplate, project.title, "pdf")
                    val rich = dev.ninfenz.mobile.data.WebPdfExporter.export(context, md, project.title, outDir, dev.ninfenz.mobile.data.WebPdfExporter.PageOptions(if (pageSize.equals("Letter", true)) 612 else 595, if (pageSize.equals("Letter", true)) 792 else 842, fileName))
                    val createdFile: File = rich?.file ?: PdfExporter.export(md, project.title, outDir, pageSize, includeTitle, fileName).file
                    val reproDir = File(context.cacheDir, "repro-pdf").apply { deleteRecursively(); mkdirs() }
                    val secondFile: File = if (rich != null) {
                        dev.ninfenz.mobile.data.WebPdfExporter.export(context, md, project.title, reproDir, dev.ninfenz.mobile.data.WebPdfExporter.PageOptions(if (pageSize.equals("Letter", true)) 612 else 595, if (pageSize.equals("Letter", true)) 792 else 842, fileName))?.file
                            ?: PdfExporter.export(md, project.title, reproDir, pageSize, includeTitle, fileName).file
                    } else {
                        PdfExporter.export(md, project.title, reproDir, pageSize, includeTitle, fileName).file
                    }
                    val report = dev.ninfenz.mobile.data.ReproChecker.check(createdFile, secondFile)
                    reproDir.deleteRecursively()
                    if (dev.ninfenz.mobile.data.FeatureGate.auditEnabled()) dev.ninfenz.mobile.data.DecisionStore(context.filesDir).append("export-pdf", context.getString(dev.ninfenz.mobile.R.string.decision_export_pdf), undoable = false)
                    onDone(createdFile, report)
                } catch (t: Throwable) {
                    setError(CoreError("NF-EXP-002", context.getString(dev.ninfenz.mobile.R.string.export_pdf_failed, t.message ?: t.javaClass.simpleName), context.getString(dev.ninfenz.mobile.R.string.export_failed_fix), null, 1))
                } finally {
                    setBusy(false)
                }
            }
        }
    ) { Text(context.getString(dev.ninfenz.mobile.R.string.delivery_export, "pdf")) }
}

@Composable
private fun PdfUaExportButton(
    markdown: String?,
    project: Project,
    context: android.content.Context,
    scope: kotlinx.coroutines.CoroutineScope,
    setBusy: (Boolean) -> Unit,
    setError: (CoreError?) -> Unit,
    busy: Boolean,
    onDone: (File, dev.ninfenz.mobile.data.ReproChecker.Report) -> Unit
) {
    Button(
        enabled = markdown != null && !busy,
        onClick = {
            val md = markdown ?: return@Button
            setBusy(true)
            setError(null)
            scope.launch {
                try {
                    val outDir = File(File(context.filesDir, "exports"), "delivery").apply { mkdirs() }
                    val created = PdfUaExporter.export(context, md, project.title, outDir)
                    if (dev.ninfenz.mobile.data.FeatureGate.auditEnabled()) dev.ninfenz.mobile.data.DecisionStore(context.filesDir).append("export-pdfua", context.getString(dev.ninfenz.mobile.R.string.delivery_pdfua_note), undoable = false)
                    onDone(created.file, dev.ninfenz.mobile.data.ReproChecker.check(created.file, created.file))
                } catch (t: Throwable) {
                    setError(CoreError("NF-EXP-002", context.getString(dev.ninfenz.mobile.R.string.export_pdf_failed, t.message ?: t.javaClass.simpleName), context.getString(dev.ninfenz.mobile.R.string.export_failed_fix), null, 1))
                } finally {
                    setBusy(false)
                }
            }
        }
    ) { Text(context.getString(dev.ninfenz.mobile.R.string.delivery_export_pdfua)) }
}

@Composable
private fun HtmlExportButton(
    markdown: String?,
    project: Project,
    context: android.content.Context,
    scope: kotlinx.coroutines.CoroutineScope,
    setBusy: (Boolean) -> Unit,
    setError: (CoreError?) -> Unit,
    busy: Boolean,
    outputTemplate: String? = null,
    onDone: (File, dev.ninfenz.mobile.data.ReproChecker.Report) -> Unit
) {
    Button(
        enabled = markdown != null && !busy,
        onClick = {
            val md = markdown ?: return@Button
            setBusy(true)
            setError(null)
            scope.launch {
                try {
                    val outDir = File(File(context.filesDir, "exports"), "delivery").apply { mkdirs() }
                    val fileName = dev.ninfenz.mobile.data.OutputNaming.resolve(outputTemplate, project.title, "html")
                    val created = HtmlExporter.export(md, project.title, outDir, fileName)
                    val reproDir = File(context.cacheDir, "repro-html").apply { deleteRecursively(); mkdirs() }
                    val second = HtmlExporter.export(md, project.title, reproDir, fileName)
                    val report = dev.ninfenz.mobile.data.ReproChecker.check(created.file, second.file)
                    reproDir.deleteRecursively()
                    onDone(created.file, report)
                } catch (t: Throwable) {
                    setError(CoreError("NF-EXP-003", context.getString(dev.ninfenz.mobile.R.string.export_html_failed, t.message ?: t.javaClass.simpleName), context.getString(dev.ninfenz.mobile.R.string.export_failed_fix), null, 1))
                } finally {
                    setBusy(false)
                }
            }
        }
    ) { Text(context.getString(dev.ninfenz.mobile.R.string.delivery_export, "html")) }
}

private fun formatBytes(bytes: Long): String = when {
    bytes < 1024 -> bytes.toString() + " B"
    bytes < 1024 * 1024 -> (bytes / 1024).toString() + " KB"
    else -> String.format(java.util.Locale.US, "%.1f MB", bytes / 1024.0 / 1024.0)
}

private fun mimeFor(format: String): String = when (format) {
    "md" -> "text/markdown"
    "zip", "skill" -> "application/zip"
    "docx" -> "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    "json" -> "application/json"
    "epub" -> "application/epub+zip"
    "pdf" -> "application/pdf"
    "html" -> "text/html"
    else -> "application/octet-stream"
}


internal data class RunDeliveryExportArgs(
    val format: String,
    val md: String,
    val project: Project,
    val context: android.content.Context,
    val setError: (CoreError?) -> Unit,
    val onDone: (File?, String?, dev.ninfenz.mobile.data.ReproChecker.Report?) -> Unit,
    val docxStyles: String?,
    val docxSectPr: String?,
    val docxTheme: String?,
    val docxNumbering: String?,
    val docxHeader: String?,
    val docxFooter: String?,
)

private suspend fun runDeliveryExport(args: RunDeliveryExportArgs) {
    with(args) {
    fun payloadFor(dir: File) = buildJsonObject {
        put("markdown", md)
        put("format", format)
        put("out_dir", dir.absolutePath)
        put("manifest", true)
        put("title", project.title)
        put("project_id", project.id)
        if (format == "docx" && docxStyles != null) put("docx_styles", docxStyles)
        if (format == "docx" && docxSectPr != null) put("docx_sect_pr", docxSectPr)
        if (format == "docx" && docxTheme != null) put("docx_theme", docxTheme)
        if (format == "docx" && docxNumbering != null) put("docx_numbering", docxNumbering)
        if (format == "docx" && docxHeader != null) put("docx_header", docxHeader)
        if (format == "docx" && docxFooter != null) put("docx_footer", docxFooter)
    }
    fun fileFor(dir: File, manifest: kotlinx.serialization.json.JsonObject?): File? {
        val name = manifest?.get("files")?.toString()?.let { raw ->
            Regex("\"name\":\"([^\"]+)\"").find(raw)?.groupValues?.getOrNull(1)
        }
        return name?.let { File(dir, it) }
    }
    val outDir = File(File(context.filesDir, "exports"), "delivery").apply { mkdirs() }
    val response = safeCall("export", payloadFor(outDir))
    if (response.ok) {
        val manifest = response.resultObject()
        val file = fileFor(outDir, manifest)
        var report: dev.ninfenz.mobile.data.ReproChecker.Report? = null
        if (file != null) {
            val reproDir = File(context.cacheDir, "repro-core-" + format).apply { deleteRecursively(); mkdirs() }
            val second = safeCall("export", payloadFor(reproDir))
            if (second.ok) {
                val secondFile = fileFor(reproDir, second.resultObject())
                if (secondFile != null) {
                    report = dev.ninfenz.mobile.data.ReproChecker.check(file, secondFile)
                }
            }
            reproDir.deleteRecursively()
        }
        onDone(file, manifest?.toString(), report)
    } else {
        setError(response.error)
    }

    }
}
