package dev.ninfenz.mobile.ui.screens

/**
 * 「选择文件」的 MIME 过滤面：文本/表格/文档包 + 图片（图片走 OCR，见 [classifyImport]）。
 * 图片类型必须与 [classifyImport] 按扩展名接受的集合一致，避免选择器能选到、解析侧不认。
 */
internal val importFileMimeTypes = arrayOf(
    "text/markdown",
    "text/plain",
    "text/csv",
    "application/json",
    "application/zip",
    "application/octet-stream",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "image/bmp"
)
