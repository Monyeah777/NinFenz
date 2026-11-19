package dev.ninfenz.mobile.data

import java.io.File
import java.util.zip.ZipFile
import javax.xml.parsers.SAXParserFactory
import org.xml.sax.Attributes
import org.xml.sax.helpers.DefaultHandler

/** DOCX 正文提取：只读 word/document.xml，不执行宏/外部关系。 */
object DocxTextImporter {
    private const val MAX_XML = 20L * 1024 * 1024

    fun extract(file: File): String {
        require(file.isFile && file.length() in 1..(25L * 1024 * 1024)) { "DOCX 文件为空或超过 25MB" }
        ZipFile(file).use { zip ->
            val entry = zip.getEntry("word/document.xml") ?: error("DOCX 缺少 word/document.xml")
            require(entry.size in 0..MAX_XML) { "DOCX 正文过大" }
            val text = StringBuilder()
            val factory = SAXParserFactory.newInstance().apply { isNamespaceAware = true }
            factory.newSAXParser().parse(zip.getInputStream(entry), object : DefaultHandler() {
                private var inText = false
                private val paragraph = StringBuilder()
                private var heading = 0
                private var listItem = false
                private var inTable = false
                private var inCell = false
                private val cell = StringBuilder()
                private val rows = mutableListOf<MutableList<String>>()
                private val row = mutableListOf<String>()
                override fun startElement(uri: String?, localName: String?, qName: String?, attributes: Attributes?) {
                    val name = localName ?: qName.orEmpty()
                    if (name == "t") inText = true
                    if (name == "tbl") inTable = true
                    if (name == "tc") { inCell = true; cell.clear() }
                    if (name == "numPr") listItem = true
                    if (name == "pStyle") {
                        val style = attributes?.getValue("w:val") ?: attributes?.getValue("val").orEmpty()
                        heading = Regex("(?i)(?:heading|标题)\\s*([1-6])").find(style)?.groupValues?.get(1)?.toIntOrNull()
                            ?: Regex("^([1-6])$").find(style)?.groupValues?.get(1)?.toIntOrNull()
                            ?: 0
                    }
                }
                override fun endElement(uri: String?, localName: String?, qName: String?) {
                    val name = localName ?: qName.orEmpty()
                    if (name == "t") inText = false
                    if (name == "p") {
                        val value = paragraph.toString().trim()
                        if (value.isNotBlank()) {
                            if (inCell) {
                                if (cell.isNotEmpty()) cell.append(' ')
                                cell.append(value)
                            } else {
                                if (heading in 1..6) text.append("#".repeat(heading)).append(' ')
                                if (listItem) text.append("- ")
                                text.append(value).append("\n\n")
                            }
                        }
                        paragraph.clear()
                        heading = 0
                        listItem = false
                    }
                    if (name == "tc") {
                        row.add(cell.toString().trim())
                        inCell = false
                        cell.clear()
                    }
                    if (name == "tr") {
                        if (row.isNotEmpty()) {
                            rows.add(row.toMutableList())
                            row.clear()
                        }
                    }
                    if (name == "tbl") {
                        rows.forEachIndexed { index, cells ->
                            text.append("| ").append(cells.joinToString(" | ")).append(" |\n")
                            if (index == 0) text.append("|").append(" --- |".repeat(cells.size)).append("\n")
                        }
                        text.append('\n')
                        rows.clear()
                        inTable = false
                    }
                }
                override fun characters(ch: CharArray, start: Int, length: Int) {
                    if (inText) paragraph.append(ch, start, length)
                }
            })
            return text.toString().replace(Regex("\n{3,}"), "\n\n").trim()
        }
    }
}
