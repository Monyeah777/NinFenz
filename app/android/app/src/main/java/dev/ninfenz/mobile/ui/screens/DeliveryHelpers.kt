package dev.ninfenz.mobile.ui.screens

import android.content.Context
import dev.ninfenz.mobile.model.ProjectStatus
import dev.ninfenz.mobile.model.SlotInput
import java.io.File

internal fun sha256File(file: File): String =
    java.security.MessageDigest.getInstance("SHA-256").digest(file.readBytes()).joinToString("") { "%02x".format(it) }

internal fun templateValueAllowed(meta: dev.ninfenz.mobile.model.SpecSlot?, value: String): Boolean {
    val clean = dev.ninfenz.mobile.model.SlotInput.sanitize(meta?.kind, value)
    if (meta?.nonEmpty == true && clean.isBlank()) return false
    if (meta?.startsWith != null && !clean.startsWith(meta.startsWith)) return false
    if (meta?.endsWith != null && !clean.endsWith(meta.endsWith)) return false
    if (meta?.minChars != null && clean.length < meta.minChars) return false
    if (meta?.maxChars != null && clean.length > meta.maxChars) return false
    if (meta?.pattern != null && !runCatching { Regex(meta.pattern).matches(clean) }.getOrDefault(false)) return false
    return true
}

internal fun slotIssue(context: Context, meta: dev.ninfenz.mobile.model.SpecSlot?, value: String): String? {
    if (meta == null) return null
    val clean = dev.ninfenz.mobile.model.SlotInput.sanitize(meta.kind, value)
    if (clean.isBlank() && (meta.required || meta.nonEmpty)) {
        return context.getString(dev.ninfenz.mobile.R.string.delivery_slot_required)
    }
    if (meta.minChars != null && clean.isNotBlank() && clean.length < meta.minChars) {
        return context.getString(dev.ninfenz.mobile.R.string.delivery_slot_budget_min, meta.minChars)
    }
    if (meta.maxChars != null && clean.length > meta.maxChars) {
        return context.getString(dev.ninfenz.mobile.R.string.delivery_slot_budget_max, meta.maxChars)
    }
    if (meta.startsWith != null && clean.isNotBlank() && !clean.startsWith(meta.startsWith)) {
        return context.getString(dev.ninfenz.mobile.R.string.delivery_slot_rule_prefix, meta.startsWith)
    }
    if (meta.endsWith != null && clean.isNotBlank() && !clean.endsWith(meta.endsWith)) {
        return context.getString(dev.ninfenz.mobile.R.string.delivery_slot_rule_suffix, meta.endsWith)
    }
    if (meta.pattern != null && clean.isNotBlank() && !runCatching { Regex(meta.pattern).matches(clean) }.getOrDefault(false)) {
        return context.getString(dev.ninfenz.mobile.R.string.delivery_slot_rule_pattern, meta.pattern)
    }
    return null
}

internal fun parseTemplateSlots(markdown: String): Map<String, String> {
    val result = mutableMapOf<String, String>()
    markdown.lineSequence().forEach { line ->
        val trimmed = line.trim()
        if (!trimmed.startsWith("- SLT-")) return@forEach
        val rest = trimmed.removePrefix("- ")
        val id = rest.substringBefore(' ').trim()
        if (!rest.contains('：') && !rest.contains(':')) return@forEach
        val body = rest.substringAfter('：', "").ifBlank { rest.substringAfter(':', "") }
        if (id.startsWith("SLT-") && body.isNotBlank()) result[id] = body.trim()
    }
    return result
}

internal fun reproTextFor(report: dev.ninfenz.mobile.data.ReproChecker.Report?, context: Context): String? =
    when {
        report == null -> null
        report.stable -> context.getString(dev.ninfenz.mobile.R.string.repro_stable)
        else -> context.getString(dev.ninfenz.mobile.R.string.repro_diff, report.firstDiff ?: -1)
    }

internal fun reproTextStable(report: dev.ninfenz.mobile.data.ReproChecker.Report, context: Context): String =
    if (report.stable) {
        context.getString(dev.ninfenz.mobile.R.string.repro_stable)
    } else {
        context.getString(dev.ninfenz.mobile.R.string.repro_diff, report.firstDiff ?: -1)
    }
internal fun slotVisible(meta: dev.ninfenz.mobile.model.SpecSlot?, inputs: Map<String, String>): Boolean {
    val cond = meta?.visibleIf ?: return true
    return inputs[cond.slot] == cond.equals
}
internal const val MAX_IMPORT_CHARS = 1_048_576

internal fun statusText(context: Context, status: ProjectStatus): String = when (status) {
    ProjectStatus.DRAFT -> context.getString(dev.ninfenz.mobile.R.string.delivery_status_draft)
    ProjectStatus.AUTHORING -> context.getString(dev.ninfenz.mobile.R.string.delivery_status_authoring)
    ProjectStatus.ASSEMBLED -> context.getString(dev.ninfenz.mobile.R.string.delivery_status_assembled)
    ProjectStatus.VALIDATED -> context.getString(dev.ninfenz.mobile.R.string.delivery_status_validated)
    ProjectStatus.EXPORTED -> context.getString(dev.ninfenz.mobile.R.string.delivery_status_exported)
    ProjectStatus.REVIEWED -> context.getString(dev.ninfenz.mobile.R.string.delivery_status_reviewed)
}
internal fun formatBytes(bytes: Long): String = when {
    bytes < 1024 -> bytes.toString() + " B"
    bytes < 1024 * 1024 -> (bytes / 1024).toString() + " KB"
    else -> String.format(java.util.Locale.US, "%.1f MB", bytes / 1024.0 / 1024.0)
}

internal fun mimeFor(format: String): String = when (format) {
    "md" -> "text/markdown"
    "zip", "skill" -> "application/zip"
    "docx" -> "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    "json" -> "application/json"
    "epub" -> "application/epub+zip"
    "pdf" -> "application/pdf"
    "html" -> "text/html"
    else -> "application/octet-stream"
}
