package dev.ninfenz.mobile.data

import java.io.File
import java.util.zip.ZipFile

/** 从参考 .docx 读取 word/styles.xml；只读、限 1 MiB、不落盘。 */
object DocxReferenceStyles {
    const val MAX_BYTES = 1024 * 1024

    fun extract(file: File): String? {
        if (!file.isFile) return null
        return try {
            ZipFile(file).use { zip ->
                val entry = zip.getEntry("word/styles.xml") ?: return null
                if (entry.size > MAX_BYTES) return null
                val bytes = zip.getInputStream(entry).use { it.readBytes() }
                if (bytes.size > MAX_BYTES) return null
                String(bytes, Charsets.UTF_8).takeIf { it.contains("<w:styles") }
            }
        } catch (t: Throwable) {
            null
        }
    }
}
