package dev.ninfenz.mobile.data

import java.io.File

/** 已保存的导入草稿列表；排除映射 sidecar、最近预览与导入历史。 */
object DraftLibrary {
    private val SPECIAL = setOf("import-last.json", "import-history.json")

    fun list(filesDir: File): List<File> {
        val dir = File(filesDir, "drafts")
        if (!dir.isDirectory) return emptyList()
        return dir.listFiles { f ->
            f.isFile && f.name.endsWith(".json") &&
                !f.name.endsWith(".mapping.json") &&
                f.name !in SPECIAL
        }?.sortedByDescending { it.lastModified() } ?: emptyList()
    }

    fun read(file: File): String? = try {
        if (file.isFile) file.readText(Charsets.UTF_8).takeIf { it.isNotBlank() } else null
    } catch (t: Throwable) {
        null
    }
}
