package dev.ninfenz.mobile.data

import java.io.File

/** 本地 AI 样本；只保存用户主动确认的 Markdown，不上传。 */
class PromptSampleStore(private val filesDir: File) {
    fun save(title: String, markdown: String): File {
        val dir = File(filesDir, "samples").apply { mkdirs() }
        val safe = title.replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "sample" }.take(40)
        val file = File(dir, "sample-" + System.currentTimeMillis() + "-" + safe + ".md")
        file.writeText(markdown, Charsets.UTF_8)
        return file
    }

    fun delete(file: File): Boolean = runCatching { file.delete() }.getOrDefault(false)

    fun list(): List<File> {
        val dir = File(filesDir, "samples")
        if (!dir.isDirectory) return emptyList()
        return dir.listFiles { f -> f.isFile && f.name.startsWith("sample-") && f.name.endsWith(".md") }
            ?.sortedByDescending { it.lastModified() }
            ?: emptyList()
    }
}
