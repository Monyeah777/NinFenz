package dev.ninfenz.mobile.data

import java.io.BufferedInputStream
import java.io.File
import java.io.FileInputStream
import java.util.zip.ZipInputStream

class PackZipException(message: String, val fix: String) : Exception(message)

/**
 * 新版 Pack zip 解包（应用内 pack-diff 的 new_root 来源）。
 * 安全：拒绝绝对路径/../、条目数/解压总量上限；只写 dest 内。
 */
object PackZipLoader {
    private const val MAX_ENTRIES = 5000
    private const val MAX_BYTES = 512L * 1024 * 1024

    fun extract(zipFile: File, destDir: File): File {
        if (!zipFile.isFile) throw PackZipException("zip 不存在", "重新选择文件")
        if (destDir.exists()) destDir.deleteRecursively()
        if (!destDir.mkdirs()) throw PackZipException("无法创建临时目录", "检查应用存储空间")

        val destCanonical = destDir.canonicalFile
        var entries = 0
        var total = 0L
        ZipInputStream(BufferedInputStream(FileInputStream(zipFile))).use { zis ->
            while (true) {
                val entry = zis.nextEntry ?: break
                entries += 1
                if (entries > MAX_ENTRIES) throw PackZipException("条目数超限", "Pack 条目上限 " + MAX_ENTRIES)
                val name = entry.name.replace('\\', '/')
                if (name.startsWith("/") || name.split('/').any { it == ".." }) {
                    throw PackZipException("zip 含越界路径：" + name, "拒绝不安全的 Pack zip")
                }
                val out = File(destDir, name)
                if (!out.canonicalFile.toPath().startsWith(destCanonical.toPath())) {
                    throw PackZipException("zip 路径越界：" + name, "拒绝不安全的 Pack zip")
                }
                if (entry.isDirectory) {
                    out.mkdirs()
                } else {
                    out.parentFile?.mkdirs()
                    out.outputStream().use { output -> zis.copyTo(output) }
                    total += out.length()
                    if (total > MAX_BYTES) throw PackZipException("解压总量超限", "Pack 解压总量上限 512 MiB")
                }
                zis.closeEntry()
            }
        }
        val root = findRoot(destDir)
        return root ?: throw PackZipException("zip 里找不到 nf-pack.json", "确认选择的是 Pack zip（根目录或单层目录含 nf-pack.json）")
    }

    private fun findRoot(destDir: File): File? {
        if (File(destDir, "nf-pack.json").isFile) return destDir
        val children = destDir.listFiles()?.filter { it.isDirectory } ?: emptyList()
        val withManifest = children.filter { File(it, "nf-pack.json").isFile }
        return if (withManifest.size == 1) withManifest.first() else null
    }
}
