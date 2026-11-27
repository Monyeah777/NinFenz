package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.runtime.Composable
import androidx.compose.ui.text.AnnotatedString
import dev.ninfenz.mobile.data.AuthorArtifacts
import kotlinx.coroutines.launch

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.StepContent() {
    val current = artifacts ?: return
    if (activeStep == 0) PlanStep(current)
    if (activeStep == 1) SlotsStep()
    if (audit && activeStep == 2) AssembleStep(current)
    if (activeStep == 3) ExportStep(current)
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.PlanStep(current: AuthorArtifacts) {
    DeliveryPlanSection(
        plan = plan,
        busy = busy,
        constraintConflicts = constraintConflicts,
        onBrowsePlan = { showBrowsePlan = true },
        onCompile = { scope.launch { compilePlan(current) } }
    )
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.SlotsStep() {
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
            onBatchImport = { launchBatchPicker(arrayOf("*/*")) },
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

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.AssembleStep(current: AuthorArtifacts) {
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

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.ExportStep(current: AuthorArtifacts) {
    if (activeStep == 3) {
        ExportSectionStep(current)
        PreviewStep()
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.ExportSectionStep(current: AuthorArtifacts) {
    DeliveryExportSection(
        DeliveryExportArgs(
            project = project, markdown = markdown,
            exportMarkdown = exportMarkdown, report = report,
            exportedFile = exportedFile, busy = busy,
            contractUnsatisfiable = contractUnsatisfiable, exportBlocked = exportBlocked,
            batchFiles = batchFiles, exportBatchNote = exportBatchNote,
            docxStyles = docxStyles, docxSectPr = docxSectPr,
            docxTheme = docxTheme, docxNumbering = docxNumbering,
            docxHeader = docxHeader, docxFooter = docxFooter,
            epubAuthor = epubAuthor, epubLanguage = epubLanguage,
            pdfPageSize = pdfPageSize, pdfIncludeTitle = pdfIncludeTitle,
            selectedOutputTemplate = selectedOutputTemplate, audit = audit,
            grant = grant, capabilityRevision = capabilityRevision,
            styleTemplates = styleTemplates, showStyleTemplates = showStyleTemplates,
            docxStyleAudit = docxStyleAudit, docxHeadingAudit = docxHeadingAudit,
            outputRuleNote = outputRuleNote, exportNotice = exportNotice,
            exportEntries = exportEntries, manifestText = manifestText,
            exportVerify = exportVerify, reproText = reproText,
            reproOk = reproOk, recentExpanded = recentExpanded,
            evidenceBusy = evidenceBusy, evidenceNote = evidenceNote,
            scope = scope, onBusy = { busy = it },
            onError = { error = it }, onExportAll = { exportMarkdown?.let { md -> startExportAll(md) } },
            onExportDone = { format, file, manifest, report -> handleExportDone(format, file, manifest, report, exportMarkdown) }, onShowGrant = { showGrant = true },
            onOpenStyleTemplates = { openStyleTemplates() }, onDismissStyleTemplates = { showStyleTemplates = false },
            onPickStyleTemplate = { template -> pickStyleTemplate(template) }, onShowSaveExportProfile = { showSaveExportProfile = true },
            onShowExportProfiles = { exportProfiles = exportProfileStore.load(); showExportProfiles = true }, onShowOutputRules = { showOutputRules = true },
            onShowPreflight = { showPreflight = true }, onEpubAuthor = { epubAuthor = it },
            onEpubLanguage = { epubLanguage = it }, onPdfPageSize = { pdfPageSize = it },
            onPdfIncludeTitle = { pdfIncludeTitle = it }, onPickReference = { launchReferencePicker(arrayOf("application/vnd.openxmlformats-officedocument.wordprocessingml.document")) },
            onBack = onBack, onToggleRecent = { recentExpanded = !recentExpanded },
            onShowTrash = { showTrash = true }, onShowAllExports = { showAllExports = true },
            onClearExports = { exportHistory.clear(); exportEntries = emptyList() }, onPendingTrash = { pendingTrash = it },
        onEvidence = { latest -> packEvidence(latest) } )
    )
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@androidx.compose.runtime.Composable
internal fun DeliveryUiState.PreviewStep() {
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
