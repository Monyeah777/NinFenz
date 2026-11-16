package dev.ninfenz.mobile.data

import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** 最近一次未捕获异常：只保留本地栈，不联网；最多 64 KiB。 */
class CrashLogStore(private val filesDir: File) {
    private fun file(): File = File(File(filesDir, "crash").apply { mkdirs() }, "last-crash.txt")

    @Synchronized
    fun record(t: Throwable) {
        val text = buildString {
            append(SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(Date()))
            append("\n")
            append(t.javaClass.name).append(": ").append(t.message ?: "").append("\n")
            append(t.stackTraceToString())
        }
        val limited = if (text.length > 64 * 1024) text.take(64 * 1024) else text
        runCatching { AtomicFiles.writeText(file(), limited) }
    }

    fun read(): String? = try {
        val f = file()
        if (f.isFile) f.readText(Charsets.UTF_8).takeIf { it.isNotBlank() } else null
    } catch (t: Throwable) {
        null
    }

    fun clear() {
        runCatching { file().delete() }
    }
}
