package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.data.ExportHistoryStore
import dev.ninfenz.mobile.data.DocxHeadingAuditResult
import dev.ninfenz.mobile.data.DocxStyleAuditResult
import dev.ninfenz.mobile.data.ExportVerifier
import dev.ninfenz.mobile.data.StyleTemplateStore
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ValidateReport
import java.io.File

internal class DeliveryExportArgs(
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
