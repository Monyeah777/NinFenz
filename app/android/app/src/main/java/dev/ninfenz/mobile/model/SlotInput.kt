package dev.ninfenz.mobile.model

/** 槽位输入的轻量类型约束；只做输入过滤，不替用户补事实。 */
object SlotInput {
    fun sanitize(kind: String?, text: String): String = when (kind) {
        "number", "int", "integer" -> text.filter { it.isDigit() }
        "decimal", "float" -> text.filter { it.isDigit() || it == '.' || it == '-' }
        else -> text
    }
}
