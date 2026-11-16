package dev.ninfenz.mobile.data

import java.io.File
import java.net.URLDecoder
import java.util.zip.ZipFile

/** EPUB 轻量导入：按 container.xml → OPF spine 顺序读取 XHTML，再转 Markdown。 */
object EpubImporter {
    fun extract(file: File): String {
        ZipFile(file).use { zip ->
            val container = read(zip, "META-INF/container.xml")
                ?: throw IllegalArgumentException("EPUB 缺 container.xml")
            val opfPath = attr(container, "full-path") ?: throw IllegalArgumentException("container 缺 rootfile")
            val opf = read(zip, opfPath) ?: throw IllegalArgumentException("EPUB 缺 OPF")
            val base = opfPath.substringBeforeLast('/', "")
            val manifest = Regex("(?is)<item\\s[^>]*>").findAll(opf).mapNotNull { m ->
                val id = attr(m.value, "id") ?: return@mapNotNull null
                val href = attr(m.value, "href") ?: return@mapNotNull null
                val type = attr(m.value, "media-type").orEmpty()
                id to Triple(href, type, resolve(base, href))
            }.toMap()
            val spine = Regex("(?is)<itemref\\s[^>]*>").findAll(opf).mapNotNull { m ->
                attr(m.value, "idref")
            }.toList()
            val order = spine.ifEmpty { manifest.keys.toList() }
            val chapterPaths = order.mapNotNull { id ->
                val (_, type, path) = manifest[id] ?: return@mapNotNull null
                if (type.isNotBlank() && !type.contains("xhtml") && !type.contains("html")) return@mapNotNull null
                path
            }
            var total = 0L
            chapterPaths.forEach { path ->
                val entry = zip.getEntry(path) ?: return@forEach
                total += entry.size.coerceAtLeast(0)
                require(total <= 256L * 1024 * 1024) { "EPUB 章节总量超限" }
            }
            val chapters = chapterPaths.mapNotNull { path ->
                read(zip, path)?.let { HtmlImporter.toMarkdown(it) }?.takeIf { it.isNotBlank() }
            }
            if (chapters.isEmpty()) throw IllegalArgumentException("EPUB 无可读章节")
            val body = chapters.joinToString("\n\n")
            val title = Regex("(?is)<dc:title[^>]*>(.*?)</dc:title>").find(opf)
                ?.groupValues?.getOrNull(1)
                ?.let { HtmlImporter.toMarkdown(it).trim() }
                .orEmpty()
            return if (title.isNotBlank() && !body.startsWith("# ")) "# $title\n\n$body" else body
        }
    }

    private fun read(zip: ZipFile, path: String): String? {
        val entry = zip.getEntry(path) ?: return null
        require(entry.size in 0..(64L * 1024 * 1024)) { "EPUB 条目过大：" + path }
        return zip.getInputStream(entry).use { String(it.readBytes(), Charsets.UTF_8) }
    }

    private fun attr(tag: String, name: String): String? =
        Regex("(?i)" + Regex.escape(name) + "\\s*=\\s*[\"']([^\"']*)[\"']").find(tag)?.groupValues?.getOrNull(1)

    private fun resolve(base: String, href: String): String {
        val decoded = runCatching { URLDecoder.decode(href, "UTF-8") }.getOrDefault(href)
        if (decoded.startsWith("/")) return decoded.dropWhile { it == '/' }
        val parts = (base.split('/').filter { it.isNotBlank() } + decoded.split('/'))
        val out = mutableListOf<String>()
        parts.forEach { part ->
            when (part) {
                "", "." -> Unit
                ".." -> if (out.isNotEmpty()) out.removeAt(out.size - 1)
                else -> out.add(part)
            }
        }
        return out.joinToString("/")
    }
}
