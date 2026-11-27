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

private data class DiffWindow(
    val oldLines: List<String>,
    val newLines: List<String>,
    val oldMid: List<String>,
    val newMid: List<String>,
    val prefix: Int,
    val suffix: Int
)

object TextDiff {
    private const val MAX_CELLS = 1_000_000

    fun diff(oldText: String, newText: String): TextDiffReport {
        val oldLines = oldText.lines()
        val newLines = newText.lines()
        val prefix = commonPrefix(oldLines, newLines)
        val suffix = commonSuffix(oldLines, newLines, prefix)

        val oldMid = oldLines.subList(prefix, oldLines.size - suffix)
        val newMid = newLines.subList(prefix, newLines.size - suffix)
        val out = mutableListOf<DiffLine>()
        for (i in 0 until prefix) {
            out += DiffLine(DiffKind.EQUAL, i + 1, i + 1, oldLines[i])
        }

        if (oldMid.size.toLong() * newMid.size.toLong() > MAX_CELLS) {
            appendDegraded(DiffWindow(oldLines, newLines, oldMid, newMid, prefix, suffix), out)
            return report(out, degraded = true)
        }

        val n = oldMid.size
        val m = newMid.size
        val dp = lcsTable(oldMid, newMid, n, m)
        walkDiff(oldMid, newMid, dp, prefix, out)
        appendSuffix(oldLines, newLines, suffix, out)
        return report(out, degraded = false)
    }

    private fun commonPrefix(oldLines: List<String>, newLines: List<String>): Int {
        var prefix = 0
        while (prefix < oldLines.size && prefix < newLines.size && oldLines[prefix] == newLines[prefix]) prefix++
        return prefix
    }

    private fun commonSuffix(oldLines: List<String>, newLines: List<String>, prefix: Int): Int {
        var suffix = 0
        while (
            suffix < oldLines.size - prefix &&
            suffix < newLines.size - prefix &&
            oldLines[oldLines.size - 1 - suffix] == newLines[newLines.size - 1 - suffix]
        ) suffix++
        return suffix
    }

    private fun appendDegraded(window: DiffWindow, out: MutableList<DiffLine>) {
        val oldSet = window.oldMid.toSet()
        val newSet = window.newMid.toSet()
        var oldNo = window.prefix + 1
        var newNo = window.prefix + 1
        window.oldMid.filter { it !in newSet }.forEach { line ->
            out += DiffLine(DiffKind.REMOVE, oldNo, null, line)
            oldNo++
        }
        window.newMid.filter { it !in oldSet }.forEach { line ->
            out += DiffLine(DiffKind.ADD, null, newNo, line)
            newNo++
        }
        appendSuffix(window.oldLines, window.newLines, window.suffix, out)
    }

    private fun lcsTable(oldMid: List<String>, newMid: List<String>, n: Int, m: Int): Array<IntArray> {
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
        return dp
    }

    private fun walkDiff(
        oldMid: List<String>,
        newMid: List<String>,
        dp: Array<IntArray>,
        prefix: Int,
        out: MutableList<DiffLine>
    ) {
        val n = oldMid.size
        val m = newMid.size
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
    }

    private fun appendSuffix(oldLines: List<String>, newLines: List<String>, suffix: Int, out: MutableList<DiffLine>) {
        for (k in 0 until suffix) {
            out += DiffLine(
                DiffKind.EQUAL,
                oldLines.size - suffix + k + 1,
                newLines.size - suffix + k + 1,
                oldLines[oldLines.size - suffix + k]
            )
        }
    }

    private fun report(out: List<DiffLine>, degraded: Boolean): TextDiffReport = TextDiffReport(
        lines = out,
        added = out.count { it.kind == DiffKind.ADD },
        removed = out.count { it.kind == DiffKind.REMOVE },
        degraded = degraded
    )
}
