package dev.ninfenz.mobile.model

/** M2 的本地启发式：用槽位名/标题/正文的字符与词重叠给建议，不冒充语义模型。 */
object FormalizationSuggester {
    data class Suggestion(val slotId: String, val slotName: String, val score: Int, val reason: String)

    private fun normalize(value: String): String =
        value.lowercase().replace(Regex("[\\s\\p{Punct}，。！？、；：（）【】《》「」“”‘’]+"), "")

    private fun bigrams(value: String): Set<String> {
        val n = normalize(value)
        if (n.length < 2) return emptySet()
        return n.windowed(2).toSet()
    }

    private fun overlap(a: String, b: String): Int = bigrams(a).intersect(bigrams(b)).size

    fun suggest(
        text: String,
        heading: String?,
        slots: List<SpecSlot>,
        taken: Set<String> = emptySet()
    ): Suggestion? {
        val body = normalize(text)
        if (body.isBlank()) return null
        val headingNorm = normalize(heading.orEmpty())
        var best: Suggestion? = null
        for (slot in slots) {
            if (slot.id in taken) continue
            val current = suggestFor(slot, body, headingNorm) ?: continue
            if (best == null || current.score > best.score) best = current
        }
        return best
    }

    private fun suggestFor(slot: SpecSlot, body: String, headingNorm: String): Suggestion? {
        val name = normalize(slot.name)
        if (name.isBlank()) return null
        val reasons = mutableListOf<String>()
        var score = nameScore(name, body, reasons) + headingScore(headingNorm, name, reasons) +
            exampleScore(slot, body, reasons)
        if (slot.required) score += 1
        if (score < 3) return null
        return Suggestion(slot.id, slot.name, score, reasons.joinToString("；"))
    }

    private fun nameScore(name: String, body: String, reasons: MutableList<String>): Int {
        var score = 0
        if (name.length >= 2 && body.contains(name)) {
            score += 5
            reasons += "正文含槽位名"
        }
        val shared = overlap(body, name)
        if (shared > 0) {
            score += minOf(shared, 3) * 2
            reasons += "词重叠 " + shared
        }
        return score
    }

    private fun headingScore(headingNorm: String, name: String, reasons: MutableList<String>): Int {
        if (headingNorm.isBlank()) return 0
        if (!headingNorm.contains(name) && overlap(headingNorm, name) <= 0) return 0
        reasons += "标题相关"
        return 3
    }

    private fun exampleScore(slot: SpecSlot, body: String, reasons: MutableList<String>): Int {
        val exampleOverlap = slot.examples.maxOfOrNull { overlap(body, it) } ?: 0
        if (exampleOverlap <= 0) return 0
        reasons += "示例相关"
        return minOf(exampleOverlap, 2) * 2
    }
}
