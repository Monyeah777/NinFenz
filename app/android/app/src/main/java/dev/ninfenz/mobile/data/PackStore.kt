package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

data class PackEntry(
    val id: String,
    val version: String,
    val title: String,
    val description: String,
    val itemCount: Int,
    val tree: String,
    val dir: File,
    val installedAt: Long = 0L
)

data class PackSnapshot(val packs: List<PackEntry>, val errors: List<String>)

/** Pack 安装注册表：library/pack-registry.json（独立于 Pack 目录，不参与 pack tree 摘要）。 */
data class PackRegistryEntry(val installedAt: Long, val source: String)

object PackRegistry {
    private fun file(filesDir: File): File = File(filesDir, "library/pack-registry.json")

    fun load(filesDir: File): Map<String, PackRegistryEntry> {
        val f = file(filesDir)
        if (!f.isFile) return emptyMap()
        return try {
            val o = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
            if (o.text("schema") != "nf-pack-registry/1") return emptyMap()
            o["packs"]?.jsonObject?.mapNotNull { (key, value) ->
                val item = value as? JsonObject ?: return@mapNotNull null
                val at = item["installed_at"]?.jsonPrimitive?.content?.toLongOrNull() ?: return@mapNotNull null
                key to PackRegistryEntry(at, item.text("source"))
            }?.toMap().orEmpty()
        } catch (t: Throwable) {
            emptyMap()
        }
    }

    fun record(target: File, source: String) {
        val filesDir = target.parentFile?.parentFile?.parentFile?.parentFile ?: return
        val id = target.parentFile?.name ?: return
        val version = target.name
        val next = load(filesDir).toMutableMap()
        next[id + "@" + version] = PackRegistryEntry(System.currentTimeMillis(), source)
        val obj = buildJsonObject {
            put("schema", "nf-pack-registry/1")
            put("packs", buildJsonObject {
                next.toSortedMap().forEach { (key, entry) ->
                    put(key, buildJsonObject {
                        put("installed_at", entry.installedAt)
                        put("source", entry.source)
                    })
                }
            })
        }
        runCatching { AtomicFiles.writeText(file(filesDir), obj.toString()) }
    }

    private fun JsonObject.text(key: String): String =
        this[key]?.jsonPrimitive?.content ?: ""
}



/** 已安装 Pack：library/packs/<id>/<version>/nf-pack.json；目录变更时重建索引缓存。 */
class PackStore(private val filesDir: File) {

    fun packsRoot(): File = File(filesDir, "library/packs")

    private fun indexFile(): File = File(filesDir, "library/pack-index.json")

    fun invalidate() {
        indexFile().delete()
    }

    fun scan(): PackSnapshot {
        val root = packsRoot()
        val fingerprint = if (!root.isDirectory) {
            0L
        } else {
            val children = root.listFiles()?.sortedBy { it.name }.orEmpty()
            var hash = children.size.toLong()
            children.forEach {
                hash = hash * 31 + it.name.hashCode()
                hash = hash * 31 + it.lastModified()
            }
            hash
        }
        loadIndex(fingerprint)?.let { return it }
        val snapshot = scanDirs(root)
        saveIndex(fingerprint, snapshot)
        return snapshot
    }

    private fun scanDirs(root: File): PackSnapshot {
        val entries = mutableListOf<PackEntry>()
        val errors = mutableListOf<String>()
        val registry = PackRegistry.load(filesDir)
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
                    val installedAt = registry[id + "@" + version]?.installedAt ?: vDir.lastModified()
                    entries.add(PackEntry(id, version, title, description, items, tree, vDir, installedAt))
                } catch (t: Throwable) {
                    errors.add(vDir.name + "：" + (t.message ?: t.javaClass.simpleName))
                }
            }
        }
        return PackSnapshot(entries, errors)
    }

    private fun loadIndex(fingerprint: Long): PackSnapshot? {
        val f = indexFile()
        if (!f.isFile) return null
        return try {
            val o = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
            if (o.text("schema") != "nf-pack-index/1") return null
            if ((o["root_mtime"]?.jsonPrimitive?.content?.toLongOrNull() ?: -1L) != fingerprint) return null
            val packs = o["packs"]?.jsonArray?.mapNotNull { el ->
                val p = el as? JsonObject ?: return@mapNotNull null
                val rel = p.text("rel")
                val dir = File(packsRoot(), rel)
                if (!File(dir, "nf-pack.json").isFile) return@mapNotNull null
                PackEntry(
                    id = p.text("id"),
                    version = p.text("version"),
                    title = p.text("title"),
                    description = p.text("description"),
                    itemCount = p["items"]?.jsonPrimitive?.int ?: 0,
                    tree = p.text("tree"),
                    dir = dir,
                    installedAt = p["installed_at"]?.jsonPrimitive?.content?.toLongOrNull() ?: dir.lastModified()
                )
            } ?: return null
            val errors = o["errors"]?.jsonArray?.mapNotNull { it.jsonPrimitive.content } ?: emptyList()
            PackSnapshot(packs, errors)
        } catch (t: Throwable) {
            null
        }
    }

    private fun saveIndex(fingerprint: Long, snapshot: PackSnapshot) {
        val root = packsRoot()
        val obj = buildJsonObject {
            put("schema", "nf-pack-index/1")
            put("root_mtime", fingerprint)
            put("packs", buildJsonArray {
                snapshot.packs.forEach { p ->
                    add(buildJsonObject {
                        put("id", p.id)
                        put("version", p.version)
                        put("title", p.title)
                        put("description", p.description)
                        put("items", p.itemCount)
                        put("tree", p.tree)
                        put("rel", p.dir.relativeTo(root).path.replace('\\', '/'))
                        put("installed_at", if (p.installedAt > 0) p.installedAt else p.dir.lastModified())
                    })
                }
            })
            put("errors", buildJsonArray { snapshot.errors.forEach { add(kotlinx.serialization.json.JsonPrimitive(it)) } })
        }
        AtomicFiles.writeText(indexFile(), obj.toString())
    }

    private fun JsonObject.text(key: String): String =
        this[key]?.jsonPrimitive?.content ?: ""
}
