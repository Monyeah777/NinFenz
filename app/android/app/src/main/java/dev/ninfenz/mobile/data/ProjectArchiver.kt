package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import java.nio.file.StandardCopyOption

/** 项目归档：移出 projects/，保存到 projects-archive/，不删除内容。 */
object ProjectArchiver {
    fun archive(projectFile: File, filesDir: File, stamp: Long = System.currentTimeMillis()): File {
        require(projectFile.isFile) { "项目文件不存在" }
        val root = File(filesDir, "projects").canonicalFile
        val src = projectFile.canonicalFile
        require(src.path.startsWith(root.path + File.separator)) { "不在 projects 目录：" + src }
        val archive = File(filesDir, "projects-archive").apply { mkdirs() }
        var target = File(archive, projectFile.name + "." + stamp + ".archived")
        var index = 2
        while (target.exists()) {
            target = File(archive, projectFile.name + "." + stamp + "-" + index + ".archived")
            index++
        }
        try {
            Files.move(src.toPath(), target.toPath(), StandardCopyOption.ATOMIC_MOVE)
        } catch (t: Throwable) {
            target.writeBytes(src.readBytes())
            if (!src.delete()) guardFailure(src, target)
        }
        return target
    }

    private fun guardFailure(src: File, target: File) {
        if (src.exists()) {
            throw IllegalStateException("归档复制成功但原文件删除失败：" + src + " -> " + target)
        }
    }
}
