package dev.ninfenz.mobile.model

/** 搜索命中类型。model 层自有类型，避免 model -> data 反向依赖。 */
enum class SearchKind(val label: String) {
    PROJECT("项目"),
    PACK("Pack"),
    CLAUSE("条款"),
    FIELD("字段"),
    NODE("管线节点"),
    SECTION("规格章节"),
    SLOT("规格槽位")
}

data class SearchHit(
    val kind: SearchKind,
    val title: String,
    val detail: String,
    val packId: String? = null,
    val packVersion: String? = null,
    val projectId: String? = null,
    val body: String = ""
)
