package dev.ninfenz.mobile.data

/** 样式匹配分：只比较可识别的 w:styleId 集合，Jaccard 百分比；不声称语义完整。 */
object StyleMatch {
    fun styleIds(xml: String?): Set<String> =
        Regex("w:styleId=\"([^\"]+)\"").findAll(xml.orEmpty())
            .map { it.groupValues[1] }
            .toSet()

    fun score(reference: String?, candidate: String?): Int {
        val a = styleIds(reference)
        val b = styleIds(candidate)
        if (a.isEmpty() && b.isEmpty()) return 100
        if (a.isEmpty() || b.isEmpty()) return 0
        val union = a.union(b).size
        if (union == 0) return 100
        return a.intersect(b).size * 100 / union
    }
}
