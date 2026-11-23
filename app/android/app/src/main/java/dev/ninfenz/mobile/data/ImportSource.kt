package dev.ninfenz.mobile.data

/** nf-import/1 的 source.kind 白名单；禁止在 UI 里写裸字符串。 */
object ImportSource {
    const val SHARE = "share"
    const val VIEW = "view"
    const val PROCESS_TEXT = "process_text"
    const val SAF = "saf"
    const val CLIPBOARD = "clipboard"
    const val FILE = "file"
    const val INBOX = "inbox"

    val ALL = setOf(SHARE, VIEW, PROCESS_TEXT, SAF, CLIPBOARD, FILE, INBOX)
}
