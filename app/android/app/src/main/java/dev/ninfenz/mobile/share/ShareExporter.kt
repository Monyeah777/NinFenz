package dev.ninfenz.mobile.share

import android.content.ClipData
import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import java.io.File

/**
 * 分享只读 URI（CONTRACT §6）：写 cache/shared/，FileProvider 授权，临时缓存可清理。
 * 不写外部存储根；文件名做白名单清洗，防路径穿越。
 */
object ShareExporter {
    const val AUTHORITY = "dev.ninfenz.mobile.fileprovider"

    fun sharedDir(context: Context): File = File(context.cacheDir, "shared").apply { mkdirs() }

    fun writeSharedFile(context: Context, baseName: String, extension: String, content: String): File {
        val dir = sharedDir(context)
        val safe = baseName.replace(Regex("[^A-Za-z0-9._-]"), "_").trim('_').ifBlank { "export" }
        val file = File(dir, safe + "." + extension)
        file.writeText(content, Charsets.UTF_8)
        return file
    }

    /** 生成 ACTION_SEND Intent（text/markdown + 只读 URI）。 */
    fun shareFileIntent(context: Context, file: File, mime: String, subject: String): Intent {
        val uri = FileProvider.getUriForFile(context, AUTHORITY, file)
        val intent = Intent(Intent.ACTION_SEND)
        intent.type = mime
        intent.putExtra(Intent.EXTRA_STREAM, uri)
        intent.putExtra(Intent.EXTRA_SUBJECT, subject)
        intent.clipData = ClipData.newRawUri(subject, uri)
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        return intent
    }

    fun shareMarkdown(context: Context, title: String, markdown: String): Intent {
        val file = writeSharedFile(context, title, "md", markdown)
        return shareFileIntent(context, file, "text/markdown", title)
    }

    /** 从任意 Context（含本地化 wrapper）拉起系统分享面板；非 Activity 必须 NEW_TASK。 */
    fun launchChooser(context: Context, target: Intent, title: String) {
        val chooser = Intent.createChooser(target, title)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(chooser)
    }

    fun cleanup(context: Context) {
        val dir = File(context.cacheDir, "shared")
        if (dir.exists()) {
            val files = dir.listFiles()
            if (files != null) {
                for (f in files) f.delete()
            }
        }
    }
}
