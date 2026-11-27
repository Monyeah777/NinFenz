package dev.ninfenz.mobile.data

import java.io.File
import java.security.MessageDigest
import java.util.zip.CRC32
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** 轻量 EPUB 3 导出：基础 Markdown 转 XHTML，确定性 zip；离线、无外部依赖。 */
object EpubExporter {
    data class Chapter(val title: String, val body: String)
    data class Created(val file: File, val chapters: Int, val bytes: Long)

    fun export(markdown: String, title: String, outDir: File, author: String = "", language: String = "zh", fileName: String = "result.epub"): Created {
        outDir.mkdirs()
        val target = File(outDir, fileName)
        val chapters = chapters(markdown)
        val id = "urn:nf:" + sha256(title.toByteArray()).take(16)
        val files = chapters.indices.map { "chapter-" + (it + 1).toString().padStart(3, '0') + ".xhtml" }
        ZipOutputStream(target.outputStream()).use { out ->
            val mimetype = "application/epub+zip".toByteArray()
            val crc = CRC32().apply { update(mimetype) }.value
            out.putNextEntry(ZipEntry("mimetype").apply {
                method = ZipEntry.STORED; time = 0L; size = mimetype.size.toLong(); compressedSize = size; this.crc = crc
            })
            out.write(mimetype)
            out.closeEntry()
            put(out, "META-INF/container.xml", container())
            put(out, "OEBPS/content.opf", opf(title, id, files, author, language))
            put(out, "OEBPS/nav.xhtml", nav(title, chapters, files))
            put(out, "OEBPS/style.css", "body{font-family:serif;line-height:1.6;margin:1em}pre{white-space:pre-wrap}")
            chapters.forEachIndexed { i, c -> put(out, "OEBPS/" + files[i], chapterXhtml(c)) }
        }
        return Created(target, chapters.size, target.length())
    }

    fun chapters(markdown: String): List<Chapter> {
        val out = mutableListOf<Chapter>()
        var title = "正文"
        val body = StringBuilder()
        var started = false
        fun flush() {
            if (started || out.isEmpty()) out.add(Chapter(title, body.toString()))
            body.clear()
        }
        markdown.replace("\r\n", "\n").split('\n').forEach { line ->
            val h1 = Regex("^#\\s+(.+)$").find(line)
            if (h1 != null) {
                if (started) flush()
                title = h1.groupValues[1].trim()
                started = true
            } else {
                body.append(line).append('\n')
                if (line.isNotBlank()) started = true
            }
        }
        flush()
        return out.filter { it.title.isNotBlank() || it.body.isNotBlank() }.ifEmpty { listOf(Chapter("正文", "")) }
    }

    private fun chapterXhtml(c: Chapter): String {
        val sb = StringBuilder()
        sb.append("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")
        sb.append("<!DOCTYPE html>\n<html xmlns=\"http://www.w3.org/1999/xhtml\" lang=\"zh\"><head><meta charset=\"utf-8\"/><title>")
        sb.append(MarkdownHtml.esc(c.title)).append("</title><link rel=\"stylesheet\" href=\"style.css\"/></head><body><h1>")
        sb.append(MarkdownHtml.esc(c.title)).append("</h1>\n")
        sb.append(MarkdownHtml.body(c.body, MarkdownHtml.ImagePolicy.DATA_ONLY))
        sb.append("</body></html>\n")
        return sb.toString()
    }

    private fun opf(title: String, id: String, files: List<String>, author: String, language: String): String {
        val sb = StringBuilder()
        sb.append("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")
        sb.append("<package xmlns=\"http://www.idpf.org/2007/opf\" version=\"3.0\" unique-identifier=\"uid\">")
        sb.append("<metadata xmlns:dc=\"http://purl.org/dc/elements/1.1/\">")
        sb.append("<dc:identifier id=\"uid\">").append(MarkdownHtml.esc(id)).append("</dc:identifier>")
        sb.append("<dc:title>").append(MarkdownHtml.esc(title)).append("</dc:title><dc:language>")
            .append(MarkdownHtml.esc(language.ifBlank { "zh" })).append("</dc:language>")
        if (author.isNotBlank()) sb.append("<dc:creator>").append(MarkdownHtml.esc(author)).append("</dc:creator>")
        sb.append("<meta property=\"dcterms:modified\">1970-01-01T00:00:00Z</meta></metadata><manifest>")
        sb.append("<item id=\"nav\" href=\"nav.xhtml\" media-type=\"application/xhtml+xml\" properties=\"nav\"/>")
        sb.append("<item id=\"css\" href=\"style.css\" media-type=\"text/css\"/>")
        files.forEachIndexed { i, f ->
            sb.append("<item id=\"ch").append(i + 1).append("\" href=\"").append(f)
                .append("\" media-type=\"application/xhtml+xml\"/>")
        }
        sb.append("</manifest><spine>")
        files.indices.forEach { sb.append("<itemref idref=\"ch").append(it + 1).append("\"/>") }
        sb.append("</spine></package>\n")
        return sb.toString()
    }

    private fun nav(title: String, chapters: List<Chapter>, files: List<String>): String {
        val sb = StringBuilder()
        sb.append("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")
        sb.append("<!DOCTYPE html>\n<html xmlns=\"http://www.w3.org/1999/xhtml\" xmlns:epub=\"http://www.idpf.org/2007/ops\" lang=\"zh\">")
        sb.append("<head><meta charset=\"utf-8\"/><title>").append(MarkdownHtml.esc(title)).append("</title></head>")
        sb.append("<body><nav epub:type=\"toc\"><h1>").append(MarkdownHtml.esc(title)).append("</h1><ol>")
        chapters.forEachIndexed { i, c ->
            sb.append("<li><a href=\"").append(files[i]).append("\">").append(MarkdownHtml.esc(c.title)).append("</a></li>")
        }
        sb.append("</ol></nav></body></html>\n")
        return sb.toString()
    }

    private fun container(): String =
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<container version=\"1.0\" xmlns=\"urn:oasis:names:tc:opendocument:xmlns:container\">" +
            "<rootfiles><rootfile full-path=\"OEBPS/content.opf\" media-type=\"application/oebps-package+xml\"/></rootfiles></container>\n"

    private fun put(out: ZipOutputStream, name: String, text: String) {
        out.putNextEntry(ZipEntry(name).apply { time = 0L })
        out.write(text.toByteArray(Charsets.UTF_8))
        out.closeEntry()
    }

    private fun sha256(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
}
