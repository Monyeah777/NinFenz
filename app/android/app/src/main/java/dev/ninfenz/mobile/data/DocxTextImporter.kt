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
                override fun startElement(uri: String?, localName: String?, qName: String?, attributes: Attributes?) {
                    val name = localName ?: qName.orEmpty()
                    if (name == "t") inText = true
                }
                override fun endElement(uri: String?, localName: String?, qName: String?) {
                    val name = localName ?: qName.orEmpty()
                    if (name == "t") inText = false
                    if (name == "p") text.append("\n\n")
                }
                override fun characters(ch: CharArray, start: Int, length: Int) {
                    if (inText) text.append(ch, start, length)
                }
            })
            return text.toString().replace(Regex("\n{3,}"), "\n\n").trim()
        }
    }
}
