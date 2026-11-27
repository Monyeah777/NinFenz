package dev.ninfenz.mobile.util

import android.util.Log

/**
 * Result 失败显式上报后降级为 null。
 *
 * 审计规则 E-001 要求 UI 层不得静默吞错：直接用 `runCatching { ... }.getOrNull()` 会丢掉失败原因。
 * 统一改为 `runCatching { ... }.orNullLogged("Screen.action")`，失败经 logcat 的 NF-UI tag 上报，
 * 返回值语义（null = 不可用）保持不变。
 */
inline fun <T> Result<T>.orNullLogged(tag: String): T? =
    onFailure { Log.w("NF-UI", tag + ": " + it.javaClass.simpleName + ": " + it.message) }.getOrNull()
