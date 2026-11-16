package dev.ninfenz.mobile.data

import java.io.File
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** 本地备份：projects/ + drafts/ + 内置 manifest；不备份 cache/exports 产物。 */
object BackupService {
    data class Created(val file: File, val entries: Int, val bytes: Long)

    fun create(filesDir: File, stamp: Long = System.currentTimeMillis()): Created {
        val root = File(filesDir, "exports/backups").apply { mkdirs() }
        val target = File(root, "nf-backup-" + stamp + ".zip")
        val sources = mutableListOf<Pair<String, File>>()
        listOf("projects", "drafts").forEach { name ->
            val dir = File(filesDir, name)
            if (dir.isDirectory) {
                dir.walkTopDown().filter { it.isFile }.sortedBy { it.path }.forEach { f ->
                    sources.add(name + "/" + f.relativeTo(dir).path.replace('\\', '/') to f)
                }
            }
        }
        val manifest = buildJsonObject {
            put("schema", "nf-backup/1")
            put("generated_at", stamp)
            put("files", buildJsonArray {
                sources.forEach { (path, file) ->
                    add(buildJsonObject {
                        put("path", path)
                        put("bytes", file.length())
                        put("sha256", sha256(file))
                    })
                }
            })
        }
        ZipOutputStream(target.outputStream()).use { out ->
            out.putNextEntry(ZipEntry("manifest.json").apply { time = 0L })
            out.write(manifest.toString().toByteArray(Charsets.UTF_8))
            out.closeEntry()
            sources.forEach { (path, file) ->
                out.putNextEntry(ZipEntry(path).apply { time = 0L })
                file.inputStream().use { it.copyTo(out) }
                out.closeEntry()
            }
        }
        return Created(target, sources.size, target.length())
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(8192)
            while (true) {
                val n = input.read(buffer)
                if (n < 0) break
                digest.update(buffer, 0, n)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}
