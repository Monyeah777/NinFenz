package dev.ninfenz.mobile.data

import java.io.File
import java.security.MessageDigest
import java.util.zip.ZipFile
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long

/** 备份检查/恢复：只允许 projects/ 与 drafts/ 下的普通文件，先校验再写入。 */
object BackupRestoreService {
    data class Entry(val path: String, val bytes: Long, val sha256: String)
    data class Inspect(val entries: List<Entry>, val ok: Boolean, val error: String? = null)
    data class Restored(val files: Int, val skipped: Int, val snapshot: File? = null)

    fun inspect(file: File): Inspect {
        if (!file.isFile) return Inspect(emptyList(), false, "备份文件不存在")
        return try {
            ZipFile(file).use { zip ->
                val manifestEntry = zip.getEntry("manifest.json") ?: return Inspect(emptyList(), false, "缺 manifest.json")
                val manifestBytes = zip.getInputStream(manifestEntry).use { it.readBytes() }
                val manifestText = TextEncoding.decode(manifestBytes)?.text ?: String(manifestBytes, Charsets.UTF_8)
                val root = Json.parseToJsonElement(manifestText).jsonObject
                if (root["schema"]?.jsonPrimitive?.content != "nf-backup/1") {
                    return Inspect(emptyList(), false, "不是 nf-backup/1")
                }
                val rawFiles = root["files"]?.jsonArray ?: return Inspect(emptyList(), false, "manifest 缺 files")
                val entries = rawFiles.map { el ->
                    val o = el as? JsonObject ?: return Inspect(emptyList(), false, "manifest 条目格式错误")
                    val path = o["path"]?.jsonPrimitive?.content
                        ?: return Inspect(emptyList(), false, "manifest 条目缺 path")
                    val bytes = o["bytes"]?.jsonPrimitive?.long
                        ?: return Inspect(emptyList(), false, "manifest 条目缺 bytes")
                    val sha = o["sha256"]?.jsonPrimitive?.content
                        ?: return Inspect(emptyList(), false, "manifest 条目缺 sha256")
                    if (bytes < 0 || sha.isBlank()) return Inspect(emptyList(), false, "manifest 条目字段非法")
                    Entry(path, bytes, sha)
                }
                if (entries.isEmpty()) return Inspect(emptyList(), true)
                if (entries.any { it.bytes > 256L * 1024 * 1024 }) {
                    return Inspect(entries, false, "备份单条声明过大")
                }
                val total = entries.sumOf { it.bytes }
                if (total > 512L * 1024 * 1024) return Inspect(entries, false, "备份声明总量超限")
                val listed = entries.map { it.path }.toSet()
                val actual = zip.entries().asSequence()
                    .filter { !it.isDirectory && it.name != "manifest.json" }
                    .map { it.name }
                    .toSet()
                if (actual != listed) return Inspect(entries, false, "manifest 与备份条目不一致")
                val seen = mutableSetOf<String>()
                var actualTotal = 0L
                for (e in entries) {
                    if (!safePath(e.path)) return Inspect(entries, false, "非法路径：" + e.path)
                    if (!seen.add(e.path)) return Inspect(entries, false, "重复条目：" + e.path)
                    val ze = zip.getEntry(e.path) ?: return Inspect(entries, false, "缺条目：" + e.path)
                    val data = zip.getInputStream(ze).use { it.readBytes() }
                    actualTotal += data.size
                    if (data.size > 256L * 1024 * 1024 || actualTotal > 512L * 1024 * 1024) {
                        return Inspect(entries, false, "备份实际内容超限：" + e.path)
                    }
                    if (e.bytes >= 0 && data.size.toLong() != e.bytes) {
                        return Inspect(entries, false, "bytes 不一致：" + e.path)
                    }
                    if (e.sha256.isNotBlank() && sha256(data) != e.sha256) {
                        return Inspect(entries, false, "sha256 不一致：" + e.path)
                    }
                }
                Inspect(entries, true)
            }
        } catch (t: Throwable) {
            Inspect(emptyList(), false, "备份解析失败：" + (t.message ?: t.javaClass.simpleName))
        }
    }

    fun restore(file: File, filesDir: File): Restored {
        val checked = inspect(file)
        require(checked.ok) { checked.error ?: "备份校验失败" }
        val snapshot = BackupService.create(filesDir).file
        pointerFile(filesDir).let { pointer ->
            pointer.parentFile?.mkdirs()
            AtomicFiles.writeText(pointer, snapshot.absolutePath)
        }
        var restored = 0
        ZipFile(file).use { zip ->
            for (e in checked.entries) {
                val target = File(filesDir, e.path)
                val canonical = target.canonicalFile
                val root = filesDir.canonicalFile
                require(canonical.path.startsWith(root.path + File.separator)) { "路径越界：" + e.path }
                val data = zip.getInputStream(zip.getEntry(e.path)).use { it.readBytes() }
                AtomicFiles.writeBytes(target, data)
                restored++
            }
        }
        return Restored(restored, 0, snapshot)
    }

    fun lastSnapshot(filesDir: File): File? {
        val pointer = pointerFile(filesDir)
        if (!pointer.isFile) return null
        return try {
            pointer.readText(Charsets.UTF_8).trim().takeIf { it.isNotBlank() }?.let { File(it).takeIf { f -> f.isFile } }
        } catch (t: Throwable) {
            null
        }
    }

    private fun pointerFile(filesDir: File): File =
        File(File(filesDir, "exports/backups").apply { mkdirs() }, "last-restore-snapshot.txt")

    private fun safePath(path: String): Boolean =
        (
            path.startsWith("projects/") || path.startsWith("projects-archive/") || path.startsWith("drafts/") ||
                path in BackupService.META_FILES
            ) &&
            !path.contains("..") && !path.startsWith("/") && !path.contains("\\")

    private fun sha256(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
}
