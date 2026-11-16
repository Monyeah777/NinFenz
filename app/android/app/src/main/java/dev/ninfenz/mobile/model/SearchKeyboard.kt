package dev.ninfenz.mobile.model

/** 搜索键盘导航的纯边界逻辑，避免空结果/越界。 */
object SearchKeyboard {
    fun move(current: Int, size: Int, delta: Int): Int {
        if (size <= 0) return 0
        return (current + delta).coerceIn(0, size - 1)
    }
}
