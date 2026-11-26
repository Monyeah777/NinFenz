package dev.ninfenz.mobile.data

import java.io.File
import java.security.MessageDigest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 样式模板库：保存 DOCX/PDF 抽取的样式片段；首版不做完整语义逆向。 */
class StyleTemplateStore(private val filesDir: File) {
    data class StyleTemplate(
        val id: String,
        val name: String,
        val sourceFormat: String,
        val stylesXml: String,
        val sectPr: String,
        val themeXml: String,
        val numberingXml: String,
        val digest: String
    )

    private fun dir(): File = File(filesDir, "styles").apply { mkdirs() }

    fun list(): List<StyleTemplate> = dir().listFiles()
        ?.filter { it.isFile && it.name.endsWith(".json") }
        ?.sortedBy { it.name }
        ?.mapNotNull { f ->
            runCatching {
                val o = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
                StyleTemplate(
                    id = o["id"]?.jsonPrimitive?.content ?: return@runCatching null,
                    name = o["name"]?.jsonPrimitive?.content.orEmpty(),
                    sourceFormat = o["source_format"]?.jsonPrimitive?.content ?: "docx",
                    stylesXml = o["styles_xml"]?.jsonPrimitive?.content.orEmpty(),
                    sectPr = o["sect_pr"]?.jsonPrimitive?.content.orEmpty(),
                    themeXml = o["theme_xml"]?.jsonPrimitive?.content.orEmpty(),
                    numberingXml = o["numbering_xml"]?.jsonPrimitive?.content.orEmpty(),
                    digest = o["digest"]?.jsonPrimitive?.content.orEmpty()
                )
            }.getOrNull()
        }.orEmpty()

    fun save(
        name: String,
        sourceFormat: String,
        stylesXml: String,
        sectPr: String = "",
        themeXml: String = "",
        numberingXml: String = ""
    ): StyleTemplate {
        if (stylesXml.isBlank()) throw IllegalArgumentException("styles_xml 不能为空")
        val digest = sha256(stylesXml)
        val id = "style-" + digest.take(12)
        val o = buildJsonObject {
            put("schema", "nf-style-template/1")
            put("id", id)
            put("name", name.ifBlank { id })
            put("source_format", sourceFormat)
            put("styles_xml", stylesXml)
            if (sectPr.isNotBlank()) put("sect_pr", sectPr)
            if (themeXml.isNotBlank()) put("theme_xml", themeXml)
            if (numberingXml.isNotBlank()) put("numbering_xml", numberingXml)
            put("digest", digest)
        }
        AtomicFiles.writeText(File(dir(), id + ".json"), o.toString())
        return StyleTemplate(id, name.ifBlank { id }, sourceFormat, stylesXml, sectPr, themeXml, numberingXml, digest)
    }

    fun fromDocx(file: File, name: String): StyleTemplate {
        val styles = DocxReferenceStyles.extract(file)
            ?: throw IllegalArgumentException("DOCX 缺 word/styles.xml")
        return save(
            name = name,
            sourceFormat = "docx",
            stylesXml = styles,
            sectPr = DocxReferenceStyles.extractSectPr(file).orEmpty(),
            themeXml = DocxReferenceStyles.extractTheme(file).orEmpty(),
            numberingXml = DocxReferenceStyles.extractNumbering(file).orEmpty()
        )
    }

    fun delete(id: String) {
        File(dir(), id.replace(Regex("[^A-Za-z0-9._-]"), "_") + ".json").delete()
    }

    private fun sha256(text: String): String =
        MessageDigest.getInstance("SHA-256").digest(text.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }
}
