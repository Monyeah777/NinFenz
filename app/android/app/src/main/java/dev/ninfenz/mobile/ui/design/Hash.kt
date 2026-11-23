package dev.ninfenz.mobile.ui.design

/** 哈希/ID 展示：4 字符分组，中间省略，单行不拆断。 */
fun shortHash(raw: String, group: Int = 4): String {
    val clean = raw.filter { it.isLetterOrDigit() }
    if (clean.length <= group * 3) return clean.chunked(group).joinToString(" ")
    val head = clean.take(group)
    val second = clean.substring(group, group * 2)
    val tail = clean.takeLast(group)
    return "$head $second … $tail"
}
