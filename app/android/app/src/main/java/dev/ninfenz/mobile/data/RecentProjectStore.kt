package dev.ninfenz.mobile.data

import java.io.File

/** 最近打开项目的本地优先级；点击项目后把它移到最前，最多保留 20 条。 */
class RecentProjectStore(private val filesDir: File) {
    private fun file(): File = File(filesDir, "recent-projects.txt")

    fun load(): List<String> {
        val f = file()
        if (!f.isFile) return emptyList()
        return runCatching {
            f.readLines(Charsets.UTF_8).map { it.trim() }.filter { it.isNotBlank() }.distinct().take(20)
        }.getOrDefault(emptyList())
    }

    fun record(projectId: String): List<String> {
        val next = (listOf(projectId) + load().filterNot { it == projectId }).take(20)
        AtomicFiles.writeText(file(), next.joinToString("\n"))
        return next
    }
}
