package dev.ninfenz.mobile.ui

/** 一次性把 Daily 粘贴内容交给导入页；进程死亡不恢复，避免旧预览。 */
object ImportSeed {
    @Volatile
    private var pending: String? = null

    fun put(text: String) {
        pending = text
    }

    fun consume(): String? {
        val value = pending
        pending = null
        return value?.takeIf { it.isNotBlank() }
    }
}
