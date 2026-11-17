package dev.ninfenz.mobile.data

import android.content.Context
import android.net.Uri
import android.provider.DocumentsContract
import android.provider.OpenableColumns
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

/** SAF URI → 文本 / 缓存文件 / 目录树副本（只写 app 私有目录）。 */
object FileAccess {

    const val MAX_IMPORT_BYTES = 64L * 1024 * 1024
    const val MAX_TREE_FILE_BYTES = 128L * 1024 * 1024
    const val MAX_TREE_BYTES = 512L * 1024 * 1024

    data class FileMeta(val name: String, val size: Long, val mime: String?)

    suspend fun readText(context: Context, uri: Uri): String = withContext(Dispatchers.IO) {
        context.contentResolver.openInputStream(uri)?.use { input ->
            String(readLimited(input, MAX_IMPORT_BYTES), Charsets.UTF_8)
        } ?: throw IllegalStateException("无法打开 URI：" + uri)
    }

    fun readLimited(input: java.io.InputStream, maxBytes: Long): ByteArray {
        val out = java.io.ByteArrayOutputStream()
        val buffer = ByteArray(8192)
        var total = 0L
        while (true) {
            val n = input.read(buffer)
            if (n < 0) break
            total += n
            if (total > maxBytes) {
                throw IllegalStateException("文件超过 " + (maxBytes / (1024 * 1024)) + " MiB 导入上限")
            }
            out.write(buffer, 0, n)
        }
        return out.toByteArray()
    }

    suspend fun meta(context: Context, uri: Uri): FileMeta = withContext(Dispatchers.IO) {
        var name = uri.lastPathSegment ?: "input"
        var size = -1L
        try {
            context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use { cursor ->
                if (cursor.moveToFirst()) {
                    val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    if (nameIndex >= 0 && !cursor.isNull(nameIndex)) name = cursor.getString(nameIndex)
                    val sizeIndex = cursor.getColumnIndex(OpenableColumns.SIZE)
                    if (sizeIndex >= 0 && !cursor.isNull(sizeIndex)) size = cursor.getLong(sizeIndex)
                }
            }
        } catch (t: Throwable) {
            // 元数据可用性不影响导入；名称回退到 lastPathSegment
        }
        FileMeta(name, size, context.contentResolver.getType(uri))
    }

    suspend fun copyToCache(context: Context, uri: Uri, name: String): File = withContext(Dispatchers.IO) {
        val dir = File(context.cacheDir, "imports").apply { mkdirs() }
        val safe = name.replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "input" }
        val target = File(dir, System.nanoTime().toString() + "-" + safe)
        context.contentResolver.openInputStream(uri)?.use { input ->
            target.outputStream().use { output ->
                val buffer = ByteArray(8192)
                var total = 0L
                while (true) {
                    val n = input.read(buffer)
                    if (n < 0) break
                    total += n
                    if (total > MAX_IMPORT_BYTES) {
                        output.close()
                        target.delete()
                        throw IllegalStateException("文件超过 64 MiB 导入上限，已拒绝复制")
                    }
                    output.write(buffer, 0, n)
                }
            }
        } ?: throw IllegalStateException("无法读取 URI：" + uri)
        target
    }

    /** 目录树复制（ACTION_OPEN_DOCUMENT_TREE → app 私有目录）；返回复制文件数。 */
    suspend fun copyTree(context: Context, treeUri: Uri, dest: File): Int = withContext(Dispatchers.IO) {
        dest.mkdirs()
        val rootDoc = DocumentsContract.buildDocumentUriUsingTree(
            treeUri,
            DocumentsContract.getTreeDocumentId(treeUri)
        )
        val budget = longArrayOf(MAX_TREE_BYTES)
        copyDocument(context, rootDoc, dest, 0, budget)
    }

    private fun copyDocument(context: Context, docUri: Uri, destDir: File, depth: Int, budget: LongArray): Int {
        if (depth > 32) throw IllegalStateException("目录层级过深（>32）")
        destDir.mkdirs()
        val childrenUri = DocumentsContract.buildChildDocumentsUriUsingTree(
            docUri,
            DocumentsContract.getDocumentId(docUri)
        )
        val projection = arrayOf(
            DocumentsContract.Document.COLUMN_DOCUMENT_ID,
            DocumentsContract.Document.COLUMN_DISPLAY_NAME,
            DocumentsContract.Document.COLUMN_MIME_TYPE
        )
        var copied = 0
        val cursor = context.contentResolver.query(childrenUri, projection, null, null, null)
            ?: throw IllegalStateException("无法枚举目录：" + docUri)
        cursor.use { c ->
            while (c.moveToNext()) {
                val docId = c.getString(0)
                val name = c.getString(1) ?: continue
                val mime = c.getString(2)
                val safe = name.replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "item" }
                val childUri = DocumentsContract.buildDocumentUriUsingTree(docUri, docId)
                if (mime == DocumentsContract.Document.MIME_TYPE_DIR) {
                    copied += copyDocument(context, childUri, File(destDir, safe), depth + 1, budget)
                } else {
                    val target = File(destDir, safe)
                    try {
                        context.contentResolver.openInputStream(childUri)?.use { input ->
                            target.outputStream().use { output ->
                                copyLimited(input, output, MAX_TREE_FILE_BYTES, budget)
                            }
                        }
                    } catch (t: Throwable) {
                        target.delete()
                        throw t
                    }
                    copied++
                }
            }
        }
        return copied
    }

    fun copyLimited(
        input: java.io.InputStream,
        output: java.io.OutputStream,
        maxBytes: Long,
        budget: LongArray = longArrayOf(Long.MAX_VALUE)
    ) {
        val buffer = ByteArray(8192)
        var total = 0L
        while (true) {
            val n = input.read(buffer)
            if (n < 0) break
            total += n
            if (total > maxBytes) throw IllegalStateException("单个文件超过目录导入上限")
            budget[0] -= n
            if (budget[0] < 0) throw IllegalStateException("目录导入总量超过上限")
            output.write(buffer, 0, n)
        }
    }

    fun listFiles(dir: File): List<File> =
        dir.listFiles { f -> f.isFile }?.sortedBy { it.name } ?: emptyList()
}
