package dev.ninfenz.mobile.data

import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray

/** 多项目交付包：外层 manifest + 每个完整项目包；只打包，不改项目内容。 */
object ProjectBundleExporter {
    data class Created(val file: File, val count: Int)

    fun create(filesDir: File, outDir: File): Created {
        val projectsDir = File(filesDir, "projects")
        val projectFiles = projectsDir.listFiles { f -> f.isFile && f.name.endsWith(".nfproject.json") }
            ?.sortedBy { it.name }
            .orEmpty()
        require(projectFiles.isNotEmpty()) { "没有可导出的项目" }
        outDir.mkdirs()
        val staging = File(outDir, "bundle-" + System.nanoTime()).apply { mkdirs() }
        try {
            val packages = projectFiles.map { projectFile ->
                val id = projectFile.name.removeSuffix(".nfproject.json")
                val zip = ProjectPackage.create(projectFile, File(projectsDir, id), staging)
                id to zip
            }
            val manifest = buildJsonObject {
                put("schema", "nf-bundle/1")
                putJsonArray("projects") {
                    packages.forEach { (id, zip) ->
                        add(buildJsonObject {
                            put("id", id)
                            put("package", "projects/" + zip.name)
                            put("bytes", zip.length())
                            put("sha256", ProjectPackage.sha256(zip.readBytes()))
                        })
                    }
                }
            }
            val target = File(outDir, "nf-bundle-" + System.nanoTime() + ".zip")
            ZipOutputStream(target.outputStream()).use { out ->
                out.putNextEntry(ZipEntry("nf-bundle.json").apply { time = 0L })
                out.write(manifest.toString().toByteArray(Charsets.UTF_8))
                out.closeEntry()
                packages.forEach { (_, zip) ->
                    out.putNextEntry(ZipEntry("projects/" + zip.name).apply { time = 0L })
                    zip.inputStream().use { it.copyTo(out) }
                    out.closeEntry()
                }
            }
            return Created(target, packages.size)
        } finally {
            staging.deleteRecursively()
        }
    }
}
