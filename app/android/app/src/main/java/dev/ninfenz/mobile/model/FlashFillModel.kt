package dev.ninfenz.mobile.model

/** M1 白名单变换：从一次 before→after 推断可批量应用的规则。 */
object FlashFillModel {
    data class Transform(val kind: String, val a: String = "", val b: String = "") {
        fun apply(text: String): String = when (kind) {
            "prefix" -> a + text
            "suffix" -> text + a
            "strip_prefix" -> if (text.startsWith(a)) text.removePrefix(a) else text
            "strip_suffix" -> if (a.isNotEmpty() && text.endsWith(a)) text.removeSuffix(a) else text
            "replace" -> if (a.isNotEmpty()) text.replace(a, b) else text
            "truncate" -> a.toIntOrNull()?.let { text.take(it) } ?: text
            else -> text
        }

        fun describe(): String = when (kind) {
            "prefix" -> "加前缀「" + a + "」"
            "suffix" -> "加后缀「" + a + "」"
            "strip_prefix" -> "去前缀「" + a + "」"
            "strip_suffix" -> "去后缀「" + a + "」"
            "replace" -> "把「" + a + "」替换为「" + b + "」"
            "truncate" -> "截断到 " + a + " 字"
            else -> kind
        }
    }

    private fun commonPrefix(values: List<String>): String {
        if (values.isEmpty()) return ""
        var out = values.first()
        for (value in values.drop(1)) {
            while (!value.startsWith(out)) out = out.dropLast(1)
        }
        return out
    }

    private fun commonSuffix(values: List<String>): String {
        if (values.isEmpty()) return ""
        var out = values.first()
        for (value in values.drop(1)) {
            while (!value.endsWith(out)) out = out.dropLast(1)
        }
        return out
    }

    fun infer(before: String, after: String): Transform? = infer(listOf(before to after))

    /** 多例推断：候选变换必须同时解释所有 before→after。 */
    fun infer(examples: List<Pair<String, String>>): Transform? {
        val changed = examples.filter { it.first != it.second }
        if (changed.isEmpty()) return null
        val first = changed.first()
        return candidates(first.first, first.second)
            .firstOrNull { transform -> changed.all { transform.apply(it.first) == it.second } }
    }

    private fun candidates(before: String, after: String): List<Transform> = buildList {
        if (after.startsWith(before) && after.length > before.length) {
            val s = after.removePrefix(before)
            if (s.isNotEmpty()) add(Transform("suffix", s))
        }
        if (after.endsWith(before) && after.length > before.length) {
            val p = after.removeSuffix(before)
            if (p.isNotEmpty()) add(Transform("prefix", p))
        }
        if (before.endsWith(after) && before.length > after.length) {
            val p = before.removeSuffix(after)
            if (p.isNotEmpty()) add(Transform("strip_prefix", p))
        }
        if (before.startsWith(after) && before.length > after.length) {
            val s = before.removePrefix(after)
            if (s.isNotEmpty()) add(Transform("strip_suffix", s))
        }
        if (before.startsWith(after) && after.isNotEmpty()) {
            add(Transform("truncate", after.length.toString()))
        }

        var n = 0
        while (n < minOf(before.length, after.length) && before[n] == after[n]) n++
        var m = 0
        while (m < minOf(before.length, after.length) - n && before[before.length - 1 - m] == after[after.length - 1 - m]) m++
        val old = if (m > 0) before.substring(n, before.length - m) else before.substring(n)
        val new = if (m > 0) after.substring(n, after.length - m) else after.substring(n)
        if (old.length >= 2 && before.replace(old, new) == after) add(Transform("replace", old, new))
    }.distinct()
}
