package dev.ninfenz.mobile.data

/** Markdown 链接目标白名单：拒绝脚本/本地文件协议。 */
object SafeLink {
    fun allowedImage(target: String): Boolean = target.trim().startsWith("data:image/", ignoreCase = true) || allowed(target)

    fun allowed(target: String): Boolean {
        val t = target.trim()
        if (t.isBlank()) return false
        if (t.startsWith("#") || t.startsWith("/") || t.startsWith("./") || t.startsWith("../")) return true
        val scheme = t.substringBefore(':', "").lowercase()
        return scheme.isEmpty() || scheme == "http" || scheme == "https" || scheme == "mailto"
    }
}
