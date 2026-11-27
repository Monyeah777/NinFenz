package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.data.EpubImporter
import java.io.File

internal class ImportKind(
    val isCsv: Boolean = false,
    val isImage: Boolean = false,
    val isPdf: Boolean = false,
    val isDocx: Boolean = false,
    val isEpub: Boolean = false,
    val isHtml: Boolean = false,
    val isText: Boolean = false
)

internal fun classifyImport(name: String, mime: String?, file: File): ImportKind {
    if (isCsvFile(name, mime)) return ImportKind(isCsv = true)
    if (isImageFile(name, mime)) return ImportKind(isImage = true)
    if (isPdfFile(name, mime)) return ImportKind(isPdf = true)
    if (isDocxFile(name, mime)) return ImportKind(isDocx = true)
    if (isEpubFile(name, mime, file)) return ImportKind(isEpub = true)
    if (isHtmlFile(name, mime)) return ImportKind(isHtml = true)
    if (isTextFile(name, mime)) return ImportKind(isText = true)
    return ImportKind()
}

private fun isPdfFile(name: String, mime: String?): Boolean =
    name.endsWith(".pdf", true) || (mime ?: "").contains("pdf", ignoreCase = true)

private fun isCsvFile(name: String, mime: String?): Boolean =
    name.endsWith(".csv", true) || name.endsWith(".tsv", true) ||
        (mime ?: "").contains("csv", ignoreCase = true) || (mime ?: "").contains("tab-separated", ignoreCase = true)

private fun isImageFile(name: String, mime: String?): Boolean =
    (mime ?: "").startsWith("image/") || listOf(".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp").any { name.endsWith(it, true) }

private fun isDocxFile(name: String, mime: String?): Boolean =
    name.endsWith(".docx", true) || mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

private fun isEpubFile(name: String, mime: String?, file: File): Boolean =
    name.endsWith(".epub", true) || mime == "application/epub+zip" ||
        ((name.endsWith(".zip", true) || mime == "application/zip") && EpubImporter.isEpub(file))

private fun isHtmlFile(name: String, mime: String?): Boolean =
    name.endsWith(".html", true) || name.endsWith(".htm", true) || mime == "text/html"

private fun isTextFile(name: String, mime: String?): Boolean =
    name.endsWith(".txt", true) || name.endsWith(".md", true) ||
        name.endsWith(".markdown", true) || mime?.startsWith("text/") == true
