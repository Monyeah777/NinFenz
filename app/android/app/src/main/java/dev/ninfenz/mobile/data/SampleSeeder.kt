package dev.ninfenz.mobile.data

import android.content.Context
import java.io.File
import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

sealed interface SeedResult {
    data class Installed(val id: String, val version: String, val files: Int) : SeedResult
    data class AlreadyPresent(val id: String, val version: String) : SeedResult
    data class Failed(val message: String, val fix: String) : SeedResult
}

/**
 * 首启种子：把 assets/sample-pack 复制到 app 私有库。
 * 幂等：目标已存在同 id/version 时直接返回 AlreadyPresent（不覆盖用户内容）。
 * v0.02 只做结构校验（manifest 可解析 + 文件齐全计数）；core pack-verify 在后续波次接入。
 */
class SampleSeeder(
    private val context: Context,
    private val filesDir: File,
    private val prefs: AppPrefs
) {
    suspend fun seed(): SeedResult = withContext(Dispatchers.IO) {
        try {
            val targetRoot = File(filesDir, "library/incoming")
            val stage = File(targetRoot, "sample-pack-stage")
            if (stage.exists()) stage.deleteRecursively()
            if (!stage.mkdirs()) throw IOException("无法创建临时目录")

            val count = copyAssetTree("sample-pack", stage)
            val manifest = File(stage, "nf-pack.json")
            if (!manifest.isFile) throw IOException("assets 缺少 nf-pack.json")

            val obj = Json.parseToJsonElement(manifest.readText(Charsets.UTF_8)).jsonObject
            val id = obj["id"]?.jsonPrimitive?.content ?: throw IOException("manifest 缺 id")
            val version = obj["version"]?.jsonPrimitive?.content ?: throw IOException("manifest 缺 version")
            val expected = obj["items"]?.jsonArray?.size ?: 0

            val target = File(File(File(filesDir, "library/packs"), id), version)
            if (File(target, "nf-pack.json").isFile) {
                stage.deleteRecursively()
                prefs.sampleSeeded = true
                return@withContext SeedResult.AlreadyPresent(id, version)
            }
            PackInstaller.install(stage, target)
            PackStore(filesDir).invalidate()
            prefs.sampleSeeded = true
            SeedResult.Installed(id, version, count.coerceAtLeast(expected))
        } catch (t: Throwable) {
            SeedResult.Failed(
                message = "示例 Pack 载入失败：" + (t.message ?: t.javaClass.simpleName),
                fix = "重试；若仍失败，检查 APK assets 是否完整（app/android/app/src/main/assets/sample-pack）"
            )
        }
    }

    private fun copyAssetTree(assetPath: String, dest: File): Int {
        val children = context.assets.list(assetPath)
        if (children == null || children.isEmpty()) {
            dest.parentFile?.mkdirs()
            context.assets.open(assetPath).use { input ->
                dest.outputStream().use { output -> input.copyTo(output) }
            }
            return 1
        }
        dest.mkdirs()
        var count = 0
        for (child in children) {
            count += copyAssetTree(assetPath + "/" + child, File(dest, child))
        }
        return count
    }
}
