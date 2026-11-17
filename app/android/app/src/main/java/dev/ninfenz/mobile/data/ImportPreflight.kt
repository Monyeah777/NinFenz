package dev.ninfenz.mobile.data

import java.io.File
import java.util.zip.ZipFile

/** 导入 zip 预检：条目数、声明总量、单条压缩比；防压缩炸弹。 */
object ImportPreflight {
    const val MAX_ENTRIES = 1000
    const val MAX_TOTAL_BYTES = 256L * 1024 * 1024
    const val MAX_RATIO = 120L

    fun check(file: File) {
        try {
            ZipFile(file).use { zip ->
                val entries = zip.entries().toList()
                require(entries.size <= MAX_ENTRIES) { "zip 条目过多（${entries.size}）" }
                var total = 0L
                for (entry in entries) {
                    val size = entry.size
                    require(size >= 0) { "zip 条目大小未知：${entry.name}" }
                    total += size
                    require(total <= MAX_TOTAL_BYTES) { "zip 解压总量过大" }
                    if (entry.compressedSize > 0 && size > entry.compressedSize * MAX_RATIO) {
                        require(false) { "zip 压缩比过高：${entry.name}" }
                    }
                }
            }
        } catch (t: IllegalArgumentException) {
            throw t
        } catch (t: Throwable) {
            throw IllegalArgumentException("zip 预检失败：${t.message ?: t.javaClass.simpleName}")
        }
    }
}
