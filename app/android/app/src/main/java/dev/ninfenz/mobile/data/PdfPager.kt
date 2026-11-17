package dev.ninfenz.mobile.data

/** PDF 文本分页：按测量宽度逐行折行，再按行数切页；纯逻辑可单测。 */
object PdfPager {
    fun wrap(line: String, maxWidth: Float, measure: (String) -> Float): List<String> {
        if (line.isEmpty()) return listOf("")
        if (measure(line) <= maxWidth) return listOf(line)
        val out = mutableListOf<String>()
        var current = StringBuilder()
        for (ch in line) {
            current.append(ch)
            if (measure(current.toString()) > maxWidth && current.length > 1) {
                current.deleteCharAt(current.length - 1)
                out.add(current.toString())
                current = StringBuilder().append(ch)
            }
        }
        if (current.isNotEmpty()) out.add(current.toString())
        return out.ifEmpty { listOf("") }
    }

    fun paginate(lines: List<String>, linesPerPage: Int): List<List<String>> {
        require(linesPerPage > 0) { "linesPerPage 必须为正" }
        if (lines.isEmpty()) return listOf(listOf(""))
        return lines.chunked(linesPerPage)
    }

    /** 按权重（图片占多行）切页，返回每页的 [start, end) 下标。 */
    fun paginateWeighted(weights: List<Int>, linesPerPage: Int): List<IntRange> {
        require(linesPerPage > 0) { "linesPerPage 必须为正" }
        if (weights.isEmpty()) return emptyList()
        val out = mutableListOf<IntRange>()
        var start = 0
        var used = 0
        for (i in weights.indices) {
            val w = weights[i].coerceAtLeast(1)
            if (i > start && used + w > linesPerPage) {
                out.add(start until i)
                start = i
                used = 0
            }
            used += w
        }
        out.add(start until weights.size)
        return out
    }

    fun <T> repeatTableHeaders(
        items: List<T>,
        ranges: List<IntRange>,
        isTable: (T) -> Boolean,
        isHeader: (T) -> Boolean
    ): List<List<T>> {
        return ranges.mapIndexed { index, range ->
            val page = items.subList(range.first, range.last + 1)
            if (index > 0 && page.firstOrNull()?.let(isTable) == true) {
                val header = items.subList(0, range.first).lastOrNull(isHeader)
                if (header != null) listOf(header) + page else page
            } else {
                page
            }
        }
    }

    fun <T> paginateItems(lines: List<T>, linesPerPage: Int): List<List<T>> {
        require(linesPerPage > 0) { "linesPerPage 必须为正" }
        if (lines.isEmpty()) return emptyList()
        return lines.chunked(linesPerPage)
    }
}
