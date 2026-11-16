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

    fun list(filesDir: File): List<File> {
        val dir = File(filesDir, "projects-archive")
        if (!dir.isDirectory) return emptyList()
        return dir.listFiles { f -> f.isFile && f.name.endsWith(".archived") }
            ?.sortedByDescending { it.lastModified() }
            ?: emptyList()
    }

    fun restore(archived: File, filesDir: File): File {
        require(archived.isFile) { "归档文件不存在" }
        val raw = archived.readText(Charsets.UTF_8)
        dev.ninfenz.mobile.model.ProjectModel.parse(raw)
        val original = archived.name.substringBefore(".nfproject.json") + ".nfproject.json"
        val projects = File(filesDir, "projects").apply { mkdirs() }
        var target = File(projects, original)
        var index = 2
        while (target.exists()) {
            target = File(projects, original.removeSuffix(".nfproject.json") + "-" + index + ".nfproject.json")
            index++
        }
        try {
            Files.move(archived.toPath(), target.toPath(), StandardCopyOption.ATOMIC_MOVE)
        } catch (t: Throwable) {
            target.writeBytes(archived.readBytes())
            if (!archived.delete()) throw IllegalStateException("归档恢复后删除失败：" + archived)
        }
        return target
    }

    private fun guardFailure(src: File, target: File) {
        if (src.exists()) {
            throw IllegalStateException("归档复制成功但原文件删除失败：" + src + " -> " + target)
        }
    }
}
