package dev.ninfenz.mobile.ui.screens

import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import android.content.Context
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.data.EpubExporter
import dev.ninfenz.mobile.data.HtmlExporter
import dev.ninfenz.mobile.data.PdfExporter
import dev.ninfenz.mobile.data.PdfUaExporter
import dev.ninfenz.mobile.model.Project
import java.io.File
import kotlinx.coroutines.launch

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
internal fun ExportButton(args: ExportButtonArgs) = with(args) {
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
internal fun PreservationExportButton(
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
internal fun NfDocExportButton(
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
internal fun EpubExportButton(args: EpubExportButtonArgs) = with(args) {
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
internal fun PdfExportButton(args: PdfExportButtonArgs) = with(args) {
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
internal fun PdfUaExportButton(
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
internal fun HtmlExportButton(
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
