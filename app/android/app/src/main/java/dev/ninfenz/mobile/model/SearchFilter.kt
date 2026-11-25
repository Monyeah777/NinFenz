package dev.ninfenz.mobile.model

import dev.ninfenz.mobile.data.SearchHit
import dev.ninfenz.mobile.data.SearchKind

/** 搜索结果 kind 过滤：null = 全部。 */
object SearchFilter {
    fun apply(hits: List<SearchHit>, kind: SearchKind?, packId: String? = null, projectId: String? = null): List<SearchHit> {
        var out = hits
        if (kind != null) out = out.filter { it.kind == kind }
        if (packId != null) out = out.filter { it.packId == packId }
        if (projectId != null) out = out.filter { it.projectId == projectId }
        return out
    }
}
