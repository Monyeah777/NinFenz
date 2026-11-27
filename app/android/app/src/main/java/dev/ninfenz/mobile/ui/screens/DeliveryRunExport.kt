package dev.ninfenz.mobile.ui.screens

import android.content.Context
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.ui.safeCall
import java.io.File
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonObjectBuilder
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

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

internal suspend fun runDeliveryExport(args: RunDeliveryExportArgs) {
    with(args) {
        val outDir = File(File(context.filesDir, "exports"), "delivery").apply { mkdirs() }
        val response = safeCall("export", exportPayload(args, outDir))
        if (!response.ok) {
            setError(response.error)
            return
        }
        val manifest = response.resultObject()
        val file = exportFileFor(outDir, manifest)
        val report = file?.let { checkRepro(args, it) }
        onDone(file, manifest?.toString(), report)
    }
}

private fun exportPayload(args: RunDeliveryExportArgs, dir: File): JsonObject = buildJsonObject {
    put("markdown", args.md)
    put("format", args.format)
    put("out_dir", dir.absolutePath)
    put("manifest", true)
    put("title", args.project.title)
    put("project_id", args.project.id)
    addDocxFields(this, args)
}

private fun addDocxFields(target: JsonObjectBuilder, args: RunDeliveryExportArgs) {
    if (args.format != "docx") return
    putIfNotNull(target, "docx_styles", args.docxStyles)
    putIfNotNull(target, "docx_sect_pr", args.docxSectPr)
    putIfNotNull(target, "docx_theme", args.docxTheme)
    putIfNotNull(target, "docx_numbering", args.docxNumbering)
    putIfNotNull(target, "docx_header", args.docxHeader)
    putIfNotNull(target, "docx_footer", args.docxFooter)
}

private fun putIfNotNull(target: JsonObjectBuilder, key: String, value: String?) {
    if (value == null) return
    target.put(key, value)
}

private fun exportFileFor(dir: File, manifest: JsonObject?): File? {
    val name = manifest?.get("files")?.toString()?.let { raw ->
        Regex("\"name\":\"([^\"]+)\"").find(raw)?.groupValues?.getOrNull(1)
    }
    return name?.let { File(dir, it) }
}

private suspend fun checkRepro(
    args: RunDeliveryExportArgs,
    file: File
): dev.ninfenz.mobile.data.ReproChecker.Report? {
    val reproDir = File(args.context.cacheDir, "repro-core-" + args.format).apply {
        deleteRecursively()
        mkdirs()
    }
    val second = safeCall("export", exportPayload(args, reproDir))
    var report: dev.ninfenz.mobile.data.ReproChecker.Report? = null
    if (second.ok) {
        val secondFile = exportFileFor(reproDir, second.resultObject())
        if (secondFile != null) report = dev.ninfenz.mobile.data.ReproChecker.check(file, secondFile)
    }
    reproDir.deleteRecursively()
    return report
}
