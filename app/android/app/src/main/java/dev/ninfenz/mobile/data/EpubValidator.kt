package dev.ninfenz.mobile.data

import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import javax.xml.parsers.DocumentBuilderFactory
import org.w3c.dom.Element

/** EPUB 结构自检：mimetype/container/OPF/nav/章节引用与 XHTML 可解析性。 */
object EpubValidator {
    data class Result(val ok: Boolean, val message: String, val issues: List<String>)

    fun inspect(file: File): Result {
        if (!file.isFile) return Result(false, "EPUB 不存在", listOf("missing file"))
        val issues = mutableListOf<String>()
        try {
            ZipFile(file).use { zip ->
                val entries = zip.entries().toList()
                if (entries.isEmpty() || entries.first().name != "mimetype") issues.add("mimetype 不是第一个条目")
                val mime = zip.getEntry("mimetype")
                if (mime == null) issues.add("缺少 mimetype")
                else {
                    if (mime.method != ZipEntry.STORED) issues.add("mimetype 未使用 STORED")
                    val text = zip.getInputStream(mime).bufferedReader().readText()
                    if (text != "application/epub+zip") issues.add("mimetype 内容错误")
                }
                val container = zip.getEntry("META-INF/container.xml")
                if (container == null) issues.add("缺少 container.xml")
                else {
                    val doc = parse(zip, container)
                    if (doc == null) issues.add("container.xml 不是合法 XML")
                    else {
                        val roots = doc.getElementsByTagName("rootfile")
                        if (roots.length == 0) issues.add("container 无 rootfile")
                        else {
                            val path = (roots.item(0) as Element).getAttribute("full-path")
                            val opf = zip.getEntry(path)
                            if (opf == null) issues.add("OPF 不存在：" + path)
                            else checkOpf(zip, opf, issues)
                        }
                    }
                }
            }
        } catch (t: Throwable) {
            return Result(false, "EPUB 解析失败：" + (t.message ?: t.javaClass.simpleName), issues + t.javaClass.simpleName)
        }
        return Result(issues.isEmpty(), if (issues.isEmpty()) "EPUB 结构校验通过" else issues.first(), issues)
    }

    private fun checkOpf(zip: ZipFile, opf: ZipEntry, issues: MutableList<String>) {
        val doc = parse(zip, opf)
        if (doc == null) { issues.add("OPF 不是合法 XML"); return }
        val items = doc.getElementsByTagName("item")
        val ids = mutableSetOf<String>()
        val hrefs = mutableSetOf<String>()
        var nav = false
        for (i in 0 until items.length) {
            val e = items.item(i) as Element
            val id = e.getAttribute("id")
            val href = e.getAttribute("href")
            ids.add(id)
            hrefs.add(href)
            if (e.getAttribute("properties").split(' ').contains("nav")) nav = true
            if (href.isBlank() || href.contains("..") || href.startsWith("/")) {
                issues.add("OPF 非法 href：" + href)
            } else if (zip.getEntry("OEBPS/" + href) == null) {
                issues.add("OPF 引用不存在：" + href)
            } else {
                val entry = zip.getEntry("OEBPS/" + href)
                if (href.endsWith(".xhtml") && parse(zip, entry) == null) issues.add("XHTML 解析失败：" + href)
            }
        }
        if (!nav) issues.add("OPF 缺少 nav 项")
        val refs = doc.getElementsByTagName("itemref")
        if (refs.length == 0) issues.add("spine 为空")
        for (i in 0 until refs.length) {
            val idref = (refs.item(i) as Element).getAttribute("idref")
            if (idref !in ids) issues.add("spine 引用不存在：" + idref)
        }
        if (hrefs.isEmpty()) issues.add("manifest 为空")
    }

    private fun parse(zip: ZipFile, entry: ZipEntry) = try {
        val factory = DocumentBuilderFactory.newInstance().apply { isNamespaceAware = true }
        runCatching { factory.setFeature("http://xml.org/sax/features/external-general-entities", false) }
        runCatching { factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false) }
        factory.newDocumentBuilder().parse(zip.getInputStream(entry))
    } catch (t: Throwable) {
        null
    }
}
