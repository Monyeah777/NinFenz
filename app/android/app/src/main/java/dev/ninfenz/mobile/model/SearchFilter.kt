package dev.ninfenz.mobile.model

import dev.ninfenz.mobile.data.SearchHit
import dev.ninfenz.mobile.data.SearchKind

/** 搜索结果 kind 过滤：null = 全部。 */
object SearchFilter {
    fun apply(hits: List<SearchHit>, kind: SearchKind?): List<SearchHit> {
        if (kind == null) return hits
        return hits.filter { it.kind == kind }
    }
}
