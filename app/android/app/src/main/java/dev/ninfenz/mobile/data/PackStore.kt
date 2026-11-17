package dev.ninfenz.mobile.data

import android.content.ContentValues
import android.database.sqlite.SQLiteDatabase
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

/** Pack 安装注册表：SQLite 为主（library/pack-registry.db），JSON 镜像兼容旧环境；均独立于 Pack 目录。 */
data class PackRegistryEntry(val installedAt: Long, val source: String)

object PackRegistry {
    private fun file(filesDir: File): File = File(filesDir, "library/pack-registry.json")

    fun load(filesDir: File): Map<String, PackRegistryEntry> {
        sqliteLoad(filesDir)?.takeIf { it.isNotEmpty() }?.let { return it }
        return jsonLoad(filesDir)
    }

    private fun jsonLoad(filesDir: File): Map<String, PackRegistryEntry> {
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

    /** 旧 JSON 注册表迁移到 SQLite；由 PackStore.scan 在首次扫描时调用。 */
    fun ensureMigrated(filesDir: File) {
        val f = dbFile(filesDir)
        if (f.isFile) return
        try {
            f.parentFile?.mkdirs()
            val db = SQLiteDatabase.openOrCreateDatabase(f, null)
            db.use { database ->
                database.beginTransaction()
                try {
                    database.execSQL(CREATE_TABLE_SQL)
                    var count = 0L
                    database.rawQuery("SELECT COUNT(*) FROM pack_registry", null).use { c ->
                        if (c.moveToFirst()) count = c.getLong(0)
                    }
                    if (count == 0L) {
                        jsonLoad(filesDir).forEach { (key, entry) ->
                            val at = key.lastIndexOf('@')
                            if (at > 0) {
                                val values = ContentValues().apply {
                                    put("id", key.substring(0, at))
                                    put("version", key.substring(at + 1))
                                    put("installed_at", entry.installedAt)
                                    put("source", entry.source)
                                }
                                database.insertWithOnConflict("pack_registry", null, values, SQLiteDatabase.CONFLICT_REPLACE)
                            }
                        }
                    }
                    database.setTransactionSuccessful()
                } finally {
                    database.endTransaction()
                }
            }
        } catch (t: Throwable) {
            // 迁移失败保留 JSON 回退，不阻断扫描
        }
    }

    const val CREATE_TABLE_SQL = "CREATE TABLE IF NOT EXISTS pack_registry (" +
        "id TEXT NOT NULL, version TEXT NOT NULL, installed_at INTEGER NOT NULL, source TEXT NOT NULL, " +
        "PRIMARY KEY(id, version))"

    fun record(target: File, source: String) {
        val filesDir = target.parentFile?.parentFile?.parentFile?.parentFile ?: return
        val id = target.parentFile?.name ?: return
        val version = target.name
        sqliteRecord(filesDir, id, version, source)
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

    private fun dbFile(filesDir: File): File = File(filesDir, "library/pack-registry.db")

    private fun sqliteLoad(filesDir: File): Map<String, PackRegistryEntry>? {
        return try {
            val f = dbFile(filesDir)
            if (!f.isFile) return null
            val db = SQLiteDatabase.openDatabase(f.path, null, SQLiteDatabase.OPEN_READONLY)
            db.use {
                it.execSQL("PRAGMA busy_timeout=3000")
                val out = mutableMapOf<String, PackRegistryEntry>()
                it.rawQuery("SELECT id, version, installed_at, source FROM pack_registry", null).use { c ->
                    while (c.moveToNext()) {
                        out[c.getString(0) + "@" + c.getString(1)] = PackRegistryEntry(c.getLong(2), c.getString(3))
                    }
                }
                out
            }
        } catch (t: Throwable) {
            null
        }
    }

    private fun sqliteRecord(filesDir: File, id: String, version: String, source: String): Boolean {
        return try {
            val f = dbFile(filesDir)
            f.parentFile?.mkdirs()
            val db = SQLiteDatabase.openOrCreateDatabase(f, null)
            db.use { database ->
                database.execSQL("PRAGMA journal_mode=WAL")
                database.execSQL("PRAGMA busy_timeout=3000")
                database.beginTransaction()
                try {
                            database.execSQL(CREATE_TABLE_SQL)
                    fun put(id: String, version: String, at: Long, source: String) {
                        val values = ContentValues().apply {
                            put("id", id)
                            put("version", version)
                            put("installed_at", at)
                            put("source", source)
                        }
                        database.insertWithOnConflict("pack_registry", null, values, SQLiteDatabase.CONFLICT_REPLACE)
                    }
                    var count = 0L
                    database.rawQuery("SELECT COUNT(*) FROM pack_registry", null).use { c ->
                        if (c.moveToFirst()) count = c.getLong(0)
                    }
                    if (count == 0L) {
                        // 首次建库：把旧 JSON 注册表迁入 SQLite，避免丢 installed_at/source。
                        jsonLoad(filesDir).forEach { (key, entry) ->
                            val at = key.lastIndexOf('@')
                            if (at > 0) put(key.substring(0, at), key.substring(at + 1), entry.installedAt, entry.source)
                        }
                    }
                    put(id, version, System.currentTimeMillis(), source)
                    database.setTransactionSuccessful()
                } finally {
                    database.endTransaction()
                }
            }
            true
        } catch (t: Throwable) {
            false
        }
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
        PackRegistry.ensureMigrated(filesDir)
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
