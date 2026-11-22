package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.ConstraintMUS
import dev.ninfenz.mobile.model.FlashFillModel
import kotlin.random.Random

/** M15：确定性 property 自检；失败即带 seed/序号，便于复现。 */
object PropertyHarness {
    data class Failure(val seed: Long, val index: Int, val message: String)
    data class Report(val checked: Int, val failures: List<Failure>) {
        val ok: Boolean get() = failures.isEmpty()
    }

    fun <T> check(seed: Long, count: Int, gen: (Random) -> T, property: (T) -> Boolean): Report {
        val rng = Random(seed)
        val failures = mutableListOf<Failure>()
        repeat(count) { i ->
            val value = gen(rng)
            if (!property(value)) failures += Failure(seed, i, "property failed")
        }
        return Report(count, failures)
    }
}

/** 应用内可跑的自检项：M1 推断、M12 MUS、M25 到期。 */
object AppSelfCheck {
    private val letters = "abcdefghijklmnopqrstuvwxyz"

    private fun word(rng: Random): String =
        (1..(5 + rng.nextInt(10))).map { letters[rng.nextInt(letters.length)] }.joinToString("")

    fun run(seed: Long = 42, count: Int = 50): PropertyHarness.Report {
        val rng = Random(seed)
        val failures = mutableListOf<PropertyHarness.Failure>()
        repeat(count) { i ->
            val base = word(rng)
            val (before, after) = when (rng.nextInt(5)) {
                0 -> base to "【$base"
                1 -> base to "$base】"
                2 -> "【$base" to base
                3 -> "$base】" to base
                else -> {
                    val old = "QQ"
                    "$base$old$base" to "$base" + "X" + "$base"
                }
            }
            val inferred = FlashFillModel.infer(before, after)
            if (inferred == null || inferred.apply(before) != after) {
                failures += PropertyHarness.Failure(seed, i, "flash-fill")
            }
        }

        val mus = PropertyHarness.check(seed, count, { r ->
            val a = r.nextInt(10)
            val b = r.nextInt(10)
            listOf(
                ConstraintMUS.Rule("min", ConstraintMUS.Kind.MIN_CHARS, "f", a.toString()),
                ConstraintMUS.Rule("max", ConstraintMUS.Kind.MAX_CHARS, "f", b.toString())
            )
        }) { rules ->
            (ConstraintMUS.minimalConflicts(rules).isEmpty()) == ConstraintMUS.satisfiable(rules)
        }
        failures += mus.failures

        val grant = PropertyHarness.check(seed, count, { r -> 1_000L + r.nextInt(1_000) }) { expires ->
            !CapabilityGrant(setOf(CapabilityGrant.READ), expiresAt = expires).allows(CapabilityGrant.READ, expires)
        }
        failures += grant.failures

        return PropertyHarness.Report(count * 3, failures)
    }
}
