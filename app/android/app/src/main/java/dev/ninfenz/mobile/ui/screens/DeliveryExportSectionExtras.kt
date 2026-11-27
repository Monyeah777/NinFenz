package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.TextButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import dev.ninfenz.mobile.data.ExportHistoryStore
import dev.ninfenz.mobile.share.ShareExporter
import dev.ninfenz.mobile.ui.components.NfCard
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType
import java.io.File

@Composable
internal fun ExportFieldsRow(a: DeliveryExportArgs) {
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
internal fun ExportNoticeText(a: DeliveryExportArgs) {
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
internal fun ExportDoneCard(onBack: () -> Unit) {
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
internal fun LatestExportCard(a: DeliveryExportArgs, latest: ExportHistoryStore.Entry) {
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
internal fun LatestExportActions(latest: ExportHistoryStore.Entry) {
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
internal fun LatestEvidenceButton(a: DeliveryExportArgs, latest: ExportHistoryStore.Entry) {
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
internal fun ExportResultLines(a: DeliveryExportArgs) {
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
internal fun DocxAuditLines(a: DeliveryExportArgs) {
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
internal fun ExportRecentBlock(a: DeliveryExportArgs) {
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
internal fun RecentExportRow(entry: ExportHistoryStore.Entry, onRemove: (ExportHistoryStore.Entry) -> Unit) {
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
