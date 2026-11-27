package dev.ninfenz.mobile.data

/** 单个分享条目：content/file URI 或纯文本（二选一，可并存）。
 *  从 share 包下沉到 data：share -> data 已是既有方向，回引会让 data <-> share 成环（ARCH-004）。 */
data class SharedItem(
    val uri: String?,
    val text: String?,
    val mime: String?,
    val name: String?
)
