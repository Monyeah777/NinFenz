package dev.ninfenz.mobile.data

import java.io.BufferedInputStream
import java.io.File
import java.io.FileInputStream
import java.util.zip.ZipEntry
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
        preflight(zipFile)
        if (destDir.exists()) destDir.deleteRecursively()
        if (!destDir.mkdirs()) throw PackZipException("无法创建临时目录", "检查应用存储空间")

        val destCanonical = destDir.canonicalFile
        var entries = 0
        var total = 0L
        val seen = mutableSetOf<String>()
        ZipInputStream(BufferedInputStream(FileInputStream(zipFile))).use { zis ->
            while (true) {
                val entry = zis.nextEntry ?: break
                entries += 1
                if (entries > MAX_ENTRIES) throw PackZipException("条目数超限", "Pack 条目上限 " + MAX_ENTRIES)
                total += copyEntry(zis, entry, destDir, destCanonical, seen)
                if (total > MAX_BYTES) throw PackZipException("解压总量超限", "Pack 解压总量上限 512 MiB")
                zis.closeEntry()
            }
        }
        val root = findRoot(destDir)
        return root ?: throw PackZipException("zip 里找不到 nf-pack.json", "确认选择的是 Pack zip（根目录或单层目录含 nf-pack.json）")
    }

    private fun copyEntry(
        zis: ZipInputStream,
        entry: ZipEntry,
        destDir: File,
        destCanonical: File,
        seen: MutableSet<String>
    ): Long {
        val name = entry.name.replace('\\', '/')
        if (name.isBlank() || name.any { it.code < 0x20 }) {
            throw PackZipException("zip 含非法条目名", "拒绝不安全的 Pack zip")
        }
        if (!seen.add(name)) {
            throw PackZipException("zip 含重复条目：" + name, "拒绝不安全的 Pack zip")
        }
        if (name.startsWith("/") || name.split('/').any { it == ".." }) {
            throw PackZipException("zip 含越界路径：" + name, "拒绝不安全的 Pack zip")
        }
        if (name.split('/').any { isWindowsReserved(it) }) {
            throw PackZipException("zip 含 Windows 保留名：" + name, "拒绝不安全的 Pack zip")
        }
        val out = File(destDir, name)
        if (!out.canonicalFile.toPath().startsWith(destCanonical.toPath())) {
            throw PackZipException("zip 路径越界：" + name, "拒绝不安全的 Pack zip")
        }
        if (entry.isDirectory) {
            out.mkdirs()
            return 0L
        }
        out.parentFile?.mkdirs()
        out.outputStream().use { output -> zis.copyTo(output) }
        return out.length()
    }

    private fun isWindowsReserved(component: String): Boolean {
        val base = component.substringBefore('.').trim().uppercase()
        if (base in setOf("CON", "PRN", "AUX", "NUL")) return true
        if (base.length == 4 && (base.startsWith("COM") || base.startsWith("LPT")) && base[3] in '1'..'9') return true
        return component.endsWith(".") || component.endsWith(" ")
    }

    /** 解包前用 central directory 做压缩比/声明总量预检，防高压缩比炸弹。 */
    private fun preflight(zipFile: File) {
        if (containsUnsafeEntry(zipFile)) {
            throw PackZipException("zip 含特殊文件条目", "拒绝不安全的 Pack zip")
        }
        if (containsEncryptedEntry(zipFile)) {
            throw PackZipException("zip 含加密条目", "拒绝加密 Pack zip")
        }
        java.util.zip.ZipFile(zipFile).use { zf ->
            var declared = 0L
            var count = 0
            for (entry in zf.entries()) {
                count++
                if (count > MAX_ENTRIES) throw PackZipException("条目数超限", "Pack 条目上限 " + MAX_ENTRIES)
                if (entry.size > 0) declared += entry.size
                if (declared > MAX_BYTES) throw PackZipException("声明解压总量超限", "Pack 解压总量上限 512 MiB")
                if (entry.size > 0 && entry.compressedSize > 0) {
                    val ratio = entry.size.toDouble() / entry.compressedSize.toDouble()
                    if (ratio > 1000.0) {
                        throw PackZipException("压缩比异常：" + entry.name, "拒绝高压缩比 Pack zip")
                    }
                }
            }
        }
    }

    /** 读 central directory 的 external attributes，拒绝 symlink/fifo/device/socket；普通文件与目录放行。 */
    private fun containsUnsafeEntry(zipFile: File): Boolean {
        return try {
            java.io.RandomAccessFile(zipFile, "r").use { raf -> centralDirectoryUnsafe(raf) }
        } catch (t: Throwable) {
            false
        }
    }

    private fun centralDirectoryUnsafe(raf: java.io.RandomAccessFile): Boolean {
        val length = raf.length()
        if (length < 22) return false
        val tail = readTail(raf, length)
        val eocd = eocdOffset(tail)
        if (eocd < 0) return false
        val count = le16(tail, eocd + 10)
        val offset = le32(tail, eocd + 16)
        if (offset <= 0 || offset >= length) return false
        raf.seek(offset)
        repeat(count) {
            val header = ByteArray(46)
            raf.readFully(header)
            if (le32(header, 0) != 0x02014b50L) return false
            if (hasUnsafeExternalAttrs(header)) return true
            raf.seek(raf.filePointer + centralDirectorySkip(header))
        }
        return false
    }

    private fun readTail(raf: java.io.RandomAccessFile, length: Long): ByteArray {
        val tailLength = minOf(length, 65557L).toInt()
        val tail = ByteArray(tailLength)
        raf.seek(length - tailLength)
        raf.readFully(tail)
        return tail
    }

    private fun eocdOffset(tail: ByteArray): Int {
        for (i in tail.size - 22 downTo 0) {
            if (le32(tail, i) == 0x06054b50L) return i
        }
        return -1
    }

    private fun hasUnsafeExternalAttrs(header: ByteArray): Boolean {
        val madeBy = le16(header, 4)
        val os = (madeBy ushr 8) and 0xFF
        val external = le32(header, 38)
        val mode = ((external ushr 16) and 0xF000).toInt()
        return os == 3 && mode != 0 && mode != 0x8000 && mode != 0x4000
    }

    private fun centralDirectorySkip(header: ByteArray): Long =
        (le16(header, 28) + le16(header, 30) + le16(header, 32)).toLong()

    /** 读 central directory 的通用位标记，检测加密条目（不依赖解包异常）。 */
    private fun containsEncryptedEntry(zipFile: File): Boolean {
        return try {
            java.io.RandomAccessFile(zipFile, "r").use { raf ->
                val length = raf.length()
                if (length < 22) return false
                val tailLength = minOf(length, 65557L).toInt()
                val tail = ByteArray(tailLength)
                raf.seek(length - tailLength)
                raf.readFully(tail)
                var eocd = -1
                for (i in tail.size - 22 downTo 0) {
                    if (le32(tail, i) == 0x06054b50L) { eocd = i; break }
                }
                if (eocd < 0) return false
                val count = le16(tail, eocd + 10)
                val offset = le32(tail, eocd + 16)
                if (offset <= 0 || offset >= length) return false
                raf.seek(offset)
                repeat(count) {
                    val header = ByteArray(46)
                    raf.readFully(header)
                    if (le32(header, 0) != 0x02014b50L) return false
                    val flags = le16(header, 8)
                    if (flags and 1 != 0) return true
                    val skip = le16(header, 28) + le16(header, 30) + le16(header, 32)
                    raf.seek(raf.filePointer + skip)
                }
                false
            }
        } catch (t: Throwable) {
            false
        }
    }

    private fun le16(bytes: ByteArray, at: Int): Int =
        (bytes[at].toInt() and 0xFF) or ((bytes[at + 1].toInt() and 0xFF) shl 8)

    private fun le32(bytes: ByteArray, at: Int): Long =
        (le16(bytes, at).toLong()) or (le16(bytes, at + 2).toLong() shl 16)

    private fun findRoot(destDir: File): File? {
        if (File(destDir, "nf-pack.json").isFile) return destDir
        val children = destDir.listFiles()?.filter { it.isDirectory } ?: emptyList()
        val withManifest = children.filter { File(it, "nf-pack.json").isFile }
        return if (withManifest.size == 1) withManifest.first() else null
    }
}
