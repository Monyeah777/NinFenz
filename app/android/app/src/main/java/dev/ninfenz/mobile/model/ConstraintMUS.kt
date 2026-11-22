package dev.ninfenz.mobile.model

/** M12：约束可满足性与最小不可满足子集（MUS）。只覆盖白名单约束。 */
object ConstraintMUS {
    enum class Kind { MIN_CHARS, MAX_CHARS, REQUIRED, FORBIDDEN_EMPTY, MUST_INCLUDE, MUST_AVOID }

    data class Rule(val id: String, val kind: Kind, val field: String = "", val value: String = "")

    private fun intValue(rule: Rule): Int? = rule.value.toIntOrNull()

    fun satisfiable(rules: List<Rule>): Boolean {
        rules.groupBy { it.field }.forEach { (_, group) ->
            val required = group.any { it.kind == Kind.REQUIRED }
            val forbidden = group.any { it.kind == Kind.FORBIDDEN_EMPTY }
            if (required && forbidden) return false
            val mins = group.filter { it.kind == Kind.MIN_CHARS }.mapNotNull(::intValue)
            val maxs = group.filter { it.kind == Kind.MAX_CHARS }.mapNotNull(::intValue)
            if (mins.isNotEmpty() && maxs.isNotEmpty() && mins.max() > maxs.min()) return false
            val includes = group.filter { it.kind == Kind.MUST_INCLUDE }.map { it.value }.toSet()
            val avoids = group.filter { it.kind == Kind.MUST_AVOID }.map { it.value }.toSet()
            if (includes.intersect(avoids).isNotEmpty()) return false
        }
        return true
    }

    fun minimalConflicts(rules: List<Rule>): List<List<Rule>> {
        if (satisfiable(rules)) return emptyList()
        val found = mutableListOf<List<Rule>>()
        for (size in 1..rules.size) {
            combinations(rules, size).forEach { subset ->
                if (satisfiable(subset)) return@forEach
                if (found.any { existing -> existing.toSet().all { it in subset } }) return@forEach
                val minimal = subset.all { drop -> satisfiable(subset.filter { it != drop }) }
                if (minimal) found += subset
            }
        }
        return found
    }

    private fun combinations(items: List<Rule>, size: Int): List<List<Rule>> {
        if (size == 0) return listOf(emptyList())
        if (size > items.size) return emptyList()
        val out = mutableListOf<List<Rule>>()
        fun walk(start: Int, current: MutableList<Rule>) {
            if (current.size == size) {
                out += current.toList()
                return
            }
            for (i in start until items.size) {
                current += items[i]
                walk(i + 1, current)
                current.removeAt(current.lastIndex)
            }
        }
        walk(0, mutableListOf())
        return out
    }
}
