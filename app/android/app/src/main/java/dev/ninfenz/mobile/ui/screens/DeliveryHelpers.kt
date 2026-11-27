package dev.ninfenz.mobile.ui.screens

import android.content.Context
import dev.ninfenz.mobile.model.ProjectStatus
import dev.ninfenz.mobile.model.SlotInput
import java.io.File

internal fun sha256File(file: File): String =
    java.security.MessageDigest.getInstance("SHA-256").digest(file.readBytes()).joinToString("") { "%02x".format(it) }

internal fun templateValueAllowed(meta: dev.ninfenz.mobile.model.SpecSlot?, value: String): Boolean {
    val clean = dev.ninfenz.mobile.model.SlotInput.sanitize(meta?.kind, value)
    return requiredAllowed(meta, clean) && startsAllowed(meta, clean) && endsAllowed(meta, clean) &&
        minAllowed(meta, clean) && maxAllowed(meta, clean) && patternAllowed(meta, clean)
}

internal fun slotIssue(context: Context, meta: dev.ninfenz.mobile.model.SpecSlot?, value: String): String? {
    if (meta == null) return null
    val clean = dev.ninfenz.mobile.model.SlotInput.sanitize(meta.kind, value)
    return blankIssue(context, meta, clean)
        ?: minIssue(context, meta, clean)
        ?: maxIssue(context, meta, clean)
        ?: prefixIssue(context, meta, clean)
        ?: suffixIssue(context, meta, clean)
        ?: patternIssue(context, meta, clean)
}

private fun requiredAllowed(meta: dev.ninfenz.mobile.model.SpecSlot?, clean: String): Boolean {
    if (meta?.nonEmpty != true) return true
    return clean.isNotBlank()
}

private fun startsAllowed(meta: dev.ninfenz.mobile.model.SpecSlot?, clean: String): Boolean {
    val prefix = meta?.startsWith ?: return true
    return clean.startsWith(prefix)
}

private fun endsAllowed(meta: dev.ninfenz.mobile.model.SpecSlot?, clean: String): Boolean {
    val suffix = meta?.endsWith ?: return true
    return clean.endsWith(suffix)
}

private fun minAllowed(meta: dev.ninfenz.mobile.model.SpecSlot?, clean: String): Boolean {
    val min = meta?.minChars ?: return true
    return clean.length >= min
}

private fun maxAllowed(meta: dev.ninfenz.mobile.model.SpecSlot?, clean: String): Boolean {
    val max = meta?.maxChars ?: return true
    return clean.length <= max
}

private fun patternAllowed(meta: dev.ninfenz.mobile.model.SpecSlot?, clean: String): Boolean {
    val pattern = meta?.pattern ?: return true
    return runCatching { Regex(pattern).matches(clean) }.getOrDefault(false)
}

private fun blankIssue(context: Context, meta: dev.ninfenz.mobile.model.SpecSlot, clean: String): String? {
    if (!(clean.isBlank() && (meta.required || meta.nonEmpty))) return null
    return context.getString(dev.ninfenz.mobile.R.string.delivery_slot_required)
}

private fun minIssue(context: Context, meta: dev.ninfenz.mobile.model.SpecSlot, clean: String): String? {
    val min = meta.minChars ?: return null
    if (!(clean.isNotBlank() && clean.length < min)) return null
    return context.getString(dev.ninfenz.mobile.R.string.delivery_slot_budget_min, min)
}

private fun maxIssue(context: Context, meta: dev.ninfenz.mobile.model.SpecSlot, clean: String): String? {
    val max = meta.maxChars ?: return null
    if (clean.length <= max) return null
    return context.getString(dev.ninfenz.mobile.R.string.delivery_slot_budget_max, max)
}

private fun prefixIssue(context: Context, meta: dev.ninfenz.mobile.model.SpecSlot, clean: String): String? {
    val prefix = meta.startsWith ?: return null
    if (!(clean.isNotBlank() && !clean.startsWith(prefix))) return null
    return context.getString(dev.ninfenz.mobile.R.string.delivery_slot_rule_prefix, prefix)
}

private fun suffixIssue(context: Context, meta: dev.ninfenz.mobile.model.SpecSlot, clean: String): String? {
    val suffix = meta.endsWith ?: return null
    if (!(clean.isNotBlank() && !clean.endsWith(suffix))) return null
    return context.getString(dev.ninfenz.mobile.R.string.delivery_slot_rule_suffix, suffix)
}

private fun patternIssue(context: Context, meta: dev.ninfenz.mobile.model.SpecSlot, clean: String): String? {
    val pattern = meta.pattern ?: return null
    if (!(clean.isNotBlank() && !runCatching { Regex(pattern).matches(clean) }.getOrDefault(false))) return null
    return context.getString(dev.ninfenz.mobile.R.string.delivery_slot_rule_pattern, pattern)
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
