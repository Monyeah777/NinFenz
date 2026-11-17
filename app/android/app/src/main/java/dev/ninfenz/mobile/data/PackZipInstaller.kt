package dev.ninfenz.mobile.data

import java.io.File
import dev.ninfenz.mobile.core.J

data class PackInstallResult(
    val ok: Boolean,
    val id: String = "",
    val version: String = "",
    val message: String = ""
)

/** 从 Pack zip 安装新 Pack：安全解包 → 读 nf-pack.json → 原子安装 + 注册。 */
object PackZipInstaller {
    fun install(zip: File, filesDir: File): PackInstallResult {
        val staging = File(File(filesDir, "library/incoming"), "zip-" + System.currentTimeMillis())
        var root: File? = null
        try {
            root = PackZipLoader.extract(zip, staging)
            val manifest = File(root, "nf-pack.json")
            if (!manifest.isFile) return PackInstallResult(false, message = "zip 里找不到 nf-pack.json")
            val obj = J.parseObject(manifest.readText(Charsets.UTF_8), "nf-pack/1")
            val id = J.optString(obj, "id")?.trim().orEmpty()
            val version = J.optString(obj, "version")?.trim().orEmpty()
            if (id.isBlank() || version.isBlank()) {
                return PackInstallResult(false, message = "nf-pack.json 缺 id/version")
            }
            val target = File(File(File(filesDir, "library/packs"), id), version)
            if (target.exists()) {
                return PackInstallResult(false, id, version, "同 id+version 已存在，未覆盖")
            }
            target.parentFile?.mkdirs()
            PackInstaller.install(root, target, "zip")
            return PackInstallResult(true, id, version)
        } catch (t: Throwable) {
            return PackInstallResult(false, message = t.message ?: t.javaClass.simpleName)
        } finally {
            root = null
            staging.deleteRecursively()
        }
    }
}
