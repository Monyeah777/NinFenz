package dev.ninfenz.mobile.model

/** M6：把槽位约束与当前值合成一份可展示的视图；不修改输入。 */
object ConstraintLens {
    enum class Issue { REQUIRED, MIN, MAX, PREFIX, SUFFIX, PATTERN }

    data class SlotView(
        val id: String,
        val name: String,
        val kind: String,
        val required: Boolean,
        val value: String,
        val minChars: Int?,
        val maxChars: Int?,
        val startsWith: String?,
        val endsWith: String?,
        val pattern: String?,
        val issues: List<Issue>
    )

    fun view(slots: List<SpecSlot>, inputs: Map<String, String>): List<SlotView> = slots.map { slot ->
        val value = inputs[slot.id].orEmpty()
        val issues = buildList {
            if (slot.required && value.isBlank()) add(Issue.REQUIRED)
            if (value.isNotBlank()) {
                slot.minChars?.let { if (value.length < it) add(Issue.MIN) }
                slot.maxChars?.let { if (value.length > it) add(Issue.MAX) }
                slot.startsWith?.let { if (!value.startsWith(it)) add(Issue.PREFIX) }
                slot.endsWith?.let { if (!value.endsWith(it)) add(Issue.SUFFIX) }
                slot.pattern?.let { pattern ->
                    val matches = runCatching { Regex(pattern).matches(value) }.getOrDefault(false)
                    if (!matches) add(Issue.PATTERN)
                }
            }
        }
        SlotView(
            id = slot.id,
            name = slot.name,
            kind = slot.kind,
            required = slot.required,
            value = value,
            minChars = slot.minChars,
            maxChars = slot.maxChars,
            startsWith = slot.startsWith,
            endsWith = slot.endsWith,
            pattern = slot.pattern,
            issues = issues
        )
    }
}
