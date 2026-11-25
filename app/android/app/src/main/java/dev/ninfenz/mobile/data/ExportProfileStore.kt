package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long
import kotlinx.serialization.json.put

/** 导出样式预设：保存 DOCX 参考样式的提取结果，应用到后续 DOCX 导出。 */
class ExportProfileStore(private val filesDir: File) {
    data class Profile(
        val id: String,
        val name: String,
        val at: Long,
        val styles: String?,
        val sectPr: String?,
        val theme: String?,
        val numbering: String?,
        val header: String?,
        val footer: String?,
        val epubAuthor: String?,
        val epubLanguage: String?,
        val pdfPageSize: String?,
        val pdfIncludeTitle: Boolean?
    )

    private fun file(): File = File(filesDir, "export-profiles.json")

    fun load(): List<Profile> {
        val f = file()
        if (!f.isFile) return emptyList()
        return runCatching {
            Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject["profiles"]?.jsonArray?.mapNotNull { el ->
                val o = el.jsonObject
                Profile(
                    id = o["id"]?.jsonPrimitive?.content ?: "",
                    name = o["name"]?.jsonPrimitive?.content ?: "",
                    at = o["at"]?.jsonPrimitive?.long ?: 0L,
                    styles = o["styles"]?.jsonPrimitive?.content,
                    sectPr = o["sectPr"]?.jsonPrimitive?.content,
                    theme = o["theme"]?.jsonPrimitive?.content,
                    numbering = o["numbering"]?.jsonPrimitive?.content,
                    header = o["header"]?.jsonPrimitive?.content,
                    footer = o["footer"]?.jsonPrimitive?.content,
                    epubAuthor = o["epubAuthor"]?.jsonPrimitive?.content,
                    epubLanguage = o["epubLanguage"]?.jsonPrimitive?.content,
                    pdfPageSize = o["pdfPageSize"]?.jsonPrimitive?.content,
                    pdfIncludeTitle = o["pdfIncludeTitle"]?.jsonPrimitive?.content?.toBooleanStrictOrNull()
                )
            }.orEmpty()
        }.getOrElse { emptyList() }
    }

    fun save(
        name: String,
        styles: String?,
        sectPr: String?,
        theme: String?,
        numbering: String?,
        header: String?,
        footer: String?,
        epubAuthor: String? = null,
        epubLanguage: String? = null,
        pdfPageSize: String? = null,
        pdfIncludeTitle: Boolean? = null
    ): List<Profile> {
        val p = Profile(
            id = "e" + System.currentTimeMillis().toString(36),
            name = name.trim().ifBlank { "Export" },
            at = System.currentTimeMillis(),
            styles = styles,
            sectPr = sectPr,
            theme = theme,
            numbering = numbering,
            header = header,
            footer = footer,
            epubAuthor = epubAuthor,
            epubLanguage = epubLanguage,
            pdfPageSize = pdfPageSize,
            pdfIncludeTitle = pdfIncludeTitle
        )
        val next = (listOf(p) + load()).take(20)
        write(next)
        return next
    }

    fun remove(id: String) { write(load().filterNot { it.id == id }) }

    private fun write(profiles: List<Profile>) {
        val arr = buildJsonArray {
            profiles.forEach { p ->
                add(buildJsonObject {
                    put("id", p.id); put("name", p.name); put("at", p.at)
                    p.styles?.let { put("styles", it) }
                    p.sectPr?.let { put("sectPr", it) }
                    p.theme?.let { put("theme", it) }
                    p.numbering?.let { put("numbering", it) }
                    p.header?.let { put("header", it) }
                    p.footer?.let { put("footer", it) }
                    p.epubAuthor?.let { put("epubAuthor", it) }
                    p.epubLanguage?.let { put("epubLanguage", it) }
                    p.pdfPageSize?.let { put("pdfPageSize", it) }
                    p.pdfIncludeTitle?.let { put("pdfIncludeTitle", it) }
                })
            }
        }
        AtomicFiles.writeText(file(), buildJsonObject { put("profiles", arr) }.toString())
    }
}
