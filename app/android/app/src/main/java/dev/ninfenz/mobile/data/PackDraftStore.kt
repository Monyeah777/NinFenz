package dev.ninfenz.mobile.data

import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** Pack Studio 草稿：复制已安装 Pack 到 files/pack-drafts，编辑/校验/打包，不碰已安装目录。 */
class PackDraftStore(private val filesDir: File) {
    data class Draft(val id: String, val version: String, val title: String, val dir: File)

    private fun root(): File = File(filesDir, "pack-drafts").apply { mkdirs() }

    fun list(): List<Draft> = root().listFiles()?.filter { it.isDirectory }?.mapNotNull { dir ->
        val manifest = File(dir, "nf-pack.json").takeIf { it.isFile } ?: return@mapNotNull null
        runCatching {
            val o = Json.parseToJsonElement(manifest.readText(Charsets.UTF_8)).jsonObject
            Draft(
                id = o["id"]?.jsonPrimitive?.content ?: dir.name.substringBefore('@'),
                version = o["version"]?.jsonPrimitive?.content ?: dir.name.substringAfter('@', "0.0.0"),
                title = o["title"]?.jsonPrimitive?.content ?: dir.name,
                dir = dir
            )
        }.getOrNull()
    }?.sortedBy { it.id } ?: emptyList()

    fun load(id: String): Draft? = list().firstOrNull { it.id == id }

    fun createFrom(pack: PackEntry, id: String, version: String, title: String): Draft {
        val target = File(root(), id + "@" + version)
        require(!target.exists()) { "草稿已存在：" + target.name }
        pack.dir.copyRecursively(target, overwrite = false)
        target.walkTopDown().filter { it.isFile && it.name.endsWith(".bak") }.forEach { it.delete() }
        val manifest = File(target, "nf-pack.json")
        val o = Json.parseToJsonElement(manifest.readText(Charsets.UTF_8)).jsonObject
        val next = buildJsonObject {
            o.forEach { (k, v) -> if (k !in setOf("id", "version", "title")) put(k, v) }
            put("id", id)
            put("version", version)
            put("title", title)
        }
        AtomicFiles.writeText(manifest, next.toString())
        return Draft(id, version, title, target)
    }

    fun updateMeta(draft: Draft, id: String, version: String, title: String) {
        val manifest = File(draft.dir, "nf-pack.json")
        val o = Json.parseToJsonElement(manifest.readText(Charsets.UTF_8)).jsonObject
        val next = buildJsonObject {
            o.forEach { (k, v) -> if (k !in setOf("id", "version", "title")) put(k, v) }
            put("id", id); put("version", version); put("title", title)
        }
        AtomicFiles.writeText(manifest, next.toString())
    }

    fun writeHashes(draft: Draft, items: JsonElement, hashes: JsonElement) {
        val manifest = File(draft.dir, "nf-pack.json")
        val o = Json.parseToJsonElement(manifest.readText(Charsets.UTF_8)).jsonObject
        val next = buildJsonObject {
            o.forEach { (k, v) -> if (k !in setOf("items", "hashes")) put(k, v) }
            put("items", items)
            put("hashes", hashes)
        }
        AtomicFiles.writeText(manifest, next.toString())
    }

    fun packageToZip(draft: Draft, outDir: File): File {
        outDir.mkdirs()
        val target = File(outDir, draft.id + "-" + draft.version + ".zip")
        ZipOutputStream(FileOutputStream(target)).use { zip ->
            draft.dir.walkTopDown().filter { it.isFile && it.name != ".draft.json" && it.name != ".golden.md" && !it.name.endsWith(".bak") }.sortedBy { it.path }.forEach { file ->
                val rel = file.relativeTo(draft.dir).invariantSeparatorsPath
                zip.putNextEntry(ZipEntry(rel))
                FileInputStream(file).use { it.copyTo(zip) }
                zip.closeEntry()
            }
        }
        return target
    }

    fun goldenFile(draft: Draft): File = File(draft.dir, ".golden.md")

    fun loadGolden(draft: Draft): String? = goldenFile(draft).takeIf { it.isFile }?.readText(Charsets.UTF_8)

    fun saveGolden(draft: Draft, markdown: String) {
        AtomicFiles.writeText(goldenFile(draft), markdown)
    }

    fun delete(draft: Draft) { draft.dir.deleteRecursively() }
}
