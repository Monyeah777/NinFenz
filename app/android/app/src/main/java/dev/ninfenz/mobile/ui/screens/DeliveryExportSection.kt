package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.TextButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import dev.ninfenz.mobile.data.Capability
import dev.ninfenz.mobile.data.CapabilityRegistry
import dev.ninfenz.mobile.data.StyleMatch
import dev.ninfenz.mobile.data.StyleTemplateStore
import dev.ninfenz.mobile.share.ShareExporter
import dev.ninfenz.mobile.ui.components.NfCollapsibleSection
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType

@Composable
internal fun DeliveryPreflightButton(onShow: () -> Unit) {
    TextButton(onClick = onShow) {
        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_preflight))
    }
}
@Composable
internal fun DeliveryExportSection(a: DeliveryExportArgs) {
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
internal fun ExportSummary(a: DeliveryExportArgs) {
    val summary = buildList {
        add(stringResource(if (a.markdown != null) dev.ninfenz.mobile.R.string.delivery_summary_assembled else dev.ninfenz.mobile.R.string.delivery_summary_unassembled))
        if (a.audit) add(stringResource(if (a.report?.verdict == "pass") dev.ninfenz.mobile.R.string.delivery_summary_validated else dev.ninfenz.mobile.R.string.delivery_summary_unvalidated))
        add(stringResource(if (a.exportedFile != null) dev.ninfenz.mobile.R.string.delivery_summary_exported else dev.ninfenz.mobile.R.string.delivery_summary_unexported))
    }.joinToString(" · ")
    Text(summary, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page))
    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_export_group_docs), style = NfType.label, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(start = NfSpacing.page, end = NfSpacing.page, top = NfSpacing.s))
}

@Composable
internal fun ExportAllBlock(a: DeliveryExportArgs) {
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
internal fun ExportDocsRow(a: DeliveryExportArgs) {
    val context = androidx.compose.ui.platform.LocalContext.current
    FlowRow(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
        ExportButton(ExportButtonArgs("md", "text/markdown", a.exportMarkdown, a.project, context, a.scope, { a.onBusy(it) }, { a.onError(it) }, a.exportBlocked, onDone = { file, manifest, report -> a.onExportDone("md", file, manifest, report) }))
        ExportButton(ExportButtonArgs("zip", "application/zip", a.exportMarkdown, a.project, context, a.scope, { a.onBusy(it) }, { a.onError(it) }, a.exportBlocked, onDone = { file, manifest, report -> a.onExportDone("zip", file, manifest, report) }))
        ExportButton(ExportButtonArgs("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", a.exportMarkdown, a.project, context, a.scope, { a.onBusy(it) }, { a.onError(it) }, a.exportBlocked, docxStyles = a.docxStyles, docxSectPr = a.docxSectPr, docxTheme = a.docxTheme, docxNumbering = a.docxNumbering, docxHeader = a.docxHeader, docxFooter = a.docxFooter, onDone = { file, manifest, report -> a.onExportDone("docx", file, manifest, report) }))
    }
}

@Composable
internal fun ExportDataRow(a: DeliveryExportArgs) {
    val context = androidx.compose.ui.platform.LocalContext.current
    Text(stringResource(dev.ninfenz.mobile.R.string.delivery_export_group_data), style = NfType.label, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(start = NfSpacing.page, end = NfSpacing.page, top = NfSpacing.s))
    FlowRow(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
        ExportButton(ExportButtonArgs("json", "application/json", a.exportMarkdown, a.project, context, a.scope, { a.onBusy(it) }, { a.onError(it) }, a.exportBlocked, onDone = { file, manifest, report -> a.onExportDone("json", file, manifest, report) }))
        ExportButton(ExportButtonArgs("skill", "application/zip", a.exportMarkdown, a.project, context, a.scope, { a.onBusy(it) }, { a.onError(it) }, a.exportBlocked, onDone = { file, manifest, report -> a.onExportDone("skill", file, manifest, report) }))
    }
}

@Composable
internal fun ExportReadingRow(a: DeliveryExportArgs) {
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
internal fun ExportPreserveRow(a: DeliveryExportArgs) {
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
internal fun ExportShareRow(a: DeliveryExportArgs) {
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
internal fun ExportStyleRow(a: DeliveryExportArgs) {
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
internal fun StyleTemplatesDialog(a: DeliveryExportArgs) {
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
internal fun StyleTemplateRow(
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
internal fun ExportToolsRow(a: DeliveryExportArgs) {
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
