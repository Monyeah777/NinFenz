package dev.ninfenz.mobile.data

import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** 完整项目分享包：项目 JSON + projects/<id>/ 数据目录。 */
object ProjectPackage {
    fun create(projectFile: File, projectDir: File, outDir: File): File {
        require(projectFile.isFile) { "项目文件不存在" }
        outDir.mkdirs()
        val target = File(outDir, "nf-project-" + projectFile.name.removeSuffix(".nfproject.json") + ".zip")
        ZipOutputStream(target.outputStream()).use { out ->
            put(out, projectFile.name, projectFile.readBytes())
            if (projectDir.isDirectory) {
                projectDir.walkTopDown().filter { it.isFile }.sortedBy { it.path }.forEach { file ->
                    val name = "data/" + file.relativeTo(projectDir).path.replace('\\', '/')
                    put(out, name, file.readBytes())
                }
            }
        }
        return target
    }

    private fun put(out: ZipOutputStream, name: String, bytes: ByteArray) {
        out.putNextEntry(ZipEntry(name).apply { time = 0L })
        out.write(bytes)
        out.closeEntry()
    }
}
