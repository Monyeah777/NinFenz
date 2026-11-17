package dev.ninfenz.mobile.data

import java.io.File
import java.io.FileOutputStream
import java.nio.channels.FileChannel
import java.nio.file.StandardOpenOption

/**
 * Pack 目录原子安装：先 fsync 完整 staging，再 rename 到目标；已有版本先转 .old 备份，
 * 失败时恢复旧版本。不静默 copy 覆盖，避免半安装目录。
 */
object PackInstaller {
    /**
     * 卸载已安装 Pack：先原子移到 library/packs-removed，再删注册记录；注册失败可回滚目录。
     * 调用方必须先确认没有项目引用该 Pack。
     */
    fun uninstall(packDir: File, filesDir: File) {
        val root = File(filesDir, "library/packs").canonicalFile
        val src = packDir.canonicalFile
        require(src.parentFile?.parentFile?.canonicalFile == root) { "Pack 不在安装目录：" + src }
        val id = src.parentFile?.name ?: throw IllegalArgumentException("缺少 Pack id")
        val version = src.name
        require(id.isNotBlank() && version.isNotBlank()) { "缺少 Pack id/version" }
        if (!src.isDirectory) return
        val removedRoot = File(filesDir, "library/packs-removed").apply { mkdirs() }
        val dest = File(removedRoot, id + "@" + version + "." + System.currentTimeMillis())
        java.nio.file.Files.move(
            src.toPath(),
            dest.toPath(),
            java.nio.file.StandardCopyOption.ATOMIC_MOVE
        )
        try {
            PackRegistry.remove(filesDir, id, version)
        } catch (t: Throwable) {
            runCatching {
                java.nio.file.Files.move(dest.toPath(), src.toPath(), java.nio.file.StandardCopyOption.ATOMIC_MOVE)
            }
            throw t
        }
        runCatching { dest.deleteRecursively() }
    }

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
            PackRegistry.record(target, source)
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
