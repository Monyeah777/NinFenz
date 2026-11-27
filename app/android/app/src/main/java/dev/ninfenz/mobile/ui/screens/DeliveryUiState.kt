package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.size
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import android.content.Context
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.data.AuthorArtifacts
import dev.ninfenz.mobile.data.AssemblyPresetStore
import dev.ninfenz.mobile.data.DeliveryDraftStore
import dev.ninfenz.mobile.data.DeliveryVersionStore
import dev.ninfenz.mobile.data.ExtensionStore
import dev.ninfenz.mobile.data.ExportProfileStore
import dev.ninfenz.mobile.data.ExportHistoryStore
import dev.ninfenz.mobile.data.ContractGate
import dev.ninfenz.mobile.data.ContractIrStore
import dev.ninfenz.mobile.data.DocxHeadingAuditResult
import dev.ninfenz.mobile.data.DocxStyleAuditResult
import dev.ninfenz.mobile.data.ExportVerifier
import dev.ninfenz.mobile.data.MacroStore
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.StyleTemplateStore
import dev.ninfenz.mobile.data.ProjectStatusStore
import dev.ninfenz.mobile.model.AssemblyPlan
import dev.ninfenz.mobile.model.MarkdownBlock
import dev.ninfenz.mobile.model.FidelityReconcile
import dev.ninfenz.mobile.model.MacroBatchResult
import dev.ninfenz.mobile.model.MacroRunResult
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.SlotBatchImporter
import dev.ninfenz.mobile.model.ValidateReport
import java.io.File
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonPrimitive
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue

internal class DeliveryUiState(
    val context: android.content.Context,
    val clipboard: androidx.compose.ui.platform.ClipboardManager,
    val scope: kotlinx.coroutines.CoroutineScope,
    var project: Project,
    var pack: PackEntry?,
    var onBack: () -> Unit,
    var onOpenPacks: () -> Unit,
    var onPatch: () -> Unit,
    var onStatusChanged: () -> Unit,
    var audit: Boolean,
    var capabilityRevision: Int = 0,
) {
    val sampleStore = dev.ninfenz.mobile.data.PromptSampleStore(context.filesDir)
    val statusStore = ProjectStatusStore(context.filesDir)
    val contractStore = dev.ninfenz.mobile.data.ContractStore(context.filesDir)
    val grantStore = dev.ninfenz.mobile.data.CapabilityGrantStore(context.filesDir)
    var grant by mutableStateOf(grantStore.load(project.id) ?: dev.ninfenz.mobile.data.CapabilityGrant.defaultForPackage())
    var showGrant by mutableStateOf(false)
    var status by mutableStateOf(project.status)
    var signoff by mutableStateOf(contractStore.load(project.id))
    var statusNote by mutableStateOf<String?>(null)
    var artifacts by mutableStateOf<AuthorArtifacts?>(null)
    var loadError by mutableStateOf<String?>(null)
    var loading by mutableStateOf(true)
    var plan by mutableStateOf<AssemblyPlan?>(null)
    var rawPlan by mutableStateOf<JsonObject?>(null)
    var inputs by mutableStateOf<Map<String, String>>(emptyMap())
    var templateReference = run {
dev.ninfenz.mobile.data.ProjectPaths.templateMd(context.filesDir, project.id)
            .takeIf { it.isFile }?.readText(Charsets.UTF_8)
    }
    var parsedTemplateSlots = parseTemplateSlots(templateReference.orEmpty())
    var markdown by mutableStateOf<String?>(null)
    var showFullPreview by mutableStateOf(false)
    var editingPreview by mutableStateOf(false)
    var showResetConfirm by mutableStateOf(false)
    var previewBlocks by mutableStateOf<List<MarkdownBlock>>(emptyList())
    var previewBaseline by mutableStateOf<List<MarkdownBlock>>(emptyList())
    var ignoredHints by mutableStateOf<Set<Int>>(emptySet())
    var inferredTransform by mutableStateOf<dev.ninfenz.mobile.model.FlashFillModel.Transform?>(null)
    var showManualTransform by mutableStateOf(false)
    var manualKind by mutableStateOf("lower")
    var manualA by mutableStateOf("")
    var manualB by mutableStateOf("")
    var savedTransform by mutableStateOf(dev.ninfenz.mobile.data.TransformStore(context.filesDir).load(project.id))
    var previewHistory by mutableStateOf<List<List<MarkdownBlock>>>(emptyList())
    var previewRedo by mutableStateOf<List<List<MarkdownBlock>>>(emptyList())
    var previewDirty by mutableStateOf(false)
    var showBulk by mutableStateOf(false)
    var bulkFrom by mutableStateOf("")
    var bulkTo by mutableStateOf("")
    var bulkError by mutableStateOf<String?>(null)
    var bulkMode by mutableStateOf("replace")
    var needsRevalidate by mutableStateOf(false)
    val assembleRequester = BringIntoViewRequester()
    val validateRequester = BringIntoViewRequester()
    var missingRequired by mutableStateOf<List<String>>(emptyList())
    var oversizedSlots by mutableStateOf<List<String>>(emptyList())
    var constraintViolations by mutableStateOf<List<String>>(emptyList())
    var showDiscardPreview by mutableStateOf(false)
    var showConstraintLens by mutableStateOf(false)
    var assignBlockText by mutableStateOf<String?>(null)
    var report by mutableStateOf<ValidateReport?>(null)
    var manifestText by mutableStateOf<String?>(null)
    var exportedFile by mutableStateOf<File?>(null)
    var batchFiles by mutableStateOf<List<File>>(emptyList())
    var exportBatchNote by mutableStateOf<String?>(null)
    var error by mutableStateOf<CoreError?>(null)
    var slotImportTarget by mutableStateOf<String?>(null)
    var slotImportSource by mutableStateOf("")
    var slotImportFormat by mutableStateOf("text")
    var slotImportOriginal by mutableIntStateOf(0)
    var slotImportAdapted by mutableIntStateOf(0)
    var slotImportText by mutableStateOf("")
    var batchChunks by mutableStateOf<List<SlotBatchImporter.Chunk>>(emptyList())
    var batchSource by mutableStateOf("")
    var batchNote by mutableStateOf<String?>(null)
    var batchUndo by mutableStateOf<Map<String, String>?>(null)
    val draftStore = DeliveryDraftStore(context.filesDir)
    val versionStore = DeliveryVersionStore(context.filesDir)
    val presetStore = AssemblyPresetStore(context.filesDir)
    var showVersions by mutableStateOf(false)
    var compareVersionText by mutableStateOf<String?>(null)
    var compareVersionLabel by mutableStateOf("")
    var fidelityResult by mutableStateOf<FidelityReconcile?>(null)
    var showPresets by mutableStateOf(false)
    val extensionVariants = ExtensionStore(context.filesDir).contributions(setOf("delivery_variant"))
    val extensionTransforms = ExtensionStore(context.filesDir).contributions(setOf("slot_transform"))
    val assemblyRecipes = ExtensionStore(context.filesDir).contributions(setOf("assembly_recipe"))
    var showVariants by mutableStateOf(false)
    var showTransforms by mutableStateOf(false)
    var variantNote by mutableStateOf<String?>(null)
    var showSavePreset by mutableStateOf(false)
    var presetName by mutableStateOf("")
    val exportHistory = ExportHistoryStore(context.filesDir)
    var exportEntries by mutableStateOf(exportHistory.load())
    var recentExpanded by mutableStateOf(true)
    var showAllExports by mutableStateOf(false)
    var showTrash by mutableStateOf(false)
    var pendingTrash by mutableStateOf<dev.ninfenz.mobile.data.ExportHistoryStore.Entry?>(null)
    var exportNotice by mutableStateOf<String?>(null)
    var evidenceBusy by mutableStateOf(false)
    var evidenceNote by mutableStateOf<String?>(null)
    var exportVerify by mutableStateOf<ExportVerifier.Result?>(null)
    var reproText by mutableStateOf<String?>(null)
    var reproOk by mutableStateOf<Boolean?>(null)
    var validateRepro by mutableStateOf<String?>(null)
    val exportProfileStore = ExportProfileStore(context.filesDir)
    var exportProfiles by mutableStateOf(exportProfileStore.load())
    val extensionProfiles = run {
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
    var showExportProfiles by mutableStateOf(false)
    var showSaveExportProfile by mutableStateOf(false)
    var exportProfileName by mutableStateOf("")
    val outputRules = ExtensionStore(context.filesDir).contributions(setOf("output_rule"))
    var selectedOutputTemplate by mutableStateOf<String?>(null)
    var showOutputRules by mutableStateOf(false)
    var outputRuleNote by mutableStateOf<String?>(null)
    val preflightProfiles = if (audit) ExtensionStore(context.filesDir).contributions(setOf("preflight_profile")) else emptyList()
    var selectedPreflight by mutableStateOf<dev.ninfenz.mobile.data.ExtensionStore.Contribution?>(null)
    var showPreflight by mutableStateOf(false)
    var pdfPageSize by mutableStateOf("A4")
    var pdfIncludeTitle by mutableStateOf(true)
    var epubAuthor by mutableStateOf("")
    var epubLanguage by mutableStateOf("zh")
    var docxStyles by mutableStateOf<String?>(null)
    var docxStyleAudit by mutableStateOf<DocxStyleAuditResult?>(null)
    var docxHeadingAudit by mutableStateOf<DocxHeadingAuditResult?>(null)
    var contractUnsatisfiable = ContractGate.blocked(ContractIrStore(context.filesDir, project.id).loadSolve())
    var contractValues = ContractIrStore(context.filesDir, project.id).loadValues()
    var docxSectPr by mutableStateOf<String?>(null)
    var docxTheme by mutableStateOf<String?>(null)
    var docxNumbering by mutableStateOf<String?>(null)
    var docxHeader by mutableStateOf<String?>(null)
    var docxFooter by mutableStateOf<String?>(null)
    val styleStore = StyleTemplateStore(context.filesDir)
    var styleTemplates by mutableStateOf(emptyList<StyleTemplateStore.StyleTemplate>())
    var showStyleTemplates by mutableStateOf(false)
    var restoredInputs = draftStore.load(project.id)
    var zeroPrefill = run {
val file = dev.ninfenz.mobile.data.ProjectPaths.zeroSlice(context.filesDir, project.id)
        dev.ninfenz.mobile.data.ZeroSliceStore(context.filesDir).read(file)?.slotValues ?: emptyMap()
    }
    var restoredPlan = draftStore.loadPlan(project.id)
    var restoredMarkdown = draftStore.loadMarkdown(project.id)
    var draftNote by mutableStateOf(
            when {
                restoredInputs.isNotEmpty() -> context.getString(dev.ninfenz.mobile.R.string.delivery_draft_restored)
                protocolPrefill.isNotEmpty() -> context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.delivery_protocol_prefill, protocolPrefill.size, protocolPrefill.size)
                else -> null
            }
        )
    var busy by mutableStateOf(false)
    var deliveryMenu by mutableStateOf(false)
    var showMacros by mutableStateOf(false)
    var macroItems by mutableStateOf(emptyList<MacroStore.Macro>())
    var macroResult by mutableStateOf<MacroRunResult?>(null)
    var macroBatchResult by mutableStateOf<MacroBatchResult?>(null)
    var macroSelected by mutableStateOf<MacroStore.Macro?>(null)
    var macroParams by mutableStateOf<Map<String, String>>(emptyMap())
    var showMacroParams by mutableStateOf(false)
    var showMacroBatchConfirm by mutableStateOf(false)
    var showBrowsePlan by mutableStateOf(false)
    var activeStep by mutableStateOf(step)
    var showLeaveConfirm by mutableStateOf(false)

    val latestInputs = mutableStateOf(inputs)
    val latestPlan = mutableStateOf(plan)
    var launchReferencePicker: (Array<String>) -> Unit = {}
    var launchSlotPicker: (Array<String>) -> Unit = {}
    var launchBatchPicker: (Array<String>) -> Unit = {}

    private var resetProjectId: String? = project.id

    fun resetForProject(project: Project) {
        if (resetProjectId == project.id) return
        resetProjectId = project.id
        this.project = project
        grant = grantStore.load(project.id) ?: dev.ninfenz.mobile.data.CapabilityGrant.defaultForPackage()
        status = project.status
        signoff = contractStore.load(project.id)
        templateReference = run {
dev.ninfenz.mobile.data.ProjectPaths.templateMd(context.filesDir, project.id)
            .takeIf { it.isFile }?.readText(Charsets.UTF_8)
    }
        parsedTemplateSlots = parseTemplateSlots(templateReference.orEmpty())
        savedTransform = dev.ninfenz.mobile.data.TransformStore(context.filesDir).load(project.id)
        contractUnsatisfiable = ContractGate.blocked(ContractIrStore(context.filesDir, project.id).loadSolve())
        contractValues = ContractIrStore(context.filesDir, project.id).loadValues()
        restoredInputs = draftStore.load(project.id)
        zeroPrefill = run {
val file = dev.ninfenz.mobile.data.ProjectPaths.zeroSlice(context.filesDir, project.id)
        dev.ninfenz.mobile.data.ZeroSliceStore(context.filesDir).read(file)?.slotValues ?: emptyMap()
    }
        restoredPlan = draftStore.loadPlan(project.id)
        restoredMarkdown = draftStore.loadMarkdown(project.id)
        draftNote = when {
                restoredInputs.isNotEmpty() -> context.getString(dev.ninfenz.mobile.R.string.delivery_draft_restored)
                protocolPrefill.isNotEmpty() -> context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.delivery_protocol_prefill, protocolPrefill.size, protocolPrefill.size)
                else -> null
            }
        activeStep = step
    }
}
