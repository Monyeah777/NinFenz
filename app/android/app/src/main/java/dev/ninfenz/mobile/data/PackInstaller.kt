package dev.ninfenz.mobile.data

import java.io.File
import java.io.FileOutputStream
import java.nio.channels.FileChannel
import java.nio.file.StandardOpenOption
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/**
 * Pack 目录原子安装：先 fsync 完整 staging，再 rename 到目标；已有版本先转 .old 备份，
 * 失败时恢复旧版本。不静默 copy 覆盖，避免半安装目录。
 */
object PackInstaller {
    fun install(stage: File, target: File, source: String = "install") {
        require(stage.isDirectory) { "staging 不是目录：$stage" }
        target.parentFile?.mkdirs()
        fsyncTree(stage)
        val backup = File(target.parentFile, target.name + ".old")
        if (backup.exists()) backup.deleteRecursively()
        if (target.exists() && !target.renameTo(backup)) {
            throw IllegalStateException("无法备份旧版本：" + target)
        }
        try {
            if (!stage.renameTo(target)) throw IllegalStateException("无法原子安装到：" + target)
            runCatching {
                AtomicFiles.writeText(
                    File(target, ".nf-install.json"),
                    buildJsonObject {
                        put("schema", "nf-install/1")
                        put("installed_at", System.currentTimeMillis())
                        put("source", source)
                    }.toString()
                )
            }
            fsyncDir(target.parentFile)
            backup.deleteRecursively()
        } catch (t: Throwable) {
            if (!target.exists() && backup.exists()) backup.renameTo(target)
            throw t
        }
    }

    private fun fsyncTree(dir: File) {
        dir.listFiles()?.forEach { f ->
            if (f.isDirectory) fsyncTree(f) else FileOutputStream(f, true).use { it.fd.sync() }
        }
        fsyncDir(dir)
    }

    private fun fsyncDir(dir: File?) {
        if (dir == null) return
        try {
            FileChannel.open(dir.toPath(), StandardOpenOption.READ).use { it.force(true) }
        } catch (t: Throwable) {
            // 目录 fsync 在个别文件系统不可用；文件本身已 fsync，保留最优努力。
        }
    }
}
