package dev.ninfenz.mobile.data

import java.io.File
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray

/** 完整项目分享包：manifest + 项目 JSON + data/。manifest 提供本地完整性校验。 */
object ProjectPackage {
    const val MANIFEST = "manifest.json"

    fun create(projectFile: File, projectDir: File, outDir: File): File {
        require(projectFile.isFile) { "项目文件不存在" }
        outDir.mkdirs()
        val projectBytes = projectFile.readBytes()
        val data = if (projectDir.isDirectory) {
            projectDir.walkTopDown()
                .filter { it.isFile && !it.name.endsWith(".bak") && !it.name.endsWith(".tmp") }
                .map { "data/" + it.relativeTo(projectDir).path.replace('\\', '/') to it.readBytes() }
                .sortedBy { it.first }
                .toList()
        } else {
            emptyList()
        }
        val manifest = buildJsonObject {
            put("schema", "nf-project-package/1")
            put("project", projectFile.name)
            put("project_sha256", sha256(projectBytes))
            putJsonArray("data") {
                data.forEach { (name, bytes) ->
                    add(buildJsonObject {
                        put("path", name)
                        put("size", bytes.size)
                        put("sha256", sha256(bytes))
                    })
                }
            }
        }
        val target = File(outDir, "nf-project-" + projectFile.name.removeSuffix(".nfproject.json") + "-" + System.nanoTime() + ".zip")
        ZipOutputStream(target.outputStream()).use { out ->
            put(out, MANIFEST, manifest.toString().toByteArray())
            put(out, projectFile.name, projectBytes)
            data.forEach { (name, bytes) -> put(out, name, bytes) }
        }
        return target
    }

    fun sha256(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(1024 * 1024)
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                digest.update(buffer, 0, read)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun put(out: ZipOutputStream, name: String, bytes: ByteArray) {
        out.putNextEntry(ZipEntry(name).apply { time = 0L })
        out.write(bytes)
        out.closeEntry()
    }
}
