package dev.ninfenz.mobile.data

import java.io.File

/** 最近一次导入预览的原始 nf-import JSON，用于进程死亡后恢复（不替代草稿）。 */
class ImportDraftStore(private val filesDir: File) {
    private fun file(): File = File(File(filesDir, "drafts").apply { mkdirs() }, "import-last.json")

    fun load(): String? {
        val f = file()
        if (!f.isFile) return null
        return try {
            f.readText(Charsets.UTF_8).takeIf { it.isNotBlank() }
        } catch (t: Throwable) {
            null
        }
    }

    fun save(rawJson: String) {
        if (rawJson.isBlank()) return
        AtomicFiles.writeText(file(), rawJson)
    }

    fun clear() {
        file().delete()
    }
}
