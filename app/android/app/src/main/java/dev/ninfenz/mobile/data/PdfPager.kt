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

    fun <T> paginateItems(lines: List<T>, linesPerPage: Int): List<List<T>> {
        require(linesPerPage > 0) { "linesPerPage 必须为正" }
        if (lines.isEmpty()) return emptyList()
        return lines.chunked(linesPerPage)
    }
}
