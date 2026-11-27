package dev.ninfenz.mobile.share

/** 单个分享条目已下沉到 data 包；这里保留别名兼容既有 import（data -> share 回引会成环）。 */
typealias SharedItem = dev.ninfenz.mobile.data.SharedItem

/** 分享/打开/划词入口的统一载荷（ShareReceiverActivity → 主界面导入流程）。 */
data class SharePayload(
    val kind: String,
    val mime: String?,
    val items: List<SharedItem>,
    val processText: String?
) {
    val count: Int get() = items.size
    val hasText: Boolean get() = processText != null || items.any { it.text != null }

    fun summary(itemLabel: String = "条目 " + count, processLabel: String? = processText?.let { "划词 " + it.length + " 字" }): String {
        val head = when (kind) {
            SharePayloadParser.KIND_SEND_MULTIPLE -> "SEND_MULTIPLE"
            SharePayloadParser.KIND_SEND -> "SEND"
            SharePayloadParser.KIND_VIEW -> "VIEW"
            SharePayloadParser.KIND_PROCESS_TEXT -> "PROCESS_TEXT"
            else -> kind.uppercase()
        }
        val types = items.mapNotNull { it.mime }.distinct()
        val parts = mutableListOf<String>()
        parts.add(head)
        parts.add(itemLabel)
        if (types.isNotEmpty()) parts.add(types.joinToString("/"))
        processLabel?.let { parts.add(it) }
        return parts.joinToString(" · ")
    }
}

object SharePayloadParser {
    const val KIND_SEND = "send"
    const val KIND_SEND_MULTIPLE = "send_multiple"
    const val KIND_VIEW = "view"
    const val KIND_PROCESS_TEXT = "process_text"

    fun kindOf(action: String?): String = when (action) {
        "android.intent.action.SEND" -> KIND_SEND
        "android.intent.action.SEND_MULTIPLE" -> KIND_SEND_MULTIPLE
        "android.intent.action.VIEW" -> KIND_VIEW
        "android.intent.action.PROCESS_TEXT" -> KIND_PROCESS_TEXT
        else -> "unknown"
    }

    /**
     * 纯函数解析：Intent 在本层之外拆好（便于 JVM 单测）。
     * 不透传任何绝对路径/用户名；URI 原样保留、由调用方按需读取。
     */
    fun parse(
        action: String?,
        mime: String?,
        text: CharSequence?,
        streamUris: List<String>,
        processText: CharSequence?
    ): SharePayload {
        val kind = kindOf(action)
        val items = mutableListOf<SharedItem>()
        when (kind) {
            KIND_SEND -> {
                if (!text.isNullOrBlank()) {
                    items.add(SharedItem(uri = null, text = text.toString(), mime = mime ?: "text/plain", name = null))
                }
                for (uri in streamUris) {
                    items.add(SharedItem(uri = uri, text = null, mime = mime, name = null))
                }
            }
            KIND_SEND_MULTIPLE -> {
                if (!text.isNullOrBlank()) {
                    items.add(SharedItem(uri = null, text = text.toString(), mime = mime ?: "text/plain", name = null))
                }
                for (uri in streamUris) {
                    items.add(SharedItem(uri = uri, text = null, mime = mime, name = null))
                }
            }
            KIND_VIEW -> {
                for (uri in streamUris) {
                    items.add(SharedItem(uri = uri, text = null, mime = mime, name = null))
                }
            }
            KIND_PROCESS_TEXT -> {
                if (!processText.isNullOrBlank()) {
                    items.add(SharedItem(uri = null, text = processText.toString(), mime = "text/plain", name = null))
                }
            }
            else -> {
                // 未知 action：不猜，交给 UI 显示不支持
            }
        }
        return SharePayload(
            kind = kind,
            mime = mime,
            items = items,
            processText = processText?.toString()
        )
    }
}
