package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.ImportModel
import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject

/** 已保存的导入草稿列表；排除映射 sidecar、最近预览与导入历史。 */
object DraftLibrary {
    private val SPECIAL = setOf("import-last.json", "import-history.json")

    fun list(filesDir: File): List<File> {
        val dir = File(filesDir, "drafts")
        if (!dir.isDirectory) return emptyList()
        return dir.listFiles { f ->
            f.isFile && f.name.endsWith(".json") &&
                !f.name.endsWith(".mapping.json") &&
                f.name !in SPECIAL
        }?.sortedByDescending { it.lastModified() } ?: emptyList()
    }

    fun findByDigest(filesDir: File, digest: String): File? {
        if (digest.isBlank()) return null
        return list(filesDir).firstOrNull { file ->
            val raw = read(file) ?: return@firstOrNull false
            try {
                val doc = ImportModel.parse(Json.parseToJsonElement(raw).jsonObject)
                (doc.source.sha256 ?: doc.textDigest) == digest
            } catch (t: Throwable) {
                false
            }
        }
    }

    fun read(file: File): String? = try {
        if (file.isFile) file.readText(Charsets.UTF_8).takeIf { it.isNotBlank() } else null
    } catch (t: Throwable) {
        null
    }

    fun delete(file: File): Boolean {
        val mapping = File(file.parentFile, file.name.removeSuffix(".json") + ".mapping.json")
        mapping.delete()
        return file.delete()
    }

    fun rename(file: File, newBase: String): File {
        val safe = newBase.trim().replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "draft" }
        val target = File(file.parentFile, safe + ".json")
        require(target != file) { "文件名未变化" }
        require(!target.exists()) { "同名草稿已存在" }
        require(file.renameTo(target)) { "重命名失败" }
        val oldMapping = File(file.parentFile, file.name.removeSuffix(".json") + ".mapping.json")
        if (oldMapping.isFile) oldMapping.renameTo(File(file.parentFile, safe + ".mapping.json"))
        return target
    }
}
