package dev.ninfenz.mobile.data

import java.io.File
import java.io.FileOutputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption

/**
 * 原子写：同目录 temp → fsync → rename；替换前保留 .bak。
 * 目标：进程被杀后文件要么旧内容、要么新内容，不出现半截 JSON。
 */
object AtomicFiles {
    fun writeText(target: File, text: String) = writeBytes(target, text.toByteArray(Charsets.UTF_8))

    fun writeBytes(target: File, bytes: ByteArray) {
        val parent = target.parentFile ?: throw IllegalArgumentException("目标文件无父目录")
        parent.mkdirs()
        if (target.isFile) {
            val backup = File(parent, target.name + ".bak")
            FileOutputStream(backup).use { out ->
                out.write(target.readBytes())
                out.flush()
                out.fd.sync()
            }
        }
        val temp = File.createTempFile(target.name + ".", ".tmp", parent)
        try {
            FileOutputStream(temp).use { out ->
                out.write(bytes)
                out.flush()
                out.fd.sync()
            }
            try {
                Files.move(
                    temp.toPath(),
                    target.toPath(),
                    StandardCopyOption.ATOMIC_MOVE,
                    StandardCopyOption.REPLACE_EXISTING
                )
            } catch (t: Throwable) {
                if (!temp.renameTo(target)) throw t
            }
        } finally {
            if (temp.exists()) temp.delete()
        }
    }
}
