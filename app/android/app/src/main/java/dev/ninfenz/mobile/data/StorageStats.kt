package dev.ninfenz.mobile.data

import java.io.File

/** 存储明细：只读统计；清理只针对 app cache 下的导入/分享临时文件。 */
object StorageStats {
    data class Breakdown(
        val projects: Long,
        val drafts: Long,
        val exports: Long,
        val cache: Long
    ) {
        val total: Long get() = projects + drafts + exports + cache
    }

    fun scan(filesDir: File, cacheDir: File): Breakdown = Breakdown(
        projects = size(File(filesDir, "projects")),
        drafts = size(File(filesDir, "drafts")),
        exports = size(File(filesDir, "exports")),
        cache = size(cacheDir)
    )

    fun clearImportCache(cacheDir: File): Int {
        var removed = 0
        listOf("imports", "shared").forEach { name ->
            val dir = File(cacheDir, name)
            if (dir.exists()) {
                removed += dir.walkTopDown().filter { it.isFile }.count()
                dir.deleteRecursively()
            }
        }
        return removed
    }

    private fun size(dir: File): Long =
        if (!dir.exists()) 0L else dir.walkTopDown().filter { it.isFile }.sumOf { it.length() }
}
