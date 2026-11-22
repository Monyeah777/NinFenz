package dev.ninfenz.mobile.model

/** 把 SpecSlot 的长度/必填约束映射成 M12 规则，供交付台做本地自检。 */
object SpecConstraintAudit {
    fun rules(slots: List<SpecSlot>): List<ConstraintMUS.Rule> = slots.flatMap { slot ->
        buildList {
            if (slot.required) add(ConstraintMUS.Rule(slot.id + ".required", ConstraintMUS.Kind.REQUIRED, slot.id))
            slot.maxChars?.let { max ->
                add(ConstraintMUS.Rule(slot.id + ".max", ConstraintMUS.Kind.MAX_CHARS, slot.id, max.toString()))
                if (max == 0) add(ConstraintMUS.Rule(slot.id + ".empty", ConstraintMUS.Kind.FORBIDDEN_EMPTY, slot.id))
            }
            slot.minChars?.let { min ->
                add(ConstraintMUS.Rule(slot.id + ".min", ConstraintMUS.Kind.MIN_CHARS, slot.id, min.toString()))
            }
        }
    }

    fun conflicts(slots: List<SpecSlot>): List<List<ConstraintMUS.Rule>> =
        ConstraintMUS.minimalConflicts(rules(slots))
}
