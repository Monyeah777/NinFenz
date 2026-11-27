package dev.ninfenz.mobile.ui.screens

import android.content.Context
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.ui.safeCall
import java.io.File
import kotlinx.serialization.json.JsonObject
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
