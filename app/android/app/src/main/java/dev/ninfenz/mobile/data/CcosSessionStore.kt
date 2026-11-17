package dev.ninfenz.mobile.data

import java.io.File

/** CCOS 导入的 task/result 原文落盘，供进程恢复；只写 app 私有目录。 */
object CcosSessionStore {
    private fun dir(filesDir: File) = File(filesDir, "ccos-session").apply { mkdirs() }

    fun saveTask(filesDir: File, text: String) = AtomicFiles.writeText(File(dir(filesDir), "task.json"), text)

    fun saveResult(filesDir: File, text: String) = AtomicFiles.writeText(File(dir(filesDir), "result.json"), text)

    fun loadTask(filesDir: File): String? = readOrNull(File(dir(filesDir), "task.json"))

    fun loadResult(filesDir: File): String? = readOrNull(File(dir(filesDir), "result.json"))

    private fun readOrNull(file: File): String? =
        if (file.isFile) runCatching { file.readText(Charsets.UTF_8) }.getOrNull() else null
}
