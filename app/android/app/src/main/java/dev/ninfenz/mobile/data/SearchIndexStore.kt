package dev.ninfenz.mobile.data

import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper

/** SQLite FTS5 搜索索引；FTS5 不可用时自动回退普通表 LIKE。 */
class SearchIndexStore(
    context: Context,
    dbName: String = "search-index.db"
) {
    private val helper = object : SQLiteOpenHelper(context, dbName, null, 1) {
        override fun onCreate(db: SQLiteDatabase) {
            db.execSQL("CREATE TABLE hits_flat (kind TEXT,title TEXT,detail TEXT,pack_id TEXT,pack_version TEXT,project_id TEXT,body TEXT)")
            ftsAvailable = runCatching {
                db.execSQL("CREATE VIRTUAL TABLE hits_fts USING fts5(kind,title,detail,pack_id,pack_version,project_id,body)")
            }.isSuccess
        }

        override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
            db.execSQL("DROP TABLE IF EXISTS hits_fts")
            db.execSQL("DROP TABLE IF EXISTS hits_flat")
            onCreate(db)
        }
    }

    @Volatile
    private var ftsAvailable: Boolean = true

    fun rebuild(hits: List<SearchHit>) {
        val db = helper.writableDatabase
        db.beginTransaction()
        try {
            db.delete("hits_flat", null, null)
            runCatching { db.delete("hits_fts", null, null) }
            for (hit in hits) {
                val values = ContentValues().apply {
                    put("kind", hit.kind.name)
                    put("title", hit.title)
                    put("detail", hit.detail)
                    put("pack_id", hit.packId)
                    put("pack_version", hit.packVersion)
                    put("project_id", hit.projectId)
                    put("body", hit.body)
                }
                db.insert("hits_flat", null, values)
                if (ftsAvailable) runCatching { db.insert("hits_fts", null, values) }
            }
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    fun search(query: String, limit: Int = 200): List<SearchHit> {
        if (query.isBlank()) return emptyList()
        val db = helper.readableDatabase
        if (ftsAvailable) {
            val safe = query.replace("\"", "").trim()
            if (safe.isNotEmpty()) {
                runCatching {
                    db.rawQuery(
                        "SELECT kind,title,detail,pack_id,pack_version,project_id,body FROM hits_fts WHERE hits_fts MATCH ? LIMIT ?",
                        arrayOf(safe + "*", limit.toString())
                    ).use { readAll(it) }
                }.getOrNull()?.let { return it }
            }
        }
        val like = "%" + query.trim() + "%"
        return db.rawQuery(
            "SELECT kind,title,detail,pack_id,pack_version,project_id,body FROM hits_flat WHERE title LIKE ? OR detail LIKE ? OR body LIKE ? LIMIT ?",
            arrayOf(like, like, like, limit.toString())
        ).use { readAll(it) }
    }

    private fun readAll(cursor: Cursor): List<SearchHit> {
        val out = mutableListOf<SearchHit>()
        while (cursor.moveToNext()) {
            val kind = runCatching { SearchKind.valueOf(cursor.getString(0)) }.getOrDefault(SearchKind.PROJECT)
            out += SearchHit(
                kind = kind,
                title = cursor.getString(1).orEmpty(),
                detail = cursor.getString(2).orEmpty(),
                packId = cursor.getString(3),
                packVersion = cursor.getString(4),
                projectId = cursor.getString(5),
                body = cursor.getString(6).orEmpty()
            )
        }
        return out
    }

    fun close() = helper.close()
}
