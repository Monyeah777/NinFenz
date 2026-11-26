package dev.ninfenz.mobile.model

/** 行级 diff：优先 LCS；超大输入降级为集合对比并显式标记 degraded。 */
enum class DiffKind { EQUAL, ADD, REMOVE }

data class DiffLine(
    val kind: DiffKind,
    val oldLine: Int?,
    val newLine: Int?,
    val text: String
)

data class TextDiffReport(
    val lines: List<DiffLine>,
    val added: Int,
    val removed: Int,
    val degraded: Boolean = false
) {
    val changed: Int get() = added + removed
}

object TextDiff {
    private const val MAX_CELLS = 1_000_000

    fun diff(oldText: String, newText: String): TextDiffReport {
        val oldLines = oldText.lines()
        val newLines = newText.lines()
        var prefix = 0
        while (prefix < oldLines.size && prefix < newLines.size && oldLines[prefix] == newLines[prefix]) prefix++
        var suffix = 0
        while (
            suffix < oldLines.size - prefix &&
            suffix < newLines.size - prefix &&
            oldLines[oldLines.size - 1 - suffix] == newLines[newLines.size - 1 - suffix]
        ) suffix++

        val oldMid = oldLines.subList(prefix, oldLines.size - suffix)
        val newMid = newLines.subList(prefix, newLines.size - suffix)
        val out = mutableListOf<DiffLine>()
        for (i in 0 until prefix) {
            out += DiffLine(DiffKind.EQUAL, i + 1, i + 1, oldLines[i])
        }

        if (oldMid.size.toLong() * newMid.size.toLong() > MAX_CELLS) {
            val oldSet = oldMid.toSet()
            val newSet = newMid.toSet()
            var oldNo = prefix + 1
            var newNo = prefix + 1
            oldMid.filter { it !in newSet }.forEach { line ->
                out += DiffLine(DiffKind.REMOVE, oldNo, null, line)
                oldNo++
            }
            newMid.filter { it !in oldSet }.forEach { line ->
                out += DiffLine(DiffKind.ADD, null, newNo, line)
                newNo++
            }
            for (i in 0 until suffix) {
                out += DiffLine(
                    DiffKind.EQUAL,
                    oldLines.size - suffix + i + 1,
                    newLines.size - suffix + i + 1,
                    oldLines[oldLines.size - suffix + i]
                )
            }
            return TextDiffReport(
                lines = out,
                added = out.count { it.kind == DiffKind.ADD },
                removed = out.count { it.kind == DiffKind.REMOVE },
                degraded = true
            )
        }

        val n = oldMid.size
        val m = newMid.size
        val dp = Array(n + 1) { IntArray(m + 1) }
        for (i in n - 1 downTo 0) {
            for (j in m - 1 downTo 0) {
                dp[i][j] = if (oldMid[i] == newMid[j]) {
                    dp[i + 1][j + 1] + 1
                } else {
                    maxOf(dp[i + 1][j], dp[i][j + 1])
                }
            }
        }
        var i = 0
        var j = 0
        while (i < n && j < m) {
            when {
                oldMid[i] == newMid[j] -> {
                    out += DiffLine(DiffKind.EQUAL, prefix + i + 1, prefix + j + 1, oldMid[i])
                    i++
                    j++
                }
                dp[i + 1][j] >= dp[i][j + 1] -> {
                    out += DiffLine(DiffKind.REMOVE, prefix + i + 1, null, oldMid[i])
                    i++
                }
                else -> {
                    out += DiffLine(DiffKind.ADD, null, prefix + j + 1, newMid[j])
                    j++
                }
            }
        }
        while (i < n) {
            out += DiffLine(DiffKind.REMOVE, prefix + i + 1, null, oldMid[i])
            i++
        }
        while (j < m) {
            out += DiffLine(DiffKind.ADD, null, prefix + j + 1, newMid[j])
            j++
        }
        for (k in 0 until suffix) {
            out += DiffLine(
                DiffKind.EQUAL,
                oldLines.size - suffix + k + 1,
                newLines.size - suffix + k + 1,
                oldLines[oldLines.size - suffix + k]
            )
        }
        return TextDiffReport(
            lines = out,
            added = out.count { it.kind == DiffKind.ADD },
            removed = out.count { it.kind == DiffKind.REMOVE },
            degraded = false
        )
    }
}
