package dev.ninfenz.mobile.data

import java.io.File
import java.net.URLDecoder
import java.util.zip.ZipFile

/** EPUB 轻量导入：按 container.xml → OPF spine 顺序读取 XHTML，再转 Markdown。 */
object EpubImporter {
    fun isEpub(file: File): Boolean = try {
        ZipFile(file).use { zip ->
            val mime = zip.getEntry("mimetype")?.let { entry ->
                zip.getInputStream(entry).use { String(it.readBytes(), Charsets.US_ASCII).trim() }
            }
            mime == "application/epub+zip" || zip.getEntry("META-INF/container.xml") != null
        }
    } catch (t: Throwable) {
        false
    }

    fun extract(file: File): String {
        ImportPreflight.check(file)
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
            val budget = longArrayOf(20L * 1024 * 1024)
            val chapters = chapterPaths.mapNotNull { path ->
                read(zip, path)?.let { HtmlImporter.toMarkdown(embedImages(zip, path, it, budget)) }?.takeIf { it.isNotBlank() }
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

    private fun embedImages(zip: ZipFile, chapterPath: String, html: String, budget: LongArray): String {
        val base = chapterPath.substringBeforeLast('/', "")
        return Regex("(?is)<img\\s+([^>]*?)src=[\"']([^\"']+)[\"']([^>]*)>").replace(html) { m ->
            val src = m.groupValues[2]
            if (src.startsWith("data:") || src.startsWith("http://") || src.startsWith("https://")) {
                return@replace m.value
            }
            val entryPath = resolve(base, src)
            val entry = zip.getEntry(entryPath) ?: return@replace m.value
            if (entry.size !in 0..(2L * 1024 * 1024) || entry.size > budget[0]) return@replace m.value
            val mime = when (entryPath.substringAfterLast('.', "").lowercase()) {
                "png" -> "image/png"
                "jpg", "jpeg" -> "image/jpeg"
                "gif" -> "image/gif"
                "webp" -> "image/webp"
                "svg" -> "image/svg+xml"
                else -> return@replace m.value
            }
            val bytes = zip.getInputStream(entry).use { it.readBytes() }
            budget[0] -= bytes.size
            val b64 = java.util.Base64.getEncoder().encodeToString(bytes)
            "<img " + m.groupValues[1] + "src=\"data:" + mime + ";base64," + b64 + "\"" + m.groupValues[3] + ">"
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
