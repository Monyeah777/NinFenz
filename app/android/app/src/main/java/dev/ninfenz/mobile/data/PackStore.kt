package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

data class PackEntry(
    val id: String,
    val version: String,
    val title: String,
    val description: String,
    val itemCount: Int,
    val tree: String,
    val dir: File
)

data class PackSnapshot(val packs: List<PackEntry>, val errors: List<String>)

/** 已安装 Pack 扫描：library/packs/<id>/<version>/nf-pack.json（只读）。 */
class PackStore(private val filesDir: File) {

    fun packsRoot(): File = File(filesDir, "library/packs")

    fun scan(): PackSnapshot {
        val root = packsRoot()
        val entries = mutableListOf<PackEntry>()
        val errors = mutableListOf<String>()
        val versions = root.listFiles()?.filter { it.isDirectory } ?: emptyList()
        for (idDir in versions.sortedBy { it.name }) {
            val versionDirs = idDir.listFiles()?.filter { it.isDirectory } ?: emptyList()
            for (vDir in versionDirs.sortedBy { it.name }) {
                val manifest = File(vDir, "nf-pack.json")
                if (!manifest.isFile) continue
                try {
                    val obj = Json.parseToJsonElement(manifest.readText(Charsets.UTF_8)).jsonObject
                    val id = obj.text("id")
                    val version = obj.text("version")
                    val title = obj.text("title")
                    val description = obj.text("description")
                    val items = obj["items"]?.jsonArray?.size ?: 0
                    val tree = obj["hashes"]?.jsonObject?.get("tree")?.jsonPrimitive?.content ?: ""
                    entries.add(PackEntry(id, version, title, description, items, tree, vDir))
                } catch (t: Throwable) {
                    errors.add(vDir.name + "：" + (t.message ?: t.javaClass.simpleName))
                }
            }
        }
        return PackSnapshot(entries, errors)
    }

    private fun JsonObject.text(key: String): String =
        this[key]?.jsonPrimitive?.content ?: ""
}
