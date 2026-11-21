package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.NfDocModel
import java.io.File

/** 导出 nf-doc/1，作为再装配的结构化输入；JSON 固定格式以便复算。 */
object NfDocExporter {
    data class Created(val file: File)

    fun export(markdown: String, title: String, projectId: String, outDir: File): Created {
        val safe = projectId.replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "project" }
        outDir.mkdirs()
        val file = File(outDir, safe + ".nfdoc.json")
        val doc = NfDocModel.fromMarkdown(title, projectId, markdown)
        file.writeText(NfDocModel.toJson(doc).toString() + "\n", Charsets.UTF_8)
        return Created(file)
    }
}
